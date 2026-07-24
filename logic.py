"""
Logic game thuần Python — không import discord, dễ test độc lập.
"""

import random
import config


def get_car_stats(car_id: str, durability_level: int, cooldown_level: int) -> dict:
    """Trả về stats thực tế của xe sau khi cộng upgrade."""
    base = config.CARS[car_id]
    up = config.CAR_UPGRADE

    max_durability = base["durability"] + durability_level * up["durability_per_level"]
    cooldown_min = max(
        up["min_cooldown_min"],
        base["cooldown_min"] - cooldown_level * up["cooldown_reduction_per_level_min"],
    )
    return {
        "name": base["name"],
        "max_durability": max_durability,
        "cooldown_min": cooldown_min,
        "max_ef": base["max_ef"],
        "base_rate": base["base_rate"],
    }


def upgrade_cost(upgrade_key: str, current_level: int) -> int:
    """upgrade_key: 'car_durability' | 'car_cooldown' | 'radar' | 'armor'"""
    table = {
        "car": config.CAR_UPGRADE,
        "radar": config.RADAR_UPGRADE,
        "armor": config.ARMOR_UPGRADE,
    }[upgrade_key]
    return int(table["base_cost"] * (table["cost_growth"] ** current_level))


def roll_ef(max_ef: int, radar_level: int) -> int:
    """Random EF khi bắt đầu session, giới hạn bởi max_ef của xe, luck cộng từ radar."""
    weights = dict(config.EF_ROLL_BASE_WEIGHTS)
    # luck_bonus cap ở 0.6 (radar max lvl10 * 0.06 = 0.6) — dịch trọng số dần về phía EF cao,
    # không cộng dồn vào total (tránh 1 EF chiếm quá nửa map ở radar cao)
    luck_bonus = min(0.6, radar_level * config.RADAR_UPGRADE["ef_luck_bonus_per_level"])

    allowed = {ef: float(w) for ef, w in weights.items() if ef <= max_ef}
    if allowed:
        top_ef = max(allowed.keys())
        # chuyển 1 phần trọng số từ các EF thấp hơn sang EF cao nhất, tỉ lệ theo luck_bonus
        for ef in list(allowed.keys()):
            if ef != top_ef:
                shift = allowed[ef] * luck_bonus * 0.5
                allowed[ef] -= shift
                allowed[top_ef] += shift

    efs = list(allowed.keys())
    wts = list(allowed.values())
    return random.choices(efs, weights=wts, k=1)[0]


def roll_session_length_sec(ef: int) -> int:
    lo, hi = config.EF_SCALE[ef]["session_min"]
    return random.randint(int(lo * 60), int(hi * 60))


def wait_time_sec(radar_level: int) -> int:
    r = config.RADAR_UPGRADE
    sec = r["base_wait_sec"] - radar_level * r["wait_reduction_sec_per_level"]
    return max(r["min_wait_sec"], sec)


def roll_tick_event() -> str:
    events = list(config.EVENT_WEIGHTS.keys())
    weights = list(config.EVENT_WEIGHTS.values())
    return random.choices(events, weights=weights, k=1)[0]


def roll_special_sub_event() -> str:
    subs = list(config.SPECIAL_SUB_WEIGHTS.keys())
    weights = list(config.SPECIAL_SUB_WEIGHTS.values())
    return random.choices(subs, weights=weights, k=1)[0]


def compute_tick(ef: int, event: str, armor_level: int) -> dict:
    """
    Tính kết quả 1 tick: dmg thực nhận, log text.
    Trả về {"dmg": float, "heal": float, "state": str, "log": str}
    """
    lo, hi = config.EF_SCALE[ef]["dmg_tick"]
    base_dmg = random.uniform(lo, hi)
    armor_reduction = min(
        config.ARMOR_UPGRADE["max_reduction"],
        armor_level * config.ARMOR_UPGRADE["dmg_reduction_per_level"],
    )

    dmg = 0.0
    heal = 0.0
    state = event
    log = ""

    if event == "steady":
        dmg = base_dmg
        log = "🌪️ Lốc xoáy đứng yên, sức gió ổn định."
    elif event == "approach":
        mult = random.uniform(*config.APPROACH_DMG_MULT_RANGE)
        dmg = base_dmg * mult
        log = "⚠️ Lốc xoáy đang tiến lại gần! Sát thương tăng mạnh."
    elif event == "recede":
        mult = random.uniform(*config.RECEDE_DMG_MULT_RANGE)
        dmg = base_dmg * mult
        log = "↘️ Lốc xoáy đang di chuyển ra xa, sát thương giảm."
    elif event == "special":
        sub = roll_special_sub_event()
        if sub == "gust_spike":
            mult = random.uniform(*config.GUST_SPIKE_DMG_MULT_RANGE)
            dmg = base_dmg * mult
            log = "💥 Gió giật mạnh + mảnh vỡ bay! Sát thương đột biến."
        else:
            heal = random.uniform(*config.CALM_LULL_HEAL_RANGE)
            log = "🍃 Khoảng lặng gió — xe được sửa chữa tạm thời."
        state = sub

    dmg *= (1 - armor_reduction)
    return {"dmg": round(dmg, 1), "heal": round(heal, 1), "state": state, "log": log}


def compute_payout(
    car_base_rate: float,
    ef: int,
    elapsed_sec: int,
    destroyed: bool,
) -> dict:
    """Tính thưởng cuối session. Trả về {"money": int, "mango": int}"""
    minutes = elapsed_sec / 60.0
    mult = config.EF_SCALE[ef]["payout_mult"]
    money = car_base_rate * minutes * mult

    if destroyed:
        money *= config.DESTROYED_RISK_BONUS

    mango = int(minutes // config.MANGO_EVERY_MIN)

    return {"money": round(money), "mango": mango}
