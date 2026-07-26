import io
import math
import random

from PIL import Image, ImageDraw

SOIL_BASE_PATH = "assets/soil_base.png"

# Toạ độ neo (gốc cây) trên ảnh nền 400x300 — điểm giữa luống dưới cùng,
# trùng vị trí ô đánh dấu nâu đậm trong ảnh mẫu.
PLANT_ANCHOR = (200, 268)

CROP_COLORS = {
    "mango":  {"trunk": (92, 61, 33),  "leaf": (58, 130, 58),  "leaf_dark": (40, 100, 42),  "fruit": (235, 180, 40)},
    "lemon":  {"trunk": (99, 68, 38),  "leaf": (70, 140, 60),  "leaf_dark": (48, 108, 46),  "fruit": (232, 214, 60)},
    "orange": {"trunk": (101, 66, 35), "leaf": (54, 122, 54),  "leaf_dark": (36, 92, 40),   "fruit": (235, 140, 30)},
    "apple":  {"trunk": (87, 55, 30),  "leaf": (50, 120, 62),  "leaf_dark": (32, 90, 48),   "fruit": (205, 40, 45)},
}

FRUIT_COLOR_BY_STAGE = {
    "mango_unripe": (110, 170, 70), "mango_ripe": (235, 180, 40), "mango_rotten": (110, 90, 60),
    "lemon_green": (140, 180, 70), "lemon_yellow": (232, 214, 60), "lemon_orange": (230, 150, 40),
    "orange_green": (120, 170, 70), "orange_ripe": (235, 140, 30), "orange_rotten": (110, 90, 60),
    "apple_green": (120, 175, 80), "apple_ripe": (205, 40, 45), "apple_rotten": (120, 85, 60),
}

def _lerp(a, b, t):
    return a + (b - a) * t

def _draw_sprout(draw: ImageDraw.ImageDraw, x, y, t, colors):
    """t in [0,1): mầm non nhú lên khỏi đất."""
    h = _lerp(4, 22, t)
    draw.line([(x, y), (x, y - h)], fill=colors["trunk"], width=3)
    leaf_len = _lerp(3, 14, t)
    draw.ellipse([x - leaf_len, y - h - 4, x + 2, y - h + 6], fill=colors["leaf"])
    draw.ellipse([x - 2, y - h - 6, x + leaf_len, y - h + 4], fill=colors["leaf"])

def _draw_sapling(draw: ImageDraw.ImageDraw, x, y, t, colors):
    """t in [0,1): thân cây con cao dần, tán lá nhỏ tròn."""
    trunk_h = _lerp(22, 55, t)
    trunk_w = int(_lerp(3, 6, t))
    draw.line([(x, y), (x, y - trunk_h)], fill=colors["trunk"], width=trunk_w)
    canopy_r = _lerp(12, 26, t)
    cx, cy = x, y - trunk_h
    draw.ellipse([cx - canopy_r, cy - canopy_r * 0.9, cx + canopy_r, cy + canopy_r * 0.5],
                 fill=colors["leaf"])
    draw.ellipse([cx - canopy_r * 0.6, cy - canopy_r * 1.1, cx + canopy_r * 0.7, cy - canopy_r * 0.2],
                 fill=colors["leaf_dark"])

def _draw_mature_tree(draw: ImageDraw.ImageDraw, x, y, t, colors, fruit_color=None, fruit_count=0, seed=0):
    """t in [0,1): cây trưởng thành, tán lá đầy, có thể ra quả (fruit_count>0)."""
    trunk_h = _lerp(55, 78, t)
    trunk_w = 7
    draw.line([(x, y), (x, y - trunk_h)], fill=colors["trunk"], width=trunk_w)
    # nhánh phụ
    draw.line([(x, y - trunk_h * 0.55), (x - 14, y - trunk_h * 0.75)], fill=colors["trunk"], width=4)
    draw.line([(x, y - trunk_h * 0.6), (x + 15, y - trunk_h * 0.8)], fill=colors["trunk"], width=4)

    cx, cy = x, y - trunk_h - 6
    canopy_r = _lerp(26, 34, t)
    # tán lá nhiều tầng cho dày dặn
    offsets = [(0, 0, 1.0), (-canopy_r * 0.55, canopy_r * 0.35, 0.75),
               (canopy_r * 0.55, canopy_r * 0.3, 0.75), (0, -canopy_r * 0.5, 0.7)]
    for i, (ox, oy, scale) in enumerate(offsets):
        r = canopy_r * scale
        fill = colors["leaf"] if i % 2 == 0 else colors["leaf_dark"]
        draw.ellipse([cx + ox - r, cy + oy - r * 0.85, cx + ox + r, cy + oy + r * 0.85], fill=fill)

    if fruit_count > 0 and fruit_color:
        rnd = random.Random(seed)
        for _ in range(fruit_count):
            ang = rnd.uniform(0, 2 * math.pi)
            rad = rnd.uniform(canopy_r * 0.25, canopy_r * 0.85)
            fx = cx + math.cos(ang) * rad
            fy = cy + math.sin(ang) * rad * 0.8
            fr = 4
            draw.ellipse([fx - fr, fy - fr, fx + fr, fy + fr], fill=fruit_color, outline=(40, 30, 20))

def render_plant_stage(colors: dict, progress_ratio: float, ready: bool,
                        stage_key: str | None = None, seed: int = 0) -> Image.Image:
    """
    Vẽ 1 cây trên canvas trong suốt kích thước đủ chứa (120x140), gốc cây ở đáy-giữa.
    progress_ratio: 0.0 -> 1.0 (chưa lớn -> đủ điều kiện thu hoạch)
    ready: True nếu đã đạt 100% (hiển thị quả chín sẵn sàng hái)
    """
    W, H = 120, 140
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    x, y = W // 2, H - 6

    progress_ratio = max(0.0, min(1.0, progress_ratio))

    if progress_ratio < 0.2:
        _draw_sprout(draw, x, y, progress_ratio / 0.2, colors)
    elif progress_ratio < 0.6:
        _draw_sapling(draw, x, y, (progress_ratio - 0.2) / 0.4, colors)
    else:
        t = (progress_ratio - 0.6) / 0.4
        fruit_count = 0
        fruit_color = None
        if ready:
            fruit_count = 6
            fruit_color = FRUIT_COLOR_BY_STAGE.get(stage_key, colors["fruit"])
        elif progress_ratio > 0.85:
            fruit_count = 3
            fruit_color = colors["fruit"]
        _draw_mature_tree(draw, x, y, t, colors, fruit_color=fruit_color, fruit_count=fruit_count, seed=seed)

    return canvas

def render_farm_image(crop_type: str, planted: bool, progress: float, needed: float,
                       stage_preview: str | None = None, sprinkler_active: bool = False,
                       soil_image_path: str = SOIL_BASE_PATH) -> bytes:
    """
    [Giữ lại cho tương thích] Ghép 1 cây đơn lẻ lên ảnh nền đất — dùng khi chỉ có 1 ô/1 slot.
    """
    base = Image.open(soil_image_path).convert("RGBA")

    if planted:
        colors = CROP_COLORS.get(crop_type, CROP_COLORS["mango"])
        ratio = (progress / needed) if needed else 0.0
        ready = progress >= needed
        plant_img = render_plant_stage(colors, ratio, ready, stage_key=stage_preview, seed=hash(crop_type) & 0xFFFF)

        anchor_x, anchor_y = PLANT_ANCHOR
        paste_x = anchor_x - plant_img.width // 2
        paste_y = anchor_y - plant_img.height + 10
        base.alpha_composite(plant_img, dest=(paste_x, paste_y))

        if sprinkler_active:
            _draw_rain_drops(base, anchor_x, anchor_y)

    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

def _draw_rain_drops(base: Image.Image, anchor_x: int, anchor_y: int, seed: int = 1):
    drop_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(drop_layer)
    rnd = random.Random(seed)
    for _ in range(10):
        dx = rnd.randint(anchor_x - 40, anchor_x + 40)
        dy = rnd.randint(anchor_y - 90, anchor_y - 10)
        dd.line([(dx, dy), (dx - 2, dy + 6)], fill=(120, 180, 230, 180), width=2)
    base.alpha_composite(drop_layer)

def render_multi_plot_image(plots_render_data: list[dict], soil_image_path: str = SOIL_BASE_PATH) -> bytes:
    """
    Vẽ nhiều cây nhỏ trên cùng 1 ảnh nền đất, sắp theo lưới ô x slot.

    plots_render_data: list các dict, mỗi dict ứng với 1 Ô ĐÃ MỞ KHOÁ:
        {
            "plot_id": int,
            "unlocked": True,
            "slots": [
                {"planted": bool, "crop_type": str|None, "progress": float, "needed": float,
                 "stage_preview": str|None, "sprinkler_active": bool}
                ... (đúng SLOTS_PER_PLOT phần tử, phần tử planted=False nếu ô trống)
            ]
        }
    Chỉ vẽ các ô có unlocked=True. Ô khoá không xuất hiện trên ảnh (tránh rối mắt).
    Layout: mỗi ô chiếm 1 "cụm" gồm 3 cây nhỏ nằm ngang, các cụm xếp thành lưới theo số ô đã mở khoá.
    """
    base = Image.open(soil_image_path).convert("RGBA")
    W, H = base.size

    unlocked_plots = [p for p in plots_render_data if p.get("unlocked")]
    if not unlocked_plots:
        buf = io.BytesIO()
        base.convert("RGB").save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    n_plots = len(unlocked_plots)
    # lưới cụm ô: tối đa 3 cụm/hàng để không quá chật với 6 ô
    cols = min(3, n_plots)
    rows = (n_plots + cols - 1) // cols

    margin_x, margin_top, margin_bottom = 25, 15, 8
    usable_w = W - 2 * margin_x
    usable_h = H - margin_top - margin_bottom - 82

    cell_w = usable_w / cols
    cell_h = usable_h / rows if rows > 0 else usable_h

    plant_small_size = (72, 82)  # kích thước mỗi cây thu nhỏ khi vẽ nhiều cây

    for idx, plot_data in enumerate(unlocked_plots):
        col = idx % cols
        row = idx // cols
        cluster_cx = margin_x + cell_w * (col + 0.5)
        cluster_base_y = margin_top + 82 + cell_h * (row + 1) - 12

        slots = plot_data["slots"]
        n_slots = len(slots)
        slot_spacing = min(plant_small_size[0] + 6, cell_w / max(1, n_slots))
        start_x = cluster_cx - (slot_spacing * (n_slots - 1)) / 2

        for si, slot in enumerate(slots):
            sx = start_x + slot_spacing * si
            sy = cluster_base_y

            if not slot.get("planted"):
                # ô đất trống: chấm nâu nhỏ đánh dấu vị trí
                d = ImageDraw.Draw(base)
                d.ellipse([sx - 4, sy - 4, sx + 4, sy + 4], fill=(90, 60, 35))
                continue

            crop_type = slot.get("crop_type") or "mango"
            colors = CROP_COLORS.get(crop_type, CROP_COLORS["mango"])
            needed = slot.get("needed") or 1.0
            ratio = (slot.get("progress", 0.0) / needed) if needed else 0.0
            ready = slot.get("progress", 0.0) >= needed

            plant_img = render_plant_stage(
                colors, ratio, ready,
                stage_key=slot.get("stage_preview"),
                seed=hash((plot_data["plot_id"], si, crop_type)) & 0xFFFF,
            )
            # scale xuống kích thước nhỏ cho nhiều cây cùng khung hình
            plant_img = plant_img.resize(plant_small_size, Image.LANCZOS)

            paste_x = int(sx - plant_img.width / 2)
            paste_y = int(sy - plant_img.height + 8)
            base.alpha_composite(plant_img, dest=(paste_x, paste_y))

            if slot.get("sprinkler_active"):
                _draw_rain_drops(base, int(sx), int(sy), seed=idx * 10 + si)

    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()