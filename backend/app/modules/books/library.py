import hashlib
import mimetypes
import shutil
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings

EBOOK_EXTENSIONS = {".epub", ".pdf", ".fb2", ".mobi", ".azw3", ".djvu", ".txt"}
AUDIOBOOK_EXTENSIONS = {".mp3", ".m4b", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wav"}
MIME_OVERRIDES = {
    ".epub": "application/epub+zip",
    ".fb2": "application/x-fictionbook+xml",
    ".mobi": "application/x-mobipocket-ebook",
    ".azw3": "application/vnd.amazon.ebook",
    ".djvu": "image/vnd.djvu",
    ".m4b": "audio/mp4",
}


class DuplicateBookError(Exception):
    pass


class BooksStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        for directory in (settings.books_originals_dir, settings.books_covers_dir, settings.books_staging_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def extension_for(self, filename: str, media_type: str) -> str:
        extension = Path(filename).suffix.lower()
        supported = EBOOK_EXTENSIONS if media_type == "ebook" else AUDIOBOOK_EXTENSIONS
        if media_type not in {"ebook", "audiobook"}:
            raise HTTPException(status_code=422, detail="Неизвестный тип книги")
        if extension not in supported:
            formats = ", ".join(sorted(item.lstrip(".").upper() for item in supported))
            raise HTTPException(
                status_code=415,
                detail=f"Формат {extension or 'без расширения'} не поддерживается. Доступно: {formats}",
            )
        return extension

    async def stage(self, upload: UploadFile, media_type: str) -> tuple[Path, str, int, str, str]:
        filename = Path(upload.filename or "book").name
        extension = self.extension_for(filename, media_type)
        destination = self.settings.books_staging_dir / f"{uuid.uuid4()}{extension}"
        digest = hashlib.sha256()
        size = 0
        limit = self.settings.max_upload_mb * 1024 * 1024
        try:
            with destination.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Файл превышает лимит {self.settings.max_upload_mb} МБ",
                        )
                    digest.update(chunk)
                    output.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()
        if not size:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Нельзя загрузить пустой файл")
        return destination, filename, size, digest.hexdigest(), extension

    def commit_file(self, staged: Path, book_id: str, extension: str) -> Path:
        bucket = self.settings.books_originals_dir / book_id[:2]
        bucket.mkdir(parents=True, exist_ok=True)
        destination = bucket / f"{book_id}{extension}"
        shutil.move(str(staged), destination)
        return destination

    async def save_cover(self, upload: UploadFile, book_id: str) -> Path:
        raw = await upload.read(12 * 1024 * 1024 + 1)
        await upload.close()
        if len(raw) > 12 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Обложка превышает лимит 12 МБ")
        try:
            with Image.open(BytesIO(raw)) as image:
                image.load()
                image.thumbnail((1200, 1800), Image.Resampling.LANCZOS)
                if image.mode not in {"RGB", "RGBA"}:
                    image = image.convert("RGB")
                bucket = self.settings.books_covers_dir / book_id[:2]
                bucket.mkdir(parents=True, exist_ok=True)
                destination = bucket / f"{book_id}.webp"
                image.save(destination, "WEBP", quality=90, method=6)
                return destination
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise HTTPException(status_code=415, detail="Обложка должна быть изображением JPG, PNG или WebP") from exc

    def managed(self, relative_path: str) -> Path:
        path = (self.settings.media_root / relative_path).resolve()
        root = (self.settings.media_root / "books").resolve()
        if path != root and root not in path.parents:
            raise ValueError("Путь находится вне хранилища книг")
        return path

    def relative(self, path: Path) -> str:
        return path.relative_to(self.settings.media_root).as_posix()

    @staticmethod
    def mime_type(extension: str) -> str:
        guessed = mimetypes.guess_type(f"book{extension}")[0]
        return MIME_OVERRIDES.get(extension) or guessed or "application/octet-stream"


def audio_duration(path: Path) -> float | None:
    try:
        from mutagen import File as MutagenFile

        media = MutagenFile(path)
        length = getattr(getattr(media, "info", None), "length", None)
        return round(float(length), 3) if length else None
    except Exception:
        return None


def iter_file_range(path: Path, start: int, length: int):
    with path.open("rb") as source:
        source.seek(start)
        remaining = length
        while remaining > 0:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def parse_range_header(value: str, file_size: int) -> tuple[int, int]:
    unit, raw_range = value.strip().split("=", 1)
    if unit != "bytes" or "," in raw_range:
        raise ValueError
    start_raw, end_raw = raw_range.split("-", 1)
    if not start_raw:
        suffix = int(end_raw)
        if suffix <= 0:
            raise ValueError
        return max(0, file_size - suffix), file_size - 1
    start = int(start_raw)
    end = int(end_raw) if end_raw else file_size - 1
    if start < 0 or start >= file_size or end < start:
        raise ValueError
    return start, min(end, file_size - 1)
