"""Compose the BUILDWISE AI Digital Office map (4 Agent Team Zones + Central Orchestrator Hub).

Usage:
  uv run --no-project --with pillow python assets/map/build_map.py

Outputs (assets/map/):
  office_floor.png       static floor + walls + wall-mounted boards
  office_map.json        full zone/object/agent/waypoint spec for the UI
  office_map.js          same data exposed on window.OFFICE_MAP
  office_preview_x1.png  1x static preview showing agents working in each zone
  office_preview.png     2x crisp preview
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]   # assets/
OUT = Path(__file__).parent
T = 32
COLS, ROWS = 30, 20
W, H = COLS * T, ROWS * T                    # 960 x 640

# ------------------------------------------------------------------ 1) tile grid
grid = [["wood_floor"] * COLS for _ in range(ROWS)]

# Outer walls + top wall face
for x in range(COLS):
    grid[0][x] = "wall_top"
    grid[1][x] = grid[2][x] = "wall_face"
    grid[ROWS - 1][x] = "wall_top"
for y in range(ROWS):
    grid[y][0] = grid[y][COLS - 1] = "wall_top"

# Entrance opening at bottom center
grid[ROWS - 1][14] = grid[ROWS - 1][15] = "wood_floor"

# Team Zone 1: Consultation (top-left, cols 2..11, rows 3..8)
for y in range(3, 9):
    for x in range(2, 12):
        grid[y][x] = "zone_consult"

# Team Zone 2: Solution (top-right, cols 18..27, rows 3..8)
for y in range(3, 9):
    for x in range(18, 28):
        grid[y][x] = "zone_solution"

# Team Zone 3: Validation (bottom-left, cols 2..11, rows 12..18)
for y in range(12, 18):
    for x in range(2, 12):
        grid[y][x] = "zone_validation"

# Team Zone 4: Quotation (bottom-right, cols 18..27, rows 12..18)
for y in range(12, 18):
    for x in range(18, 28):
        grid[y][x] = "zone_quotation"

# Central Orchestrator Hub (cols 13..16, rows 8..12)
for y in range(8, 12):
    for x in range(13, 17):
        grid[y][x] = "hub_tile"

# Handoff Lanes connecting the 4 team zones through the central hub
for x in range(12, 18):
    grid[6][x] = "lane_h"
    grid[14][x] = "lane_h"
for y in range(6, 15):
    if grid[y][14] == "wood_floor":
        grid[y][14] = "lane_v"
    if grid[y][15] == "wood_floor":
        grid[y][15] = "lane_v"

# Small pantry corner in top-center-right alcove (cols 13..16, rows 3..5)
for y in range(3, 5):
    for x in range(13, 17):
        grid[y][x] = "white_tile"

# ------------------------------------------------------------------ 2) objects
OBJS = [
    # --- Top wall windows & boards
    ("window_city", 48, 36),
    ("board_requirements", 132, 40),
    ("bulletin_board", 244, 44),
    ("wall_clock", 360, 46),
    ("tv", 436, 38),
    ("board_architecture", 604, 40),
    ("window_city", 720, 36),
    ("window_city", 800, 36),

    # --- Pantry / break alcove (top center)
    ("coffee_machine", 420, 56),
    ("water_cooler", 514, 54),
    ("plant_small", 386, 86),

    # --- Zone 1: 상담팀 (Consultation Zone, top-left)
    ("plant_big", 64, 72),
    ("desk_consultation", 148, 148),
    ("sofa_down", 68, 224),
    ("coffee_table_glass", 200, 236),
    ("glass_partition_h", 64, 274),
    ("glass_partition_h", 268, 274),
    ("glass_partition_v", 368, 108),

    # --- Zone 2: 설계팀 (Solution & Architecture Zone, top-right)
    ("server_rack_gpu", 796, 68),
    ("server_rack_gpu", 844, 68),
    ("desk_solution", 628, 148),
    ("hw_bench", 784, 198),
    ("plant_big", 578, 76),
    ("glass_partition_v", 576, 108),
    ("glass_partition_h", 588, 274),
    ("glass_partition_h", 792, 274),

    # --- Central Orchestrator Hub
    ("orchestrator_hub", 412, 276),

    # --- Zone 3: 검증팀 (Validation & QA Lab Zone, bottom-left)
    ("glass_partition_h", 64, 338),
    ("glass_partition_h", 268, 338),
    ("glass_partition_v", 368, 410),
    ("bookshelf", 68, 386),
    ("board_compat", 178, 390),
    ("desk_validation", 148, 474),
    ("filing_cabinet", 304, 462),
    ("plant_big", 68, 520),

    # --- Zone 4: 견적팀 (Quotation & Delivery Zone, bottom-right)
    ("glass_partition_h", 588, 338),
    ("glass_partition_h", 792, 338),
    ("glass_partition_v", 576, 410),
    ("board_pricing", 616, 390),
    ("filing_cabinet", 740, 390),
    ("filing_cabinet", 776, 390),
    ("desk_quotation", 628, 474),
    ("printer", 828, 416),
    ("mail_station", 820, 504),
    ("plant_big", 884, 520),

    # --- Entrance (bottom center)
    ("coat_rack", 408, 536),
    ("fire_extinguisher", 534, 566),
    ("glass_door", 448, 576),
]

# Dynamic Validation Tower spot (rendered according to current validation state: idle/pass/warn/fail)
VALIDATION_TOWER = {"x": 296, "y": 388}

# 4 BUILDWISE Agent Seats & Handoff Pickup/Dropoff Waypoints
AGENTS = [
    {
        "id": "consultation",
        "team": "상담팀",
        "role": "Consultation Agent",
        "desc": "실시간 상담 · 요구사항 추출 · 피드백 구조화",
        "color": "#f97316",
        "seatX": 184, "seatY": 110, "sortY": 190,
        "handoffX": 352, "handoffY": 168,
        "zoneRect": [64, 96, 320, 192],
        "defaultState": "talking",
        "defaultBadge": "talking",
    },
    {
        "id": "solution",
        "team": "설계팀",
        "role": "Solution Agent",
        "desc": "자원 분석 · 유지/업그레이드/신규/클라우드 설계",
        "color": "#0ea5e9",
        "seatX": 664, "seatY": 110, "sortY": 190,
        "handoffX": 544, "handoffY": 168,
        "zoneRect": [576, 96, 320, 192],
        "defaultState": "working",
        "defaultBadge": "working",
    },
    {
        "id": "validation",
        "team": "검증팀",
        "role": "Validation Agent",
        "desc": "공식 사양 확인 · 호환성 규칙 검사 (PASS/WARN/FAIL)",
        "color": "#10b981",
        "seatX": 184, "seatY": 436, "sortY": 516,
        "handoffX": 352, "handoffY": 440,
        "zoneRect": [64, 384, 320, 192],
        "defaultState": "analyzing",
        "defaultBadge": "analyzing",
    },
    {
        "id": "quotation",
        "team": "견적팀",
        "role": "Quotation Agent",
        "desc": "비교표·견적서 생성 · 승인 후 이메일 발송",
        "color": "#8b5cf6",
        "seatX": 664, "seatY": 436, "sortY": 516,
        "handoffX": 544, "handoffY": 440,
        "zoneRect": [576, 384, 320, 192],
        "defaultState": "idle",
        "defaultBadge": "idle",
    },
]

HUB_POINT = {"x": 448, "y": 286}

# ------------------------------------------------------------------ 3) build floor & metadata
meta = json.loads((ROOT / "objects" / "objects.json").read_text(encoding="utf-8"))
tiles = {}


def get_tile(name):
    if name not in tiles:
        tiles[name] = Image.open(ROOT / "tiles" / f"{name}.png").convert("RGBA")
    return tiles[name]


def get_obj(name):
    return Image.open(ROOT / "objects" / f"{name}.png").convert("RGBA")


floor = Image.new("RGBA", (W, H))
for y in range(ROWS):
    for x in range(COLS):
        floor.paste(get_tile(grid[y][x]), (x * T, y * T))

# Subtle pixel border around each team zone rug for crispness
fd = ImageDraw.Draw(floor)
for ag in AGENTS:
    zx, zy, zw, zh = ag["zoneRect"]
    fd.rectangle([zx, zy, zx + zw - 1, zy + zh - 1], outline=(40, 48, 68, 90), width=1)

objects = []
for name, x, y in OBJS:
    m = meta[name]
    o = {"name": name, "x": x, "y": y, "w": m["w"], "h": m["h"], "kind": m["kind"]}
    if m["kind"] == "wall":
        floor.alpha_composite(get_obj(name), (x, y))
    objects.append(o)

OUT.mkdir(parents=True, exist_ok=True)
floor.save(OUT / "office_floor.png")

data = {
    "title": "BUILDWISE — AI Digital Office",
    "tile": T, "cols": COLS, "rows": ROWS, "width": W, "height": H,
    "objects": [o for o in objects if o["kind"] != "wall"],
    "wallDecor": [o for o in objects if o["kind"] == "wall"],
    "validationTower": VALIDATION_TOWER,
    "hubPoint": HUB_POINT,
    "agents": AGENTS,
    "workStates": [
        "idle", "working", "talking", "analyzing", "waiting_info",
        "reviewing", "waiting_approval", "failed", "retrying", "completed",
    ],
    "badges": [
        "idle", "talking", "working", "analyzing", "waiting_info",
        "reviewing", "waiting_approval", "pass", "warning", "fail",
        "retrying", "email_sent",
    ],
}
(OUT / "office_map.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "office_map.js").write_text("window.OFFICE_MAP = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")

# ------------------------------------------------------------------ 4) static preview render
draw_list = []
for o in data["objects"]:
    draw_list.append((o["y"] + o["h"], "obj", o))
draw_list.append((VALIDATION_TOWER["y"] + 64, "tower", VALIDATION_TOWER))
for ag in AGENTS:
    draw_list.append((ag["sortY"], "agent", ag))

preview = floor.copy()
state_rows = data["workStates"]
for _, kind, item in sorted(draw_list, key=lambda t: t[0]):
    if kind == "obj":
        preview.alpha_composite(get_obj(item["name"]), (item["x"], item["y"]))
    elif kind == "tower":
        preview.alpha_composite(get_obj("validation_tower_pass"), (item["x"], item["y"]))
    elif kind == "agent":
        ws = Image.open(ROOT / "characters" / item["id"] / f"{item['id']}_work_states.png").convert("RGBA")
        r = state_rows.index(item["defaultState"])
        fr = ws.crop((0, r * 64, 64, (r + 1) * 64))
        preview.alpha_composite(fr, (item["seatX"], item["seatY"]))
        bd = Image.open(ROOT / "badges" / f"badge_{item['defaultBadge']}.png").convert("RGBA")
        preview.alpha_composite(bd, (item["seatX"] + 16, item["seatY"] - 26))

preview.save(OUT / "office_preview_x1.png")
preview.resize((W * 2, H * 2), Image.NEAREST).save(OUT / "office_preview.png")
print("BUILDWISE map built:", W, "x", H, "objects:", len(objects))
