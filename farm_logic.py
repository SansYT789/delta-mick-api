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

def roll_water_progress(can_tier: str, sprinkler_active: bool, sprinkler_tier: str | None) -> float:
    lo, hi = farm_config.WATERING_CANS[can_tier]["progress_range"]
    progress = random.uniform(lo, hi)
    if sprinkler_active and sprinkler_tier:
        progress += farm_config.SPRINKLERS[sprinkler_tier]["progress_boost"]
    return round(progress, 1)

def upgrade_cost(kind: str, current_level: int) -> int:
    table = {
        "yield": farm_config.YIELD_UPGRADE,
        "water_speed": farm_config.WATER_SPEED_UPGRADE,
        "farmer": farm_config.FARMER_UPGRADE,
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

def roll_mutations(weather: str, sprinkler_active: bool, sprinkler_tier: str | None) -> list[str]:
    result = []
    weather_effect = farm_config.WEATHER_MUTATION_EFFECT.get(weather, {})

    # --- stackable ---
    for key, cfg in farm_config.MUTATIONS_STACKABLE.items():
        chance = cfg["base_chance"] + weather_effect.get(key, 0.0)
        if key == "flooded" and sprinkler_active and sprinkler_tier:
            chance += farm_config.SPRINKLERS[sprinkler_tier]["flood_mutation_chance"]
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
            break  # chỉ có tối đa 1 exclusive trong list

    value = base * stackable_mult * exclusive_mult
    return max(1, round(value))

def is_farmer_active(farmer: dict, now: datetime.datetime) -> bool:
    """Farmer còn hoạt động không: đã thuê VÀ (permanent HOẶC chưa hết hạn thuê)."""
    if not farmer.get("hired"):
        return False
    if farmer.get("permanent"):
        return True
    hired_until = farmer.get("hired_until")
    if not hired_until:
        return False
    until = hired_until if isinstance(hired_until, datetime.datetime) else datetime.datetime.fromisoformat(hired_until)
    return now < until

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
    """
    Tính số 'vòng việc' farmer đã hoàn thành từ last_processed_at đến now.
    Mỗi vòng = work_duration_min phút làm + job_wait_sec giây chờ.
    Nếu hired_until được truyền (thuê tạm thời, không permanent), việc chỉ được tính
    tới thời điểm hired_until — farmer không làm việc sau khi hết hạn thuê.
    Trả về số vòng đã hoàn thành (làm tròn xuống).
    """
    effective_now = now
    if hired_until is not None and hired_until < now:
        effective_now = hired_until

    elapsed_sec = (effective_now - last_processed_at).total_seconds()
    cycle_sec = work_duration_min * 60 + job_wait_sec
    if cycle_sec <= 0 or elapsed_sec <= 0:
        return 0
    return int(elapsed_sec // cycle_sec)

# ---------------- MULTI-PLOT: PASSIVE GROWTH ----------------
def compute_passive_progress_gain(crop_type: str, last_tick_at: datetime.datetime, now: datetime.datetime) -> float:
    """
    Tính progress tự tăng thụ động (KHÔNG cần tưới) từ last_tick_at đến now,
    dựa trên passive_progress_per_min của crop_type. Luôn >= 0.
    """
    if now <= last_tick_at:
        return 0.0
    elapsed_min = (now - last_tick_at).total_seconds() / 60
    rate = farm_config.CROPS[crop_type]["passive_progress_per_min"]
    return elapsed_min * rate

def plot_unlock_cost(plot_id: int) -> dict:
    """Trả về {'cost': int, 'currency': 'mango'|'mango_plus'} cho ô đất."""
    cfg = farm_config.PLOTS[plot_id]
    return {"cost": cfg["unlock_cost"], "currency": cfg["currency"]}

def farmer_can_work_plot(plot_id: int, farmer_level: int, plot_unlocked: bool) -> bool:
    """
    Farmer chỉ được tự động làm việc ở 1 ô nếu CẢ HAI điều kiện đều đúng:
    1. Ô đã được mở khoá bằng tiền (plot_unlocked).
    2. Level nông dân >= farmer_level_required của ô đó.
    """
    if not plot_unlocked:
        return False
    required_level = farm_config.PLOTS[plot_id]["farmer_level_required"]
    return farmer_level >= required_level


def next_locked_plot(unlocked_plot_ids: set[int]) -> int | None:
    """Trả về ID ô tiếp theo cần mở khoá (mở khoá tuần tự), hoặc None nếu đã mở hết."""
    for pid in farm_config.PLOT_ORDER:
        if pid not in unlocked_plot_ids:
            return pid
    return None