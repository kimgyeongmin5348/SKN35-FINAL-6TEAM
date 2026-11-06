"""Hand-coded pixel-art office objects (top-down 3/4 view, 32px tile grid).

Usage: uv run --no-project --with pillow python build_objects.py
Writes one transparent PNG per object + objects.json (size + collision footprint)
+ objects_preview.png into this folder.
"""
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parent
rng = random.Random(3)

# ---------------------------------------------------------------- palette
OL = (34, 28, 36, 255)                  # outline
W_TOP, W_TOP_HI = (196, 132, 80), (214, 154, 100)
W_MID, W_DARK = (158, 100, 60), (116, 72, 42)
GRAY_D, GRAY, GRAY_L, GRAY_XL = (52, 54, 64), (92, 96, 108), (150, 156, 168), (210, 214, 222)
BLUE_SCR, BLUE_SCR_L = (40, 92, 168), (98, 160, 226)
PURPLE_D, PURPLE, PURPLE_L = (74, 40, 102), (110, 62, 146), (140, 90, 176)
GREEN_D, GREEN, GREEN_L = (34, 102, 52), (52, 140, 66), (90, 182, 92)
WHITE, WHITE_S = (244, 244, 248), (206, 210, 220)
GLASS = (170, 226, 240, 150)
GLASS_HI = (230, 250, 255, 200)

OBJECTS = {}   # name -> (image, footprint_height_px, kind)


def obj(name, w, h, foot=None, kind="floor"):
    """Decorator: create canvas, run drawing fn, register object.
    foot = collision height from the bottom (None = whole height, 0 = walkable/wall deco)."""
    def wrap(fn):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        fn(ImageDraw.Draw(im), w, h, im)
        OBJECTS[name] = (im, h if foot is None else foot, kind)
        return fn
    return wrap


def R(d, x0, y0, x1, y1, fill, ol=True):
    d.rectangle([x0, y0, x1, y1], fill=fill, outline=OL if ol else None)


def hline(d, x0, x1, y, c):
    d.line([x0, y, x1, y], fill=c)


def wood_desk(d, w, h, top_h):
    """Desk body: top surface + front panel + side drawer."""
    R(d, 0, 10, w - 1, 10 + top_h, W_TOP)
    hline(d, 1, w - 2, 11, W_TOP_HI)
    R(d, 0, 10 + top_h, w - 1, h - 1, W_MID)
    hline(d, 1, w - 2, 11 + top_h, W_DARK)
    R(d, w - 30, 14 + top_h, w - 5, h - 4, W_TOP)          # drawer
    R(d, w - 21, 18 + top_h, w - 14, 19 + top_h, OL[:3], ol=False)
    R(d, 4, 14 + top_h, 8, h - 1, W_DARK, ol=False)          # leg shadow


def monitor(d, x, y, w=36, h=24):
    R(d, x, y, x + w, y + h, GRAY_D)
    R(d, x + 3, y + 3, x + w - 3, y + h - 4, BLUE_SCR, ol=False)
    d.line([x + 6, y + h - 6, x + 14, y + 5], fill=BLUE_SCR_L)
    d.line([x + 9, y + h - 6, x + 17, y + 5], fill=BLUE_SCR_L)
    R(d, x + w // 2 - 3, y + h, x + w // 2 + 3, y + h + 5, GRAY)
    R(d, x + w // 2 - 9, y + h + 5, x + w // 2 + 9, y + h + 8, GRAY)


def keyboard(d, x, y, w=30):
    R(d, x, y, x + w, y + 6, GRAY_XL)
    for kx in range(x + 2, x + w - 1, 3):
        d.point((kx, y + 2), fill=GRAY_L)
        d.point((kx + 1, y + 4), fill=GRAY_L)


# ---------------------------------------------------------------- desks / tables
@obj("desk_pc", 96, 64, foot=40)
def _(d, w, h, im):
    wood_desk(d, w, h, 30)
    monitor(d, 30, 0)
    keyboard(d, 32, 34)
    R(d, 68, 35, 72, 40, GRAY_XL)                            # mouse
    R(d, 8, 22, 16, 32, WHITE)                               # mug
    R(d, 10, 24, 14, 26, (150, 90, 50), ol=False)
    R(d, 76, 18, 90, 30, (250, 236, 150))                    # sticky pad


@obj("desk_laptop", 96, 64, foot=40)
def _(d, w, h, im):
    wood_desk(d, w, h, 30)
    R(d, 32, 8, 64, 30, GRAY)                                # lid / screen
    R(d, 35, 11, 61, 27, BLUE_SCR, ol=False)
    d.line([38, 25, 44, 12], fill=BLUE_SCR_L)
    R(d, 30, 30, 66, 36, GRAY_L)                             # base
    for i, c in enumerate([(255, 255, 255), (240, 240, 230), (230, 236, 250)]):
        R(d, 6 + i * 3, 16 + i * 2, 24 + i * 3, 32 + i * 2, c)   # papers
    R(d, 74, 20, 82, 32, (60, 140, 200))                     # bottle
    R(d, 76, 16, 80, 20, WHITE)


@obj("desk_manager", 128, 64, foot=40)
def _(d, w, h, im):
    R(d, 0, 10, w - 1, 42, (120, 72, 44))
    hline(d, 1, w - 2, 11, (150, 96, 60))
    R(d, 0, 42, w - 1, h - 1, (92, 54, 34))
    R(d, 6, 46, 40, h - 4, (120, 72, 44))
    R(d, w - 41, 46, w - 7, h - 4, (120, 72, 44))
    monitor(d, 30, 0)
    monitor(d, 64, 0)
    keyboard(d, 48, 34)
    R(d, 10, 18, 22, 32, (40, 40, 48))                       # desk phone
    R(d, 12, 20, 20, 24, (90, 200, 120), ol=False)
    R(d, 104, 24, 116, 34, (250, 250, 250))                  # name plate
    R(d, 106, 28, 114, 30, (200, 160, 60), ol=False)


@obj("meeting_table", 160, 72, foot=52)
def _(d, w, h, im):
    R(d, 0, 0, w - 1, 52, W_TOP)
    hline(d, 1, w - 2, 1, W_TOP_HI)
    for x in range(20, w - 10, 24):                          # grain
        d.line([x, 6, x + 10, 6], fill=W_MID)
        d.line([x - 8, 30, x + 4, 30], fill=W_MID)
    R(d, 0, 52, w - 1, 62, W_MID)
    R(d, 6, 62, 14, h - 1, W_DARK)
    R(d, w - 15, 62, w - 7, h - 1, W_DARK)
    for x in (24, 64, 104):                                  # documents & laptop
        R(d, x + 6, 10, x + 22, 24, WHITE)
    R(d, 66, 30, 92, 44, GRAY)
    R(d, 68, 32, 90, 40, BLUE_SCR, ol=False)


@obj("coffee_table_glass", 64, 40, foot=24)
def _(d, w, h, im):
    d.line([12, 22, 12, h - 2], fill=GRAY_L, width=2)
    d.line([w - 13, 22, w - 13, h - 2], fill=GRAY_L, width=2)
    d.line([31, 24, 31, h - 1], fill=GRAY_L, width=2)
    top = Image.new("RGBA", (w, 30), (0, 0, 0, 0))
    td = ImageDraw.Draw(top)
    td.ellipse([0, 0, w - 1, 28], fill=GLASS, outline=OL)
    td.arc([8, 4, w - 20, 20], 190, 260, fill=GLASS_HI, width=2)
    im.alpha_composite(top, (0, 0))
    R(d, 26, 8, 34, 15, WHITE)                               # cup
    R(d, 28, 9, 32, 11, (140, 80, 40), ol=False)


@obj("reception_desk", 128, 64, foot=36)
def _(d, w, h, im):
    R(d, 0, 4, w - 1, 22, (250, 250, 252))                   # counter top
    hline(d, 1, w - 2, 5, (255, 255, 255))
    R(d, 0, 22, w - 1, h - 1, (110, 116, 130))
    glass = Image.new("RGBA", (w - 8, h - 30), GLASS)
    im.alpha_composite(glass, (4, 26))
    d.line([10, h - 6, 30, 28], fill=GLASS_HI, width=2)
    d.line([70, h - 6, 90, 28], fill=GLASS_HI, width=2)
    monitor(d, 46, 0, 30, 16)


# ---------------------------------------------------------------- seating
@obj("chair_down", 32, 44, foot=16)
def _(d, w, h, im):
    R(d, 7, 0, 24, 20, GRAY_D)                               # backrest (behind)
    hline(d, 9, 22, 2, GRAY)
    R(d, 4, 18, 27, 29, (64, 66, 78))                        # seat
    hline(d, 6, 25, 19, GRAY)
    R(d, 2, 16, 6, 26, GRAY_D)                               # arms
    R(d, 25, 16, 29, 26, GRAY_D)
    R(d, 14, 30, 17, 36, GRAY)
    R(d, 5, 36, 26, 39, GRAY_D)
    for x in (5, 15, 25):
        R(d, x - 1, 40, x + 2, 43, OL[:3], ol=False)


@obj("chair_up", 32, 44, foot=16)
def _(d, w, h, im):
    R(d, 4, 8, 27, 18, (64, 66, 78))                         # seat (behind)
    R(d, 2, 6, 6, 16, GRAY_D)
    R(d, 25, 6, 29, 16, GRAY_D)
    R(d, 7, 12, 24, 32, GRAY_D)                              # backrest (front)
    hline(d, 9, 22, 14, GRAY)
    d.line([15, 18, 15, 28], fill=(42, 44, 52))
    R(d, 14, 33, 17, 36, GRAY)
    R(d, 5, 36, 26, 39, GRAY_D)
    for x in (5, 15, 25):
        R(d, x - 1, 40, x + 2, 43, OL[:3], ol=False)


@obj("sofa_down", 112, 52, foot=40)
def _(d, w, h, im):
    R(d, 6, 0, w - 7, 24, PURPLE_D)                          # back
    hline(d, 8, w - 9, 2, PURPLE)
    for i in range(3):                                       # seat cushions
        x0 = 12 + i * 30
        R(d, x0, 18, x0 + 29, 36, PURPLE)
        hline(d, x0 + 2, x0 + 27, 19, PURPLE_L)
    R(d, 6, 36, w - 7, 45, PURPLE_D)
    R(d, 0, 10, 12, 46, PURPLE)                              # arms
    R(d, w - 13, 10, w - 1, 46, PURPLE)
    hline(d, 1, 11, 11, PURPLE_L)
    hline(d, w - 12, w - 2, 11, PURPLE_L)
    for x in (4, w - 8):
        R(d, x, 46, x + 4, h - 1, W_DARK)


@obj("sofa_up", 112, 52, foot=40)
def _(d, w, h, im):
    for i in range(3):                                       # seat (behind)
        x0 = 12 + i * 30
        R(d, x0, 4, x0 + 29, 20, PURPLE)
    R(d, 0, 0, 12, 40, PURPLE)
    R(d, w - 13, 0, w - 1, 40, PURPLE)
    R(d, 6, 16, w - 7, 46, PURPLE_D)                         # backrest (front)
    hline(d, 8, w - 9, 18, PURPLE)
    for x in (4, w - 8):
        R(d, x, 46, x + 4, h - 1, W_DARK)


@obj("sofa_left", 52, 96, foot=80)
def _(d, w, h, im):
    R(d, 28, 4, w - 1, 86, PURPLE_D)                         # back (right side)
    hline(d, 29, w - 2, 5, PURPLE)
    for i in range(2):                                       # seat cushions
        y0 = 14 + i * 32
        R(d, 8, y0, 32, y0 + 31, PURPLE)
        hline(d, 9, 31, y0 + 1, PURPLE_L)
    R(d, 4, 0, w - 1, 14, PURPLE)                            # arms (top/bottom)
    R(d, 4, 78, w - 1, 90, PURPLE)
    hline(d, 5, w - 2, 1, PURPLE_L)
    R(d, 6, 90, 10, h - 1, W_DARK)
    R(d, w - 8, 90, w - 4, h - 1, W_DARK)


# ---------------------------------------------------------------- storage / appliances
@obj("bookshelf", 96, 96, foot=24)
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, W_DARK)
    colors = [(190, 60, 60), (60, 110, 190), (230, 190, 70), (70, 150, 90),
              (220, 220, 220), (150, 80, 160), (230, 130, 60), (90, 70, 60)]
    for s in range(4):
        y0, y1 = 4 + s * 23, 4 + s * 23 + 19
        R(d, 4, y0, w - 5, y1, (70, 44, 28), ol=False)
        x = 5
        while x < w - 8:
            bw = rng.choice([4, 5, 6])
            bh = rng.randrange(12, 19)
            if rng.random() < 0.12:
                x += bw
                continue
            c = rng.choice(colors)
            R(d, x, y1 - bh, x + bw - 1, y1, c, ol=False)
            d.line([x, y1 - bh, x, y1], fill=tuple(max(0, v - 50) for v in c))
            hline(d, x, x + bw - 1, y1 - bh + 3, tuple(min(255, v + 40) for v in c))
            x += bw
        hline(d, 2, w - 3, y1 + 1, W_TOP)


@obj("filing_cabinet", 32, 52, foot=20)
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, GRAY_L)
    for i in range(3):
        y0 = 3 + i * 16
        R(d, 3, y0, w - 4, y0 + 13, GRAY_XL)
        R(d, 12, y0 + 5, 19, y0 + 7, GRAY_D, ol=False)


@obj("water_cooler", 28, 60, foot=16)
def _(d, w, h, im):
    R(d, 6, 0, 21, 20, (110, 180, 240))
    d.line([9, 3, 9, 17], fill=(200, 236, 255))
    R(d, 3, 20, 24, h - 1, WHITE)
    hline(d, 4, 23, 21, (255, 255, 255))
    R(d, 7, 28, 10, 32, (220, 60, 60))
    R(d, 17, 28, 20, 32, (60, 120, 220))
    R(d, 6, 36, 21, 40, WHITE_S)


@obj("coffee_machine", 44, 60, foot=24)
def _(d, w, h, im):
    R(d, 0, 26, w - 1, h - 1, W_MID)                         # cabinet
    R(d, 3, 34, 20, h - 4, W_TOP)
    R(d, 23, 34, w - 4, h - 4, W_TOP)
    R(d, 0, 22, w - 1, 28, W_TOP_HI)                         # counter top
    R(d, 8, 0, 34, 24, (36, 36, 42))                         # machine
    R(d, 11, 3, 31, 9, GRAY_L)
    R(d, 14, 12, 28, 18, (20, 20, 24))
    R(d, 18, 16, 23, 22, WHITE)                              # cup
    d.point((26, 5), fill=(90, 220, 120))


@obj("printer", 48, 52, foot=24)
def _(d, w, h, im):
    R(d, 2, 14, w - 3, h - 1, GRAY_XL)
    R(d, 0, 4, w - 1, 16, (232, 234, 238))
    R(d, 6, 0, 30, 6, WHITE)                                 # paper
    R(d, 32, 6, 44, 12, GRAY_D)                              # panel
    d.point((35, 9), fill=(90, 220, 120))
    R(d, 6, 22, w - 7, 30, GRAY_L)                           # tray
    R(d, 6, 34, w - 7, 42, GRAY_L)
    R(d, 6, 44, w - 7, h - 4, GRAY_L)


@obj("fridge", 36, 72, foot=20)
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, (226, 230, 236))
    hline(d, 1, w - 2, 24, OL[:3])
    R(d, 28, 8, 30, 18, GRAY)
    R(d, 28, 30, 30, 48, GRAY)
    R(d, 6, 6, 12, 12, (250, 220, 80))                       # magnet note


@obj("kitchen_counter", 96, 60, foot=26)
def _(d, w, h, im):
    R(d, 0, 22, w - 1, h - 1, WHITE)                         # cabinets
    for x in range(0, w, 32):
        R(d, x + 2, 30, x + 29, h - 4, (236, 238, 242))
        R(d, x + 24, 38, x + 26, 46, GRAY, ol=False)
    R(d, 0, 14, w - 1, 26, GRAY_L)                           # counter top
    hline(d, 1, w - 2, 15, GRAY_XL)
    R(d, 12, 16, 40, 24, GRAY)                               # sink
    R(d, 24, 4, 27, 16, GRAY_D)                              # faucet
    R(d, 24, 4, 34, 7, GRAY_D)
    R(d, 60, 6, 80, 18, (60, 60, 70))                        # microwave
    R(d, 63, 9, 73, 15, (30, 30, 34), ol=False)


@obj("trash_bin", 20, 24, foot=10)
def _(d, w, h, im):
    R(d, 2, 4, w - 3, h - 1, GRAY)
    R(d, 0, 2, w - 1, 6, GRAY_L)
    d.line([7, 9, 7, h - 4], fill=GRAY_D)
    d.line([12, 9, 12, h - 4], fill=GRAY_D)


# ---------------------------------------------------------------- plants / deco (floor)
def leaves(d, cx, cy, r, n):
    for _ in range(n):
        x = cx + rng.randrange(-r, r + 1)
        y = cy + rng.randrange(-r, r // 2 + 1)
        s = rng.randrange(5, 9)
        d.ellipse([x - s, y - s // 2 - 2, x + s, y + s // 2 + 2], fill=rng.choice([GREEN_D, GREEN, GREEN_L]), outline=OL)


@obj("plant_big", 40, 64, foot=14)
def _(d, w, h, im):
    for x in (16, 20, 24):
        d.line([20, 46, x + rng.randrange(-6, 7), 26], fill=GREEN_D, width=2)
    leaves(d, 20, 28, 12, 22)
    R(d, 10, 44, 29, h - 1, WHITE)
    hline(d, 11, 28, 45, (255, 255, 255))
    R(d, 9, 42, 30, 47, WHITE_S)


@obj("plant_small", 26, 34, foot=10)
def _(d, w, h, im):
    leaves(d, 13, 12, 7, 8)
    R(d, 6, 20, 19, h - 1, (200, 110, 70))
    R(d, 5, 18, 20, 22, (220, 130, 86))


@obj("coat_rack", 28, 68, foot=8)
def _(d, w, h, im):
    R(d, 12, 6, 15, h - 6, W_DARK)
    R(d, 4, h - 6, 23, h - 2, W_DARK)
    d.line([6, 6, 22, 6], fill=W_DARK, width=2)
    R(d, 3, 10, 13, 40, (150, 90, 50))                       # coat
    R(d, 15, 8, 24, 28, (60, 70, 110))                       # scarf/bag
    R(d, 9, 0, 18, 6, (40, 40, 48))                          # hat


@obj("floor_lamp", 20, 64, foot=8)
def _(d, w, h, im):
    d.polygon([(3, 16), (16, 16), (13, 2), (6, 2)], fill=(250, 236, 190), outline=OL)
    R(d, 9, 16, 10, h - 6, GRAY_D, ol=False)
    R(d, 3, h - 6, 16, h - 2, GRAY_D)


@obj("fire_extinguisher", 14, 28, foot=6)
def _(d, w, h, im):
    R(d, 2, 6, 11, h - 1, (210, 40, 40))
    hline(d, 4, 9, 8, (250, 110, 110))
    R(d, 4, 0, 9, 6, GRAY_D)
    R(d, 4, 14, 9, 18, WHITE)


@obj("glass_partition_h", 96, 44, foot=8)
def _(d, w, h, im):
    im.alpha_composite(Image.new("RGBA", (w - 4, h - 8), GLASS), (2, 2))
    d.rectangle([0, 0, w - 1, h - 6], outline=GRAY_L)
    d.line([12, h - 10, 30, 4], fill=GLASS_HI, width=2)
    d.line([56, h - 10, 74, 4], fill=GLASS_HI, width=2)
    R(d, 0, h - 6, w - 1, h - 1, GRAY_L)


@obj("glass_partition_v", 12, 96, foot=96)
def _(d, w, h, im):
    im.alpha_composite(Image.new("RGBA", (w - 4, h - 4), GLASS), (2, 2))
    d.rectangle([0, 0, w - 1, h - 1], outline=GRAY_L)
    d.line([4, 30, 7, 20], fill=GLASS_HI, width=1)


# ---------------------------------------------------------------- wall-mounted (no collision)
@obj("window_city", 64, 56, foot=0, kind="wall")
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, GRAY_L)
    R(d, 4, 4, w - 5, h - 5, (130, 190, 240), ol=False)
    for x0, bw, bh, c in [(4, 12, 34, (60, 100, 160)), (16, 10, 42, (44, 80, 140)),
                          (26, 14, 28, (70, 120, 180)), (40, 10, 38, (50, 90, 150)),
                          (50, 10, 24, (80, 130, 190))]:
        R(d, x0, h - 5 - bh, x0 + bw - 1, h - 5, c, ol=False)
        for wy in range(h - bh, h - 7, 5):
            for wx in range(x0 + 2, x0 + bw - 2, 4):
                d.point((wx, wy), fill=(250, 230, 140))
    d.line([w // 2, 4, w // 2, h - 5], fill=GRAY_L, width=2)
    d.line([4, h // 2, w - 5, h // 2], fill=GRAY_L, width=2)


@obj("whiteboard", 96, 52, foot=0, kind="wall")
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 6, GRAY_L)
    R(d, 3, 3, w - 4, h - 9, (252, 252, 252), ol=False)
    d.line([10, 12, 40, 12], fill=(40, 90, 200), width=2)
    d.line([10, 20, 56, 20], fill=(40, 40, 40))
    d.line([10, 26, 48, 26], fill=(40, 40, 40))
    d.rectangle([60, 10, 84, 30], outline=(210, 50, 50))
    d.line([62, 28, 70, 18, 76, 24, 82, 12], fill=(40, 160, 80), width=2)
    R(d, 20, h - 6, 76, h - 2, GRAY)
    R(d, 30, h - 8, 38, h - 6, (210, 50, 50), ol=False)


@obj("tv", 88, 52, foot=0, kind="wall")
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, (24, 24, 30))
    R(d, 4, 4, w - 5, h - 5, (36, 40, 56), ol=False)
    d.line([10, h - 10, 30, 8], fill=(60, 66, 90), width=3)
    d.point((w - 8, h - 3), fill=(90, 220, 120))


@obj("wall_clock", 22, 22, foot=0, kind="wall")
def _(d, w, h, im):
    d.ellipse([0, 0, w - 1, h - 1], fill=WHITE, outline=OL)
    d.ellipse([2, 2, w - 3, h - 3], outline=GRAY_L)
    d.line([11, 11, 11, 4], fill=OL)
    d.line([11, 11, 16, 13], fill=OL)


@obj("painting", 48, 36, foot=0, kind="wall")
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, (180, 140, 60))
    R(d, 3, 3, w - 4, h - 4, (150, 200, 240), ol=False)
    d.polygon([(3, h - 4), (18, 12), (30, h - 4)], fill=(80, 140, 90))
    d.polygon([(20, h - 4), (34, 16), (w - 4, h - 4)], fill=(60, 120, 80))
    d.ellipse([34, 6, 40, 12], fill=(250, 220, 90))


@obj("bulletin_board", 56, 40, foot=0, kind="wall")
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, W_DARK)
    R(d, 3, 3, w - 4, h - 4, (200, 150, 96), ol=False)
    for x, y, c in [(6, 6, (250, 230, 110)), (20, 10, (250, 160, 180)), (34, 6, (150, 220, 250)),
                    (10, 22, (160, 230, 150)), (28, 24, (250, 230, 110)), (42, 20, (255, 255, 255))]:
        R(d, x, y, x + 9, y + 9, c)


@obj("glass_door", 64, 64, foot=0, kind="wall")
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, (40, 90, 100))
    for x0 in (4, 33):
        R(d, x0, 4, x0 + 26, h - 2, (80, 200, 210))
        d.line([x0 + 4, h - 8, x0 + 14, 10], fill=(190, 245, 250), width=2)
    R(d, 27, 26, 29, 38, GRAY_XL)
    R(d, 35, 26, 37, 38, GRAY_XL)


# ---------------------------------------------------------------- BUILDWISE specialized assets
@obj("desk_consultation", 136, 54, foot=34)
def _(d, w, h, im):
    """Consultation Team workstation: warm wood desk, left voice-waveform monitor,
    studio mic arm, right requirement/feedback cards, open center for seated agent."""
    R(d, 0, 14, w - 1, 34, (214, 152, 102))
    hline(d, 1, w - 2, 15, (232, 176, 128))
    R(d, 0, 34, w - 1, h - 1, (168, 110, 68))
    R(d, 6, 38, 34, h - 4, (196, 134, 86))
    R(d, w - 35, 38, w - 7, h - 4, (196, 134, 86))
    # Front team accent badge on desk modesty panel
    R(d, 52, 39, 83, 47, (249, 115, 22))
    hline(d, 55, 80, 43, WHITE)
    # Left monitor: live voice waveform
    R(d, 8, 0, 44, 22, GRAY_D)
    R(d, 11, 3, 41, 19, (30, 41, 59), ol=False)
    for i, bh in enumerate([4, 10, 6, 12, 8, 11, 5, 9]):
        bx = 14 + i * 3
        d.line([bx, 11 - bh // 2, bx, 11 + bh // 2], fill=(251, 146, 60), width=2)
    R(d, 23, 22, 29, 26, GRAY)
    # Condenser mic on desk
    R(d, 48, 10, 52, 18, GRAY_D)
    d.line([50, 18, 50, 25], fill=GRAY, width=2)
    # Right side: structured requirement & feedback cards
    R(d, 92, 17, 108, 29, (255, 247, 237))
    d.line([95, 21, 105, 21], fill=(249, 115, 22))
    d.line([95, 24, 104, 24], fill=GRAY)
    R(d, 112, 19, 128, 30, (254, 226, 226))
    d.line([115, 23, 125, 23], fill=(236, 72, 153))


@obj("desk_solution", 136, 54, foot=34)
def _(d, w, h, im):
    """Solution Team workstation: dark tech desk, left GPU/VRAM monitor,
    right Local-vs-Cloud architecture monitor, mini LLM test rig."""
    R(d, 0, 14, w - 1, 34, (62, 74, 96))
    hline(d, 1, w - 2, 15, (92, 108, 138))
    R(d, 0, 34, w - 1, h - 1, (40, 48, 66))
    R(d, 52, 39, 83, 47, (14, 165, 233))
    hline(d, 55, 80, 43, WHITE)
    # Left monitor: GPU VRAM bar chart
    R(d, 6, 0, 44, 23, (24, 28, 38))
    R(d, 9, 3, 41, 20, (15, 23, 42), ol=False)
    for i, (bh, c) in enumerate([(7, (56, 189, 248)), (11, (34, 211, 238)), (14, (16, 185, 129)), (9, (250, 204, 21))]):
        bx = 12 + i * 7
        d.rectangle([bx, 18 - bh, bx + 4, 18], fill=c)
    R(d, 22, 23, 28, 27, GRAY)
    # Right monitor: Local vs Cloud comparison screen
    R(d, 92, 0, 130, 23, (24, 28, 38))
    R(d, 95, 3, 127, 20, (15, 23, 42), ol=False)
    d.line([98, 16, 106, 10, 114, 13, 124, 6], fill=(56, 189, 248), width=2)
    R(d, 108, 23, 114, 27, GRAY)
    # Small GPU module on desk
    R(d, 86, 22, 98, 30, (30, 64, 175))
    d.point((90, 26), fill=(56, 189, 248))


@obj("desk_validation", 136, 54, foot=34)
def _(d, w, h, im):
    """Validation Team workstation: clean QA desk, left spec-matrix monitor,
    right compatibility checker + PASS/WARN/FAIL stamp set."""
    R(d, 0, 14, w - 1, 34, (226, 234, 232))
    hline(d, 1, w - 2, 15, (245, 250, 248))
    R(d, 0, 34, w - 1, h - 1, (142, 160, 156))
    R(d, 52, 39, 83, 47, (16, 185, 129))
    hline(d, 55, 80, 43, WHITE)
    # Left monitor: official spec sheet + checkmarks
    R(d, 6, 0, 44, 23, GRAY_D)
    R(d, 9, 3, 41, 20, (248, 250, 252), ol=False)
    for ry, col in [(6, (16, 185, 129)), (11, (245, 158, 11)), (16, (16, 185, 129))]:
        d.rectangle([12, ry, 15, ry + 2], fill=col)
        d.line([18, ry + 1, 37, ry + 1], fill=(100, 116, 139))
    R(d, 22, 23, 28, 27, GRAY)
    # Right side: PASS / WARN / FAIL stamps & official manual binder
    for sx, sc in [(94, (16, 185, 129)), (104, (245, 158, 11)), (114, (239, 68, 68))]:
        R(d, sx, 19, sx + 7, 29, sc)
        R(d, sx + 2, 15, sx + 5, 19, GRAY_D)


@obj("desk_quotation", 136, 54, foot=34)
def _(d, w, h, im):
    """Quotation Team workstation: executive wood/indigo desk, left comparison spreadsheet,
    right calculator + sealed quotation & email tray."""
    R(d, 0, 14, w - 1, 34, (186, 134, 92))
    hline(d, 1, w - 2, 15, (212, 160, 116))
    R(d, 0, 34, w - 1, h - 1, (132, 90, 58))
    R(d, 52, 39, 83, 47, (139, 92, 246))
    hline(d, 55, 80, 43, WHITE)
    # Left monitor: comparison table & price quote
    R(d, 6, 0, 44, 23, GRAY_D)
    R(d, 9, 3, 41, 20, WHITE, ol=False)
    d.rectangle([11, 5, 39, 8], fill=(139, 92, 246))
    for gy in (11, 15):
        d.line([11, gy, 39, gy], fill=(203, 213, 225))
    d.line([22, 5, 22, 18], fill=(203, 213, 225))
    R(d, 22, 23, 28, 27, GRAY)
    # Right side: calculator + stacked quote sheets
    R(d, 92, 18, 104, 30, (51, 65, 85))
    R(d, 94, 20, 102, 23, (186, 230, 253), ol=False)
    R(d, 108, 17, 127, 30, (245, 243, 255))
    d.line([111, 21, 124, 21], fill=(139, 92, 246))
    d.line([111, 25, 122, 25], fill=GRAY)


@obj("server_rack_gpu", 44, 82, foot=24)
def _(d, w, h, im):
    """Local LLM GPU server rack with glowing VRAM/compute blades."""
    R(d, 0, 0, w - 1, h - 1, (30, 36, 50))
    R(d, 3, 3, w - 4, h - 5, (17, 24, 39), ol=False)
    for i in range(5):
        y0 = 7 + i * 14
        R(d, 6, y0, w - 7, y0 + 10, (38, 48, 68))
        d.point((10, y0 + 5), fill=(56, 189, 248))
        d.point((14, y0 + 5), fill=(16, 185, 129) if i != 3 else (250, 204, 21))
        for vx in range(20, w - 10, 3):
            d.line([vx, y0 + 3, vx, y0 + 7], fill=(71, 85, 105))


@obj("hw_bench", 92, 54, foot=26)
def _(d, w, h, im):
    """Hardware test bench with GPU box, DDR5 RAM sticks, and test laptop."""
    R(d, 0, 14, w - 1, 32, (90, 102, 124))
    R(d, 0, 32, w - 1, h - 1, (58, 68, 86))
    # GPU retail box
    R(d, 6, 2, 30, 24, (22, 101, 52))
    R(d, 9, 6, 27, 20, (34, 197, 94), ol=False)
    # RAM sticks on anti-static mat
    R(d, 36, 17, 56, 28, (30, 58, 138))
    d.line([39, 20, 53, 20], fill=(74, 222, 128), width=2)
    d.line([39, 24, 53, 24], fill=(74, 222, 128), width=2)
    # Open test laptop
    R(d, 62, 6, 86, 22, GRAY_D)
    R(d, 65, 9, 83, 19, BLUE_SCR, ol=False)
    R(d, 60, 22, 88, 28, GRAY_L)


def _draw_tower(d, w, h, active):
    R(d, 6, h - 8, w - 7, h - 1, GRAY_D)
    R(d, 10, 42, 13, h - 8, GRAY)
    R(d, 5, 4, w - 6, 42, (36, 40, 50))
    lights = [
        (7,  (239, 68, 68) if active == "fail" else (90, 36, 38)),
        (18, (250, 204, 21) if active == "warn" else (92, 78, 28)),
        (29, (16, 185, 129) if active == "pass" else (28, 82, 60)),
    ]
    for ly, col in lights:
        R(d, 7, ly, w - 8, ly + 9, col)


@obj("validation_tower_idle", 24, 64, foot=12)
def _(d, w, h, im): _draw_tower(d, w, h, "idle")


@obj("validation_tower_pass", 24, 64, foot=12)
def _(d, w, h, im): _draw_tower(d, w, h, "pass")


@obj("validation_tower_warn", 24, 64, foot=12)
def _(d, w, h, im): _draw_tower(d, w, h, "warn")


@obj("validation_tower_fail", 24, 64, foot=12)
def _(d, w, h, im): _draw_tower(d, w, h, "fail")


@obj("mail_station", 56, 56, foot=22)
def _(d, w, h, im):
    """Approved quotation email dispatch kiosk."""
    R(d, 0, 20, w - 1, h - 1, (79, 70, 229))
    R(d, 4, 26, w - 5, h - 5, (238, 242, 255))
    R(d, 8, 2, w - 9, 22, (255, 255, 255))
    d.line([9, 3, w // 2, 13, w - 10, 3], fill=(79, 70, 229), width=2)
    d.line([10, 34, w - 11, 34], fill=(129, 140, 248), width=2)
    d.point((w - 10, 24), fill=(52, 211, 153))


@obj("orchestrator_hub", 136, 62, foot=34)
def _(d, w, h, im):
    """Central BUILDWISE Orchestrator status console."""
    R(d, 0, 18, w - 1, h - 1, (30, 41, 59))
    R(d, 4, 22, w - 5, 40, (15, 23, 42))
    # 4 pipeline stage nodes on console screen: Consult -> Solution -> Validation -> Quote
    cols = [(249, 115, 22), (56, 189, 248), (16, 185, 129), (167, 139, 250)]
    for i, c in enumerate(cols):
        nx = 18 + i * 30
        if i < 3:
            d.line([nx + 10, 31, nx + 28, 31], fill=(100, 116, 139), width=2)
        d.ellipse([nx, 25, nx + 12, 37], fill=c, outline=WHITE)
    R(d, 10, 45, w - 11, h - 6, (51, 65, 85))


@obj("board_requirements", 96, 48, foot=0, kind="wall")
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, (120, 82, 52))
    R(d, 3, 3, w - 4, h - 4, (255, 251, 235), ol=False)
    R(d, 6, 6, 36, 14, (249, 115, 22))
    for x, y, c in [(8, 18, (254, 240, 138)), (28, 18, (254, 215, 170)),
                    (48, 8, (254, 205, 211)), (68, 8, (191, 219, 254)),
                    (48, 24, (187, 247, 208)), (68, 24, (254, 240, 138))]:
        R(d, x, y, x + 16, y + 14, c)


@obj("board_architecture", 96, 48, foot=0, kind="wall")
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, (30, 41, 59))
    R(d, 3, 3, w - 4, h - 4, (15, 23, 42), ol=False)
    # 4 option comparison quadrants: Keep / Upgrade / New / Cloud
    for i, (x, y, c) in enumerate([(7, 7, (148, 163, 184)), (49, 7, (56, 189, 248)),
                                   (7, 25, (16, 185, 129)), (49, 25, (167, 139, 250))]):
        d.rectangle([x, y, x + 38, y + 15], outline=c)
        d.line([x + 4, y + 7, x + 28, y + 7], fill=c, width=2)
        d.line([x + 4, y + 11, x + 20, y + 11], fill=(100, 116, 139))


@obj("board_compat", 96, 48, foot=0, kind="wall")
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, GRAY_D)
    R(d, 3, 3, w - 4, h - 4, (248, 250, 252), ol=False)
    for i, c in enumerate([(16, 185, 129), (245, 158, 11), (239, 68, 68)]):
        y = 8 + i * 12
        R(d, 8, y, 18, y + 8, c)
        d.line([24, y + 4, 84, y + 4], fill=(71, 85, 105), width=2)


@obj("board_pricing", 96, 48, foot=0, kind="wall")
def _(d, w, h, im):
    R(d, 0, 0, w - 1, h - 1, (76, 29, 149))
    R(d, 3, 3, w - 4, h - 4, (250, 245, 255), ol=False)
    R(d, 7, 7, 88, 14, (139, 92, 246))
    for y in (20, 28, 36):
        d.line([8, y, 86, y], fill=(196, 181, 253))
    d.line([36, 7, 36, 41], fill=(196, 181, 253))
    d.line([64, 7, 64, 41], fill=(196, 181, 253))


# ---------------------------------------------------------------- export
if __name__ == "__main__":
    meta = {}
    for name, (im, foot, kind) in OBJECTS.items():
        im.save(OUT / f"{name}.png")
        meta[name] = {"w": im.width, "h": im.height, "foot": foot, "kind": kind}
    (OUT / "objects.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # contact sheet preview (x2)
    pad, cols = 12, 6
    items = list(OBJECTS.items())
    cw = max(i.width for i, _, _ in OBJECTS.values()) + pad
    chh = max(i.height for i, _, _ in OBJECTS.values()) + pad
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGBA", (cw * cols, chh * rows), (214, 128, 62, 255))
    for k, (name, (im, _, _)) in enumerate(items):
        sheet.alpha_composite(im, ((k % cols) * cw + pad // 2, (k // cols) * chh + pad // 2))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(OUT / "objects_preview.png")
    print(len(OBJECTS), "objects")
