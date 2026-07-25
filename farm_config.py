# ---------------- CÂY TRỒNG ----------------
# Cây (loại) là NÂNG CẤP — unlock 1 lần để mở khoá loại cây, sau đó vẫn phải MUA HẠT GIỐNG
# (seed_cost) mỗi lần muốn trồng, giá hạt tăng theo cây cao cấp hơn.
CROPS = {
    "mango": {
        "name": "Xoài",
        "unlock_cost": 0,       # cây mặc định, đã unlock sẵn từ đầu
        "grow_progress_needed": 8,
        "seed_cost": 4,          # giá 1 hạt giống xoài
        "next_unlock": "lemon",
    },
    "lemon": {
        "name": "Chanh",
        "unlock_cost": 80,     # nâng cấp mở khoá loại cây chanh (1 lần)
        "grow_progress_needed": 10,
        "seed_cost": 8,          # giá 1 hạt giống chanh
        "next_unlock": None,
    },
}

CROP_ORDER = ["mango", "lemon"]

# ---------------- SẢN PHẨM & GIÁ BÁN (mango) ----------------
# key: "loại_trái" -> giá bán base (chưa nhân mutation)
PRODUCE_PRICES = {
    "mango_unripe": 3,    # xoài non
    "mango_ripe": 7,      # xoài chín
    "mango_rotten": 1,    # xoài thúi
    "lemon_green": 5,     # chanh xanh
    "lemon_yellow": 10,   # chanh vàng
    "lemon_orange": 14,   # chanh cam
}

# mỗi loại cây sẽ random ra 1 trong các "giai đoạn chín" khi thu hoạch
PRODUCE_STAGES = {
    "mango": {
        "stages": ["mango_unripe", "mango_ripe", "mango_rotten"],
        "weights": [30, 55, 15],  # đa số ra chín, ít khi thúi
    },
    "lemon": {
        "stages": ["lemon_green", "lemon_yellow", "lemon_orange"],
        "weights": [30, 45, 25],
    },
}

# ---------------- TƯỚI CÂY ----------------
WATER_COOLDOWN_MIN = 60         # 1 giờ / lần tưới (base, chưa cộng upgrade)
WATERING_CANS = {
    "basic": {"name": "Bình tưới cơ bản", "price": 0, "progress_range": (1, 2)},
    "advanced": {"name": "Bình tưới nâng cao", "price": 100, "progress_range": (2, 4)},
}

# ---------------- NÔNG DÂN (farmer tự động) ----------------
FARMER_HIRE_COST_MANGO = 300
FARMER_HIRE_DURATION_MIN = 120      # thuê 1 lần dùng được 2 tiếng, hết giờ tự mất
FARMER_PERMANENT_COST_MANGO = 20000  # nâng cấp 1 lần để nông dân ở vĩnh viễn, không cần thuê lại
FARMER_BASE = {
    "work_duration_min": 30,   # mỗi X phút làm 1 "vòng việc" (tưới/trồng/thu hoạch)
    "job_wait_sec": 30,         # chờ giữa các job trong 1 vòng (tưới xong -> đợi -> trồng lại...)
}
# nâng cấp nông dân: giảm work_duration, giảm job_wait, hoặc unlock chọn cây khác để tự trồng
FARMER_UPGRADE = {
    "work_duration_reduction_min_per_level": 3,
    "min_work_duration_min": 5,
    "job_wait_reduction_sec_per_level": 3,
    "min_job_wait_sec": 1,
    "max_level": 8,
    "base_cost": 600,       # mango
    "cost_growth": 1.3,
}

# ---------------- NÂNG CẤP NĂNG SUẤT ----------------
YIELD_UPGRADE = {
    # mỗi level +% cơ hội x2 trái khi thu hoạch
    "double_fruit_chance_per_level": 0.05,
    "max_level": 10,
    "base_cost": 500,
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

# ---------------- Giá dụng cụ ----------------
TOOL_PRICE_SCANNER = 100     # kính lúp (mango) — dụng cụ mua 1 lần trong shop, dùng mãi
TOOL_MUTATION_PLUCKER = 400  # đồ gắp — chọn 1 mutation để gỡ khỏi trái

# ---------------- SPRINKLER ----------------
# duration_min: hiệu lực kéo dài bao lâu sau khi đặt
# progress_boost: cộng thêm progress mỗi lần tưới trong thời gian hiệu lực
# flood_mutation_chance: tỉ lệ ra mutation "ngập nước" khi thu hoạch trong lúc sprinkler hoạt động
SPRINKLERS = {
    "basic": {
        "name": "Sprinkler Basic",
        "price": 60,
        "duration_min": 5,
        "progress_boost": 1,
        "flood_mutation_chance": 0.05,
    },
    "uncommon": {
        "name": "Sprinkler Uncommon",
        "price": 180,
        "duration_min": 10,
        "progress_boost": 2,
        "flood_mutation_chance": 0.12,
    },
    "rare": {
        "name": "Sprinkler Rare",
        "price": 250,
        "duration_min": 15,
        "progress_boost": 3,
        "flood_mutation_chance": 0.25,
    },
    "legendary": {
        "name": "Sprinkler Legendary",
        "price": 600,
        "duration_min": 20,
        "progress_boost": 5,
        "flood_mutation_chance": 0.45,
    },
}
SPRINKLER_ORDER = ["basic", "uncommon", "rare", "legendary"]

# ---------------- ĐỘT BIẾN (MUTATIONS) ----------------
# "stackable": cộng dồn được với nhau và với nhóm exclusive
# "exclusive": trong nhóm này chỉ chọn tối đa 1 (không cộng dồn lẫn nhau)
MUTATIONS_STACKABLE = {
    "giant": {"name": "To lớn", "mult": 1.5, "base_chance": 0.10},
    "flooded": {"name": "Ngập nước", "mult": 1.2, "base_chance": 0.0},  # chỉ ra từ mưa/sprinkler, không random nền
}

MUTATIONS_EXCLUSIVE = {
    "gold": {"name": "Vàng", "mult": 2.0, "base_chance": 0.03},
    "rainbow": {"name": "Bảy sắc", "mult": 3.0, "base_chance": 0.01},   # cũng ra từ thời tiết cầu vồng
    "radioactive": {"name": "Dược tễ", "mult": 4.0, "base_chance": 0.0},  # chỉ ra từ mưa hạt nhân
}

# ---------------- THỜI TIẾT (cấp guild) ----------------
WEATHER_TYPES = {
    "clear": {"name": "Trời quang", "weight": 50},
    "rain": {"name": "Mưa", "weight": 20},
    "fog": {"name": "Sương mù", "weight": 15},
    "storm": {"name": "Sấm sét", "weight": 8},
    "rainbow": {"name": "Cầu vồng", "weight": 5},
    "nuclear_rain": {"name": "Mưa hạt nhân", "weight": 2},
}
WEATHER_CYCLE_MIN = 10  # đổi thời tiết mỗi X phút

# hiệu ứng thời tiết lên tỉ lệ mutation khi thu hoạch (cộng thêm vào base_chance)
WEATHER_MUTATION_EFFECT = {
    "rain": {"flooded": 0.35},
    "rainbow": {"rainbow": 0.20},
    "nuclear_rain": {"radioactive": 0.15},
    "storm": {"giant": 0.10},  # sấm sét làm cây phát triển bất thường -> dễ to lớn hơn
    "fog": {},
    "clear": {},
}