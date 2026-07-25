"""
Schema:
users/{user_id}/farm/
    crop_type: "mango" | "lemon"          # cây đang active
    unlocked_crops: {"mango": True, "lemon": False}
    seed_inventory: {"mango": 2, "lemon": 0}   # số hạt giống đã mua, chưa trồng
    plot: {
        planted: bool,
        seed_type: str | None,
        progress: float,
        last_water_at: iso | None,
        active_sprinkler_tier: str | None,     # sprinkler ĐANG kích hoạt trên đất (None = tắt)
        active_sprinkler_until: iso | None,
    }
    sprinkler_inventory: {"basic": 2, "rare": 1}   # sprinkler đã mua, chưa dùng hết / đang chờ kích hoạt
    watering_can: "basic" | "advanced"
    upgrades: {
        "yield_level": int,
        "water_speed_level": int,
    }
    tools: {"scanner": bool, "mutation_plucker": bool}
    farmer: {
        "hired": bool,
        "hired_until": iso | None,     # hết hạn thuê (None nếu permanent hoặc chưa thuê)
        "permanent": bool,             # đã nâng cấp vĩnh viễn (100k mango) hay chưa
        "level": int,
        "last_processed_at": iso | None,   # mốc lazy-calc
    }
    inventory: { "mango_ripe|giant,flooded": count, ... }  # key format: "produce|mut1,mut2" (sorted mutations)

guilds/{guild_id}/weather/
    current: str
    changed_at: iso
    next_change_at: iso
"""

import datetime
import random

from firebase_admin import db

import farm_config

DEFAULT_FARM_DATA = {
    "crop_type": "mango",
    "unlocked_crops": {"mango": True, "lemon": False, "orange": False, "apple": False},
    "seed_inventory": {"mango": 0, "lemon": 0, "orange": 0, "apple": 0},
    "plot": {
        "planted": False,
        "seed_type": None,
        "progress": 0.0,
        "last_water_at": None,
        "active_sprinkler_tier": None,
        "active_sprinkler_until": None,
    },
    "sprinkler_inventory": {},
    "watering_can": "basic",
    "upgrades": {"yield_level": 0, "water_speed_level": 0},
    "tools": {"scanner": False, "mutation_plucker": False},
    "farmer": {"hired": False, "hired_until": None, "permanent": False, "level": 0, "last_processed_at": None},
    "inventory": {},
}

def _farm_ref(guild_id: int, user_id: int):
    return db.reference(f"users/{user_id}/farm")

def _mango_ref(guild_id: int, user_id: int):
    return db.reference(f"users/{user_id}/mango")

def _weather_ref(guild_id: int):
    return db.reference(f"guilds/{guild_id}/weather")

def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()

def parse_iso(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s)

def _deep_merge_defaults(data: dict, defaults: dict) -> dict:
    merged = dict(defaults)
    if not data:
        return merged
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(defaults.get(k), dict):
            sub = dict(defaults[k])
            sub.update(v)
            merged[k] = sub
        else:
            merged[k] = v
    return merged

def get_farm_data(guild_id: int, user_id: int) -> dict:
    ref = _farm_ref(guild_id, user_id)
    data = ref.get()
    if data is None:
        ref.set(DEFAULT_FARM_DATA)
        return dict(DEFAULT_FARM_DATA)
    return _deep_merge_defaults(data, DEFAULT_FARM_DATA)

def update_farm_data(guild_id: int, user_id: int, patch: dict):
    _farm_ref(guild_id, user_id).update(patch)

def transaction_farm_data(guild_id: int, user_id: int, fn):
    ref = _farm_ref(guild_id, user_id)

    def _txn(current):
        merged = _deep_merge_defaults(current, DEFAULT_FARM_DATA)
        return fn(merged)

    return ref.transaction(_txn)

# ---------------- MANGO----------------
def get_mango(guild_id: int, user_id: int) -> int:
    val = _mango_ref(guild_id, user_id).get()
    return val or 0

def transaction_mango(guild_id: int, user_id: int, delta: int):
    ref = _mango_ref(guild_id, user_id)
    failed = {"insufficient": False}

    def _txn(current):
        current = current or 0
        new_val = current + delta
        if new_val < 0:
            failed["insufficient"] = True
            return current
        return new_val

    result = ref.transaction(_txn)
    if failed["insufficient"]:
        return None
    return result

def spend_mango_and_apply(guild_id: int, user_id: int, cost: int, apply_fn) -> tuple[bool, str]:
    if cost < 0:
        raise ValueError("cost phải >= 0")

    if cost > 0:
        new_balance = transaction_mango(guild_id, user_id, -cost)
        if new_balance is None:
            return False, "Không đủ mango."

    try:
        transaction_farm_data(guild_id, user_id, apply_fn)
    except Exception:
        if cost > 0:
            transaction_mango(guild_id, user_id, cost)  # hoàn tiền
        return False, "Có lỗi xảy ra khi xử lý, giao dịch đã được hoàn tác."

    return True, ""

def set_mango(guild_id: int, user_id: int, amount: int):
    amount = max(0, int(amount))
    _mango_ref(guild_id, user_id).set(amount)
    return amount

# ---------------- INVENTORY ----------------
def inventory_key(produce: str, mutations: list[str]) -> str:
    sorted_muts = ",".join(sorted(mutations)) if mutations else ""
    return f"{produce}|{sorted_muts}"

def parse_inventory_key(key: str) -> tuple[str, list[str]]:
    produce, _, muts = key.partition("|")
    mutations = muts.split(",") if muts else []
    return produce, mutations

def add_to_inventory(guild_id: int, user_id: int, produce: str, mutations: list[str], qty: int = 1):
    key = inventory_key(produce, mutations)

    def _add(d):
        d.setdefault("inventory", {})
        d["inventory"][key] = d["inventory"].get(key, 0) + qty
        return d

    return transaction_farm_data(guild_id, user_id, _add)

def remove_from_inventory(guild_id: int, user_id: int, key: str, qty: int) -> bool:
    result_holder = {"ok": False}

    def _remove(d):
        inv = d.setdefault("inventory", {})
        have = inv.get(key, 0)
        if have < qty:
            result_holder["ok"] = False
            return d
        remaining = have - qty
        if remaining <= 0:
            inv.pop(key, None)
        else:
            inv[key] = remaining
        result_holder["ok"] = True
        return d

    transaction_farm_data(guild_id, user_id, _remove)
    return result_holder["ok"]

# ---------------- WEATHER ----------------
def _roll_weather() -> str:
    types = list(farm_config.WEATHER_TYPES.keys())
    weights = [farm_config.WEATHER_TYPES[t]["weight"] for t in types]
    return random.choices(types, weights=weights, k=1)[0]

def get_current_weather(guild_id: int) -> str:
    ref = _weather_ref(guild_id)
    data = ref.get()
    now = datetime.datetime.utcnow()

    if data is None or "next_change_at" not in data:
        new_weather = _roll_weather()
        next_change = now + datetime.timedelta(minutes=farm_config.WEATHER_CYCLE_MIN)
        ref.set({
            "current": new_weather,
            "changed_at": now.isoformat(),
            "next_change_at": next_change.isoformat(),
        })
        return new_weather

    next_change_at = parse_iso(data["next_change_at"])
    if now >= next_change_at:
        new_weather = _roll_weather()
        next_change = now + datetime.timedelta(minutes=farm_config.WEATHER_CYCLE_MIN)
        ref.update({
            "current": new_weather,
            "changed_at": now.isoformat(),
            "next_change_at": next_change.isoformat(),
        })
        return new_weather

    return data["current"]