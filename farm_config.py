# ---------------- CÂY TRỒNG ----------------
# Cây (loại) là NÂNG CẤP — unlock 1 lần để mở khoá loại cây, sau đó vẫn phải MUA HẠT GIỐNG
# (seed_cost) mỗi lần muốn trồng, giá hạt tăng theo cây cao cấp hơn.
#
# passive_progress_per_min: tốc độ tự tăng progress mỗi phút KHÔNG CẦN TƯỚI (auto-grow theo thời gian thực,
# tính cả lúc offline). Tưới nước vẫn có tác dụng CỘNG THÊM progress tức thời (tuỳ chọn, không bắt buộc).
# Mốc thời gian trồng đầy đủ (0 -> grow_progress_needed) nếu KHÔNG tưới gì: mango 2h / lemon 4h / orange 8h / apple 16h.
#
# sells_mango_plus: cây cao cấp (unlock sau) có thể bán ra mango+ ngoài mango thường (tính năng tương lai).
CROPS = {
    "mango": {
        "name": "Xoài",
        "unlock_cost": 0,       # cây mặc định
        "grow_progress_needed": 8,
        "seed_cost": 4,          # giá
        "next_unlock": "lemon",
        "base_yield": 3,
        "passive_progress_per_min": 8 / (2 * 60),      # đầy trong 2h
        "sells_mango_plus": False,
    },
    "lemon": {
        "name": "Chanh",
        "unlock_cost": 80,     # nâng cấp mở khoá
        "grow_progress_needed": 10,
        "seed_cost": 8,          # giá
        "next_unlock": "orange",
        "base_yield": 4,
        "passive_progress_per_min": 10 / (4 * 60),     # đầy trong 4h
        "sells_mango_plus": False,
    },
    "orange": {
        "name": "Cam",
        "unlock_cost": 250,     # nâng cấp mở khoá
        "grow_progress_needed": 15,
        "seed_cost": 15,          # giá
        "next_unlock": "apple",
        "base_yield": 5,
        "passive_progress_per_min": 15 / (8 * 60),     # đầy trong 8h
        "sells_mango_plus": True,
    },
    "apple": {
        "name": "Táo",
        "unlock_cost": 700,     # nâng cấp mở khoá
        "grow_progress_needed": 30,
        "seed_cost": 28,          # giá
        "next_unlock": "grape",
        "base_yield": 6,
        "passive_progress_per_min": 30 / (16 * 60),    # đầy trong 16h
        "sells_mango_plus": True,
    },
    "grape": {
        "name": "Nho",
        "unlock_cost": 1800,     # nâng cấp mở khoá
        "grow_progress_needed": 60,
        "seed_cost": 45,          # giá
        "next_unlock": "watermelon",
        "base_yield": 5,
        "passive_progress_per_min": 60 / (24 * 60),    # đầy trong 16h
        "sells_mango_plus": True,
    },
    "watermelon": {
        "name": "Dưa Hấu",
        "unlock_cost": 4000,     # nâng cấp mở khoá
        "grow_progress_needed": 100,
        "seed_cost": 70,          # giá
        "next_unlock": None,
        "base_yield": 1,
        "passive_progress_per_min": 100 / (36 * 60),    # đầy trong 16h
        "sells_mango_plus": True,
    },
}

CROP_ORDER = ["mango", "lemon", "orange", "apple","grape","watermelon"]

# ---------------- SẢN PHẨM & GIÁ BÁN ----------------
# key: "loại_trái" -> giá bán base (chưa nhân mutation)
PRODUCE_PRICES = {
    "mango_unripe": 3,
    "mango_ripe": 7,
    "mango_rotten": 1,

    "lemon_green": 5,
    "lemon_yellow": 10,
    "lemon_orange": 14,
    
    "orange_green": 9,
    "orange_ripe": 18,
    "orange_rotten": 4,

    "apple_green": 14,
    "apple_ripe": 28,
    "apple_rotten": 7,
    
    "grape_green": 18,
    "grape_ripe": 36,
    "grape_rotten": 9,

    "watermelon_small": 40,
    "watermelon_ripe": 80,
    "watermelon_cracked": 20,
}

PRODUCE_STAGES = {
    "mango": {
        "stages": ["mango_unripe", "mango_ripe", "mango_rotten"],
        "weights": [30, 55, 15],
    },
    "lemon": {
        "stages": ["lemon_green", "lemon_yellow", "lemon_orange"],
        "weights": [30, 45, 25],
    },
    "orange": {
        "stages": ["orange_green", "orange_ripe", "orange_rotten"],
        "weights": [25, 60, 15],
    },
    "apple": {
        "stages": ["apple_green", "apple_ripe", "apple_rotten"],
        "weights": [20, 65, 15],
    },
    "grape": {
        "stages": ["grape_green", "grape_ripe", "grape_rotten"],
        "weights": [25, 60, 15],
    },
    "watermelon": {
        "stages": ["watermelon_small", "watermelon_ripe", "watermelon_cracked"],
        "weights": [20, 70, 10],
    },
}

# ---------------- TƯỚI CÂY ----------------
WATER_COOLDOWN_MIN = 60         # 1 giờ / lần tưới (base, chưa cộng upgrade)
WATERING_CANS = {
    "basic": {
        "name": "Bình tưới cơ bản",
        "price": 0,
        "progress_range": (1, 2),
    },
    "advanced": {
        "name": "Bình tưới nâng cao",
        "price": 100,
        "progress_range": (2, 4),
    },
    "abundant": {
        "name": "Bình tưới phong phú",
        "price": 400,
        "progress_range": (3, 6),
    },
    "master": {
        "name": "Bình tưới bậc thầy",
        "price": 1200,
        "progress_range": (5, 9),
    },
}

# ---------------- NÔNG DÂN ----------------
FARMER_HIRE_COST_MANGO = 500
FARMER_HIRE_DURATION_MIN = 120      # thuê 2 tiếng/lần
FARMER_PERMANENT_COST_MANGO = 30000  # nâng cấp nông dân vĩnh viễn
FARMER_BASE = {
    "work_duration_min": 10,   # mỗi X phút làm 1 "vòng việc"
    "job_wait_sec": 10,         # chờ giữa các job trong 1 vòng
}
# nâng cấp nông dân: giảm work_duration, giảm job_wait
FARMER_UPGRADE = {
    "work_duration_reduction_min_per_level": 0.5,
    "min_work_duration_min": 5,
    "job_wait_reduction_sec_per_level": 0.3,
    "min_job_wait_sec": 1,
    "max_level": 10,
    "base_cost": 750,       # mango
    "cost_growth": 1.3,
}

# ---------------- NÂNG CẤP NĂNG SUẤT ----------------
YIELD_UPGRADE = {
    # mỗi level +% cơ hội x2 trái khi thu hoạch
    "double_fruit_chance_per_level": 0.03,
    "max_level": 10,
    "base_cost": 300,
    "cost_growth": 1.3,
}
WATER_SPEED_UPGRADE = {
    # giảm thời gian cooldown tưới cây
    "cooldown_reduction_min_per_level": 5,
    "min_cooldown_min": 15,
    "max_level": 8,
    "base_cost": 400,
    "cost_growth": 1.3,
}

# ---------------- SPRINKLER ----------------
# duration_min: hiệu lực kéo dài bao lâu sau khi đặt
# progress_boost: cộng thêm progress mỗi lần tưới trong thời gian hiệu lực
# flood_mutation_chance: tỉ lệ ra mutation "ngập nước" khi thu hoạch trong lúc sprinkler hoạt động
SPRINKLERS = {
    "basic": {
        "name": "Vòi phun Cơ Bản",
        "price": 60,
        "duration_min": 5,
        "progress_boost": 1,
        "flood_mutation_chance": 0.05,
    },
    "uncommon": {
        "name": "Vòi phun Không Phổ Biến",
        "price": 180,
        "duration_min": 10,
        "progress_boost": 2,
        "flood_mutation_chance": 0.12,
    },
    "rare": {
        "name": "Vòi phun Hiếm",
        "price": 250,
        "duration_min": 15,
        "progress_boost": 3,
        "flood_mutation_chance": 0.25,
    },
    "legendary": {
        "name": "Vòi phun Huyền Thoại",
        "price": 600,
        "duration_min": 20,
        "progress_boost": 5,
        "flood_mutation_chance": 0.45,
    },
    "master": {
        "name": "Vòi phun Bậc Thầy",
        "price": 1200,
        "duration_min": 25,
        "progress_boost": 7,
        "flood_mutation_chance": 0.60,
    },
    "mythical": {
        "name": "Vòi phun THẦN THOẠI",
        "price": 2500,
        "duration_min": 30,
        "progress_boost": 10,
        "flood_mutation_chance": 0.80,
    },
}

SPRINKLER_ORDER = [
    "basic",
    "uncommon",
    "rare",
    "legendary",
    "master",
    "mythical",
]

# ---------------- ĐỘT BIẾN (MUTATIONS) ----------------
# "stackable": cộng dồn được với nhau và với nhóm exclusive
# "exclusive": trong nhóm này chỉ chọn tối đa 1 (không cộng dồn lẫn nhau)
MUTATIONS_STACKABLE = {
    "giant": {"name": "To lớn", "mult": 1.5, "base_chance": 0.10},
    "flooded": {"name": "Ngập nước", "mult": 1.2, "base_chance": 0.0},     # Mưa
    "frozen": {"name": "Đóng băng", "mult": 1.4, "base_chance": 0.0},      # Tuyết/Băng
    "windblown": {"name": "Lộng gió", "mult": 1.3, "base_chance": 0.0},    # Gió mạnh
    "electrified": {"name": "Nhiễm điện", "mult": 1.8, "base_chance": 0.0}, # Sấm sét
    "burning": {"name": "Rực lửa", "mult": 1.6, "base_chance": 0.0},       # Nắng nóng
    "crystal": {"name": "Pha lê", "mult": 2.0, "base_chance": 0.002},
}

MUTATIONS_EXCLUSIVE = {
    "gold": {"name": "Vàng", "mult": 2.0, "base_chance": 0.03},
    "rainbow": {"name": "Bảy sắc", "mult": 3.0, "base_chance": 0.01},
    "radioactive": {"name": "Phóng xạ", "mult": 4.0, "base_chance": 0.0},  # Mưa hạt nhân
    "diamond": {"name": "Kim cương", "mult": 5.5, "base_chance": 0.003},
    "ancient": {"name": "Cổ đại", "mult": 7.0, "base_chance": 0.001},
    "celestial": {"name": "Thiên thể", "mult": 10.0, "base_chance": 0.0003},
}

# ---------------- THỜI TIẾT (cấp guild) ----------------
WEATHER_TYPES = {
    "clear": {"name": "Trời quang", "weight": 45},
    "rain": {"name": "Mưa", "weight": 20},
    "fog": {"name": "Sương mù", "weight": 12},
    "wind": {"name": "Gió lớn", "weight": 8},
    "storm": {"name": "Sấm sét", "weight": 6},
    "heatwave": {"name": "Nắng gắt", "weight": 4},
    "snow": {"name": "Tuyết", "weight": 2},
    "rainbow": {"name": "Cầu vồng", "weight": 2},
    "meteor_shower": {"name": "Mưa sao băng", "weight": 0.8},
    "nuclear_rain": {"name": "Mưa hạt nhân", "weight": 0.2},
}
WEATHER_CYCLE_MIN = 10  # đổi thời tiết mỗi X phút

# hiệu ứng thời tiết lên tỉ lệ mutation khi thu hoạch (cộng thêm vào base_chance)
WEATHER_MUTATION_EFFECT = {
    "clear": {},
    # Mưa
    "rain": {
        "flooded": 0.35,
        "giant": 0.05,
    },
    # Sương
    "fog": {
        "giant": 0.08,
    },
    # Gió lớn
    "wind": {
        "windblown": 0.25,
    },
    # Sấm sét
    "storm": {
        "electrified": 0.20,
        "giant": 0.10,
    },
    # Nắng gắt
    "heatwave": {
        "burning": 0.20,
    },
    # Tuyết
    "snow": {
        "frozen": 0.25,
        "crystal": 0.03,
    },
    # Cầu vồng
    "rainbow": {
        "rainbow": 0.20,
        "gold": 0.05,
    },
    # Mưa sao băng
    "meteor_shower": {
        "crystal": 0.20,
        "diamond": 0.05,
    },
    # Mưa hạt nhân
    "nuclear_rain": {
        "radioactive": 0.15,
        "giant": 0.20,
    },
}

# ---------------- Ô TRỒNG (PLOTS) ----------------
# Ô 1 miễn phí (mặc định, sẵn có). Ô 2-6 mở khoá tuần tự bằng mango (2,3) hoặc mango+ (4,5,6).
# farmer_level_required: cấp nông dân tối thiểu để nông dân TỰ ĐỘNG làm việc tại ô này
# (ngoài điều kiện ô phải được mở khoá bằng tiền trước — cả 2 điều kiện đều bắt buộc).
# slots_per_plot: mỗi ô trồng được tối đa N loại cây cùng lúc, mỗi slot tiến trình độc lập.
PLOTS = {
    1: {"unlock_cost": 0, "currency": "mango", "farmer_level_required": 0},
    2: {"unlock_cost": 300, "currency": "mango", "farmer_level_required": 2},
    3: {"unlock_cost": 900, "currency": "mango", "farmer_level_required": 4},
    4: {"unlock_cost": 150, "currency": "mango_plus", "farmer_level_required": 6},
    5: {"unlock_cost": 400, "currency": "mango_plus", "farmer_level_required": 8},
    6: {"unlock_cost": 900, "currency": "mango_plus", "farmer_level_required": 10},
}
PLOT_ORDER = [1, 2, 3, 4, 5, 6]
SLOTS_PER_PLOT = 3

# ---------------- GEAR (dụng cụ) ----------------
GEAR = {
    "scanner": {
        "name": "Kính lúp",
        "price": 200,
        "currency": "mango",
        "desc": "Xem giá thị trường chính xác của bất kỳ trái nào trong kho.",
    },
    "mutation_plucker": {
        "name": "Đồ gắp",
        "price": 800,
        "currency": "mango",
        "desc": "Gỡ bỏ 1 đột biến cụ thể khỏi trái (đột biến bị gắp biến mất vĩnh viễn).",
    },
    "wrench": {
        "name": "Cờ lê",
        "price": 350,
        "currency": "mango",
        "desc": "Hiện nút Shop ngay trong /farm, không cần gõ /shop riêng.",
    },
    "net": {
        "name": "Vợt",
        "price": 1000,
        "currency": "mango",
        "desc": "Thu hoạch toàn bộ trái đã sẵn sàng ở MỌI ô và MỌI cây chỉ với 1 lần bấm.",
    },
    "lightning_rod": {
        "name": "Cột thu lôi",
        "price": 1500,
        "currency": "mango",
        "desc": "Tăng thêm cơ hội ra đột biến Nhiễm Điện khi trời sấm sét, áp dụng toàn bộ cây đang trồng.",
        "electrified_bonus_chance": 0.15,
    },
}