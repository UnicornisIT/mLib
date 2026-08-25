from pathlib import Path

from PIL import Image, ImageDraw


def icon(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = round(size * 0.08)
    radius = round(size * 0.22)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=radius,
        fill=(52, 67, 83, 255),
    )
    # The three offset layers mirror the existing Layers3 home mark.
    stroke = max(2, round(size * 0.055))
    center = size / 2
    width = size * 0.52
    height = size * 0.22
    for offset, color in ((size * -0.13, (245, 243, 236, 255)), (0, (222, 225, 221, 255)), (size * 0.13, (194, 203, 207, 255))):
        y = center + offset
        points = [
            (center, y - height / 2),
            (center + width / 2, y),
            (center, y + height / 2),
            (center - width / 2, y),
        ]
        draw.line(points + [points[0]], fill=color, width=stroke, joint="curve")
    return image


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "desktop" / "build"
    root.mkdir(parents=True, exist_ok=True)
    image = icon(512)
    image.save(root / "icon.png")
    image.save(
        root / "icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
