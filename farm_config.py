# ---------------- CÂY TRỒNG ----------------
# Cây (loại) là NÂNG CẤP — unlock 1 lần để mở khoá loại cây
# (seed_cost) mỗi lần muốn trồng, giá hạt tăng theo cây cao cấp hơn.
# passive_progress_per_min: tốc độ tự tăng progress mỗi phút
# sells_mango_plus: cây cao cấp (unlock sau) có thể bán ra mango+ ngoài mango thường
CROPS = {
    "mango": {
        "name": "Xoài",
        "unlock_cost": 0,       # cây mặc định
        "grow_progress_needed": 8,
        "seed_cost": 4,          # giá
        "next_unlock": "lemon",
        "base_yield": 2,
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
        "sells_mango_plus": False,
    },
    "apple": {
        "name": "Táo",
        "unlock_cost": 700,     # nâng cấp mở khoá
        "grow_progress_needed": 30,
        "seed_cost": 28,          # giá
        "next_unlock": None,
        "base_yield": 6,
        "passive_progress_per_min": 30 / (16 * 60),    # đầy trong 16h
        "sells_mango_plus": False,
    },
    "grape": {
        "name": "Nho",
        "unlock_cost": 1800,     # nâng cấp mở khoá
        "grow_progress_needed": 45,
        "seed_cost": 45,          # giá
        "next_unlock": "watermelon",
        "base_yield": 5,
        "passive_progress_per_min": 45 / (14 * 60),    # đầy trong 14h
        "sells_mango_plus": True,
    },
    "watermelon": {
        "name": "Dưa Hấu",
        "unlock_cost": 3000,     # nâng cấp mở khoá
        "grow_progress_needed": 60,
        "seed_cost": 70,          # giá
        "next_unlock": "carrot",
        "base_yield": 1,
        "passive_progress_per_min": 60 / (18 * 60),    # đầy trong 18h
        "sells_mango_plus": True,
    },
    "carrot": {
        "name": "Cà Rốt",
        "unlock_cost": 4000,     # nâng cấp mở khoá
        "grow_progress_needed": 20,
        "seed_cost": 20,          # giá
        "next_unlock": "dragonfruit",
        "base_yield": 8,
        "passive_progress_per_min": 20 / 30,  # đầy trong 30 phút
        "sells_mango_plus": True,
    },
    "dragonfruit": {
        "name": "Thanh Long",
        "unlock_cost": 7500,     # nâng cấp mở khoá
        "grow_progress_needed": 90,
        "seed_cost": 110,          # giá
        "next_unlock": None,
        "base_yield": 4,
        "passive_progress_per_min": 90 / (22 * 60),  # đầy trong 22 giờ
        "sells_mango_plus": True,
    },
}

CROP_ORDER = [
    "mango",
    "lemon",
    "orange",
    "apple",
    "grape",
    "watermelon",
    "carrot",
    "dragonfruit",
]

# ---------------- SẢN PHẨM & GIÁ BÁN ----------------
# key: "loại_trái" -> giá bán base
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
    "carrot_small": 8,
    "carrot_ripe": 20,
    "carrot_wilted": 4,
    "apple_green": 14,
    "apple_ripe": 28,
    "apple_rotten": 7,
    "grape_green": 18,
    "grape_ripe": 36,
    "grape_rotten": 9,
    "dragonfruit_green": 25,
    "dragonfruit_ripe": 60,
    "dragonfruit_overripe": 12,
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
    "carrot": {
        "stages": ["carrot_small", "carrot_ripe", "carrot_wilted"],
        "weights": [25, 65, 10],
    },
    "dragonfruit": {
        "stages": ["dragonfruit_green", "dragonfruit_ripe", "dragonfruit_overripe"],
        "weights": [20, 70, 10],
    },
}

# ---------------- TƯỚI CÂY ----------------
WATER_COOLDOWN_MIN = 60         # 1 giờ / lần tưới
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
FARMER_PERMANENT_COST_MANGO = 6000  # nâng cấp nông dân vĩnh viễn
FARMER_BASE = {
    "work_duration_min": 10,   # mỗi X phút làm 1 "vòng việc"
    "job_wait_sec": 10,         # chờ giữa các job trong 1 vòng
}
FARMER_UPGRADE = {
    "work_duration_reduction_min_per_level": 0.5,
    "min_work_duration_min": 5,
    "job_wait_reduction_sec_per_level": 0.3,
    "min_job_wait_sec": 1,
    "max_level": 10,
    "base_cost": 750,
    "cost_growth": 1.3,
}

# ---------------- NGƯỜI BÁN NÔNG SẢN ----------------
# Tự động bán TOÀN BỘ kho nông sản mỗi chu kỳ
SELLER_HIRE_COST_MANGO = 700
SELLER_HIRE_DURATION_MIN = 300       # thuê 5 tiếng/lần
SELLER_PERMANENT_COST_MANGO = 8500  # nâng cấp nông dân vĩnh viễn
SELLER_BASE = {
    "cycle_min": 15,           # mỗi X phút bán 1 lần
}
SELLER_UPGRADE = {
    "cycle_reduction_min_per_level": 1,
    "min_cycle_min": 2,
    "price_bonus_per_level": 0.03,   # +3% giá bán/level
    "max_level": 10,
    "base_cost": 600,
    "cost_growth": 1.3,
}

# ---------------- NGƯỜI THU THẬP ----------------
# Tự động mua MIỄN PHÍ hạt giống, mỗi lần 1-3 hạt.
COLLECTOR_HIRE_COST_MANGO = 400
COLLECTOR_HIRE_DURATION_MIN = 180    # thuê 3 tiếng/lần
COLLECTOR_PERMANENT_COST_MANGO = 5000  # nâng cấp nông dân vĩnh viễn
COLLECTOR_BASE = {
    "cycle_min": 20,          # mỗi X phút mua 1 lần
    "seeds_per_cycle_range": (1, 3),
}
COLLECTOR_UPGRADE = {
    "cycle_reduction_min_per_level": 1,
    "min_cycle_min": 4,
    "extra_seed_max_per_2_levels": 1,  # mỗi 2 level +1 vào đầu trên của khoảng random hạt
    "max_level": 15,
    "base_cost": 500,
    "cost_growth": 1.3,
}
COLLECTOR_CROP_UNLOCK_LEVEL = {
    "mango": 0,
    "lemon": 2,
    "orange": 4,
    "apple": 6,
    "grape": 8,
    "watermelon": 10,
    "carrot": 12,
    "dragonfruit": 14,
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

# ---------------- ĐỘT BIẾN ----------------
# "stackable": cộng dồn được với nhau và với nhóm exclusive
# "exclusive": trong nhóm này chỉ chọn tối đa 1 (không cộng dồn lẫn nhau)
MUTATIONS_STACKABLE = {
    "giant": {"name": "To lớn", "mult": 1.5, "base_chance": 0.15},
    "flooded": {"name": "Ngập nước", "mult": 1.2, "base_chance": 0.0},
    "frozen": {"name": "Đóng băng", "mult": 1.4, "base_chance": 0.0},
    "windblown": {"name": "Lộng gió", "mult": 1.3, "base_chance": 0.0},
    "electrified": {"name": "Nhiễm điện", "mult": 1.8, "base_chance": 0.0},
    "burning": {"name": "Rực lửa", "mult": 1.6, "base_chance": 0.0},
    "radioactive": {"name": "Phóng xạ", "mult": 2.5, "base_chance": 0.0},
}

MUTATIONS_EXCLUSIVE = {
    "gold": {"name": "Vàng", "mult": 2.0, "base_chance": 0.08},
    "rainbow": {"name": "Bảy sắc", "mult": 3.0, "base_chance": 0.02},
    "diamond": {"name": "Kim cương", "mult": 4.0, "base_chance": 0.006},
}

# ---------------- THỜI TIẾT ----------------
WEATHER_TYPES = {
    "clear": {"name": "Trời quang", "weight": 45},
    "rain": {"name": "Mưa", "weight": 20},
    "fog": {"name": "Sương mù", "weight": 12},
    "wind": {"name": "Gió lớn", "weight": 8},
    "storm": {"name": "Sấm sét", "weight": 6},
    "heatwave": {"name": "Nắng gắt", "weight": 4},
    "snow": {"name": "Tuyết", "weight": 2},
    "rainbow": {"name": "Cầu vồng", "weight": 2},
    "nuclear_rain": {"name": "Mưa hạt nhân", "weight": 0.2},
}
WEATHER_CYCLE_MIN = 10  # đổi thời tiết mỗi X phút

# hiệu ứng thời tiết lên tỉ lệ mutation khi thu hoạch (cộng thêm vào base_chance)
WEATHER_MUTATION_EFFECT = {
    "clear": {},
    "rain": {"flooded": 0.35},
    "fog": {},
    "wind": {"windblown": 0.25},
    "storm": {"electrified": 0.20},
    "heatwave": {"burning": 0.20},
    "snow": {"frozen": 0.25},
    "rainbow": {"rainbow": 0.20},
    "nuclear_rain": {"radioactive": 0.15, "giant": 0.20},
}

# ---------------- Ô TRỒNG ----------------
# Ô 1 miễn phí. Ô 2-6 mở khoá tuần tự bằng mango hoặc mango+
# farmer_level_required: cấp nông dân tối thiểu
# slots_per_plot: mỗi ô trồng được tối đa N loại cây cùng lúc
PLOTS = {
    1: {"unlock_cost": 0, "currency": "mango", "farmer_level_required": 0},
    2: {"unlock_cost": 300, "currency": "mango", "farmer_level_required": 2},
    3: {"unlock_cost": 900, "currency": "mango", "farmer_level_required": 4},
    4: {"unlock_cost": 150, "currency": "mango_plus", "farmer_level_required": 6},
}
PLOT_ORDER = [1, 2, 3, 4]
SLOTS_PER_PLOT = 2

# ---------------- DỤNG CỤ ----------------
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
        "desc": "Hiện nút Shop ngay, không cần gõ /shop riêng.",
    },
    "net": {
        "name": "Vợt",
        "price": 1000,
        "currency": "mango",
        "desc": "Thu hoạch toàn bộ trái đã sẵn sàng ở mọi ô và mọi cây chỉ với 1 lần bấm.",
    },
    "lightning_rod": {
        "name": "Cột thu lôi",
        "price": 1500,
        "currency": "mango",
        "desc": "Tăng thêm cơ hội ra đột biến Nhiễm Điện khi trời sấm sét",
        "electrified_bonus_chance": 0.15,
    },
}