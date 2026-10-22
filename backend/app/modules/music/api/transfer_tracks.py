from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import AdminUser, CurrentUser
from app.core.config import Settings, get_settings
from app.database.session import get_music_db as get_db
from app.database.text import contains_text
from app.modules.music.library import (
    DuplicateTrackError,
    catalog_album_groups,
    catalog_album_key,
    catalog_artist_key,
    group_catalog_albums,
    group_catalog_artists,
    import_staged_file,
    pagination,
    primary_artist,
    serialize_catalog_track,
    serialize_track,
    track_query,
)
from app.modules.music.metadata import normalize_identity
from app.modules.music.models import CatalogTrack, Track
from app.modules.music.schemas import (
    CatalogAlbumDetail,
    CatalogAlbumRead,
    CatalogArtistDetail,
    CatalogArtistRead,
    CatalogFileLink,
    CatalogFileResult,
    CatalogGenreRead,
    CatalogSearchRead,
    CatalogTrackPage,
    CatalogTrackRead,
)
from app.modules.music.transfer.matching import match_for_track
from app.storage.service import LocalMediaStorage

# Registered before the job routes so that /transfer/tracks is not taken for a job id.
router = APIRouter(prefix="/transfer", tags=["music transfer"])

FILE_TAKEN = "У этого трека уже есть файл. Сначала отвяжите его."


def catalog_track_or_404(db: Session, catalog_track_id: str) -> CatalogTrack:
    item = db.scalar(
        select(CatalogTrack)
        .where(CatalogTrack.id == catalog_track_id)
        .options(selectinload(CatalogTrack.track))
        .execution_options(populate_existing=True)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Трек каталога не найден")
    return item


def file_result(
    db: Session, user_id: str, catalog_track_id: str, result: Literal["added", "linked_existing"], detail: str
) -> CatalogFileResult:
    item = catalog_track_or_404(db, catalog_track_id)
    track, favorite = db.execute(track_query(user_id).where(Track.catalog_track_id == catalog_track_id)).one()
    return CatalogFileResult(
        status=result,
        detail=detail,
        catalog_track=serialize_catalog_track(item),
        track=serialize_track(track, favorite),
    )


def has_file_filter():
    return select(Track.id).where(Track.catalog_track_id == CatalogTrack.id).correlate(CatalogTrack).exists()


CatalogStatus = Literal["all", "with_file", "without_file", "enriched", "not_found"]


def catalog_filters(q: str | None, file_status: CatalogStatus, genre: str | None = None) -> list:
    filters = []
    if genre:
        filters.append(CatalogTrack.genre == genre)
    if q and q.strip():
        # Normalized columns are already casefolded: SQLite LIKE ignores case only for ASCII.
        term = f"%{normalize_identity(q)}%"
        filters.append(
            or_(
                CatalogTrack.normalized_title.like(term),
                CatalogTrack.normalized_artist.like(term),
                contains_text(CatalogTrack.album_title, q),
            )
        )
    if file_status == "with_file":
        filters.append(has_file_filter())
    elif file_status == "without_file":
        filters.append(~has_file_filter())
    elif file_status == "enriched":
        filters.append(CatalogTrack.enrich_status == "enriched")
    elif file_status == "not_found":
        filters.append(CatalogTrack.enrich_status.in_(("not_found", "error")))
    return filters


@router.get("/tracks", response_model=CatalogTrackPage)
def list_catalog_tracks(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
    file_status: Annotated[CatalogStatus, Query(alias="status")] = "all",
    genre: str | None = None,
) -> CatalogTrackPage:
    page = max(1, page)
    page_size = min(200, max(1, page_size))
    filters = catalog_filters(q, file_status, genre)
    total = int(db.scalar(select(func.count(CatalogTrack.id)).where(*filters)) or 0)
    offset, limit, pages = pagination(total, page, page_size)
    items = db.scalars(
        select(CatalogTrack)
        .where(*filters)
        .options(selectinload(CatalogTrack.track))
        .order_by(func.lower(CatalogTrack.artist_name), func.lower(CatalogTrack.title), CatalogTrack.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return CatalogTrackPage(
        items=[serialize_catalog_track(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/albums", response_model=list[CatalogAlbumRead])
def list_catalog_albums(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    q: str | None = None,
    file_status: Annotated[CatalogStatus, Query(alias="status")] = "all",
    genre: str | None = None,
) -> list[CatalogAlbumRead]:
    """Albums of the catalog, so a transferred library has albums before any file is added."""
    items = db.scalars(
        select(CatalogTrack)
        .where(CatalogTrack.album_title.is_not(None), *catalog_filters(q, file_status, genre))
        .options(selectinload(CatalogTrack.track))
    ).all()
    return covering_albums(db, group_catalog_albums(items))


def fully_linked(db: Session, column, ids: set[str]) -> set[str]:
    """Library albums or artists whose every file is linked to the catalog; the rest stay listed on their own."""
    if not ids:
        return set()
    rows = db.execute(
        select(column, func.count(Track.id), func.count(Track.catalog_track_id)).where(column.in_(ids)).group_by(column)
    ).all()
    return {value for value, total, linked in rows if total == linked}


def covering_albums(db: Session, albums: list[CatalogAlbumRead]) -> list[CatalogAlbumRead]:
    covered = fully_linked(db, Track.album_id, {value for album in albums for value in album.local_album_ids})
    for album in albums:
        album.local_album_ids = [value for value in album.local_album_ids if value in covered]
    return albums


def _search_rank(item: CatalogTrack, query: str) -> tuple[int, str]:
    """Title matches first, then the artist's tracks, then everything found through the album."""
    title, artist = item.normalized_title, normalize_identity(primary_artist(item.artist_name))
    if title == query:
        rank = 0
    elif title.startswith(query):
        rank = 1
    elif artist == query or artist.startswith(query):
        rank = 2
    elif query in title:
        rank = 3
    elif query in item.normalized_artist:
        rank = 4
    else:
        rank = 5
    return rank, title


@router.get("/search", response_model=CatalogSearchRead)
def search_catalog(
    q: str, _: CurrentUser, db: Annotated[Session, Depends(get_db)], limit: int = 20
) -> CatalogSearchRead:
    """Tracks, albums and artists of the catalog whose title, artist or album contains the query, in any case."""
    query = normalize_identity(q)
    if not query:
        return CatalogSearchRead(tracks=[], tracks_total=0, albums=[], artists=[])
    limit = min(50, max(1, limit))
    term = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    matched = db.scalars(
        select(CatalogTrack)
        .where(
            or_(
                CatalogTrack.normalized_title.like(term, escape="\\"),
                CatalogTrack.normalized_artist.like(term, escape="\\"),
                contains_text(CatalogTrack.album_title, query),
            )
        )
        .options(selectinload(CatalogTrack.track))
    ).all()
    tracks = sorted(matched, key=lambda item: _search_rank(item, query))

    by_artist = [item for item in matched if query in normalize_identity(primary_artist(item.artist_name))]
    artists = [artist for artist in group_catalog_artists(by_artist) if query in artist.key]
    covered = fully_linked(db, Track.artist_id, {value for artist in artists for value in artist.local_artist_ids})
    for artist in artists:
        artist.local_artist_ids = [value for value in artist.local_artist_ids if value in covered]

    titles = {
        item.album_title
        for item in matched
        if item.album_title and (query in normalize_identity(item.album_title) or item in by_artist)
    }
    album_tracks = (
        db.scalars(
            select(CatalogTrack)
            .where(CatalogTrack.album_title.in_(titles))
            .options(selectinload(CatalogTrack.track))
            .order_by(func.lower(CatalogTrack.title), CatalogTrack.id)
        ).all()
        if titles
        else []
    )
    albums = [
        album
        for album in group_catalog_albums(album_tracks)
        if query in normalize_identity(album.title) or query in normalize_identity(album.artist_name)
    ]
    return CatalogSearchRead(
        tracks=[serialize_catalog_track(item) for item in tracks[:limit]],
        tracks_total=len(tracks),
        albums=covering_albums(db, albums[:limit]),
        artists=artists[:limit],
    )


@router.get("/genres", response_model=list[CatalogGenreRead])
def list_catalog_genres(_: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> list[CatalogGenreRead]:
    """Genres of the catalog (from Apple Music) together with genres of library files outside the catalog."""
    genres: dict[str, dict] = {}

    def entry(name: str) -> dict:
        return genres.setdefault(name.casefold(), {"name": name, "tracks": 0, "catalog": 0, "albums": set()})

    for name, album_title, artist in db.execute(
        select(CatalogTrack.genre, CatalogTrack.album_title, CatalogTrack.normalized_artist).where(
            CatalogTrack.genre.is_not(None), CatalogTrack.genre != ""
        )
    ):
        item = entry(name)
        item["tracks"] += 1
        item["catalog"] += 1
        if album_title:
            item["albums"].add(f"catalog:{album_title.casefold()}|{artist}")
    for name, album_id in db.execute(
        select(Track.genre, Track.album_id).where(
            Track.catalog_track_id.is_(None), Track.genre.is_not(None), Track.genre != ""
        )
    ):
        item = entry(name.strip())
        item["tracks"] += 1
        if album_id:
            item["albums"].add(f"library:{album_id}")
    return [
        CatalogGenreRead(
            name=item["name"],
            track_count=item["tracks"],
            album_count=len(item["albums"]),
            catalog_count=item["catalog"],
        )
        for item in sorted(genres.values(), key=lambda value: value["name"].casefold())
    ]


@router.get("/artists", response_model=list[CatalogArtistRead])
def list_catalog_artists(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    q: str | None = None,
    file_status: Annotated[CatalogStatus, Query(alias="status")] = "all",
) -> list[CatalogArtistRead]:
    """Artists of the catalog, so a transferred library has artists before any file is added."""
    items = db.scalars(
        select(CatalogTrack).where(*catalog_filters(q, file_status)).options(selectinload(CatalogTrack.track))
    ).all()
    artists = group_catalog_artists(items)
    covered = fully_linked(db, Track.artist_id, {value for artist in artists for value in artist.local_artist_ids})
    for artist in artists:
        artist.local_artist_ids = [value for value in artist.local_artist_ids if value in covered]
    return artists


@router.get("/artist", response_model=CatalogArtistDetail)
def get_catalog_artist(key: str, _: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> CatalogArtistDetail:
    """A catalog artist with their tracks and the albums those tracks belong to."""
    items = db.scalars(
        select(CatalogTrack)
        .options(selectinload(CatalogTrack.track))
        .order_by(func.lower(CatalogTrack.title), CatalogTrack.id)
    ).all()
    tracks = [item for item in items if catalog_artist_key(item) == key]
    if not tracks:
        raise HTTPException(status_code=404, detail="Исполнитель не найден в каталоге")
    [artist] = group_catalog_artists(tracks)
    own = {item.id for item in tracks}
    groups = catalog_album_groups([item for item in items if item.album_title])
    albums = [
        album
        for _, _, members in groups
        if any(item.id in own for item in members)
        for album in group_catalog_albums(members)
    ]
    return CatalogArtistDetail(
        **artist.model_dump(),
        albums=covering_albums(db, albums),
        tracks=[serialize_catalog_track(item) for item in tracks],
    )


@router.get("/album", response_model=CatalogAlbumDetail)
def get_catalog_album(key: str, _: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> CatalogAlbumDetail:
    """The album holding the track with this album key, with every track of the album."""
    candidates = db.scalars(
        select(CatalogTrack)
        .where(CatalogTrack.album_title.is_not(None))
        .options(selectinload(CatalogTrack.track))
        .order_by(func.lower(CatalogTrack.title), CatalogTrack.id)
    ).all()
    title = key.split("|", 1)[0]
    same_title = [item for item in candidates if (catalog_album_key(item) or "").split("|", 1)[0] == title]
    items = next((members for _, keys, members in catalog_album_groups(same_title) if key in keys), None)
    if not items:
        raise HTTPException(status_code=404, detail="Альбом не найден в каталоге")
    [album] = covering_albums(db, group_catalog_albums(items))
    return CatalogAlbumDetail(**album.model_dump(), tracks=[serialize_catalog_track(item) for item in items])


@router.get("/tracks/{catalog_track_id}", response_model=CatalogTrackRead)
def get_catalog_track(
    catalog_track_id: str, _: CurrentUser, db: Annotated[Session, Depends(get_db)]
) -> CatalogTrackRead:
    return serialize_catalog_track(catalog_track_or_404(db, catalog_track_id))


@router.post("/tracks/{catalog_track_id}/file", response_model=CatalogFileResult, status_code=status.HTTP_201_CREATED)
async def upload_catalog_file(
    catalog_track_id: str,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
) -> CatalogFileResult:
    """Stores the file for exactly this catalog track, whatever its tags say."""
    if catalog_track_or_404(db, catalog_track_id).track is not None:
        raise HTTPException(status_code=409, detail=FILE_TAKEN)
    storage = LocalMediaStorage(settings)
    staged = await storage.stage_upload(file)
    try:
        await run_in_threadpool(import_staged_file, db, staged, storage, settings, catalog_track_id=catalog_track_id)
    except DuplicateTrackError as exc:
        existing = exc.track
        if existing.catalog_track_id not in (None, catalog_track_id):
            raise HTTPException(
                status_code=409, detail="Этот файл уже есть в медиатеке и привязан к другому треку каталога"
            ) from exc
        existing.catalog_track_id = catalog_track_id
        db.commit()
        return file_result(db, user.id, catalog_track_id, "linked_existing", "Файл уже был в медиатеке и привязан")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc) or "Не удалось обработать файл") from exc
    return file_result(db, user.id, catalog_track_id, "added", "Файл добавлен")


@router.put("/tracks/{catalog_track_id}/file", response_model=CatalogFileResult)
def link_catalog_file(
    catalog_track_id: str,
    payload: CatalogFileLink,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> CatalogFileResult:
    item = catalog_track_or_404(db, catalog_track_id)
    track = db.get(Track, payload.track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Трек не найден")
    if item.track is not None and item.track.id != track.id:
        raise HTTPException(status_code=409, detail=FILE_TAKEN)
    if track.catalog_track_id not in (None, catalog_track_id):
        raise HTTPException(status_code=409, detail="Файл уже привязан к другому треку каталога")
    track.catalog_track_id = catalog_track_id
    db.commit()
    return file_result(db, user.id, catalog_track_id, "linked_existing", "Файл привязан")


@router.delete("/tracks/{catalog_track_id}/file", response_model=CatalogTrackRead)
def unlink_catalog_file(
    catalog_track_id: str, _: AdminUser, db: Annotated[Session, Depends(get_db)]
) -> CatalogTrackRead:
    """Detaches the file; it stays in the library as an ordinary track."""
    item = catalog_track_or_404(db, catalog_track_id)
    if item.track is None:
        raise HTTPException(status_code=404, detail="У этого трека нет файла")
    item.track.catalog_track_id = None
    db.commit()
    return serialize_catalog_track(catalog_track_or_404(db, catalog_track_id))


@router.get("/candidates/{track_id}", response_model=list[CatalogTrackRead])
def catalog_candidates(
    track_id: str, _: CurrentUser, db: Annotated[Session, Depends(get_db)]
) -> list[CatalogTrackRead]:
    """Catalog tracks without a file that may belong to this file, for a manual choice."""
    track = db.scalar(select(Track).where(Track.id == track_id).options(selectinload(Track.artist)))
    if track is None:
        raise HTTPException(status_code=404, detail="Трек не найден")
    match = match_for_track(db, track)
    found = [match.catalog_track] if match.catalog_track else match.candidates
    return [serialize_catalog_track(item) for item in found]
