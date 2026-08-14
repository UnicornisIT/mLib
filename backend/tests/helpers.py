from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.music.models import Artist, Track


def create_track(
    db: Session, *, title: str = "Test Track", suffix: str = ".mp3", content: bytes = b"0123456789"
) -> Track:
    artist = db.query(Artist).filter_by(normalized_name="test artist").first()
    if artist is None:
        artist = Artist(name="Test Artist", sort_name="Test Artist", normalized_name="test artist")
        db.add(artist)
        db.flush()
    track = Track(
        title=title,
        artist_id=artist.id,
        duration=120.0,
        file_path="",
        original_filename=f"{title}{suffix}",
        file_size=len(content),
        file_hash=(title.encode().hex() + "0" * 64)[:64],
        format=suffix.lstrip("."),
        codec=suffix.lstrip("."),
    )
    db.add(track)
    db.flush()
    settings = get_settings()
    path = settings.originals_dir / track.uuid[:2] / f"{track.uuid}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    track.file_path = path.relative_to(settings.media_root).as_posix()
    db.commit()
    db.refresh(track)
    return track
