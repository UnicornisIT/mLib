import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import Settings


@dataclass(slots=True)
class StagedFile:
    path: Path
    original_name: str
    extension: str
    size: int
    sha256: str


class LocalMediaStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        for directory in (settings.originals_dir, settings.artwork_dir, settings.staging_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def validate_extension(self, filename: str) -> str:
        extension = Path(filename).suffix.lower()
        if extension not in self.settings.supported_audio_extensions:
            raise HTTPException(status_code=415, detail=f"Формат {extension or 'без расширения'} не поддерживается")
        return extension

    async def stage_upload(self, upload: UploadFile) -> StagedFile:
        original_name = Path(upload.filename or "track").name
        extension = self.validate_extension(original_name)
        destination = self.settings.staging_dir / f"{uuid.uuid4()}{extension}"
        digest = hashlib.sha256()
        size = 0
        limit = self.settings.max_upload_mb * 1024 * 1024
        try:
            with destination.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(
                            status_code=413, detail=f"Файл превышает лимит {self.settings.max_upload_mb} МБ"
                        )
                    digest.update(chunk)
                    output.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()
        return StagedFile(destination, original_name, extension, size, digest.hexdigest())

    def stage_existing(self, source: Path) -> StagedFile:
        extension = self.validate_extension(source.name)
        destination = self.settings.staging_dir / f"{uuid.uuid4()}{extension}"
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as incoming, destination.open("wb") as output:
            while chunk := incoming.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
                output.write(chunk)
        return StagedFile(destination, source.name, extension, size, digest.hexdigest())

    def commit(self, staged: StagedFile, track_uuid: str) -> Path:
        bucket = self.settings.originals_dir / track_uuid[:2]
        bucket.mkdir(parents=True, exist_ok=True)
        destination = bucket / f"{track_uuid}{staged.extension}"
        shutil.move(str(staged.path), destination)
        return destination

    def discard(self, staged: StagedFile) -> None:
        staged.path.unlink(missing_ok=True)

    def ensure_managed_path(self, path: str | Path) -> Path:
        resolved = Path(path).resolve()
        root = self.settings.media_root.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError("Путь находится вне управляемого хранилища")
        return resolved
