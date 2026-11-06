"""Generate BUILDWISE AI Agent work/status sprite sheets + handoff carry sheets.

For each of the 4 BUILDWISE teams:
  - consultation (상담팀, base: office_lady + headset)
  - solution     (설계팀, base: developer)
  - validation   (검증팀, base: team_manager)
  - quotation    (견적팀, base: office_worker)

Outputs per agent in assets/characters/<agent>/:
  - <agent>_walk_8dir.png        (256x512, 8 dirs x 4 frames)
  - <agent>_work_states.png      (256x640, 10 states x 4 frames, 64x64)
  - <agent>_carry_4dir.png       (256x256, 4 dirs x 4 frames, carrying handoff doc)
  - states/state_<name>.png      (256x64 strip per state)
  - metadata.json
Also writes assets/characters/all_work_states_preview.png for visual inspection.

Usage:
  uv run --no-project --with pillow python assets/characters/build_work_sheets.py
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
CELL = 64
OL = (28, 24, 34, 255)

STATES = [
    "idle",              # 0 대기
    "working",           # 1 작업 중 (타이핑/설계/검증/견적작성)
    "talking",           # 2 실시간 상담 / 결과 설명
    "analyzing",         # 3 사양·자원 조사 및 분석
    "waiting_info",      # 4 추가 정보 대기
    "reviewing",         # 5 피드백 반영 재검토 / 재설계 / 재검증
    "waiting_approval",  # 6 사용자 승인 대기
    "failed",            # 7 실패 / 호환성 FAIL / 반려
    "retrying",          # 8 재시도 중
    "completed",         # 9 완료 / PASS / 발송 완료
]

AGENTS = {
    "consultation": {
        "base": "office_lady",
        "ko": "상담팀 (Consultation Agent)",
        "sleeve": (203, 171, 133), "sleeve_d": (162, 132, 98),
        "torso": (203, 171, 133), "shirt": (236, 142, 158),
        "pants": (36, 36, 42), "shoe": (32, 30, 36),
        "skin": (250, 214, 190), "head_cut": 35,
        "eyes": [(24, 23, 4, 2), (35, 23, 4, 2)], "mouth": (31, 28),
        "headset": True, "accent": (244, 114, 94), "doc_color": (255, 236, 179),
    },
    "solution": {
        "base": "developer",
        "ko": "설계팀 (Solution Agent)",
        "sleeve": (233, 162, 44), "sleeve_d": (186, 120, 24),
        "torso": (233, 162, 44), "shirt": (245, 245, 248),
        "pants": (62, 96, 146), "shoe": (240, 242, 248),
        "skin": (248, 208, 182), "head_cut": 36,
        "eyes": [(24, 24, 3, 2), (36, 24, 3, 2)], "mouth": (31, 29),
        "headset": False, "accent": (56, 189, 248), "doc_color": (190, 230, 255),
    },
    "validation": {
        "base": "team_manager",
        "ko": "검증팀 (Validation Agent)",
        "sleeve": (188, 216, 242), "sleeve_d": (144, 176, 208),
        "torso": (89, 92, 98), "shirt": (234, 34, 47),
        "pants": (52, 56, 66), "shoe": (28, 30, 36),
        "skin": (250, 206, 172), "head_cut": 35,
        "eyes": [(24, 26, 3, 2), (37, 26, 3, 2)], "mouth": (31, 31),
        "headset": False, "accent": (52, 211, 153), "doc_color": (210, 250, 224),
    },
    "quotation": {
        "base": "office_worker",
        "ko": "견적팀 (Quotation Agent)",
        "sleeve": (42, 55, 104), "sleeve_d": (26, 37, 82),
        "torso": (42, 55, 104), "shirt": (226, 232, 244),
        "pants": (70, 74, 84), "shoe": (92, 56, 38),
        "skin": (250, 210, 184), "head_cut": 35,
        "eyes": [(23, 24, 4, 2), (37, 24, 4, 2)], "mouth": (31, 29),
        "headset": False, "accent": (167, 139, 250), "doc_color": (233, 220, 255),
    },
}


def R(d, x0, y0, x1, y1, fill, ol=True):
    d.rectangle([x0, y0, x1, y1], fill=fill, outline=OL if ol else None)


def add_headset(im, facing="down"):
    """Draw a cute pixel headset + mic boom for the Consultation Agent."""
    d = ImageDraw.Draw(im)
    band = (56, 62, 78, 255)
    pad = (244, 114, 94, 255)
    if facing in ("down", "down_left", "down_right"):
        d.arc([16, 4, 47, 26], 195, 345, fill=band, width=2)
        R(d, 14, 19, 18, 26, pad)
        R(d, 45, 19, 49, 26, pad)
        d.line([17, 25, 25, 29], fill=band, width=2)
        R(d, 24, 28, 27, 30, pad, ol=False)
    elif facing == "up":
        d.arc([16, 4, 47, 26], 195, 345, fill=band, width=2)
        R(d, 14, 19, 18, 26, pad)
        R(d, 45, 19, 49, 26, pad)
    elif facing in ("left", "up_left"):
        d.arc([20, 4, 44, 26], 230, 320, fill=band, width=2)
        R(d, 27, 19, 33, 26, pad)
        d.line([27, 24, 20, 28], fill=band, width=2)
    else:
        d.arc([20, 4, 44, 26], 220, 310, fill=band, width=2)
        R(d, 31, 19, 37, 26, pad)
        d.line([37, 24, 44, 28], fill=band, width=2)
    return im


def extract_head(base_dir: Path, cut_y: int, add_hs: bool, keep_long_hair: bool = False):
    """Extract upper head+hair from down_0.png (0..cut_y), preserving long hair sides."""
    src = Image.open(base_dir / "frames" / "down_0.png").convert("RGBA")
    head = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    head.paste(src.crop((0, 0, CELL, cut_y)), (0, 0))
    if keep_long_hair:
        px_s = src.load()
        px_h = head.load()
        for y in range(cut_y, 41):
            for x in range(CELL):
                if (x < 21 or x > 42) and px_s[x, y][3] > 128:
                    px_h[x, y] = px_s[x, y]
    if add_hs:
        add_headset(head, "down")
    return head, src


def draw_chair_and_seated_body(im, cfg, body_dy=0):
    """Draw swivel chair back + seated torso + bent legs so the character is clearly seated/working."""
    d = ImageDraw.Draw(im)
    # Chair backrest peeking neatly behind shoulders
    R(d, 20, 30 + body_dy, 43, 47 + body_dy, (50, 54, 66))
    d.line([22, 31 + body_dy, 41, 31 + body_dy], fill=(78, 84, 100))
    # Chair base & wheels
    R(d, 30, 54, 33, 59, (90, 96, 110))
    R(d, 21, 58, 42, 60, (52, 56, 68))
    for wx in (22, 31, 40):
        R(d, wx, 60, wx + 2, 62, OL[:3], ol=False)

    # Seated legs (knees forward)
    R(d, 23, 47 + body_dy, 31, 56, cfg["pants"])
    R(d, 32, 47 + body_dy, 40, 56, cfg["pants"])
    R(d, 23, 55, 30, 59, cfg["shoe"])
    R(d, 33, 55, 40, 59, cfg["shoe"])

    # Seated torso (jacket/hoodie/vest + inner shirt/tie)
    ty = 34 + body_dy
    R(d, 21, ty, 42, ty + 14, cfg["torso"])
    R(d, 29, ty, 34, ty + 12, cfg["shirt"], ol=False)
    if cfg["base"] == "team_manager":  # red tie
        R(d, 31, ty + 1, 32, ty + 11, (234, 34, 47), ol=False)
        R(d, 29, ty, 34, ty + 2, (236, 242, 250), ol=False)
    elif cfg["base"] in ("office_worker", "office_lady"):  # ID lanyard
        d.line([29, ty + 1, 31, ty + 7], fill=(70, 80, 105))
        d.line([34, ty + 1, 32, ty + 7], fill=(70, 80, 105))
        R(d, 30, ty + 7, 33, ty + 11, (235, 242, 252), ol=False)


def draw_arm(d, x0, y0, x1, y1, sleeve, skin):
    """Draw a pixel arm segment + hand."""
    d.line([x0, y0, x1, y1], fill=OL, width=6)
    d.line([x0, y0, x1, y1], fill=sleeve, width=4)
    R(d, x1 - 2, y1 - 2, x1 + 2, y1 + 2, skin)


def patch_expression(head_im, cfg, expr, frame):
    """Apply subtle facial animation (blink, happy, talk, sweat, focus) on a copy of head."""
    h = head_im.copy()
    d = ImageDraw.Draw(h)
    mx, my = cfg["mouth"]
    if expr == "blink":
        for ex, ey, ew, eh in cfg["eyes"]:
            d.rectangle([ex, ey, ex + ew, ey + eh], fill=cfg["skin"])
            d.line([ex, ey + 1, ex + ew, ey + 1], fill=OL)
    elif expr == "talk" and frame % 2 == 1:
        R(d, mx - 1, my - 1, mx + 2, my + 2, (190, 72, 82))
    elif expr == "happy":
        for ex, ey, ew, eh in cfg["eyes"]:
            d.rectangle([ex, ey, ex + ew, ey + eh], fill=cfg["skin"])
            d.line([ex, ey + 1, ex + 1, ey], fill=OL)
            d.line([ex + 1, ey, ex + ew - 1, ey], fill=OL)
            d.line([ex + ew - 1, ey, ex + ew, ey + 1], fill=OL)
        R(d, mx - 1, my, mx + 2, my + 1, (205, 84, 92), ol=False)
    elif expr == "panic":
        # sweat drop on temple (bobs down with frame)
        sy = 14 + (frame % 2) * 2
        R(d, 46, sy, 49, sy + 5, (110, 200, 255))
        d.point((47, sy + 1), fill=(230, 250, 255))
        R(d, mx - 1, my, mx + 2, my + 2, (60, 40, 48), ol=False)
    elif expr == "focus":
        # determined brow line + tiny glint
        for ex, ey, ew, _ in cfg["eyes"]:
            d.line([ex, ey - 2, ex + ew, ey - 1], fill=OL)
    return h


def render_state_frame(head_im, cfg, role, state, f):
    """Render one 64x64 frame for (agent, state, frame 0..3)."""
    im = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    sl, sk, acc, doc = cfg["sleeve"], cfg["skin"], cfg["accent"], cfg["doc_color"]

    body_dy = 0
    head_dx, head_dy = 0, 0
    expr = "normal"

    if state == "idle":
        body_dy = 1 if f in (1, 2) else 0
        head_dy = body_dy
        expr = "blink" if f == 3 else "normal"
        draw_chair_and_seated_body(im, cfg, body_dy)
        im.alpha_composite(patch_expression(head_im, cfg, expr, f), (head_dx, head_dy))
        draw_arm(d, 21, 38 + body_dy, 24, 46 + body_dy, sl, sk)
        draw_arm(d, 42, 38 + body_dy, 39, 46 + body_dy, sl, sk)

    elif state == "working":
        # Mini holographic/work pad + keyboard in front, rapid alternating typing hands + pixel sparks!
        head_dy = 1 if f % 2 else 0
        expr = "focus" if f == 2 else "normal"
        draw_chair_and_seated_body(im, cfg, 0)
        im.alpha_composite(patch_expression(head_im, cfg, expr, f), (0, head_dy))
        # Work surface / keyboard strip
        R(d, 15, 48, 48, 54, (214, 220, 232))
        for kx in range(18, 46, 4):
            d.point((kx, 50), fill=(110, 118, 136))
            d.point((kx + 1, 52), fill=(110, 118, 136))
        ly = 45 if f % 2 == 0 else 48
        ry = 48 if f % 2 == 0 else 45
        draw_arm(d, 21, 38, 25, ly, sl, sk)
        draw_arm(d, 42, 38, 38, ry, sl, sk)
        # Floating activity pixels (code / spec / calc tokens)
        sx = 14 + (f * 9) % 32
        R(d, sx, 40 - (f % 2) * 2, sx + 5, 43 - (f % 2) * 2, acc, ol=False)
        d.point((49, 42 - (f % 3)), fill=acc)

    elif state == "talking":
        # Live consultation / briefing: mouth animates, hand gestures, soundwave arcs
        head_dy = 1 if f in (1, 3) else 0
        draw_chair_and_seated_body(im, cfg, 0)
        im.alpha_composite(patch_expression(head_im, cfg, "talk", f), (0, head_dy))
        # Left hand touches headset/chest, right hand gestures outward
        draw_arm(d, 21, 38, 18, 30 if cfg["headset"] else 43, sl, sk)
        gy = 38 if f % 2 == 0 else 42
        draw_arm(d, 42, 38, 49, gy, sl, sk)
        # Soundwave arcs on right
        for w_i in range((f % 3) + 1):
            x0 = 51 + w_i * 3
            d.line([x0, 22 - w_i, x0 + 1, 25, x0, 28 + w_i], fill=acc)

    elif state == "analyzing":
        # Holding spec / blueprint / comparison sheet + magnifying glass scanning across!
        scan_x = [-2, 0, 2, 0][f]
        draw_chair_and_seated_body(im, cfg, 0)
        im.alpha_composite(patch_expression(head_im, cfg, "focus", f), (scan_x // 2, 1))
        # Document held on left
        R(d, 12, 37, 27, 51, doc)
        d.line([15, 41, 24, 41], fill=(70, 80, 100))
        d.line([15, 44, 23, 44], fill=acc)
        d.line([15, 47, 22, 47], fill=(70, 80, 100))
        draw_arm(d, 21, 39, 16, 45, sl, sk)
        # Magnifying glass scanning over document
        gx, gy = 26 + scan_x * 2, 39 + (f % 2)
        d.line([gx + 5, gy + 5, gx + 10, gy + 10], fill=OL, width=3)
        d.ellipse([gx - 5, gy - 5, gx + 6, gy + 6], fill=(190, 240, 255, 190), outline=OL)
        draw_arm(d, 42, 39, gx + 8, gy + 8, sl, sk)

    elif state == "waiting_info":
        # Head shifts slightly, holding notepad + blinking '?' bubble
        hx = -1 if f in (1, 2) else 0
        draw_chair_and_seated_body(im, cfg, 0)
        im.alpha_composite(patch_expression(head_im, cfg, "blink" if f == 3 else "normal", f), (hx, 0))
        R(d, 15, 40, 26, 51, (255, 250, 210))
        d.line([17, 44, 23, 44], fill=(120, 120, 130))
        draw_arm(d, 21, 39, 19, 46, sl, sk)
        draw_arm(d, 42, 39, 45, 33, sl, sk)  # hand near chin thinking
        # '?' pixel mark on upper-right
        qy = 8 + (f % 2) * 2
        R(d, 48, qy, 58, qy + 12, (255, 255, 255))
        d.line([51, qy + 3, 55, qy + 3, 55, qy + 6, 53, qy + 6, 53, qy + 8], fill=(234, 138, 0))
        d.point((53, qy + 10), fill=(234, 138, 0))

    elif state == "reviewing":
        # Feedback / validation revision: red/amber pen + marked-up revision sheet + nod
        ny = 1 if f % 2 else 0
        draw_chair_and_seated_body(im, cfg, 0)
        im.alpha_composite(patch_expression(head_im, cfg, "focus", f), (0, ny))
        R(d, 18, 39, 36, 52, (255, 252, 240))
        d.line([21, 43, 33, 43], fill=(90, 96, 110))
        d.line([21, 46, 31, 46], fill=(220, 60, 60))
        d.line([21, 49, 33, 49], fill=(56, 140, 220))
        draw_arm(d, 21, 39, 20, 46, sl, sk)
        px_pen = 31 + (f % 2) * 3
        draw_arm(d, 42, 39, px_pen + 5, 44, sl, sk)
        d.line([px_pen, 47, px_pen + 6, 41], fill=(230, 56, 56), width=2)

    elif state == "waiting_approval":
        # Presenting approval clipboard / quotation nicely with both hands, gentle bob
        by = 1 if f in (1, 2) else 0
        draw_chair_and_seated_body(im, cfg, by)
        im.alpha_composite(patch_expression(head_im, cfg, "blink" if f == 3 else "normal", f), (0, by))
        R(d, 22, 36 + by, 41, 53 + by, (196, 142, 84))   # wooden clipboard
        R(d, 24, 39 + by, 39, 51 + by, (255, 255, 255), ol=False)
        R(d, 28, 35 + by, 35, 38 + by, (110, 116, 128))  # clip
        d.line([26, 42 + by, 37, 42 + by], fill=(80, 90, 110))
        d.line([26, 45 + by, 35, 45 + by], fill=(80, 90, 110))
        R(d, 33, 47 + by, 37, 50 + by, (245, 158, 11), ol=False)  # gold seal
        draw_arm(d, 21, 39 + by, 23, 46 + by, sl, sk)
        draw_arm(d, 42, 39 + by, 40, 46 + by, sl, sk)

    elif state == "failed":
        # Shake + sweat drop + hands up in alarm + red FAIL report in front
        sx = [-1, 1, -1, 1][f]
        draw_chair_and_seated_body(im, cfg, 0)
        im.alpha_composite(patch_expression(head_im, cfg, "panic", f), (sx, 0))
        draw_arm(d, 21, 38, 15, 29 + (f % 2), sl, sk)
        draw_arm(d, 42, 38, 48, 29 + ((f + 1) % 2), sl, sk)
        R(d, 22, 46, 41, 55, (255, 228, 230))
        d.line([26, 48, 32, 53], fill=(220, 38, 38), width=2)
        d.line([32, 48, 26, 53], fill=(220, 38, 38), width=2)

    elif state == "retrying":
        # Focused fast double-time typing + amber circular retry indicator
        draw_chair_and_seated_body(im, cfg, 0)
        im.alpha_composite(patch_expression(head_im, cfg, "focus", f), (0, f % 2))
        R(d, 15, 48, 48, 54, (214, 220, 232))
        ly = 44 if f % 2 == 0 else 48
        ry = 48 if f % 2 == 0 else 44
        draw_arm(d, 21, 38, 24, ly, sl, sk)
        draw_arm(d, 42, 38, 39, ry, sl, sk)
        # Spinning retry arc at top-right
        a0 = f * 90
        d.arc([47, 7, 59, 19], a0, a0 + 240, fill=(245, 158, 11), width=2)

    elif state == "completed":
        # Happy ^_^ smile + raised arm holding team deliverable / green check!
        by = -1 if f in (1, 2) else 0
        draw_chair_and_seated_body(im, cfg, 0)
        im.alpha_composite(patch_expression(head_im, cfg, "happy", f), (0, by))
        draw_arm(d, 21, 38, 16, 30 + by, sl, sk)
        draw_arm(d, 42, 38, 47, 28 + by, sl, sk)
        # Held deliverable / green check badge on raised right hand
        R(d, 43, 14 + by, 57, 26 + by, (236, 253, 245))
        d.line([46, 20 + by, 49, 23 + by, 54, 17 + by], fill=(16, 185, 129), width=2)

    return im


def build_carry_sheet(base_dir: Path, cfg):
    """4 directions (down, left, right, up) x 4 frames carrying a handoff document."""
    dirs = ["down", "left", "right", "up"]
    sheet = Image.new("RGBA", (CELL * 4, CELL * 4), (0, 0, 0, 0))
    strips = {}
    for r, dname in enumerate(dirs):
        strip = Image.new("RGBA", (CELL * 4, CELL), (0, 0, 0, 0))
        for c in range(4):
            fr = Image.open(base_dir / "frames" / f"{dname}_{c}.png").convert("RGBA")
            if cfg["headset"]:
                add_headset(fr, dname)
            d = ImageDraw.Draw(fr)
            bob = -1 if c in (1, 3) else 0
            if dname == "down":
                R(d, 22, 39 + bob, 41, 50 + bob, cfg["doc_color"])
                d.line([25, 43 + bob, 38, 43 + bob], fill=cfg["accent"], width=2)
                d.line([25, 46 + bob, 35, 46 + bob], fill=(90, 96, 110))
                R(d, 20, 43 + bob, 23, 47 + bob, cfg["skin"])
                R(d, 40, 43 + bob, 43, 47 + bob, cfg["skin"])
            elif dname == "left":
                R(d, 11, 38 + bob, 25, 49 + bob, cfg["doc_color"])
                d.line([14, 42 + bob, 22, 42 + bob], fill=cfg["accent"], width=2)
                R(d, 21, 42 + bob, 25, 46 + bob, cfg["skin"])
            elif dname == "right":
                R(d, 38, 38 + bob, 52, 49 + bob, cfg["doc_color"])
                d.line([41, 42 + bob, 49, 42 + bob], fill=cfg["accent"], width=2)
                R(d, 38, 42 + bob, 42, 46 + bob, cfg["skin"])
            elif dname == "up":
                # Corners of carried folder peeking out on left/right of torso
                R(d, 17, 38 + bob, 22, 46 + bob, cfg["doc_color"])
                R(d, 41, 38 + bob, 46, 46 + bob, cfg["doc_color"])
            strip.paste(fr, (c * CELL, 0))
            sheet.paste(fr, (c * CELL, r * CELL))
        strips[dname] = strip
    return sheet, strips


def build_walk_sheet(base_dir: Path, cfg):
    """Copy base 8-dir walk sheet, adding headset if needed."""
    dirs8 = ["down", "down_left", "left", "up_left", "up", "up_right", "right", "down_right"]
    sheet = Image.new("RGBA", (CELL * 4, CELL * 8), (0, 0, 0, 0))
    for r, dname in enumerate(dirs8):
        for c in range(4):
            fr = Image.open(base_dir / "frames" / f"{dname}_{c}.png").convert("RGBA")
            if cfg["headset"]:
                add_headset(fr, dname)
            sheet.paste(fr, (c * CELL, r * CELL))
    return sheet


def main():
    preview_cols = []
    for role, cfg in AGENTS.items():
        base_dir = ROOT / cfg["base"]
        out_dir = ROOT / role
        (out_dir / "states").mkdir(parents=True, exist_ok=True)

        head_im, _ = extract_head(base_dir, cfg["head_cut"], cfg["headset"], cfg["base"] == "office_lady")

        # 1) 10-row work/state sheet
        wsheet = Image.new("RGBA", (CELL * 4, CELL * len(STATES)), (0, 0, 0, 0))
        for r, sname in enumerate(STATES):
            strip = Image.new("RGBA", (CELL * 4, CELL), (0, 0, 0, 0))
            for c in range(4):
                fr = render_state_frame(head_im, cfg, role, sname, c)
                strip.paste(fr, (c * CELL, 0))
                wsheet.paste(fr, (c * CELL, r * CELL))
            strip.save(out_dir / "states" / f"state_{sname}.png")
        wsheet.save(out_dir / f"{role}_work_states.png")
        preview_cols.append(wsheet)

        # 2) 4-dir handoff carry sheet
        csheet, cstrips = build_carry_sheet(base_dir, cfg)
        csheet.save(out_dir / f"{role}_carry_4dir.png")
        for dname, st in cstrips.items():
            st.save(out_dir / "states" / f"carry_{dname}.png")

        # 3) 8-dir walk sheet
        walk = build_walk_sheet(base_dir, cfg)
        walk.save(out_dir / f"{role}_walk_8dir.png")

        meta = {
            "agent": role,
            "label": cfg["ko"],
            "baseCharacter": cfg["base"],
            "cellSize": [CELL, CELL],
            "workStates": {
                "file": f"{role}_work_states.png",
                "rows": STATES,
                "framesPerRow": 4,
            },
            "carryStates": {
                "file": f"{role}_carry_4dir.png",
                "rows": ["down", "left", "right", "up"],
                "framesPerRow": 4,
            },
            "walk8Dir": {
                "file": f"{role}_walk_8dir.png",
                "rows": ["down", "down_left", "left", "up_left", "up", "up_right", "right", "down_right"],
                "framesPerRow": 4,
            },
        }
        (out_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print("built agent:", role)

    # Combined preview of all 4 agents x 10 work states (x2)
    gap = 12
    pw = len(preview_cols) * (CELL * 4) + (len(preview_cols) - 1) * gap
    ph = CELL * len(STATES)
    prev = Image.new("RGBA", (pw, ph), (226, 230, 238, 255))
    for i, ws in enumerate(preview_cols):
        prev.alpha_composite(ws, (i * (CELL * 4 + gap), 0))
    prev.resize((pw * 2, ph * 2), Image.NEAREST).save(ROOT / "all_work_states_preview.png")


if __name__ == "__main__":
    main()
