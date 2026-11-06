"""Slice AI-generated 8x4 sprite sheet, key out magenta, normalize cells,
mirror left-facing rows to build right-facing rows, export clean PNGs.

Usage: uv run --no-project --with pillow python build_sheet.py <source_image> <character_name>
"""
import sys
from pathlib import Path
from PIL import Image

SRC = Path(sys.argv[1])
NAME = sys.argv[2]
OUT = Path(__file__).parent / NAME
CELL = 64          # final cell size (px)
ROWS, COLS = 8, 4
DIRS = ["down", "down_left", "left", "up_left", "up", "up_right", "right", "down_right"]

img = Image.open(SRC).convert("RGBA")
W, H = img.size
cw, ch = W / COLS, H / ROWS


def key_magenta(im):
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if r > 170 and b > 170 and g < 110:   # magenta (JPEG tolerant)
                px[x, y] = (0, 0, 0, 0)
            elif r > 90 and b > 90 and (r - g) > 50 and (b - g) > 50:
                px[x, y] = (0, 0, 0, 0)           # purple fringe
    return remove_specks(im)


def remove_specks(im):
    """Keep only the main sprite: drop connected components much smaller than the largest."""
    w, h = im.size
    px = im.load()
    seen = [[False] * w for _ in range(h)]
    comps = []
    for sy in range(h):
        for sx in range(w):
            if seen[sy][sx] or px[sx, sy][3] == 0:
                continue
            stack, comp = [(sx, sy)], []
            seen[sy][sx] = True
            while stack:
                x, y = stack.pop()
                comp.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and px[nx, ny][3]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            comps.append(comp)
    if not comps:
        return im
    biggest = max(len(c) for c in comps)
    for c in comps:
        if len(c) < biggest * 0.03:
            for x, y in c:
                px[x, y] = (0, 0, 0, 0)
    return im


# 1) key whole image, then find sprite bands by alpha projection (robust to uneven grids)


def key_only(im):
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if (r > 170 and b > 170 and g < 110) or (r > 90 and b > 90 and (r - g) > 50 and (b - g) > 50):
                px[x, y] = (0, 0, 0, 0)
    return im


def cuts(counts, n):
    """Split a 1-D alpha-count profile into n bands, placing each cut at the emptiest
    line near the nominal grid boundary (sprites may touch / overlap the grid)."""
    L = len(counts)
    step = L / n
    win = int(step * 0.2)
    pos = [0]
    for k in range(1, n):
        nominal = int(k * step)
        lo, hi = max(pos[-1] + 1, nominal - win), min(L - 1, nominal + win)
        pos.append(min(range(lo, hi + 1), key=lambda i: (counts[i], abs(i - nominal))))
    pos.append(L)
    return list(zip(pos[:-1], pos[1:]))


full = key_only(img.copy())
ap = full.getchannel("A").load()
row_counts = [sum(1 for x in range(W) if ap[x, y]) for y in range(H)]
frames = {}
for r, (y0, y1) in enumerate(cuts(row_counts, ROWS)):
    col_counts = [sum(1 for y in range(y0, y1) if ap[x, y]) for x in range(W)]
    for c, (x0, x1) in enumerate(cuts(col_counts, COLS)):
        f = remove_specks(full.crop((x0, y0, x1, y1)))
        frames[(r, c)] = f.crop(f.getbbox())

# 2) common scale so the tallest sprite fits CELL with 2px margin
max_h = max(f.height for f in frames.values())
max_w = max(f.width for f in frames.values())
scale = min((CELL - 2) / max_h, (CELL - 2) / max_w)


def to_cell(f):
    # per-frame height normalisation: generators often draw some views shorter/taller
    s = min((CELL - 2) / f.height, (CELL - 2) / f.width)
    f = f.resize((max(1, round(f.width * s)), max(1, round(f.height * s))), Image.NEAREST)
    cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    cell.paste(f, ((CELL - f.width) // 2, CELL - 1 - f.height), f)  # bottom-aligned baseline
    return cell


src_cells = {k: to_cell(v) for k, v in frames.items()}

# 3) pick frames for the 5 left-side directions, then mirror them to the right side.
#    Optional 3rd arg: JSON {"down": [[row, col, flip], x4], "down_left": ..., "left": ...,
#    "up_left": ..., "up": ...} to fix rows the generator drew facing the wrong way.
#    Default: source rows 0-4 used as-is.
import json
LEFT_SIDE = ["down", "down_left", "left", "up_left", "up"]
mapping = {d: [[r, c, 0] for c in range(COLS)] for r, d in enumerate(LEFT_SIDE)}
if len(sys.argv) > 3:
    mapping.update(json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")))

cells = {}
for r, d in enumerate(LEFT_SIDE):
    for c, (sr, sc, flip) in enumerate(mapping[d]):
        cell = src_cells[(sr, sc)]
        cells[(r, c)] = cell.transpose(Image.FLIP_LEFT_RIGHT) if flip else cell

mirror = {5: 3, 6: 2, 7: 1}   # up_right<-up_left, right<-left, down_right<-down_left
for dst, src in mirror.items():
    for c in range(COLS):
        cells[(dst, c)] = cells[(src, c)].transpose(Image.FLIP_LEFT_RIGHT)

# 4) export full sheet + per-direction strips + per-frame pngs
OUT.mkdir(parents=True, exist_ok=True)
sheet = Image.new("RGBA", (CELL * COLS, CELL * ROWS), (0, 0, 0, 0))
for (r, c), cell in cells.items():
    sheet.paste(cell, (c * CELL, r * CELL))
sheet.save(OUT / f"{NAME}_walk_8dir.png")
sheet.resize((sheet.width * 4, sheet.height * 4), Image.NEAREST).save(OUT / f"{NAME}_walk_8dir_preview_x4.png")

(OUT / "frames").mkdir(exist_ok=True)
for r, d in enumerate(DIRS):
    strip = Image.new("RGBA", (CELL * COLS, CELL), (0, 0, 0, 0))
    for c in range(COLS):
        strip.paste(cells[(r, c)], (c * CELL, 0))
        cells[(r, c)].save(OUT / "frames" / f"{d}_{c}.png")
    strip.save(OUT / f"walk_{d}.png")

print("done", sheet.size, "scale", round(scale, 3))

