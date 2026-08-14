import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from app.core.config import Settings
from app.modules.music.metadata import EmbeddedArtwork
from app.modules.music.models import Artwork


def save_artwork(embedded: EmbeddedArtwork, settings: Settings) -> Artwork:
    artwork_id = str(uuid.uuid4())
    directory = settings.artwork_dir / artwork_id[:2]
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(io.BytesIO(embedded.data)) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")
            paths: dict[int, Path] = {}
            for size in (512, 256, 64):
                image = ImageOps.fit(source, (size, size), method=Image.Resampling.LANCZOS)
                path = directory / f"{artwork_id}-{size}.webp"
                image.save(path, "WEBP", quality=88 if size == 512 else 82, method=6)
                paths[size] = path
            original = directory / f"{artwork_id}-original.webp"
            source.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            source.save(original, "WEBP", quality=92, method=6)
    except Exception as exc:
        for path in directory.glob(f"{artwork_id}-*"):
            path.unlink(missing_ok=True)
        raise ValueError("Встроенная обложка повреждена") from exc

    def relative(path: Path) -> str:
        return path.relative_to(settings.media_root).as_posix()

    return Artwork(
        id=artwork_id,
        original_path=relative(original),
        path_512=relative(paths[512]),
        path_256=relative(paths[256]),
        path_64=relative(paths[64]),
        mime_type="image/webp",
    )
