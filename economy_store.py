"""
users/{user_id}/mango_plus: int

users/{user_id}/work/
    last_worked_at: iso | None      # cooldown chung, không theo từng công ty
    current_company: str | None     # công ty đang gắn streak
    streak_weeks: int               # số tuần liên tục làm việc (cùng công ty)
    position_level: int             # 0 = lao công ... max = chủ tịch
    company_cooldown_until: {company_id: iso}  # cooldown riêng khi bị sự kiện xui (nghỉ việc công ty đó)

lixi/{envelope_id}/
    guild_id: int
    channel_id: int
    creator_id: int
    total_amount: int
    remaining_amount: int
    claimed_by: {user_id: amount}
    created_at: iso
    expires_at: iso
    closed: bool
"""

import datetime
import random
import uuid

from firebase_admin import db

MANGO_TO_PLUS_RATE = 0.1       # 1 mango -> 0.1 mango+
PLUS_TO_MANGO_RATE = 7         # 1 mango+ -> 7 mango (phí so với tỉ lệ gốc 10, tránh vòng lặp ăn chênh lệch)

LIXI_DURATION_MIN = 10

WORK_COOLDOWN_HOURS = 24
STREAK_BONUS_PER_WEEK = 0.02   # +2%/tuần, cộng dồn
MAX_POSITION_LEVEL = 5         # 0..5: lao công -> ... -> chủ tịch

COMPANIES = {
    "delta": {"name": "Tập đoàn Delta", "base_pay": (80, 140)},
    "mango_mustard": {"name": "Tập đoàn Mango Mustard", "base_pay": (60, 110)},
    "beast": {"name": "Công ty thành phẩm Beast", "base_pay": (70, 120)},
    "olivier": {"name": "Công ty thực vật Ô liu vi ơ", "base_pay": (50, 90)},
    "phonk": {"name": "Tập đoàn Phonk", "base_pay": (90, 150)},
    "one_more_game": {"name": "Công ty One More Game", "base_pay": (65, 130)},
}

POSITION_NAMES = ["Lao công", "Nhân viên", "Trưởng nhóm", "Quản lý", "Giám đốc", "Chủ tịch"]
POSITION_BUFF_PER_LEVEL = 0.08  # +8% lương mỗi cấp chức vụ

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
]

def _mango_plus_ref(user_id: int):
    return db.reference(f"users/{user_id}/mango_plus")

def _work_ref(user_id: int):
    return db.reference(f"users/{user_id}/work")

def _lixi_ref(envelope_id: str | None = None):
    if envelope_id:
        return db.reference(f"lixi/{envelope_id}")
    return db.reference("lixi")

def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()

def parse_iso(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s)

# ---------------- MANGO PLUS ----------------
def get_mango_plus(user_id: int) -> int:
    val = _mango_plus_ref(user_id).get()
    return val or 0

def transaction_mango_plus(user_id: int, delta: int):
    ref = _mango_plus_ref(user_id)
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

def convert_mango_to_plus(guild_id: int, user_id: int, mango_amount: int) -> tuple[bool, str, int]:
    import farm_store

    if mango_amount <= 0:
        return False, "Số lượng phải lớn hơn 0.", 0

    plus_gained = int(mango_amount * MANGO_TO_PLUS_RATE)
    if plus_gained <= 0:
        return False, f"Cần ít nhất {int(1 / MANGO_TO_PLUS_RATE)} mango để đổi được 1 mango+.", 0

    new_mango_balance = farm_store.transaction_mango(guild_id, user_id, -mango_amount)
    if new_mango_balance is None:
        return False, "Không đủ mango.", 0

    new_plus_balance = transaction_mango_plus(user_id, plus_gained)
    if new_plus_balance is None:
        farm_store.transaction_mango(guild_id, user_id, mango_amount)  # rollback (không nên xảy ra vì +)
        return False, "Có lỗi xảy ra, giao dịch đã được hoàn tác.", 0

    return True, "", plus_gained

def convert_plus_to_mango(guild_id: int, user_id: int, plus_amount: int) -> tuple[bool, str, int]:
    import farm_store

    if plus_amount <= 0:
        return False, "Số lượng phải lớn hơn 0.", 0

    mango_gained = plus_amount * PLUS_TO_MANGO_RATE

    new_plus_balance = transaction_mango_plus(user_id, -plus_amount)
    if new_plus_balance is None:
        return False, "Không đủ mango+.", 0

    new_mango_balance = farm_store.transaction_mango(guild_id, user_id, mango_gained)
    if new_mango_balance is None:
        transaction_mango_plus(user_id, plus_amount)  # hoàn tác
        return False, "Có lỗi xảy ra, giao dịch đã được hoàn tác.", 0

    return True, "", mango_gained

# ---------------- WORK ----------------
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

def do_work(guild_id: int, user_id: int, company_id: str) -> dict:
    import farm_store

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
    farm_store.transaction_mango(guild_id, user_id, pay)

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

# ---------------- LIXI ----------------
def create_lixi(guild_id: int, channel_id: int, creator_id: int, amount: int) -> tuple[bool, str, str | None]:
    import farm_store

    if amount <= 0:
        return False, "Số lượng phải lớn hơn 0.", None

    new_balance = farm_store.transaction_mango(guild_id, creator_id, -amount)
    if new_balance is None:
        return False, "Không đủ mango.", None

    envelope_id = uuid.uuid4().hex[:12]
    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(minutes=LIXI_DURATION_MIN)

    envelope = {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "creator_id": creator_id,
        "total_amount": amount,
        "remaining_amount": amount,
        "claimed_by": {},
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "closed": False,
    }
    _lixi_ref(envelope_id).set(envelope)
    return True, "", envelope_id

def get_lixi(envelope_id: str) -> dict | None:
    return _lixi_ref(envelope_id).get()

def claim_lixi(guild_id: int, envelope_id: str, user_id: int) -> tuple[bool, str, int]:
    import farm_store

    ref = _lixi_ref(envelope_id)
    result_holder = {"amount": 0, "error": None}

    def _txn(envelope):
        if envelope is None:
            result_holder["error"] = "Lì xì không tồn tại."
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
        if envelope["remaining_amount"] <= 0:
            envelope["closed"] = True

        result_holder["amount"] = share
        return envelope

    ref.transaction(_txn)

    if result_holder["error"]:
        return False, result_holder["error"], 0

    amount = result_holder["amount"]
    farm_store.transaction_mango(guild_id, user_id, amount)
    return True, "", amount

def refund_expired_lixi(guild_id: int, envelope_id: str) -> int:
    import farm_store

    ref = _lixi_ref(envelope_id)
    result_holder = {"refund": 0, "creator_id": None}

    def _txn(envelope):
        if envelope is None or envelope.get("closed"):
            return envelope
        remaining = envelope.get("remaining_amount", 0)
        envelope["closed"] = True
        result_holder["refund"] = remaining
        result_holder["creator_id"] = envelope.get("creator_id")
        envelope["remaining_amount"] = 0
        return envelope

    ref.transaction(_txn)

    refund = result_holder["refund"]
    creator_id = result_holder["creator_id"]
    if refund > 0 and creator_id:
        farm_store.transaction_mango(guild_id, creator_id, refund)
    return refund