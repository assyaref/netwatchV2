"""Generate the NETWATCH app icon (assets/netwatch.ico + netwatch/static/icon.png). Needs Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
S = 1024  # draw large, downscale for crisp edges


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m, r = 40, 210
    d.rounded_rectangle([m, m, S - m, S - m], radius=r, fill=(4, 22, 17, 255))
    d.rounded_rectangle([m, m, S - m, S - m], radius=r, outline=(31, 122, 92, 255), width=34)
    # glow layer for the prompt glyph
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    green, w = (52, 211, 153, 255), 92
    chevron = [(255, 330), (500, 520), (255, 710)]
    g.line(chevron, fill=green, width=w, joint="curve")
    for x, y in (chevron[0], chevron[2]):
        g.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=green)
    g.rounded_rectangle([555, 660, 790, 660 + w], radius=w // 2, fill=(201, 251, 229, 255))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(28)))
    img.alpha_composite(glow)
    return img


def main() -> None:
    big = draw()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big.resize((256, 256), Image.LANCZOS).save(ROOT / "assets" / "netwatch.ico",
                                               sizes=[(s, s) for s in sizes])
    big.resize((256, 256), Image.LANCZOS).save(ROOT / "netwatch" / "static" / "icon.png")
    big.resize((512, 512), Image.LANCZOS).save(ROOT / "assets" / "netwatch.png")


if __name__ == "__main__":
    main()
