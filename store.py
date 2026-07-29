import datetime
import random
import uuid
import copy

from firebase_admin import db

import farm_config

OWNER_IDS = {985004175110848512}
MAX_LOG_ENTRIES = 20
LIXI_DURATION_MIN = 10

MANGO_TO_PLUS_RATE = 0.1       # 1 mango -> 0.1 mango+
PLUS_TO_MANGO_RATE = 7         # 1 mango+ -> 7 mango

WORK_COOLDOWN_HOURS = 24
STREAK_BONUS_PER_WEEK = 0.02   # +2%/tuần, cộng dồn
MAX_POSITION_LEVEL = 9         # 0..9: lao công -> ... -> chủ tịch

COMPANIES = {
    "delta": {
        "name": "Tập đoàn Delta",
        "base_pay": (80, 140),
    },
    "mango_mustard": {
        "name": "Tập đoàn Mango Mustard",
        "base_pay": (60, 110),
    },
    "beast": {
        "name": "Công ty thành phẩm Beast",
        "base_pay": (70, 120),
    },
    "olivier": {
        "name": "Công ty thực vật Ô liu",
        "base_pay": (50, 90),
    },
    "phonk": {
        "name": "Tập đoàn Phonk",
        "base_pay": (90, 150),
    },
    "one_more_game": {
        "name": "Công ty One More Game",
        "base_pay": (65, 130),
    },
    "nova": {
        "name": "Tập đoàn Nova Technology",
        "base_pay": (120, 200),
    },
    "cyber_core": {
        "name": "Công ty Cyber Core",
        "base_pay": (150, 260),
    },
    "golden_leaf": {
        "name": "Tập đoàn Golden Leaf",
        "base_pay": (100, 180),
    },
    "storm": {
        "name": "Tập đoàn Storm Industries",
        "base_pay": (180, 320),
    },
    "quantum": {
        "name": "Công ty Quantum Labs",
        "base_pay": (250, 450),
    },
    "mango_global": {
        "name": "Mango Global Corporation",
        "base_pay": (350, 600),
    },
    "elite_group": {
        "name": "Tập đoàn Elite Group",
        "base_pay": (500, 900),
    },
}

POSITION_NAMES = [
    "Lao công",
    "Nhân viên",
    "Nhân viên cấp cao",
    "Trưởng nhóm",
    "Trưởng phòng",
    "Quản lý",
    "Giám đốc",
    "Phó tổng giám đốc",
    "Tổng giám đốc",
    "Chủ tịch",
]
POSITION_BUFFS = [
    0.00, # Lao công
    0.08, # Nhân viên
    0.15, # Nhân viên cấp cao
    0.25, # Trưởng nhóm
    0.35, # Trưởng phòng
    0.50, # Quản lý
    0.70, # Giám đốc
    1.00, # Phó tổng
    1.40, # Tổng giám đốc
    2.00, # Chủ tịch
]

# sự kiện xui: (tên, mô tả, cooldown phạt giờ)
BAD_EVENTS = [
    {
        "key": "crisis_911",
        "text": "💥 Sự kiện bất khả kháng xảy ra tại công ty — toàn bộ nhân viên phải sơ tán khẩn cấp.",
        "penalty_hours": 72,
        "chance": 0.03,
    },
    {
        "key": "boss_bankrupt",
        "text": "📉 Sếp vỡ nợ và bỏ trốn — công ty tạm ngừng hoạt động, bạn cần tìm việc khác.",
        "penalty_hours": 48,
        "chance": 0.05,
    },
    {
        "key": "company_layoff",
        "text": "✂️ Công ty cắt giảm nhân sự lớn — bạn bị tạm cho nghỉ để tái cơ cấu.",
        "penalty_hours": 36,
        "chance": 0.08,
    },
    {
        "key": "server_crash",
        "text": "🖥️ Hệ thống công ty bị sập nghiêm trọng — toàn bộ công việc bị đình trệ.",
        "penalty_hours": 24,
        "chance": 0.10,
    },
    {
        "key": "legal_problem",
        "text": "⚖️ Công ty gặp vấn đề pháp lý — hoạt động bị điều tra và tạm dừng.",
        "penalty_hours": 60,
        "chance": 0.04,
    },
    {
        "key": "strike",
        "text": "📢 Nhân viên đình công — công ty đóng cửa tạm thời để giải quyết tranh chấp.",
        "penalty_hours": 30,
        "chance": 0.07,
    },
    {
        "key": "market_crash",
        "text": "📉 Thị trường lao dốc — công ty giảm tốc độ hoạt động và đóng băng dự án.",
        "penalty_hours": 40,
        "chance": 0.06,
    },
    {
        "key": "data_breach",
        "text": "🔓 Công ty bị rò rỉ dữ liệu — mọi hoạt động bị kiểm tra bảo mật.",
        "penalty_hours": 18,
        "chance": 0.12,
    },
    {
        "key": "equipment_failure",
        "text": "🔧 Thiết bị quan trọng bị hỏng — bạn không thể tiếp tục công việc bình thường.",
        "penalty_hours": 12,
        "chance": 0.15,
    },
    {
        "key": "bad_manager",
        "text": "😡 Quản lý mới quá khắt khe — hiệu suất làm việc giảm mạnh.",
        "penalty_hours": 20,
        "chance": 0.10,
    },
]

# Farm
def _empty_slot() -> dict:
    return {
        "planted": False,
        "seed_type": None,
        "progress": 0.0,
        "last_water_at": None,
        "last_passive_tick_at": None,
    }

def _empty_plot() -> dict:
    return {"slots": [_empty_slot() for _ in range(farm_config.SLOTS_PER_PLOT)]}

def _default_plots() -> dict:
    return {str(pid): _empty_plot() for pid in farm_config.PLOT_ORDER}

def _default_unlocked_plots() -> dict:
    return {str(pid): (pid == 1) for pid in farm_config.PLOT_ORDER}

DEFAULT_FARM_DATA = {
    "unlocked_crops": {"mango": True, "lemon": False, "orange": False, "apple": False, "grape": False, "watermelon": False, "carrot": False, "dragonfruit": False, "coconut": False, "durian": False},
    "seed_inventory": {"mango": 0, "lemon": 0, "orange": 0, "apple": 0, "grape": 0, "watermelon": 0, "carrot": 0, "dragonfruit": 0, "coconut": 0, "durian": 0},
    "unlocked_plots": _default_unlocked_plots(),
    "plots": _default_plots(),
    "watering_can": "basic",
    "upgrades": {"yield_level": 0, "water_speed_level": 0},
    "gear": {
        "scanner": False, "mutation_plucker": False,
        "wrench": False, "net": False, "lightning_rod": False,
    },
    "farmer": {
        "hired": False, "hired_until": None, "permanent": False, "level": 0,
        "last_processed_at": None,
    },
    "seller": {
        "hired": False, "hired_until": None, "permanent": False, "level": 0,
        "last_processed_at": None,
    },
    "collector": {
        "hired": False, "hired_until": None, "permanent": False, "level": 0,
        "last_processed_at": None,
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

    return data

def _farm_ref(user_id: int):
    return db.reference(f"users/{user_id}/farm")

def _weather_ref(guild_id: int):
    return db.reference(f"guilds/{guild_id}/weather")

def _deep_merge_defaults(data: dict, defaults: dict) -> dict:
    merged = copy.deepcopy(defaults)
    if not data:
        return merged
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(defaults.get(k), dict):
            sub = copy.deepcopy(defaults[k])
            sub.update(copy.deepcopy(v))
            merged[k] = sub
        else:
            merged[k] = copy.deepcopy(v) if isinstance(v, (dict, list)) else v
    return merged

def get_farm_data(user_id: int) -> dict:
    ref = _farm_ref(user_id)
    data = ref.get()
    if data is None:
        fresh_default = copy.deepcopy(DEFAULT_FARM_DATA)
        ref.set(fresh_default)
        return fresh_default
    data = _migrate_v1_to_v2(dict(data))
    merged = _deep_merge_defaults(data, DEFAULT_FARM_DATA)
    return merged

def update_farm_data(user_id: int, patch: dict):
    _farm_ref(user_id).update(patch)

def transaction_farm_data(user_id: int, fn):
    ref = _farm_ref(user_id)

    def _txn(current):
        current = _migrate_v1_to_v2(dict(current)) if current else {}
        merged = _deep_merge_defaults(current, DEFAULT_FARM_DATA)
        return fn(merged)

    return ref.transaction(_txn)

# Inventory
def inventory_key(produce: str, mutations: list[str]) -> str:
    sorted_muts = ",".join(sorted(mutations)) if mutations else ""
    return f"{produce}|{sorted_muts}"

def parse_inventory_key(key: str) -> tuple[str, list[str]]:
    produce, _, muts = key.partition("|")
    mutations = muts.split(",") if muts else []
    return produce, mutations

def add_to_inventory(user_id: int, produce: str, mutations: list[str], qty: int = 1):
    key = inventory_key(produce, mutations)

    def _add(d):
        d.setdefault("inventory", {})
        d["inventory"][key] = d["inventory"].get(key, 0) + qty
        return d

    return transaction_farm_data(user_id, _add)

def remove_from_inventory(user_id: int, key: str, qty: int) -> bool:
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

    transaction_farm_data(user_id, _remove)
    return result_holder["ok"]

# Weather
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

# Utility
def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()

def parse_iso(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s)

def _mango_ref(user_id: int):
    return db.reference(f"users/{user_id}/mango")

def _mango_plus_ref(user_id: int):
    return db.reference(f"users/{user_id}/mango_plus")

def get_mango(user_id: int) -> int:
    val = _mango_ref(user_id).get()
    return val or 0

def get_mango_plus(user_id: int) -> int:
    val = _mango_plus_ref(user_id).get()
    return val or 0

def transaction_mango(user_id: int, delta: int, use_plus: bool = False):
    """
    Trả về SỐ DƯ MỚI nếu giao dịch thành công.
    Trả về None nếu không đủ tiền (delta âm khiến số dư < 0) — không có gì thay đổi.
    """
    ref = _mango_plus_ref(user_id) if use_plus else _mango_ref(user_id)
    failed = {"insufficient": False}

    def _txn(current):
        current = current or 0
        new_val = current + delta
        if new_val < 0:
            failed["insufficient"] = True
            return current  # giữ nguyên, không cho phép âm
        return new_val

    result = ref.transaction(_txn)
    if failed["insufficient"]:
        return None
    return result

def convert_mango_to_plus(user_id: int, mango_amount: int) -> tuple[bool, str, int]:
    if mango_amount <= 0:
        return False, "Số lượng phải lớn hơn 0.", 0

    plus_gained = int(mango_amount * MANGO_TO_PLUS_RATE)
    if plus_gained <= 0:
        return False, f"Cần ít nhất {int(1 / MANGO_TO_PLUS_RATE)} 🥭 để đổi được 1 mango+.", 0

    new_mango_balance = transaction_mango(user_id, -mango_amount)
    if new_mango_balance is None:
        return False, "Không đủ mango.", 0

    new_plus_balance = transaction_mango(user_id, plus_gained, use_plus=True)
    if new_plus_balance is None:
        transaction_mango(user_id, mango_amount)
        return False, "Có lỗi xảy ra, giao dịch đã được hoàn tác.", 0

    return True, "", plus_gained

def convert_plus_to_mango(user_id: int, plus_amount: int) -> tuple[bool, str, int]:
    if plus_amount <= 0:
        return False, "Số lượng phải lớn hơn 0.", 0

    mango_gained = plus_amount * PLUS_TO_MANGO_RATE

    new_plus_balance = transaction_mango(user_id, -plus_amount, use_plus=True)
    if new_plus_balance is None:
        return False, "Không đủ mango+.", 0

    new_mango_balance = transaction_mango(user_id, mango_gained)
    if new_mango_balance is None:
        transaction_mango(user_id, plus_amount, use_plus=True)  # hoàn tác
        return False, "Có lỗi xảy ra, giao dịch đã được hoàn tác.", 0

    return True, "", mango_gained

def spend_mango_and_apply(user_id: int, cost: int, apply_fn, label: str | None = None) -> tuple[bool, str]:
    if cost < 0:
        raise ValueError("cost phải >= 0")

    if cost > 0:
        new_balance = transaction_mango(user_id, -cost)
        if new_balance is None:
            return False, "Không đủ mango."

    try:
        transaction_farm_data(user_id, apply_fn)
    except Exception:
        if cost > 0:
            transaction_mango(user_id, cost)  # hoàn tiền
        return False, "Có lỗi xảy ra khi xử lý, giao dịch đã được hoàn tác."

    if label and cost > 0:
        log_purchase(user_id, label, cost, "mango")

    return True, ""

def set_mango(user_id: int, amount: int):
    amount = max(0, int(amount))
    _mango_ref(user_id).set(amount)
    return amount

def get_all_mango_data() -> dict:
    """Trả về toàn bộ node 'users' để /rank quét top mango. Đọc full-table, tốn tài nguyên khi scale lớn."""
    return db.reference("users").get() or {}

# Work
def _work_ref(user_id: int):
    return db.reference(f"users/{user_id}/work")

DEFAULT_WORK_DATA = {
    "last_worked_at": None,
    "current_company": None,
    "streak_weeks": 0,
    "position_level": 0,
    "company_cooldown_until": {},
}

def get_work_data(user_id: int) -> dict:
    data = _work_ref(user_id).get()
    if data is None:
        return dict(DEFAULT_WORK_DATA)
    merged = dict(DEFAULT_WORK_DATA)
    merged.update(data)
    merged.setdefault("company_cooldown_until", {})
    return merged

def get_work_cooldown_remaining_sec(user_id: int) -> int:
    data = get_work_data(user_id)
    last = data.get("last_worked_at")
    if not last:
        return 0
    elapsed = (datetime.datetime.utcnow() - parse_iso(last)).total_seconds()
    remaining = WORK_COOLDOWN_HOURS * 3600 - elapsed
    return max(0, int(remaining))

def get_company_penalty_remaining_sec(user_id: int, company_id: str) -> int:
    data = get_work_data(user_id)
    until = data.get("company_cooldown_until", {}).get(company_id)
    if not until:
        return 0
    remaining = (parse_iso(until) - datetime.datetime.utcnow()).total_seconds()
    return max(0, int(remaining))

def _update_work_data(user_id: int, fn):
    ref = db.reference(f"users/{user_id}")

    def _txn(current):
        current = current or {}
        current.setdefault("work", dict(DEFAULT_WORK_DATA))
        return fn(current)

    return ref.transaction(_txn)

def do_work(user_id: int, company_id: str) -> dict:
    if company_id not in COMPANIES:
        return {"ok": False, "message": "Công ty không tồn tại."}

    remaining = get_work_cooldown_remaining_sec(user_id)
    if remaining > 0:
        return {"ok": False, "message": f"cooldown:{remaining}"}

    penalty_remaining = get_company_penalty_remaining_sec(user_id, company_id)
    if penalty_remaining > 0:
        return {"ok": False, "message": f"company_penalty:{penalty_remaining}"}

    now = datetime.datetime.utcnow()
    data = get_work_data(user_id)

    same_company = data.get("current_company") == company_id
    last_worked = data.get("last_worked_at")
    streak_weeks = data.get("streak_weeks", 0)

    if same_company and last_worked:
        days_since = (now - parse_iso(last_worked)).total_seconds() / 86400
        if days_since <= 14:
            streak_weeks = min(streak_weeks + 1, 520)
        else:
            streak_weeks = 0
    else:
        streak_weeks = 0

    position_level = data.get("position_level", 0)

    triggered_event = None
    for event in BAD_EVENTS:
        if random.random() < event["chance"]:
            triggered_event = event
            break

    company_cooldowns = dict(data.get("company_cooldown_until", {}))

    if triggered_event:
        penalty_until = (now + datetime.timedelta(hours=triggered_event["penalty_hours"])).isoformat()
        company_cooldowns[company_id] = penalty_until

        def _apply_event(d):
            d.setdefault("work", dict(DEFAULT_WORK_DATA))
            d["work"]["last_worked_at"] = now.isoformat()
            d["work"]["current_company"] = company_id
            d["work"]["streak_weeks"] = 0
            d["work"]["position_level"] = position_level
            d["work"]["company_cooldown_until"] = company_cooldowns
            return d

        _update_work_data(user_id, _apply_event)
        return {
            "ok": True,
            "pay": 0,
            "event": triggered_event,
            "streak_weeks": 0,
            "position_level": position_level,
            "company_name": COMPANIES[company_id]["name"],
        }

    lo, hi = COMPANIES[company_id]["base_pay"]
    base_pay = random.randint(lo, hi)
    streak_mult = 1.0 + streak_weeks * STREAK_BONUS_PER_WEEK
    position_mult = 1.0 + position_level * POSITION_BUFF_PER_LEVEL
    pay = max(1, round(base_pay * streak_mult * position_mult))

    def _apply(d):
        d.setdefault("work", dict(DEFAULT_WORK_DATA))
        d["work"]["last_worked_at"] = now.isoformat()
        d["work"]["current_company"] = company_id
        d["work"]["streak_weeks"] = streak_weeks
        d["work"]["position_level"] = position_level
        d["work"]["company_cooldown_until"] = company_cooldowns
        return d

    _update_work_data(user_id, _apply)
    transaction_mango(user_id, pay)

    return {
        "ok": True,
        "pay": pay,
        "event": None,
        "streak_weeks": streak_weeks,
        "position_level": position_level,
        "company_name": COMPANIES[company_id]["name"],
    }

def promote_position(user_id: int) -> tuple[bool, str]:
    data = get_work_data(user_id)
    level = data.get("position_level", 0)
    if level >= MAX_POSITION_LEVEL:
        return False, "Đã đạt chức vụ cao nhất."

    def _promote(d):
        d.setdefault("work", dict(DEFAULT_WORK_DATA))
        d["work"]["position_level"] = d["work"].get("position_level", 0) + 1
        return d

    _update_work_data(user_id, _promote)
    return True, POSITION_NAMES[level + 1]

# Lixi
def _lixi_ref(envelope_id: str | None = None):
    if envelope_id:
        return db.reference(f"lixi/{envelope_id}")
    return db.reference("lixi")

def create_lixi(guild_id: int, channel_id: int, creator_id: int, amount: int, currency: str = "mango") -> tuple[bool, str, str | None]:
    if currency not in ("mango", "mango_plus"):
        return False, "Loại tiền tệ không hợp lệ.", None
    if amount <= 0:
        return False, "Số lượng phải lớn hơn 0.", None

    if currency == "mango":
        new_balance = transaction_mango(creator_id, -amount)
    else:
        new_balance = transaction_mango(creator_id, -amount, use_plus=True)
    if new_balance is None:
        return False, f"Không đủ {'mango' if currency == 'mango' else 'mango+'}.", None

    envelope_id = uuid.uuid4().hex[:12]
    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(minutes=LIXI_DURATION_MIN)

    envelope = {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "creator_id": creator_id,
        "currency": currency,
        "total_amount": amount,
        "remaining_amount": amount,
        "claimed_by": {},        # {user_id_str: amount}
        "claimed_order": [],     # [user_id_str, ...] theo thứ tự nhận, dùng để hiển thị danh sách
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "closed": False,
    }
    _lixi_ref(envelope_id).set(envelope)
    return True, "", envelope_id

def get_lixi(envelope_id: str) -> dict | None:
    return _lixi_ref(envelope_id).get()

def claim_lixi(envelope_id: str, user_id: int) -> tuple[bool, str, int]:
    ref = _lixi_ref(envelope_id)
    result_holder = {"amount": 0, "error": None, "currency": "mango"}

    def _txn(envelope):
        if envelope is None:
            result_holder["error"] = "Lì xì không tồn tại."
            return envelope

        if envelope.get("creator_id") == user_id:
            result_holder["error"] = "Bạn không thể tự nhận lì xì của chính mình."
            return envelope

        now = datetime.datetime.utcnow()
        if envelope.get("closed") or parse_iso(envelope["expires_at"]) <= now:
            envelope["closed"] = True
            result_holder["error"] = "Lì xì đã hết hạn hoặc đã đóng."
            return envelope

        claimed_by = envelope.get("claimed_by", {})
        if str(user_id) in claimed_by:
            result_holder["error"] = "Bạn đã nhận lì xì này rồi."
            return envelope

        remaining = envelope.get("remaining_amount", 0)
        if remaining <= 0:
            envelope["closed"] = True
            result_holder["error"] = "Lì xì đã hết."
            return envelope

        max_share = max(1, remaining // 3) if remaining > 3 else remaining
        share = random.randint(1, max(1, min(max_share, remaining)))
        share = min(share, remaining)

        envelope["remaining_amount"] = remaining - share
        claimed_by[str(user_id)] = share
        envelope["claimed_by"] = claimed_by
        envelope.setdefault("claimed_order", []).append(str(user_id))
        if envelope["remaining_amount"] <= 0:
            envelope["closed"] = True

        result_holder["amount"] = share
        result_holder["currency"] = envelope.get("currency", "mango")
        return envelope

    ref.transaction(_txn)

    if result_holder["error"]:
        return False, result_holder["error"], 0

    amount = result_holder["amount"]
    if result_holder["currency"] == "mango":
        transaction_mango(user_id, amount)
    else:
        transaction_mango(user_id, amount, use_plus=True)
    return True, "", amount

def refund_expired_lixi(envelope_id: str) -> int:
    ref = _lixi_ref(envelope_id)
    result_holder = {"refund": 0, "creator_id": None, "currency": "mango"}

    def _txn(envelope):
        if envelope is None or envelope.get("closed"):
            return envelope
        remaining = envelope.get("remaining_amount", 0)
        envelope["closed"] = True
        result_holder["refund"] = remaining
        result_holder["creator_id"] = envelope.get("creator_id")
        result_holder["currency"] = envelope.get("currency", "mango")
        envelope["remaining_amount"] = 0
        return envelope

    ref.transaction(_txn)

    refund = result_holder["refund"]
    creator_id = result_holder["creator_id"]
    if refund > 0 and creator_id:
        if result_holder["currency"] == "mango":
            transaction_mango(creator_id, refund)
        else:
            transaction_mango(creator_id, refund, use_plus=True)
    return refund

# Bill
def _log_ref(user_id: int):
    return db.reference(f"users/{user_id}/purchase_log")

def log_purchase(user_id: int, label: str, cost: int, currency: str = "mango") -> None:
    if cost <= 0:
        return #Không log miễn phí

    ref = _log_ref(user_id)

    def _txn(current):
        current = current or []
        current = list(current)
        current.append({
            "label": label,
            "cost": cost,
            "currency": currency,
            "at": now_iso(),
        })
        if len(current) > MAX_LOG_ENTRIES:
            current = current[-MAX_LOG_ENTRIES:]
        return current

    ref.transaction(_txn)

def get_purchase_log(user_id: int, limit: int = 20) -> list[dict]:
    data = _log_ref(user_id).get() or []
    return list(reversed(data))[:limit]

# Locked
def _locked_ref():
    return db.reference("bot_config/locked_commands")

def get_locked_commands() -> dict:
    data = _locked_ref().get()
    return data or {}

def is_locked(command_name: str) -> bool:
    locked = get_locked_commands()
    return bool(locked.get(command_name, False))

def lock_command(command_name: str) -> None:
    _locked_ref().update({command_name: True})

def unlock_command(command_name: str) -> None:
    ref = _locked_ref()
    current = ref.get() or {}
    if command_name in current:
        current.pop(command_name)
        ref.set(current)

def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS