"""Procedurally draw seamless 32x32 pixel-art floor / wall / BUILDWISE zone tiles.

Usage: uv run --no-project --with pillow python assets/tiles/build_tiles.py
"""
import random
from pathlib import Path
from PIL import Image, ImageDraw

T = 32
OUT = Path(__file__).parent
rng = random.Random(7)


def new():
    return Image.new("RGBA", (T, T))


def wood_floor():
    im = new()
    d = ImageDraw.Draw(im)
    base = [(214, 134, 72), (204, 124, 64), (222, 142, 80), (210, 130, 68)]
    plank_h = 8
    for i in range(T // plank_h):
        y0 = i * plank_h
        d.rectangle([0, y0, T - 1, y0 + plank_h - 1], fill=base[i % 4])
        for _ in range(8):
            x = rng.randrange(T)
            y = y0 + rng.randrange(1, plank_h - 1)
            d.line([x, y, min(T - 1, x + rng.randrange(3, 8)), y], fill=(190, 112, 54))
        d.line([0, y0 + plank_h - 1, T - 1, y0 + plank_h - 1], fill=(156, 88, 42))
        seam = (i * 13) % T
        d.line([seam, y0, seam, y0 + plank_h - 2], fill=(156, 88, 42))
    return im


def lane_tile(horiz=True):
    """Wood floor with subtle dotted handoff pathway guide."""
    im = wood_floor()
    d = ImageDraw.Draw(im)
    c = (245, 222, 179)
    if horiz:
        for x in range(2, T, 8):
            d.rectangle([x, 15, x + 3, 16], fill=c)
    else:
        for y in range(2, T, 8):
            d.rectangle([15, y, 16, y + 3], fill=c)
    return im


def zone_rug(rgb, trim_rgb):
    im = new()
    px = im.load()
    for y in range(T):
        for x in range(T):
            n = rng.randrange(-4, 5)
            px[x, y] = (
                max(0, min(255, rgb[0] + n)),
                max(0, min(255, rgb[1] + n)),
                max(0, min(255, rgb[2] + n)),
                255,
            )
    d = ImageDraw.Draw(im)
    for k in range(0, T, 16):
        d.point((k + 4, 4), fill=trim_rgb)
        d.point((k + 12, 20), fill=trim_rgb)
    return im


def lab_tile(rgb, grout):
    im = new()
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, T - 1, T - 1], fill=rgb)
    for k in range(0, T, 16):
        d.line([k, 0, k, T - 1], fill=grout)
        d.line([0, k, T - 1, k], fill=grout)
    return im


def hub_tile():
    im = new()
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, T - 1, T - 1], fill=(42, 50, 74))
    d.rectangle([1, 1, T - 2, T - 2], outline=(58, 70, 102))
    d.point((15, 15), fill=(96, 165, 250))
    return im


def white_tile():
    return lab_tile((238, 240, 244), (196, 200, 208))


def carpet():
    return zone_rug((226, 196, 150), (196, 164, 118))


def wall_face():
    im = new()
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, T - 1, T - 1], fill=(242, 239, 233))
    d.line([0, 0, T - 1, 0], fill=(255, 253, 248))
    d.rectangle([0, T - 6, T - 1, T - 1], fill=(112, 82, 58))
    d.line([0, T - 6, T - 1, T - 6], fill=(146, 108, 78))
    return im


def wall_top():
    im = new()
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, T - 1, T - 1], fill=(26, 32, 50))
    d.rectangle([0, 0, T - 1, T - 1], outline=(40, 48, 74))
    return im


TILES = {
    "wood_floor": wood_floor,
    "lane_h": lambda: lane_tile(True),
    "lane_v": lambda: lane_tile(False),
    "zone_consult": lambda: zone_rug((245, 224, 206), (224, 182, 154)),
    "zone_solution": lambda: lab_tile((54, 68, 92), (72, 92, 124)),
    "zone_validation": lambda: lab_tile((218, 234, 226), (176, 202, 190)),
    "zone_quotation": lambda: zone_rug((228, 222, 244), (192, 182, 222)),
    "hub_tile": hub_tile,
    "white_tile": white_tile,
    "carpet": carpet,
    "wall_face": wall_face,
    "wall_top": wall_top,
}

if __name__ == "__main__":
    sheet = Image.new("RGBA", (T * len(TILES), T))
    for i, (name, fn) in enumerate(TILES.items()):
        im = fn()
        im.save(OUT / f"{name}.png")
        sheet.paste(im, (i * T, 0))
    sheet.save(OUT / "tileset.png")
    print("tiles:", ", ".join(TILES))
