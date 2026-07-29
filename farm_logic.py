import datetime
import random

import farm_config

def get_crop_stats(crop_type: str) -> dict:
    return farm_config.CROPS[crop_type]

def unlock_cost(crop_type: str) -> int:
    return farm_config.CROPS[crop_type]["unlock_cost"]

def water_cooldown_min(water_speed_level: int) -> int:
    w = farm_config.WATER_SPEED_UPGRADE
    val = farm_config.WATER_COOLDOWN_MIN - water_speed_level * w["cooldown_reduction_min_per_level"]
    return max(w["min_cooldown_min"], val)

def roll_water_progress(can_tier: str) -> float:
    lo, hi = farm_config.WATERING_CANS[can_tier]["progress_range"]
    progress = random.uniform(lo, hi)
    return round(progress, 1)

def upgrade_cost(kind: str, current_level: int) -> int:
    table = {
        "yield": farm_config.YIELD_UPGRADE,
        "water_speed": farm_config.WATER_SPEED_UPGRADE,
        "farmer": farm_config.FARMER_UPGRADE,
        "seller": farm_config.SELLER_UPGRADE,
        "collector": farm_config.COLLECTOR_UPGRADE,
    }[kind]
    return int(table["base_cost"] * (table["cost_growth"] ** current_level))

def farmer_stats(level: int) -> dict:
    f = farm_config.FARMER_UPGRADE
    work_duration = farm_config.FARMER_BASE["work_duration_min"] - level * f["work_duration_reduction_min_per_level"]
    job_wait = farm_config.FARMER_BASE["job_wait_sec"] - level * f["job_wait_reduction_sec_per_level"]
    return {
        "work_duration_min": max(f["min_work_duration_min"], work_duration),
        "job_wait_sec": max(f["min_job_wait_sec"], job_wait),
    }

def roll_produce_stage(crop_type: str) -> str:
    stages_cfg = farm_config.PRODUCE_STAGES[crop_type]
    return random.choices(stages_cfg["stages"], weights=stages_cfg["weights"], k=1)[0]

def roll_mutations(weather: str) -> list[str]:
    result = []
    weather_effect = farm_config.WEATHER_MUTATION_EFFECT.get(weather, {})

    # --- stackable ---
    for key, cfg in farm_config.MUTATIONS_STACKABLE.items():
        chance = cfg["base_chance"] + weather_effect.get(key, 0.0)
        if random.random() < chance:
            result.append(key)

    # --- exclusive ---
    exclusive_keys = list(farm_config.MUTATIONS_EXCLUSIVE.keys())
    random.shuffle(exclusive_keys)
    for key in exclusive_keys:
        cfg = farm_config.MUTATIONS_EXCLUSIVE[key]
        chance = cfg["base_chance"] + weather_effect.get(key, 0.0)
        if random.random() < chance:
            result.append(key)
            break  # chỉ 1 exclusive

    return result

def compute_produce_value(produce: str, mutations: list[str]) -> int:
    base = farm_config.PRODUCE_PRICES[produce]

    stackable_mult = 1.0
    for m in mutations:
        if m in farm_config.MUTATIONS_STACKABLE:
            stackable_mult += (farm_config.MUTATIONS_STACKABLE[m]["mult"] - 1.0)

    exclusive_mult = 1.0
    for m in mutations:
        if m in farm_config.MUTATIONS_EXCLUSIVE:
            exclusive_mult = farm_config.MUTATIONS_EXCLUSIVE[m]["mult"]
            break  # chỉ 1 exclusive

    value = base * stackable_mult * exclusive_mult
    return max(1, round(value))

def is_farmer_active(farmer: dict, now: datetime.datetime) -> bool:
    return is_npc_active(farmer, now)

def is_npc_active(npc: dict, now: datetime.datetime) -> bool:
    if not npc.get("hired"):
        return False
    if npc.get("permanent"):
        return True
    hired_until = npc.get("hired_until")
    if not hired_until:
        return False
    until = hired_until if isinstance(hired_until, datetime.datetime) else datetime.datetime.fromisoformat(hired_until)
    return now < until

def seller_stats(level: int) -> dict:
    s = farm_config.SELLER_UPGRADE
    cycle = farm_config.SELLER_BASE["cycle_min"] - level * s["cycle_reduction_min_per_level"]
    return {
        "cycle_min": max(s["min_cycle_min"], cycle),
        "price_multiplier": 1.0 + level * s["price_bonus_per_level"],
    }

def collector_stats(level: int) -> dict:
    c = farm_config.COLLECTOR_UPGRADE
    cycle = farm_config.COLLECTOR_BASE["cycle_min"] - level * c["cycle_reduction_min_per_level"]
    lo, hi = farm_config.COLLECTOR_BASE["seeds_per_cycle_range"]
    bonus = (level // 2) * c["extra_seed_max_per_2_levels"]
    return {
        "cycle_min": max(c["min_cycle_min"], cycle),
        "seeds_range": (lo, hi + bonus),
    }

def collector_allowed_crops(level: int, unlocked_crops: dict) -> list[str]:
    allowed = []
    for crop_id, required_level in farm_config.COLLECTOR_CROP_UNLOCK_LEVEL.items():
        if level >= required_level and unlocked_crops.get(crop_id):
            allowed.append(crop_id)
    return allowed

def roll_harvest_quantity(crop_type: str, yield_level: int) -> int:
    base_yield = farm_config.CROPS[crop_type]["base_yield"]
    chance = max(0.0, min(0.9, yield_level * farm_config.YIELD_UPGRADE["double_fruit_chance_per_level"]))
    return base_yield*2 if random.random() < chance else base_yield

def simulate_farmer_ticks(
    last_processed_at: datetime.datetime,
    now: datetime.datetime,
    work_duration_min: int,
    job_wait_sec: int,
    hired_until: datetime.datetime | None = None,
) -> int:
    effective_now = now
    if hired_until is not None and hired_until < now:
        effective_now = hired_until

    elapsed_sec = (effective_now - last_processed_at).total_seconds()
    cycle_sec = work_duration_min * 60 + job_wait_sec
    if cycle_sec <= 0 or elapsed_sec <= 0:
        return 0
    return int(elapsed_sec // cycle_sec)

def compute_passive_progress_gain(crop_type: str, last_tick_at: datetime.datetime, now: datetime.datetime) -> float:
    if now <= last_tick_at:
        return 0.0
    elapsed_min = (now - last_tick_at).total_seconds() / 60
    rate = farm_config.CROPS[crop_type]["passive_progress_per_min"]
    return elapsed_min * rate

def plot_unlock_cost(plot_id: int) -> dict:
    cfg = farm_config.PLOTS[plot_id]
    return {"cost": cfg["unlock_cost"], "currency": cfg["currency"]}

def farmer_can_work_plot(plot_id: int, farmer_level: int, plot_unlocked: bool) -> bool:
    if not plot_unlocked:
        return False
    required_level = farm_config.PLOTS[plot_id]["farmer_level_required"]
    return farmer_level >= required_level

def next_locked_plot(unlocked_plot_ids: set[int]) -> int | None:
    for pid in farm_config.PLOT_ORDER:
        if pid not in unlocked_plot_ids:
            return pid
    return None