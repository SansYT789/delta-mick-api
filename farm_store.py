"""
users/{user_id}/farm/
    unlocked_crops: {"mango": True, "lemon": False, "orange": False, "apple": False}
    seed_inventory: {"mango": 2, "lemon": 0, ...}   # số hạt giống đã mua, chưa trồng
    unlocked_plots: {"1": True, "2": False, ...}    # ô nào đã mở khoá bằng tiền
    plots: {
        "1": {
            "slots": [
                {
                    "planted": bool,
                    "seed_type": str | None,
                    "progress": float,
                    "last_water_at": iso | None,
                    "last_passive_tick_at": iso | None,   # mốc lazy-calc cho auto-grow thụ động
                    "active_sprinkler_tier": str | None,
                    "active_sprinkler_until": iso | None,
                },
                ... (SLOTS_PER_PLOT phần tử, mỗi slot 1 cây độc lập, có thể khác loại nhau)
            ]
        },
        "2": {...}, ..., "6": {...}
    }
    sprinkler_inventory: {"basic": 2, "rare": 1}
    watering_can: "basic" | "advanced"
    upgrades: {"yield_level": int, "water_speed_level": int}
    gear: {"scanner": bool, "mutation_plucker": bool, "wrench": bool, "net": bool, "lightning_rod": bool}
    farmer: {
        "hired": bool, "hired_until": iso | None, "permanent": bool, "level": int,
        "last_processed_at": iso | None,
        "auto_water": bool,   # nông dân bây giờ KHÔNG tự mua hạt, chỉ tự tưới (mới)
    }
    inventory: { "mango_ripe|giant,flooded": count, ... }

guilds/{guild_id}/weather/
    current: str
    changed_at: iso
    next_change_at: iso
"""

import datetime
import random

from firebase_admin import db

import farm_config

def _empty_slot() -> dict:
    return {
        "planted": False,
        "seed_type": None,
        "progress": 0.0,
        "last_water_at": None,
        "last_passive_tick_at": None,
        "active_sprinkler_tier": None,
        "active_sprinkler_until": None,
    }

def _empty_plot() -> dict:
    return {"slots": [_empty_slot() for _ in range(farm_config.SLOTS_PER_PLOT)]}

def _default_plots() -> dict:
    return {str(pid): _empty_plot() for pid in farm_config.PLOT_ORDER}

def _default_unlocked_plots() -> dict:
    return {str(pid): (pid == 1) for pid in farm_config.PLOT_ORDER}

DEFAULT_FARM_DATA = {
    "unlocked_crops": {"mango": True, "lemon": False, "orange": False, "apple": False},
    "seed_inventory": {"mango": 0, "lemon": 0, "orange": 0, "apple": 0},
    "unlocked_plots": _default_unlocked_plots(),
    "plots": _default_plots(),
    "sprinkler_inventory": {},
    "watering_can": "basic",
    "upgrades": {"yield_level": 0, "water_speed_level": 0},
    "gear": {
        "scanner": False, "mutation_plucker": False,
        "wrench": False, "net": False, "lightning_rod": False,
    },
    "farmer": {
        "hired": False, "hired_until": None, "permanent": False, "level": 0,
        "last_processed_at": None, "auto_water": False,
    },
    "inventory": {},
}

def _migrate_v1_to_v2(data: dict) -> dict:
    if "plot" in data and "plots" not in data:
        old_plot = data.pop("plot")
        old_crop_type = data.pop("crop_type", "mango")

        plots = _default_plots()
        slot0 = _empty_slot()
        slot0["planted"] = old_plot.get("planted", False)
        slot0["seed_type"] = old_plot.get("seed_type") or (old_crop_type if old_plot.get("planted") else None)
        slot0["progress"] = old_plot.get("progress", 0.0)
        slot0["last_water_at"] = old_plot.get("last_water_at")
        slot0["last_passive_tick_at"] = old_plot.get("last_water_at") or now_iso()
        slot0["active_sprinkler_tier"] = old_plot.get("active_sprinkler_tier")
        slot0["active_sprinkler_until"] = old_plot.get("active_sprinkler_until")
        plots["1"]["slots"][0] = slot0
        data["plots"] = plots
        data["unlocked_plots"] = _default_unlocked_plots()

    if "tools" in data and "gear" not in data:
        old_tools = data.pop("tools")
        data["gear"] = {
            "scanner": old_tools.get("scanner", False),
            "mutation_plucker": old_tools.get("mutation_plucker", False),
            "wrench": False,
            "net": False,
            "lightning_rod": False,
        }

    if "farmer" in data and "auto_water" not in data["farmer"]:
        data["farmer"]["auto_water"] = False

    return data

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
    data = _migrate_v1_to_v2(dict(data))
    merged = _deep_merge_defaults(data, DEFAULT_FARM_DATA)
    return merged

def update_farm_data(guild_id: int, user_id: int, patch: dict):
    _farm_ref(guild_id, user_id).update(patch)

def transaction_farm_data(guild_id: int, user_id: int, fn):
    ref = _farm_ref(guild_id, user_id)

    def _txn(current):
        current = _migrate_v1_to_v2(dict(current)) if current else {}
        merged = _deep_merge_defaults(current, DEFAULT_FARM_DATA)
        return fn(merged)

    return ref.transaction(_txn)

# ---------------- MANGO----------------
def get_mango(guild_id: int, user_id: int) -> int:
    val = _mango_ref(guild_id, user_id).get()
    return val or 0

def transaction_mango(guild_id: int, user_id: int, delta: int):
    """
    Trả về SỐ DƯ MỚI nếu giao dịch thành công.
    Trả về None nếu không đủ mango (delta âm khiến số dư < 0) — không có gì thay đổi.
    """
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
    """
    Trừ `cost` mango rồi áp dụng `apply_fn` lên farm_data, có COMPENSATING ROLLBACK:
    nếu apply_fn raise exception sau khi tiền đã bị trừ, tự động hoàn lại mango ngay.
    Loại bỏ hoàn toàn trường hợp "mất tiền vĩnh viễn mà không nhận item" của code cũ,
    vốn tách 2 lời gọi transaction_mango + transaction_farm_data độc lập không rollback.
    """
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