from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import CurrentUser
from app.database.session import get_music_db as get_db
from app.modules.music.library import pagination, serialize_track, track_query
from app.modules.music.models import Album, Artist, Track
from app.modules.music.schemas import (
    AlbumDetail,
    AlbumPage,
    AlbumRead,
    ArtistDetail,
    ArtistPage,
    ArtistRead,
    DashboardRead,
    GenreRead,
    SearchRead,
)

router = APIRouter(tags=["music catalog"])


def album_summary(album: Album, track_count: int, duration: float | None) -> AlbumRead:
    return AlbumRead(
        id=album.id,
        title=album.title,
        album_artist=album.album_artist,
        artist={"id": album.artist.id, "name": album.artist.name} if album.artist else None,
        year=album.year,
        genre=album.genre,
        artwork_id=album.artwork_id,
        track_count=track_count,
        duration=float(duration or 0),
    )


def artist_summary(db: Session, artist: Artist) -> ArtistRead:
    album_count = int(db.scalar(select(func.count(Album.id)).where(Album.artist_id == artist.id)) or 0)
    track_count = int(db.scalar(select(func.count(Track.id)).where(Track.artist_id == artist.id)) or 0)
    return ArtistRead(
        id=artist.id,
        name=artist.name,
        sort_name=artist.sort_name,
        artwork_id=artist.artwork_id,
        album_count=album_count,
        track_count=track_count,
    )


def album_aggregate_query():
    return (
        select(Album, func.count(Track.id), func.coalesce(func.sum(Track.duration), 0.0))
        .outerjoin(Track)
        .options(selectinload(Album.artist))
        .group_by(Album.id)
    )


@router.get("/albums", response_model=AlbumPage)
def list_albums(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 40,
    q: str | None = None,
    genre: str | None = None,
) -> AlbumPage:
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    filters = []
    if q:
        filters.append(Album.title.ilike(f"%{q.strip()}%"))
    if genre:
        filters.append(func.lower(Album.genre) == genre.strip().lower())
    total = int(db.scalar(select(func.count(Album.id)).where(*filters)) or 0)
    offset, limit, pages = pagination(total, page, page_size)
    rows = db.execute(
        album_aggregate_query().where(*filters).order_by(desc(Album.created_at)).offset(offset).limit(limit)
    ).all()
    return AlbumPage(
        items=[album_summary(album, count, duration) for album, count, duration in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/albums/{album_id}", response_model=AlbumDetail)
def get_album(album_id: str, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> AlbumDetail:
    row = db.execute(album_aggregate_query().where(Album.id == album_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Альбом не найден")
    album, count, duration = row
    tracks = db.execute(
        track_query(user.id)
        .where(Track.album_id == album_id)
        .order_by(func.coalesce(Track.disc_number, 1), func.coalesce(Track.track_number, 9999), Track.title)
    ).all()
    return AlbumDetail(
        **album_summary(album, count, duration).model_dump(),
        tracks=[serialize_track(track, favorite) for track, favorite in tracks],
    )


@router.get("/artists", response_model=ArtistPage)
def list_artists(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 60,
    q: str | None = None,
) -> ArtistPage:
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    filters = [Artist.name.ilike(f"%{q.strip()}%")] if q else []
    total = int(db.scalar(select(func.count(Artist.id)).where(*filters)) or 0)
    offset, limit, pages = pagination(total, page, page_size)
    artists = db.scalars(select(Artist).where(*filters).order_by(Artist.sort_name).offset(offset).limit(limit)).all()
    return ArtistPage(
        items=[artist_summary(db, artist) for artist in artists],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/artists/{artist_id}", response_model=ArtistDetail)
def get_artist(artist_id: str, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> ArtistDetail:
    artist = db.get(Artist, artist_id)
    if artist is None:
        raise HTTPException(status_code=404, detail="Исполнитель не найден")
    album_rows = db.execute(
        album_aggregate_query().where(Album.artist_id == artist_id).order_by(desc(Album.year))
    ).all()
    track_rows = db.execute(
        track_query(user.id)
        .where(Track.artist_id == artist_id)
        .order_by(desc(Track.play_count), Track.title)
        .limit(100)
    ).all()
    summary = artist_summary(db, artist)
    return ArtistDetail(
        **summary.model_dump(),
        albums=[album_summary(album, count, duration) for album, count, duration in album_rows],
        tracks=[serialize_track(track, favorite) for track, favorite in track_rows],
    )


@router.get("/genres", response_model=list[GenreRead])
def list_genres(_: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> list[GenreRead]:
    rows = db.execute(
        select(Track.genre, func.count(Track.id), func.count(func.distinct(Track.album_id)))
        .where(Track.genre.is_not(None), Track.genre != "")
        .group_by(Track.genre)
        .order_by(func.lower(Track.genre))
    ).all()
    return [GenreRead(name=name, track_count=tracks, album_count=albums) for name, tracks, albums in rows]


@router.get("/search", response_model=SearchRead)
def search(q: str, user: CurrentUser, db: Annotated[Session, Depends(get_db)], limit: int = 8) -> SearchRead:
    query = q.strip()
    if not query:
        return SearchRead(tracks=[], albums=[], artists=[])
    limit = min(25, max(1, limit))
    term = f"%{query}%"
    track_rows = db.execute(
        track_query(user.id)
        .join(Artist)
        .outerjoin(Album)
        .where(or_(Track.title.ilike(term), Artist.name.ilike(term), Album.title.ilike(term)))
        .order_by(desc(Track.play_count), Track.title)
        .limit(limit)
    ).all()
    album_rows = db.execute(
        album_aggregate_query().where(or_(Album.title.ilike(term), Album.album_artist.ilike(term))).limit(limit)
    ).all()
    artists = db.scalars(select(Artist).where(Artist.name.ilike(term)).order_by(Artist.sort_name).limit(limit)).all()
    return SearchRead(
        tracks=[serialize_track(track, favorite) for track, favorite in track_rows],
        albums=[album_summary(album, count, duration) for album, count, duration in album_rows],
        artists=[artist_summary(db, artist) for artist in artists],
    )


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> DashboardRead:
    total_tracks = int(db.scalar(select(func.count(Track.id))) or 0)
    total_albums = int(db.scalar(select(func.count(Album.id))) or 0)
    total_artists = int(db.scalar(select(func.count(Artist.id))) or 0)
    total_genres = int(db.scalar(select(func.count(func.distinct(Track.genre))).where(Track.genre.is_not(None))) or 0)
    duration = float(db.scalar(select(func.coalesce(func.sum(Track.duration), 0.0))) or 0)
    recent_rows = db.execute(track_query(user.id).order_by(desc(Track.date_added)).limit(12)).all()
    played_rows = db.execute(
        track_query(user.id).where(Track.last_played_at.is_not(None)).order_by(desc(Track.last_played_at)).limit(12)
    ).all()
    album_rows = db.execute(album_aggregate_query().order_by(desc(Album.created_at)).limit(8)).all()
    return DashboardRead(
        tracks=total_tracks,
        albums=total_albums,
        artists=total_artists,
        genres=total_genres,
        duration=duration,
        recently_added=[serialize_track(track, favorite) for track, favorite in recent_rows],
        recently_played=[serialize_track(track, favorite) for track, favorite in played_rows],
        albums_recent=[album_summary(album, count, album_duration) for album, count, album_duration in album_rows],
    )
