import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import Settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


class CollectionPhotoStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.collections_photos_dir
        self.staging = settings.collections_staging_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self.staging.mkdir(parents=True, exist_ok=True)

    async def save(self, upload: UploadFile, item_id: str, photo_id: str) -> tuple[str, str, str]:
        original_name = Path(upload.filename or "photo").name
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail="Поддерживаются JPG, PNG, WebP и AVIF")
        staged = self.staging / f"{uuid.uuid4()}{extension}"
        full: Path | None = None
        thumb: Path | None = None
        size = 0
        limit = min(self.settings.max_upload_mb, 25) * 1024 * 1024
        try:
            with staged.open("wb") as target:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(status_code=413, detail="Фотография превышает лимит 25 МБ")
                    target.write(chunk)
            bucket = self.root / item_id[:2] / item_id
            bucket.mkdir(parents=True, exist_ok=True)
            full = bucket / f"{photo_id}.webp"
            thumb = bucket / f"{photo_id}-thumb.webp"
            try:
                with Image.open(staged) as source:
                    image = ImageOps.exif_transpose(source)
                    if image.mode not in {"RGB", "RGBA"}:
                        image = image.convert("RGB")
                    elif image.mode == "RGBA":
                        background = Image.new("RGB", image.size, "white")
                        background.paste(image, mask=image.getchannel("A"))
                        image = background
                    full_image = image.copy()
                    full_image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
                    full_image.save(full, "WEBP", quality=90, method=6)
                    thumbnail = image.copy()
                    thumbnail.thumbnail((720, 900), Image.Resampling.LANCZOS)
                    thumbnail.save(thumb, "WEBP", quality=84, method=6)
            except (UnidentifiedImageError, OSError) as exc:
                raise HTTPException(status_code=415, detail="Файл не является корректным изображением") from exc
            return self.relative(full), self.relative(thumb), original_name
        except Exception:
            if full:
                full.unlink(missing_ok=True)
            if thumb:
                thumb.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()
            staged.unlink(missing_ok=True)

    def relative(self, path: Path) -> str:
        return path.relative_to(self.settings.media_root).as_posix()

    def managed(self, relative_path: str) -> Path:
        root = self.settings.media_root.resolve()
        path = (root / relative_path).resolve()
        if root not in path.parents:
            raise ValueError("Path is outside media storage")
        return path

    def delete(self, *paths: str | None) -> None:
        for relative_path in paths:
            if not relative_path:
                continue
            try:
                self.managed(relative_path).unlink(missing_ok=True)
            except ValueError:
                continue

    def delete_item_directory(self, item_id: str) -> None:
        directory = self.root / item_id[:2] / item_id
        if directory.is_dir():
            shutil.rmtree(directory)
