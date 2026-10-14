#!/usr/bin/env python3
"""Generate the app icons and the GitHub social-preview image.

Draws everything with Pillow (no external artwork), using the dark + orange palette shared with
SnapshotAll. Run it from the repository root whenever the artwork changes:

    python tools/make_icons.py

Outputs
  assets/logo.png            512 x 512 logo (About dialog)
  assets/logo_64.png          64 x  64 logo (toolbar, Linux/macOS window icon)
  assets/icon.ico            multi-size Windows icon (exe, installer, window)
  docs/social-preview.png    1280 x 640 image for Settings -> Social preview on GitHub
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DOCS = ROOT / "docs"

# Palette (same values as the SnapshotAll theme)
BG = "#110D0A"
PANEL = "#1F1813"
BORDER = "#3A2E24"
FG = "#F5EEE8"
MUTED = "#A99B8E"
ORANGE = "#F97316"
ORANGE_H = "#FB923C"
ORANGE_D = "#EA580C"
ON_ORANGE = "#1A0E05"

SIZE = 1024  # drawn large, then downscaled for smooth edges


def _hex(color, alpha=255):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def _vertical_gradient(size, stops):
    """stops: [(position 0..1, '#rrggbb'), ...]"""
    w, h = size
    img = Image.new("RGBA", size)
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        for (p0, c0), (p1, c1) in zip(stops, stops[1:], strict=False):
            if p0 <= t <= p1:
                k = (t - p0) / (p1 - p0) if p1 > p0 else 0
                a, b = _hex(c0), _hex(c1)
                color = tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(4))
                break
        else:
            color = _hex(stops[-1][1])
        for x in range(w):
            px[x, y] = color
    return img


def _rounded_mask(size, box, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    return mask


def _arrow(draw, y, x0, x1, thickness, head, color):
    """Horizontal arrow from x0 to x1 (the head is at x1)."""
    direction = 1 if x1 > x0 else -1
    shaft_end = x1 - direction * head
    draw.rectangle([min(x0, shaft_end), y - thickness // 2, max(x0, shaft_end), y + thickness // 2], fill=color)
    draw.polygon([(x1, y), (shaft_end, y - head), (shaft_end, y + head)], fill=color)


def draw_logo(size=SIZE):
    """Orange tile with two stacked photos and a 'swap' badge (= converting between formats)."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Tile with a vertical orange gradient
    tile = _vertical_gradient((size, size), [(0, "#FDBA74"), (0.45, ORANGE), (1, ORANGE_D)])
    canvas.paste(tile, (0, 0), _rounded_mask((size, size), (0, 0, size - 1, size - 1), 230))

    # Soft shadow under the photos
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((250, 250, 800, 760), radius=70, fill=(90, 30, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    canvas.alpha_composite(shadow)

    # Back photo (translucent, tilted)
    back = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(back).rounded_rectangle((190, 170, 690, 640), radius=70, fill=(255, 255, 255, 120))
    canvas.alpha_composite(back.rotate(9, resample=Image.BICUBIC, center=(440, 405)))

    # Front photo: white card with a sun and two mountains, tilted the other way
    front = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    box = (270, 270, 790, 760)
    ImageDraw.Draw(front).rounded_rectangle(box, radius=70, fill=_hex("#FFF7ED"))
    scene = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scene)
    sd.ellipse((600, 340, 710, 450), fill=_hex(ORANGE_H))                       # sun
    sd.polygon([(270, 760), (470, 470), (640, 760)], fill=_hex(ORANGE))        # big mountain
    sd.polygon([(500, 760), (640, 560), (790, 760)], fill=_hex(ORANGE_D))      # small mountain
    scene.putalpha(ImageChops.multiply(scene.getchannel("A"), _rounded_mask((size, size), box, 70)))
    front.alpha_composite(scene)
    canvas.alpha_composite(front.rotate(-6, resample=Image.BICUBIC, center=(530, 515)))

    # Dark badge with a double arrow
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    cx, cy, r = 745, 745, 175
    bd.ellipse((cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14), fill=_hex("#FFF7ED"))
    bd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_hex(ON_ORANGE))
    _arrow(bd, cy - 48, cx - 105, cx + 105, 30, 52, _hex(ORANGE_H))
    _arrow(bd, cy + 48, cx + 105, cx - 105, 30, 52, _hex("#FFF7ED"))
    canvas.alpha_composite(badge)
    return canvas


def _font(size, bold=False):
    names = (["segoeuib.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold
             else ["segoeui.ttf", "DejaVuSans.ttf", "arial.ttf"])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_social_preview(logo):
    w, h = 1280, 640
    img = Image.new("RGBA", (w, h), _hex(BG))

    # Warm glow behind the logo
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-120, -80, 760, 760), fill=_hex(ORANGE, 70))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(140)))

    img.alpha_composite(logo.resize((340, 340), Image.LANCZOS), (80, 150))

    d = ImageDraw.Draw(img)
    left = 470
    d.text((left, 150), "Image Format", font=_font(74, True), fill=_hex(FG))
    d.text((left, 236), "Converter", font=_font(74, True), fill=_hex(ORANGE))
    sub = _font(24)
    d.text((left + 2, 350), "Convert images between JPG, PNG, WEBP, BMP, GIF,", font=sub, fill=_hex(MUTED))
    d.text((left + 2, 388), "TIFF and ICO - free and open-source for Windows.", font=sub, fill=_hex(MUTED))

    x = left + 2
    chip = _font(22, True)
    for label in ("JPG", "PNG", "WEBP", "BMP", "GIF", "TIFF", "ICO"):
        tw = d.textlength(label, font=chip)
        d.rounded_rectangle((x, 460, x + tw + 28, 506), radius=12, fill=_hex(PANEL), outline=_hex(BORDER), width=2)
        d.text((x + 14, 467), label, font=chip, fill=_hex(ORANGE_H))
        x += tw + 28 + 10
    assert x < w - 30, "social preview chips overflow the image"
    return img.convert("RGB")


def main():
    ASSETS.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    logo = draw_logo()
    logo512 = logo.resize((512, 512), Image.LANCZOS)
    logo512.save(ASSETS / "logo.png", optimize=True)
    logo.resize((64, 64), Image.LANCZOS).save(ASSETS / "logo_64.png", optimize=True)
    logo.save(ASSETS / "icon.ico", format="ICO",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    draw_social_preview(logo).save(DOCS / "social-preview.png", optimize=True)
    print("Wrote assets/logo.png, assets/logo_64.png, assets/icon.ico, docs/social-preview.png")


if __name__ == "__main__":
    main()
