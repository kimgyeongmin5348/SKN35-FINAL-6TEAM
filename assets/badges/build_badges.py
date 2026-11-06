"""Generate pixel-art status bubbles (assets/badges/) & handoff deliverable icons (assets/deliverables/)
for the BUILDWISE AI Digital Office UI.

Usage:
  uv run --no-project --with pillow python assets/badges/build_badges.py
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

BADGE_DIR = Path(__file__).parent
DELIV_DIR = BADGE_DIR.parent / "deliverables"
OL = (26, 28, 38, 255)
S = 32


def speech_bubble(bg=(255, 255, 255), border=(40, 46, 62), bob=0):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y0, y1 = 2 + bob, 23 + bob
    d.rounded_rectangle([3, y0, 28, y1], radius=5, fill=bg, outline=border, width=2)
    # bubble tail at bottom center
    d.polygon([(13, y1), (18, y1), (15, y1 + 4)], fill=bg)
    d.line([13, y1, 15, y1 + 4, 18, y1], fill=border, width=1)
    return im, d, y0


def make_badge_strip(fn):
    strip = Image.new("RGBA", (S * 4, S), (0, 0, 0, 0))
    first = None
    for f in range(4):
        im = fn(f)
        if f == 0:
            first = im
        strip.paste(im, (f * S, 0))
    return first, strip


def b_idle(f):
    im, d, y0 = speech_bubble((248, 250, 252), (100, 116, 139), bob=1 if f in (1, 2) else 0)
    for i, x in enumerate((10, 15, 20)):
        c = (51, 65, 85) if i <= f else (180, 190, 205)
        d.rectangle([x, y0 + 9, x + 2, y0 + 11], fill=c)
    return im


def b_talking(f):
    im, d, y0 = speech_bubble((255, 247, 237), (234, 88, 12), bob=f % 2)
    # mic + sound bars
    d.rounded_rectangle([8, y0 + 5, 13, y0 + 13], radius=2, fill=(234, 88, 12))
    d.line([10, y0 + 14, 10, y0 + 17], fill=(120, 53, 15), width=2)
    heights = [(4, 9, 5), (8, 5, 10), (5, 10, 6), (9, 6, 8)][f]
    for i, h in enumerate(heights):
        bx = 16 + i * 3
        cy = y0 + 11
        d.line([bx, cy - h // 2, bx, cy + h // 2], fill=(249, 115, 22), width=2)
    return im


def b_working(f):
    im, d, y0 = speech_bubble((239, 246, 255), (37, 99, 235), bob=0)
    cx, cy = 15, y0 + 10
    # animated gear teeth + progress dots
    offsets = [(0, -6), (6, 0), (0, 6), (-6, 0)] if f % 2 == 0 else [(-4, -4), (4, -4), (4, 4), (-4, 4)]
    for ox, oy in offsets:
        d.rectangle([cx + ox - 1, cy + oy - 1, cx + ox + 1, cy + oy + 1], fill=(37, 99, 235))
    d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(59, 130, 246), outline=(29, 78, 216))
    d.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=(255, 255, 255))
    return im


def b_analyzing(f):
    im, d, y0 = speech_bubble((240, 253, 250), (13, 148, 136), bob=0)
    ox = [-2, 0, 2, 0][f]
    # mini chart bars + scanning lens
    d.rectangle([8, y0 + 11, 10, y0 + 16], fill=(94, 234, 212))
    d.rectangle([12, y0 + 8, 14, y0 + 16], fill=(45, 212, 191))
    d.rectangle([16, y0 + 6, 18, y0 + 16], fill=(20, 184, 166))
    gx, gy = 16 + ox, y0 + 10
    d.ellipse([gx - 4, gy - 4, gx + 4, gy + 4], fill=(224, 242, 254, 180), outline=(15, 118, 110), width=2)
    d.line([gx + 3, gy + 3, gx + 6, gy + 6], fill=(15, 118, 110), width=2)
    return im


def b_waiting_info(f):
    im, d, y0 = speech_bubble((254, 252, 232), (202, 138, 4), bob=1 if f % 2 else 0)
    # bold '?'
    c = (180, 83, 9)
    d.line([12, y0 + 6, 18, y0 + 6, 18, y0 + 10, 15, y0 + 11, 15, y0 + 13], fill=c, width=2)
    d.rectangle([14, y0 + 15, 16, y0 + 17], fill=c)
    return im


def b_reviewing(f):
    im, d, y0 = speech_bubble((255, 247, 237), (217, 119, 6), bob=0)
    # circular revision arc + edit pen
    a = f * 90
    d.arc([8, y0 + 4, 22, y0 + 18], a, a + 250, fill=(217, 119, 6), width=2)
    d.line([13, y0 + 13, 18, y0 + 8], fill=(220, 38, 38), width=2)
    return im


def b_waiting_approval(f):
    im, d, y0 = speech_bubble((245, 243, 255), (124, 58, 237), bob=1 if f in (1, 2) else 0)
    # clipboard with pulsing gold check seal
    d.rectangle([10, y0 + 4, 21, y0 + 17], fill=(255, 255, 255), outline=(109, 40, 217))
    d.rectangle([13, y0 + 3, 18, y0 + 5], fill=(124, 58, 237))
    d.line([12, y0 + 8, 19, y0 + 8], fill=(148, 163, 184))
    seal = (245, 158, 11) if f % 2 == 0 else (251, 191, 36)
    d.ellipse([13, y0 + 10, 18, y0 + 15], fill=seal)
    return im


def b_pass(f):
    im, d, y0 = speech_bubble((236, 253, 245), (5, 150, 105), bob=1 if f == 1 else 0)
    d.ellipse([9, y0 + 4, 22, y0 + 17], fill=(16, 185, 129))
    d.line([12, y0 + 10, 15, y0 + 13, 19, y0 + 8], fill=(255, 255, 255), width=2)
    return im


def b_warning(f):
    bg = (254, 249, 195) if f % 2 == 0 else (254, 240, 138)
    im, d, y0 = speech_bubble(bg, (202, 138, 4), bob=0)
    d.polygon([(15, y0 + 4), (8, y0 + 17), (22, y0 + 17)], fill=(245, 158, 11), outline=(146, 64, 14))
    d.line([15, y0 + 8, 15, y0 + 12], fill=(255, 255, 255), width=2)
    d.point((15, y0 + 15), fill=(255, 255, 255))
    return im


def b_fail(f):
    ox = [-1, 1, 0, 0][f]
    im, d, y0 = speech_bubble((254, 226, 226), (220, 38, 38), bob=0)
    d.ellipse([9 + ox, y0 + 4, 22 + ox, y0 + 17], fill=(239, 68, 68))
    d.line([12 + ox, y0 + 7, 19 + ox, y0 + 14], fill=(255, 255, 255), width=2)
    d.line([19 + ox, y0 + 7, 12 + ox, y0 + 14], fill=(255, 255, 255), width=2)
    return im


def b_retrying(f):
    im, d, y0 = speech_bubble((255, 251, 235), (217, 119, 6), bob=0)
    a = f * 90
    d.arc([9, y0 + 4, 22, y0 + 17], a, a + 270, fill=(245, 158, 11), width=2)
    return im


def b_email_sent(f):
    im, d, y0 = speech_bubble((238, 242, 255), (79, 70, 229), bob=-1 if f in (1, 2) else 0)
    d.rectangle([8, y0 + 6, 23, y0 + 16], fill=(255, 255, 255), outline=(79, 70, 229))
    d.line([8, y0 + 6, 15, y0 + 12, 23, y0 + 6], fill=(79, 70, 229))
    return im


BADGES = {
    "idle": b_idle,
    "talking": b_talking,
    "working": b_working,
    "analyzing": b_analyzing,
    "waiting_info": b_waiting_info,
    "reviewing": b_reviewing,
    "waiting_approval": b_waiting_approval,
    "pass": b_pass,
    "warning": b_warning,
    "fail": b_fail,
    "retrying": b_retrying,
    "email_sent": b_email_sent,
}


def make_deliverable(bg, header_c, mark="lines"):
    im = Image.new("RGBA", (28, 28), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 2, 23, 25], radius=2, fill=bg, outline=OL)
    d.rectangle([5, 3, 22, 7], fill=header_c)
    if mark == "lines":
        for y in (11, 15, 19):
            d.line([8, y, 19, y], fill=(90, 100, 120))
    elif mark == "gpu":
        d.rectangle([8, 10, 19, 18], fill=(30, 64, 175), outline=OL)
        d.ellipse([11, 12, 16, 16], fill=(56, 189, 248))
        d.line([8, 21, 19, 21], fill=(71, 85, 105))
    elif mark == "pass":
        d.line([9, 15, 13, 19, 19, 11], fill=(16, 185, 129), width=2)
    elif mark == "warn":
        d.polygon([(13, 10), (8, 20), (19, 20)], fill=(245, 158, 11), outline=(146, 64, 14))
    elif mark == "fail":
        d.line([9, 11, 18, 20], fill=(220, 38, 38), width=2)
        d.line([18, 11, 9, 20], fill=(220, 38, 38), width=2)
    elif mark == "quote":
        d.rectangle([8, 10, 19, 21], outline=(109, 40, 217))
        d.line([13, 10, 13, 21], fill=(109, 40, 217))
        d.line([8, 15, 19, 15], fill=(109, 40, 217))
    elif mark == "mail":
        im = Image.new("RGBA", (28, 28), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([3, 6, 24, 21], radius=2, fill=(255, 255, 255), outline=OL)
        d.line([4, 7, 13, 15, 23, 7], fill=(79, 70, 229), width=2)
    return im


DELIVERABLES = {
    "doc_requirements": ((255, 251, 235), (249, 115, 22), "lines"),
    "doc_feedback":     ((254, 242, 242), (236, 72, 153), "lines"),
    "doc_solution":     ((239, 246, 255), (14, 165, 233), "gpu"),
    "doc_validation_pass": ((236, 253, 245), (16, 185, 129), "pass"),
    "doc_validation_warn": ((254, 252, 232), (245, 158, 11), "warn"),
    "doc_validation_fail": ((254, 242, 242), (239, 68, 68), "fail"),
    "doc_quotation":    ((245, 243, 255), (139, 92, 246), "quote"),
    "doc_email":        ((238, 242, 255), (79, 70, 229), "mail"),
}


if __name__ == "__main__":
    BADGE_DIR.mkdir(parents=True, exist_ok=True)
    DELIV_DIR.mkdir(parents=True, exist_ok=True)

    sheet = Image.new("RGBA", (S * 4, S * len(BADGES)), (0, 0, 0, 0))
    for i, (name, fn) in enumerate(BADGES.items()):
        first, strip = make_badge_strip(fn)
        first.save(BADGE_DIR / f"badge_{name}.png")
        strip.save(BADGE_DIR / f"badge_{name}_strip.png")
        sheet.paste(strip, (0, i * S))
    sheet.save(BADGE_DIR / "badges_sheet.png")

    dsheet = Image.new("RGBA", (28 * len(DELIVERABLES), 28), (0, 0, 0, 0))
    for i, (name, args) in enumerate(DELIVERABLES.items()):
        im = make_deliverable(*args)
        im.save(DELIV_DIR / f"{name}.png")
        dsheet.paste(im, (i * 28, 0))
    dsheet.save(DELIV_DIR / "deliverables_sheet.png")

    (BADGE_DIR / "badges.json").write_text(json.dumps({
        "cellSize": [S, S], "frames": 4, "rows": list(BADGES.keys()),
        "deliverables": list(DELIVERABLES.keys()),
    }, indent=2), encoding="utf-8")
    print("badges:", len(BADGES), "deliverables:", len(DELIVERABLES))
