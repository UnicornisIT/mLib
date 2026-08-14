from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import CurrentUser
from app.database.session import get_music_db as get_db
from app.modules.music.library import serialize_track
from app.modules.music.models import Favorite, Playlist, PlaylistTrack, Track
from app.modules.music.schemas import (
    PlaylistCreate,
    PlaylistItemRead,
    PlaylistRead,
    PlaylistReorder,
    PlaylistTrackAdd,
    PlaylistUpdate,
)

router = APIRouter(prefix="/playlists", tags=["music playlists"])


def playlist_query():
    return (
        select(Playlist)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Playlist.items).selectinload(PlaylistTrack.track).selectinload(Track.artist),
            selectinload(Playlist.items).selectinload(PlaylistTrack.track).selectinload(Track.album),
        )
    )


def get_playlist(db: Session, playlist_id: str, user_id: str) -> Playlist:
    playlist = db.scalar(playlist_query().where(Playlist.id == playlist_id, Playlist.owner_id == user_id))
    if playlist is None:
        raise HTTPException(status_code=404, detail="Плейлист не найден")
    return playlist


def serialize_playlist(db: Session, playlist: Playlist, include_items: bool = False) -> PlaylistRead:
    favorite_ids = (
        set(
            db.scalars(
                select(Favorite.track_id).where(
                    Favorite.user_id == playlist.owner_id,
                    Favorite.track_id.in_([item.track_id for item in playlist.items]),
                )
            ).all()
        )
        if playlist.items
        else set()
    )
    items = None
    if include_items:
        items = [
            PlaylistItemRead(
                id=item.id,
                position=item.position,
                track=serialize_track(item.track, item.track_id in favorite_ids),
            )
            for item in sorted(playlist.items, key=lambda value: value.position)
        ]
    return PlaylistRead(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        is_system=playlist.is_system,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
        track_count=len(playlist.items),
        duration=sum(item.track.duration for item in playlist.items),
        items=items,
    )


@router.get("", response_model=list[PlaylistRead])
def list_playlists(user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> list[PlaylistRead]:
    playlists = db.scalars(
        playlist_query().where(Playlist.owner_id == user.id).order_by(Playlist.updated_at.desc())
    ).all()
    return [serialize_playlist(db, playlist) for playlist in playlists]


@router.post("", response_model=PlaylistRead, status_code=status.HTTP_201_CREATED)
def create_playlist(
    payload: PlaylistCreate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> PlaylistRead:
    playlist = Playlist(owner_id=user.id, name=payload.name.strip(), description=payload.description)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return serialize_playlist(db, playlist)


@router.get("/{playlist_id}", response_model=PlaylistRead)
def playlist_detail(playlist_id: str, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> PlaylistRead:
    return serialize_playlist(db, get_playlist(db, playlist_id, user.id), include_items=True)


@router.patch("/{playlist_id}", response_model=PlaylistRead)
def update_playlist(
    playlist_id: str,
    payload: PlaylistUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> PlaylistRead:
    playlist = get_playlist(db, playlist_id, user.id)
    if playlist.is_system:
        raise HTTPException(status_code=409, detail="Системный плейлист нельзя переименовать")
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(playlist, key, value.strip() if isinstance(value, str) and key == "name" else value)
    db.commit()
    db.refresh(playlist)
    return serialize_playlist(db, playlist, include_items=True)


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(
    playlist_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    playlist = get_playlist(db, playlist_id, user.id)
    if playlist.is_system:
        raise HTTPException(status_code=409, detail="Системный плейлист нельзя удалить")
    db.delete(playlist)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def apply_positions(db: Session, items: list[PlaylistTrack]) -> None:
    for index, item in enumerate(items):
        item.position = -(index + 1)
    db.flush()
    for index, item in enumerate(items):
        item.position = index
    db.flush()


@router.post("/{playlist_id}/tracks", response_model=PlaylistRead)
def add_playlist_track(
    playlist_id: str,
    payload: PlaylistTrackAdd,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> PlaylistRead:
    playlist = get_playlist(db, playlist_id, user.id)
    if db.get(Track, payload.track_id) is None:
        raise HTTPException(status_code=404, detail="Трек не найден")
    items = sorted(playlist.items, key=lambda value: value.position)
    insert_at = len(items) if payload.position is None else min(payload.position, len(items))
    item = PlaylistTrack(playlist_id=playlist.id, track_id=payload.track_id, position=-(len(items) + 1))
    db.add(item)
    db.flush()
    items.insert(insert_at, item)
    apply_positions(db, items)
    db.commit()
    return serialize_playlist(db, get_playlist(db, playlist_id, user.id), include_items=True)


@router.delete("/{playlist_id}/tracks/{item_id}", response_model=PlaylistRead)
def remove_playlist_track(
    playlist_id: str,
    item_id: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> PlaylistRead:
    playlist = get_playlist(db, playlist_id, user.id)
    item = next((value for value in playlist.items if value.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Композиция не найдена в плейлисте")
    remaining = [value for value in playlist.items if value.id != item_id]
    db.delete(item)
    db.flush()
    apply_positions(db, remaining)
    db.commit()
    return serialize_playlist(db, get_playlist(db, playlist_id, user.id), include_items=True)


@router.put("/{playlist_id}/tracks/reorder", response_model=PlaylistRead)
def reorder_playlist(
    playlist_id: str,
    payload: PlaylistReorder,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> PlaylistRead:
    playlist = get_playlist(db, playlist_id, user.id)
    by_id = {item.id: item for item in playlist.items}
    if len(payload.item_ids) != len(by_id) or set(payload.item_ids) != set(by_id):
        raise HTTPException(status_code=422, detail="Порядок должен содержать все элементы плейлиста")
    apply_positions(db, [by_id[item_id] for item_id in payload.item_ids])
    db.commit()
    return serialize_playlist(db, get_playlist(db, playlist_id, user.id), include_items=True)
