# ---------------- XE ----------------
# durability: máu tối đa (base, chưa cộng upgrade)
# max_ef: EF cao nhất xe này được phép săn
# cooldown_min: thời gian hồi sau mỗi session (phút)
# base_rate: $/phút trụ, dùng để tính payout
CARS = {
    "rookie_truck": {
        "name": "Rookie Truck",
        "price": 0,
        "durability": 100,
        "max_ef": 2,
        "cooldown_min": 20,
        "base_rate": 40,
    },

    "weather_scout": {
        "name": "Weather Scout SUV",
        "price": 2500,
        "durability": 130,
        "max_ef": 2,
        "cooldown_min": 17,
        "base_rate": 55,
    },

    "storm_van": {
        "name": "Storm Chaser Van",
        "price": 5000,
        "durability": 150,
        "max_ef": 3,
        "cooldown_min": 15,
        "base_rate": 65,
    },

    "storm_ranger": {
        "name": "Storm Ranger Pickup",
        "price": 10000,
        "durability": 190,
        "max_ef": 3,
        "cooldown_min": 13,
        "base_rate": 80,
    },

    "armored_interceptor": {
        "name": "Armored Interceptor",
        "price": 20000,
        "durability": 250,
        "max_ef": 4,
        "cooldown_min": 10,
        "base_rate": 100,
    },

    "dominator_mk1": {
        "name": "Dominator MK-I",
        "price": 45000,
        "durability": 350,
        "max_ef": 4,
        "cooldown_min": 8,
        "base_rate": 130,
    },

    "tiv_classic": {
        "name": "TIV Classic",
        "price": 75000,
        "durability": 500,
        "max_ef": 5,
        "cooldown_min": 7,
        "base_rate": 170,
    },

    "titan_vortex_rig": {
        "name": "Titan Vortex Rig",
        "price": 120000,
        "durability": 700,
        "max_ef": 5,
        "cooldown_min": 5,
        "base_rate": 230,
    },

    "dominator_mk3": {
        "name": "Dominator MK-III",
        "price": 250000,
        "durability": 1000,
        "max_ef": 5,
        "cooldown_min": 3,
        "base_rate": 350,
    },

    "tiv_apocalypse": {
        "name": "TIV Apocalypse",
        "price": 600000,
        "durability": 1600,
        "max_ef": 5,
        "cooldown_min": 2,
        "base_rate": 550,
    },

    "omega_storm_platform": {
        "name": "Omega Storm Platform",
        "price": 1500000,
        "durability": 3000,
        "max_ef": 5,
        "cooldown_min": 1,
        "base_rate": 900,
    },
}

# thứ tự mua xe để check "xe tiếp theo" trong shop
CAR_ORDER = ["rookie_truck", "weather_scout", "storm_van", "storm_ranger", "armored_interceptor", "dominator_mk1",
    "tiv_classic", "titan_vortex_rig", "dominator_mk3", "tiv_apocalypse", "omega_storm_platform"]

# ---------------- EF SCALE ----------------
# session_min: (min, max) phút bão tồn tại trước khi tan tự nhiên
# dmg_tick: (min, max) sát thương base mỗi tick (30s) khi bão ở trạng thái bình thường
# payout_mult: hệ số nhân vào base_rate khi tính thưởng
EF_SCALE = {
    0: {"session_min": (3, 5), "dmg_tick": (2, 4), "payout_mult": 1.0},
    1: {"session_min": (4, 6), "dmg_tick": (4, 6), "payout_mult": 1.3},
    2: {"session_min": (5, 8), "dmg_tick": (7, 10), "payout_mult": 1.7},
    3: {"session_min": (6, 10), "dmg_tick": (11, 16), "payout_mult": 2.3},
    4: {"session_min": (8, 13), "dmg_tick": (16, 24), "payout_mult": 3.0},
    5: {"session_min": (10, 15), "dmg_tick": (24, 36), "payout_mult": 4.0},
}

TICK_SECONDS = 5  # 1 tick sự kiện = 5s real-time

# ---------------- SỰ KIỆN MỖI TICK ----------------
# trọng số random (cộng lại không cần bằng 100, dùng random.choices weights)
EVENT_WEIGHTS = {
    "steady": 40,      # bão đứng yên, dmg bình thường
    "approach": 30,    # bão lại gần, dmg x1.5~2, tăng dần
    "recede": 20,      # bão đi xa, dmg x0.4, session CHƯA kết thúc
    "special": 10,     # gió giật / mảnh vỡ / lặng gió
}

APPROACH_DMG_MULT_RANGE = (1.5, 2.0)
RECEDE_DMG_MULT_RANGE = (0.3, 0.5)

# special event con: gió giật (dmg spike) hoặc lặng gió (heal nhẹ)
SPECIAL_SUB_WEIGHTS = {
    "gust_spike": 70,   # sát thương đột biến 1 lần
    "calm_lull": 30,    # hồi nhẹ độ bền
}
GUST_SPIKE_DMG_MULT_RANGE = (2.0, 3.0)
CALM_LULL_HEAL_RANGE = (3, 8)  # hồi bao nhiêu durability

# ---------------- KẾT THÚC SESSION ----------------
# nếu xe hết durability giữa chừng -> vẫn nhận thưởng theo % thời gian trụ,
# nhưng có bonus vì rủi ro cao hơn
DESTROYED_RISK_BONUS = 1.5

# ---------------- MANGO ----------------
MANGO_EVERY_MIN = 5          # mỗi X phút trụ vững -> 1 mango
MONEY_PER_MANGO = 1000       # tỉ giá quy đổi (chỉ hiển thị, không auto-convert)

# ---------------- SỬA XE ----------------
REPAIR_COST = 500     # money
REPAIR_AMOUNT = 5     # durability hồi mỗi lần trả REPAIR_COST

# ---------------- NÂNG CẤP XE (durability / cooldown / max_ef) ----------------
# mỗi level cộng thêm, giá tăng dần theo level hiện tại
CAR_UPGRADE = {
    "durability_per_level": 20,
    "cooldown_reduction_per_level_min": 2,
    "min_cooldown_min": 5,       # sàn, không giảm dưới mức này
    "max_level": 10,
    "base_cost": 2000,
    "cost_growth": 1.4,          # cost = base_cost * (cost_growth ** current_level)
}

# ---------------- RADAR (giảm thời gian chờ bão xuất hiện, tăng cơ hội EF cao) ----------------
RADAR_UPGRADE = {
    "wait_reduction_sec_per_level": 15,   # giảm thời gian chờ trước khi session bắt đầu
    "base_wait_sec": 60,
    "min_wait_sec": 10,
    "ef_luck_bonus_per_level": 0.06,      # +6%/level cơ hội roll EF cao hơn khi bắt đầu
    "max_level": 10,
    "base_cost": 1500,
    "cost_growth": 1.35,
}

# ---------------- GIÁP (giảm % dmg mỗi tick) ----------------
ARMOR_UPGRADE = {
    "dmg_reduction_per_level": 0.05,   # -5%/level, cap dưới
    "max_reduction": 0.5,              # tối đa giảm 50% dmg
    "max_level": 10,
    "base_cost": 1800,
    "cost_growth": 1.35,
}

# EF roll weights mặc định (trước khi cộng radar luck) — xe max_ef giới hạn EF tối đa roll được
EF_ROLL_BASE_WEIGHTS = {0: 35, 1: 28, 2: 18, 3: 12, 4: 5, 5: 2}