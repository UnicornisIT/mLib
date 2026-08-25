from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MASTER_ICON = ROOT / "assets" / "branding" / "mlib-icon-master.png"
DESKTOP_BUILD = ROOT / "desktop" / "build"
FRONTEND_APP = ROOT / "frontend" / "src" / "app"


def render_icon(source: Image.Image, size: int) -> Image.Image:
    return source.resize((size, size), Image.Resampling.LANCZOS)


def load_master() -> Image.Image:
    if not MASTER_ICON.is_file():
        raise FileNotFoundError(f"Master icon was not found: {MASTER_ICON}")
    image = Image.open(MASTER_ICON).convert("RGBA")
    if image.width != image.height:
        raise ValueError("Master icon must have a square canvas")

    # Remove effectively invisible edge noise without touching antialiased artwork.
    alpha = image.getchannel("A").point(lambda value: 0 if value <= 4 else value)
    image.putalpha(alpha)
    return image


def main() -> None:
    source = load_master()
    DESKTOP_BUILD.mkdir(parents=True, exist_ok=True)
    FRONTEND_APP.mkdir(parents=True, exist_ok=True)

    desktop_icon = render_icon(source, 512)
    desktop_icon.save(DESKTOP_BUILD / "icon.png", optimize=True)
    desktop_icon.save(
        DESKTOP_BUILD / "icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    desktop_icon.save(FRONTEND_APP / "icon.png", optimize=True)
    render_icon(source, 180).save(FRONTEND_APP / "apple-icon.png", optimize=True)
    desktop_icon.save(
        FRONTEND_APP / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )


if __name__ == "__main__":
    main()
