#!/usr/bin/env python3
"""Generate app icons for the parkrun dashboard.

Design: parkrun-authentic barcode + bold BATES wordmark on gradient.
"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"

SIZE = 1024


def make_master():
    img = Image.new("RGB", (SIZE, SIZE), (43, 35, 61))
    draw = ImageDraw.Draw(img)

    # Diagonal gradient
    top = (43, 35, 61)
    mid = (61, 49, 85)
    bot = (255, 77, 109)
    for y in range(SIZE):
        t = y / SIZE
        if t < 0.7:
            u = t / 0.7
            c = tuple(int(top[i] + (mid[i] - top[i]) * u) for i in range(3))
        else:
            u = (t - 0.7) / 0.3
            c = tuple(int(mid[i] + (bot[i] - mid[i]) * u) for i in range(3))
        draw.line([(0, y), (SIZE, y)], fill=c)

    # Warm glow top-right
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    for r in range(500, 0, -30):
        alpha = int(70 * (1 - r / 500))
        g.ellipse(
            [SIZE - r - 50, -r + 100, SIZE + r - 50, r + 100],
            fill=(255, 163, 0, alpha),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img.paste(glow, (0, 0), glow)

    draw = ImageDraw.Draw(img, "RGBA")

    # Barcode — deterministic pattern from "BATES"
    seed = hashlib.md5(b"BATES-PARKRUN").digest()
    bars = []
    total = 0
    i = 0
    while total < 720:
        w = 6 + (seed[i % len(seed)] % 5) * 6   # bar widths 6-30
        gap = 8 + (seed[(i + 3) % len(seed)] % 3) * 6  # gaps 8-20
        bars.append((w, gap))
        total += w + gap
        i += 1
    x = (SIZE - total) // 2
    bar_top = 240
    bar_bot = 640
    for w, gap in bars:
        draw.rectangle([x, bar_top, x + w, bar_bot], fill=(255, 255, 255, 255))
        x += w + gap

    # A couple of orange accent bars for family touch
    x = (SIZE - total) // 2
    accent_positions = [2, 7, 15]
    for idx, (w, gap) in enumerate(bars):
        if idx in accent_positions:
            draw.rectangle([x, bar_top, x + w, bar_bot], fill=(255, 163, 0, 255))
        x += w + gap

    # BATES wordmark (bold, bright)
    try:
        font_big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 150)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 62)
    except OSError:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # BATES
    text = "BATES"
    bbox = draw.textbbox((0, 0), text, font=font_big)
    w = bbox[2] - bbox[0]
    draw.text(((SIZE - w) // 2, 720), text, fill=(255, 255, 255, 255), font=font_big)

    # parkrun small caps below
    text2 = "PARKRUN"
    bbox = draw.textbbox((0, 0), text2, font=font_small)
    w = bbox[2] - bbox[0]
    draw.text(((SIZE - w) // 2, 880), text2, fill=(255, 163, 0, 255), font=font_small)

    # Top "A7939292 / A7959573" style serial hint
    try:
        f_mini = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 42)
    except OSError:
        f_mini = ImageFont.load_default()
    serial = "A7959573  ·  A7939292"
    bbox = draw.textbbox((0, 0), serial, font=f_mini)
    w = bbox[2] - bbox[0]
    draw.text(((SIZE - w) // 2, 150), serial, fill=(255, 255, 255, 180), font=f_mini)

    return img


def main():
    master = make_master()
    OUT.mkdir(parents=True, exist_ok=True)

    for size in [180, 192, 512]:
        im = master.resize((size, size), Image.LANCZOS)
        im.save(OUT / f"icon-{size}.png", optimize=True)

    # Rounded favicon
    fav = master.resize((32, 32), Image.LANCZOS)
    mask = Image.new("L", (32, 32), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 32, 32], radius=7, fill=255)
    fav_rgba = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    fav_rgba.paste(fav, (0, 0), mask)
    fav_rgba.save(OUT / "favicon.png", optimize=True)

    # Master preview (square, no mask — iOS applies its own)
    master.save(OUT / "icon-1024.png", optimize=True)
    print(f"Generated icons in {OUT}")


if __name__ == "__main__":
    main()
