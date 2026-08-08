import datetime
import hashlib
import json
import math
import os
import random
import uuid
import copy

from firebase_admin import db

import config

# Utility
def is_owner(user_id: int) -> bool:
    return user_id in config.BOT_OWNER_ID

def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()

def parse_iso(s: str) -> datetime.datetime:
    """Luôn trả về datetime NAIVE (không timezone) theo giờ UTC, để nhất quán so sánh với
    datetime.datetime.utcnow() (cũng naive) dùng xuyên suốt codebase."""
    if not s:
        return None
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    if '+' not in s and '-' not in s[10:]:  # không có timezone offset ở phần sau ngày
        s = s + '+00:00'
    dt = datetime.datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt

def _coins_ref(user_id: int):
    return db.reference(f"users/{user_id}/coins")

def get_coins(user_id: int) -> int:
    val = _coins_ref(user_id).get()
    return val or 0

def transaction_coins(user_id: int, delta: int):
    ref = _coins_ref(user_id)
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

def spend_coins_and_apply(user_id: int, cost: int, apply_fn, label: str | None = None) -> tuple[bool, str]:
    if cost < 0:
        raise ValueError("giá phải lớn hơn hoặc bằng 0")

    if cost > 0:
        new_balance = transaction_coins(user_id, -cost)
        if new_balance is None:
            return False, "Không đủ xu."

    if label and cost > 0:
        log_purchase(user_id, label, cost, "coins")

    return True, ""

def set_coins(user_id: int, amount: int):
    amount = max(0, int(amount))
    _coins_ref(user_id).set(amount)
    return amount

def get_all_users_data() -> dict:
    return db.reference("users").get() or {}

# Work
def _work_ref(user_id: int):
    return db.reference(f"users/{user_id}/work")

DEFAULT_WORK_DATA = {
    "last_worked_date": None,       # "YYYY-MM-DD" theo giờ VN, dùng cho giới hạn 1 lần/ngày
    "current_company": None,
    "streak_weeks": 0,
    "position_level": 0,
    "company_cooldown_until": {},
    "company_switched_at": None,    # ISO, dùng để tính cooldown đổi công ty 7 ngày
    "premium_paid": {},             # {company_id: True} đã trả phí công ty cao cấp chưa
    "resign_cooldown_until": None,  # ISO, không được /work tới lúc này nếu vừa từ chức
}

def _work_vn_date_str(dt: datetime.datetime) -> str:
    vn_dt = dt + datetime.timedelta(hours=config.WORK_TZ_OFFSET_HOURS)
    return vn_dt.strftime("%Y-%m-%d")

def get_work_data(user_id: int) -> dict:
    try:
        data = _work_ref(user_id).get()
        if data is None:
            return dict(DEFAULT_WORK_DATA)
        merged = dict(DEFAULT_WORK_DATA)
        merged.update(data)
        merged.setdefault("company_cooldown_until", {})
        merged.setdefault("premium_paid", {})
        return merged
    except Exception as e:
        print(f"Error getting work data for user {user_id}: {e}")
        return dict(DEFAULT_WORK_DATA)

def get_work_cooldown_remaining_sec(user_id: int) -> int:
    """Trả về >0 nếu hôm nay (giờ VN) đã /work rồi, tính giây còn lại tới 0h VN ngày mai."""
    data = get_work_data(user_id)
    last_date = data.get("last_worked_date")
    if not last_date:
        return 0

    now = datetime.datetime.utcnow()
    today_str = _work_vn_date_str(now)
    if last_date != today_str:
        return 0

    vn_now = now + datetime.timedelta(hours=config.WORK_TZ_OFFSET_HOURS)
    vn_tomorrow_midnight = (vn_now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    remaining = (vn_tomorrow_midnight - vn_now).total_seconds()
    return max(0, int(remaining))

def get_company_penalty_remaining_sec(user_id: int, company_id: str) -> int:
    data = get_work_data(user_id)
    until = data.get("company_cooldown_until", {}).get(company_id)
    if not until:
        return 0
    parsed = parse_iso(until)
    if parsed is None:
        return 0
    remaining = (parsed - datetime.datetime.utcnow()).total_seconds()
    return max(0, int(remaining))

def get_company_switch_cooldown_remaining_sec(user_id: int) -> int:
    """Cooldown đổi công ty (7 ngày kể từ lần đổi gần nhất). 0 nếu chưa từng đổi hoặc đã qua."""
    data = get_work_data(user_id)
    switched_at = data.get("company_switched_at")
    if not switched_at:
        return 0
    parsed = parse_iso(switched_at)
    if parsed is None:
        return 0
    elapsed = (datetime.datetime.utcnow() - parsed).total_seconds()
    remaining = config.WORK_COMPANY_SWITCH_COOLDOWN_DAYS * 86400 - elapsed
    return max(0, int(remaining))

def get_resign_cooldown_remaining_sec(user_id: int) -> int:
    data = get_work_data(user_id)
    until = data.get("resign_cooldown_until")
    if not until:
        return 0
    parsed = parse_iso(until)
    if parsed is None:
        return 0
    remaining = (parsed - datetime.datetime.utcnow()).total_seconds()
    return max(0, int(remaining))

def get_work_late_penalty(now: datetime.datetime) -> tuple[float, int, bool]:
    """
    Tính phạt đi trễ dựa trên giờ hiện tại (UTC) so với mốc 6h sáng giờ VN cùng ngày.
    Trả về (penalty_pct, minutes_late, blocked) — blocked=True nếu quá giờ chặn (sau 12h trưa).
    """
    vn_now = now + datetime.timedelta(hours=config.WORK_TZ_OFFSET_HOURS)
    start_mark = vn_now.replace(hour=config.WORK_START_HOUR, minute=0, second=0, microsecond=0)
    cutoff_mark = vn_now.replace(hour=config.WORK_LATE_CUTOFF_HOUR, minute=0, second=0, microsecond=0)

    if vn_now <= start_mark:
        return 0.0, 0, False

    if vn_now >= cutoff_mark:
        return config.WORK_LATE_PENALTY_MAX, int((vn_now - start_mark).total_seconds() // 60), True

    minutes_late = int((vn_now - start_mark).total_seconds() // 60)
    penalty = min(config.WORK_LATE_PENALTY_MAX, minutes_late * config.WORK_LATE_PENALTY_PER_MINUTE)
    return penalty, minutes_late, False

def _update_work_data(user_id: int, fn):
    ref = db.reference(f"users/{user_id}")

    def _txn(current):
        current = current or {}
        work = current.setdefault("work", {})
        for k, v in DEFAULT_WORK_DATA.items():
            work.setdefault(k, copy.deepcopy(v))
        return fn(current)

    result = ref.transaction(_txn)
    return result

def get_company_entry_fee(company_id: str) -> int:
    if company_id not in config.WORK_PREMIUM_COMPANIES:
        return 0
    lo, hi = config.COMPANIES[company_id]["base_pay"]
    avg_pay = (lo + hi) / 2
    return round(avg_pay * config.WORK_PREMIUM_ENTRY_FEE_MULTIPLIER)

def pay_company_entry_fee(user_id: int, company_id: str) -> tuple[bool, str]:
    """Trả phí vào công ty cao cấp (nếu cần và chưa trả). Trả về (ok, message)."""
    fee = get_company_entry_fee(company_id)
    if fee <= 0:
        return True, ""

    data = get_work_data(user_id)
    if data.get("premium_paid", {}).get(company_id):
        return True, ""

    new_balance = transaction_coins(user_id, -fee)
    if new_balance is None:
        return False, f"Cần **{fee} xu** để vào làm tại công ty này (chưa đủ)."

    def _mark_paid(d):
        work = d.setdefault("work", {})
        for k, v in DEFAULT_WORK_DATA.items():
            work.setdefault(k, copy.deepcopy(v))
        premium_paid = dict(work.get("premium_paid", {}))
        premium_paid[company_id] = True
        work["premium_paid"] = premium_paid
        return d

    _update_work_data(user_id, _mark_paid)
    return True, ""

def do_work(user_id: int, company_id: str) -> dict:
    if company_id not in config.COMPANIES:
        return {"ok": False, "message": "Công ty không tồn tại."}

    resign_cooldown = get_resign_cooldown_remaining_sec(user_id)
    if resign_cooldown > 0:
        return {"ok": False, "message": f"resign_cooldown:{resign_cooldown}"}

    remaining = get_work_cooldown_remaining_sec(user_id)
    if remaining > 0:
        return {"ok": False, "message": f"cooldown:{remaining}"}

    penalty_remaining = get_company_penalty_remaining_sec(user_id, company_id)
    if penalty_remaining > 0:
        return {"ok": False, "message": f"company_penalty:{penalty_remaining}"}

    now = datetime.datetime.utcnow()
    data = get_work_data(user_id)

    same_company = data.get("current_company") == company_id
    if not same_company and data.get("current_company") is not None:
        switch_cooldown = get_company_switch_cooldown_remaining_sec(user_id)
        if switch_cooldown > 0:
            return {"ok": False, "message": f"switch_cooldown:{switch_cooldown}"}

    if company_id in config.WORK_PREMIUM_COMPANIES:
        ok, msg = pay_company_entry_fee(user_id, company_id)
        if not ok:
            return {"ok": False, "message": f"entry_fee:{msg}"}

    late_penalty, minutes_late, blocked = get_work_late_penalty(now)
    if blocked:
        return {"ok": False, "message": "too_late"}

    last_date = data.get("last_worked_date")
    today_str = _work_vn_date_str(now)
    yesterday_str = _work_vn_date_str(now - datetime.timedelta(days=1))
    streak_weeks = data.get("streak_weeks", 0)

    if same_company and last_date == yesterday_str:
        streak_weeks = min(streak_weeks + 1, 520)
    elif not same_company or last_date != today_str:
        if not same_company:
            streak_weeks = 0

    position_level = data.get("position_level", 0)

    triggered_event = None
    bad_event_reduction = get_work_bad_event_reduction(user_id)
    for event in config.BAD_EVENTS:
        adjusted_chance = event["chance"] * (1 - bad_event_reduction)
        if random.random() < adjusted_chance:
            triggered_event = event
            break

    triggered_good_event = None
    if triggered_event is None:
        for good_event in config.GOOD_EVENTS:
            if random.random() < good_event["chance"]:
                triggered_good_event = good_event
                break

    company_cooldowns = dict(data.get("company_cooldown_until", {}))
    switched_at = data.get("company_switched_at")
    if not same_company:
        switched_at = now.isoformat()

    if triggered_event:
        penalty_until = (now + datetime.timedelta(hours=triggered_event["penalty_hours"])).isoformat()
        company_cooldowns[company_id] = penalty_until

        def _apply_event(d):
            work = d.setdefault("work", {})
            for k, v in DEFAULT_WORK_DATA.items():
                work.setdefault(k, copy.deepcopy(v))
            work["last_worked_date"] = today_str
            work["current_company"] = company_id
            work["streak_weeks"] = 0
            work["position_level"] = position_level
            work["company_cooldown_until"] = company_cooldowns
            work["company_switched_at"] = switched_at
            return d

        _update_work_data(user_id, _apply_event)
        return {
            "ok": True,
            "pay": 0,
            "event": triggered_event,
            "good_event": None,
            "streak_weeks": 0,
            "position_level": position_level,
            "company_name": config.COMPANIES[company_id]["name"],
            "minutes_late": minutes_late,
            "late_penalty": late_penalty,
        }

    lo, hi = config.COMPANIES[company_id]["base_pay"]
    base_pay = random.randint(lo, hi)
    streak_mult = 1.0 + streak_weeks * config.STREAK_BONUS_PER_WEEK
    level = min(position_level, len(config.POSITION_BUFFS)-1)
    position_mult = 1.0 + config.POSITION_BUFFS[level]
    pay = max(1, round(base_pay * streak_mult * position_mult))

    # Phạt đi trễ
    pay = round(pay * (1 - late_penalty))

    final_streak_weeks = streak_weeks
    final_position_level = position_level

    if triggered_good_event:
        etype = triggered_good_event["type"]
        if etype == "bonus_pay":
            pay = round(pay * (1 + triggered_good_event["value"]))
        elif etype == "streak_boost":
            final_streak_weeks = min(final_streak_weeks + triggered_good_event["value"], 520)
        elif etype == "promotion":
            final_position_level = min(final_position_level + triggered_good_event["value"], config.MAX_POSITION_LEVEL)
        # cooldown_reduction: không còn ý nghĩa với cơ chế theo-ngày, bỏ qua hiệu ứng này

    pay = max(1, apply_coins_mult(user_id, pay, command="work"))

    def _apply(d):
        work = d.setdefault("work", {})
        for k, v in DEFAULT_WORK_DATA.items():
            work.setdefault(k, copy.deepcopy(v))
        work["last_worked_date"] = today_str
        work["current_company"] = company_id
        work["streak_weeks"] = final_streak_weeks
        work["position_level"] = final_position_level
        work["company_cooldown_until"] = company_cooldowns
        work["company_switched_at"] = switched_at
        return d

    _update_work_data(user_id, _apply)
    try:
        new_balance = transaction_coins(user_id, pay)
        if new_balance is None:
            print(f"Warning: transaction coins returned None for user {user_id}")
    except Exception as e:
        print(f"Error in transaction coins: {e}")

    became_president = (
        final_position_level >= config.MAX_POSITION_LEVEL and position_level < config.MAX_POSITION_LEVEL
    )

    return {
        "ok": True,
        "pay": pay,
        "event": None,
        "good_event": triggered_good_event,
        "streak_weeks": final_streak_weeks,
        "position_level": final_position_level,
        "company_name": config.COMPANIES[company_id]["name"],
        "minutes_late": minutes_late,
        "late_penalty": late_penalty,
        "became_president": became_president,
    }

def resign_work(user_id: int) -> dict:
    """Từ chức: mất phí, reset position_level về 0, cooldown 3 ngày không được /work."""
    data = get_work_data(user_id)
    if not data.get("current_company"):
        return {"ok": False, "message": "Bạn hiện không làm việc ở đâu cả."}

    new_balance = transaction_coins(user_id, -config.WORK_RESIGN_FEE)
    if new_balance is None:
        return {"ok": False, "message": f"Cần **{config.WORK_RESIGN_FEE} xu** để từ chức (chưa đủ)."}

    now = datetime.datetime.utcnow()
    cooldown_until = (now + datetime.timedelta(days=config.WORK_RESIGN_COOLDOWN_DAYS)).isoformat()

    def _resign(d):
        work = d.setdefault("work", {})
        for k, v in DEFAULT_WORK_DATA.items():
            work.setdefault(k, copy.deepcopy(v))
        work["current_company"] = None
        work["position_level"] = 0
        work["streak_weeks"] = 0
        work["resign_cooldown_until"] = cooldown_until
        return d

    _update_work_data(user_id, _resign)
    return {"ok": True, "message": "", "cooldown_days": config.WORK_RESIGN_COOLDOWN_DAYS}

def promote_position(user_id: int) -> tuple[bool, str]:
    data = get_work_data(user_id)
    level = data.get("position_level", 0)
    if level >= config.MAX_POSITION_LEVEL:
        return False, "Đã đạt chức vụ cao nhất."

    def _promote(d):
        work = d.setdefault("work", {})
        for k, v in DEFAULT_WORK_DATA.items():
            work.setdefault(k, copy.deepcopy(v))
        lvl = work["position_level"]
        if lvl >= config.MAX_POSITION_LEVEL:
            return d
        work["position_level"] = lvl + 1
        return d

    _update_work_data(user_id, _promote)
    return True, config.POSITION_NAMES[level + 1]

# Lixi
def _lixi_ref(envelope_id: str | None = None):
    if envelope_id:
        return db.reference(f"lixi/{envelope_id}")
    return db.reference("lixi")

def create_lixi(guild_id: int, channel_id: int, creator_id: int, amount: int) -> tuple[bool, str, str | None]:
    if amount <= 0:
        return False, "Số lượng phải lớn hơn 0.", None

    new_balance = transaction_coins(creator_id, -amount)
    if new_balance is None:
        return False, f"Không đủ xu.", None

    envelope_id = uuid.uuid4().hex[:12]
    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(minutes=config.LIXI_DURATION_MIN)

    envelope = {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "message_id": None,  # gán sau khi gửi message, dùng để edit khi đóng sớm từ DM
        "creator_id": creator_id,
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

def set_lixi_message_id(envelope_id: str, message_id: int) -> None:
    _lixi_ref(envelope_id).update({"message_id": message_id})

def get_lixi(envelope_id: str) -> dict | None:
    return _lixi_ref(envelope_id).get()

def claim_lixi(envelope_id: str, user_id: int) -> tuple[bool, str, int]:
    ref = _lixi_ref(envelope_id)
    result_holder = {"amount": 0, "error": None}

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
        return envelope

    ref.transaction(_txn)

    if result_holder["error"]:
        return False, result_holder["error"], 0

    amount = result_holder["amount"]
    transaction_coins(user_id, amount)
    return True, "", amount

def refund_expired_lixi(envelope_id: str) -> int:
    ref = _lixi_ref(envelope_id)
    result_holder = {"refund": 0, "creator_id": None, "already_closed": False}

    def _txn(envelope):
        if envelope is None:
            return envelope
        if envelope.get("closed"):
            result_holder["already_closed"] = True
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
        transaction_coins(creator_id, refund)

    ref.delete()
    return refund

# Bill
def _log_ref(user_id: int):
    return db.reference(f"users/{user_id}/purchase_log")

def log_purchase(user_id: int, label: str, cost: int, currency: str = "coins") -> None:
    if cost <= 0:
        return # Không log miễn phí

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
        if len(current) > config.MAX_LOG_ENTRIES:
            current = current[-config.MAX_LOG_ENTRIES:]
        return current

    ref.transaction(_txn)

def get_purchase_log(user_id: int, limit: int = 20) -> list[dict]:
    data = _log_ref(user_id).get() or []
    return list(reversed(data))[:limit]

# Locked
def _locked_ref():
    return db.reference("bot_config/locked")

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

# Bảo trì toàn bot
def _maintenance_ref():
    return db.reference("bot_config/maintenance")

def is_maintenance_mode() -> bool:
    data = _maintenance_ref().get()
    return bool(data and data.get("enabled"))

def get_maintenance_reason() -> str | None:
    data = _maintenance_ref().get()
    return data.get("reason") if data else None

def set_maintenance_mode(enabled: bool, reason: str | None = None) -> None:
    _maintenance_ref().set({"enabled": enabled, "reason": reason})

# Wordle
def _wordle_play_ref(user_id: int):
    return db.reference(f"users/{user_id}/wordle_plays")

def _wordle_game_ref(user_id: int):
    return db.reference(f"wordle_games/{user_id}")

def get_wordle_stats(user_id: int) -> dict:
    ref = db.reference(f"users/{user_id}/wordle_stats")
    stats = ref.get() or {}
    return stats

def update_wordle_stats(user_id: int, is_win: bool) -> dict:
    ref = db.reference(f"users/{user_id}/wordle_stats")
    result = {"achievement": None}
    
    def _txn(current):
        current = current or {}
        current["total_plays"] = current.get("total_plays", 0) + 1
        
        if is_win:
            current["total_wins"] = current.get("total_wins", 0) + 1
            current["current_streak"] = current.get("current_streak", 0) + 1
            current["max_streak"] = max(current.get("max_streak", 0), current["current_streak"])
            
            # check
            if current["current_streak"] >= config.WORDLE_WIN_STREAK_REQUIRED:
                result["achievement"] = "streak"
            elif current["total_wins"] == config.WORDLE_TOTAL_WINS_REQUIRED:
                result["achievement"] = "total_wins"
        else:
            current["current_streak"] = 0
        
        current["last_played"] = datetime.datetime.utcnow().isoformat()
        return current
    
    ref.transaction(_txn)
    return result

def get_wordle_achievement_roles() -> dict:
    return {
        "streak": 1532390640866820256,
        "total_wins": 1532390640866820256,
    }

def get_wordle_plays_remaining(user_id: int) -> int:
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    data = _wordle_play_ref(user_id).get() or {}
    daily_limit = config.WORDLE_DAILY_LIMIT + get_extra_plays(user_id, "wordle")
    used_today = data.get("count", 0) if data.get("date") == today else 0
    return max(0, daily_limit - used_today) + get_shop_bonus_plays(user_id) + get_quest_game_tickets(user_id)

def consume_wordle_play(user_id: int) -> bool:
    """Ưu tiên tiêu vé quest (có hạn dùng) trước, rồi tới vé shop (vĩnh viễn), hết vé mới trừ vào giới hạn/ngày."""
    if _consume_quest_game_ticket(user_id):
        return True
    if _consume_shop_bonus_play(user_id):
        return True

    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    daily_limit = config.WORDLE_DAILY_LIMIT + get_extra_plays(user_id, "wordle")
    ref = _wordle_play_ref(user_id)
    result_holder = {"ok": False}

    def _txn(current):
        current = current or {}
        if current.get("date") != today:
            current = {"date": today, "count": 0}
        if current["count"] >= daily_limit:
            result_holder["ok"] = False
            return current
        current["count"] += 1
        result_holder["ok"] = True
        return current

    ref.transaction(_txn)
    return result_holder["ok"]

def get_active_wordle_game(user_id: int) -> dict | None:
    game = _wordle_game_ref(user_id).get()
    if game and not game.get("finished"):
        return game
    return None

def create_wordle_game(user_id: int) -> dict:
    word = random.choice(config.WORDLE_WORDS)
    game = {
        "word": word,
        "guesses": [],
        "created_at": datetime.datetime.utcnow().isoformat(),
        "finished": False,
    }
    _wordle_game_ref(user_id).set(game)
    return game

def delete_wordle_game(user_id: int) -> None:
    _wordle_game_ref(user_id).delete()

def score_wordle_guess(secret: str, guess: str) -> list[str]:
    """
    Trả về list 5 phần tử: 'correct' (🟩 đúng vị trí), 'present' (🟨 có trong từ, sai vị trí),
    'absent' (⬜ không có trong từ).
    """
    secret = secret.upper()
    guess = guess.upper()
    result = ["absent"] * 5
    secret_chars = list(secret)

    # Bước 1: đánh dấu đúng vị trí trước
    for i in range(5):
        if guess[i] == secret[i]:
            result[i] = "correct"
            secret_chars[i] = None  # đã dùng

    # Bước 2: chữ có trong từ nhưng sai vị trí
    for i in range(5):
        if result[i] == "correct":
            continue
        if guess[i] in secret_chars:
            result[i] = "present"
            secret_chars[secret_chars.index(guess[i])] = None

    return result

def submit_wordle_guess(user_id: int, guess: str) -> dict:
    """
    {status: 'no_game'|'win'|'continue'|'lose', result: [...], guesses_left: int, word: str|None}
    """
    ref = _wordle_game_ref(user_id)
    result_holder = {"status": "no_game", "result": None, "guesses_left": 0, "word": None}

    def _txn(game):
        if game is None or game.get("finished"):
            result_holder["status"] = "no_game"
            return game

        if len(game.get("guesses", [])) >= config.WORDLE_MAX_GUESSES:
            result_holder["status"] = "no_game"
            return game

        secret = game["word"]
        score = score_wordle_guess(secret, guess)
        game.setdefault("guesses", []).append({"word": guess.upper(), "result": score})

        is_win = all(r == "correct" for r in score)
        guesses_left = config.WORDLE_MAX_GUESSES - len(game["guesses"])

        if is_win:
            game["finished"] = True
            result_holder["status"] = "win"
        elif guesses_left <= 0:
            game["finished"] = True
            result_holder["status"] = "lose"
        else:
            result_holder["status"] = "continue"

        result_holder["result"] = score
        result_holder["guesses_left"] = guesses_left
        result_holder["word"] = secret
        return game

    ref.transaction(_txn)
    return result_holder

# Meme Achievement
def get_meme_count(user_id: int) -> int:
    try:
        ref = db.reference(f"users/{user_id}/meme_count")
        return ref.get() or 0
    except Exception:
        return 0

def increment_meme_count(user_id: int) -> int:
    try:
        ref = db.reference(f"users/{user_id}/meme_count")
        current = ref.get() or 0
        new_count = current + 1
        ref.set(new_count)
        
        # Kiểm tra xem đã đạt mốc 20 chưa
        if new_count >= config.MEME_CONFIG["required_count"]:
            return new_count
        return new_count
    except Exception as e:
        print(f"Lỗi tăng số lượng meme: {e}")
        return 0

def has_meme_role(user_id: int) -> bool:
    try:
        ref = db.reference(f"users/{user_id}/meme_role_claimed")
        return ref.get() == True
    except Exception:
        return False

def claim_meme_role(user_id: int) -> bool:
    try:
        ref = db.reference(f"users/{user_id}/meme_role_claimed")
        if ref.get() == True:
            return False
        ref.set(True)
        return True
    except Exception:
        return False

def reset_meme_count_for_user(user_id: int) -> None:
    db.reference(f"users/{user_id}/meme_count").set(0)
    db.reference(f"users/{user_id}/meme_role_claimed").set(False)

def reset_meme_counts():
    try:
        users = db.reference("users").get() or {}
        for uid in users:
            if isinstance(users[uid], dict) and "meme_count" in users[uid]:
                db.reference(f"users/{uid}/meme_count").set(0)
        return True
    except Exception:
        return False

# Flag
def _flag_game_ref(user_id: int):
    return db.reference(f"flag_games/{user_id}")

def _flag_stats_ref(user_id: int):
    return db.reference(f"users/{user_id}/flag_stats")

def _normalize_guess(text: str) -> str:
    return text.strip().lower()

def get_active_flag_game(user_id: int) -> dict | None:
    game = _flag_game_ref(user_id).get()
    if game and not game.get("finished"):
        return game
    return None

def _flag_play_ref(user_id: int):
    return db.reference(f"users/{user_id}/flag_plays")

def get_flag_plays_remaining(user_id: int) -> int:
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    data = _flag_play_ref(user_id).get() or {}
    daily_limit = config.FLAG_DAILY_LIMIT + get_extra_plays(user_id, "flag")
    used_today = data.get("count", 0) if data.get("date") == today else 0
    return max(0, daily_limit - used_today) + get_shop_bonus_plays(user_id) + get_quest_game_tickets(user_id)

def consume_flag_play(user_id: int) -> bool:
    """Ưu tiên tiêu vé quest (có hạn dùng) trước, rồi tới vé shop (vĩnh viễn), hết vé mới trừ vào giới hạn/ngày."""
    if _consume_quest_game_ticket(user_id):
        return True
    if _consume_shop_bonus_play(user_id):
        return True

    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    daily_limit = config.FLAG_DAILY_LIMIT + get_extra_plays(user_id, "flag")
    ref = _flag_play_ref(user_id)
    result_holder = {"ok": False}

    def _txn(current):
        current = current or {}
        if current.get("date") != today:
            current = {"date": today, "count": 0}
        if current["count"] >= daily_limit:
            result_holder["ok"] = False
            return current
        current["count"] += 1
        result_holder["ok"] = True
        return current

    ref.transaction(_txn)
    return result_holder["ok"]

def create_flag_game(user_id: int, mode: str) -> dict:
    pool = list(config.FLAG_COUNTRIES[mode])
    random.shuffle(pool)
    chosen = pool[:config.FLAG_QUESTIONS_PER_GAME]
    # nếu nhóm có ít hơn 5 quốc gia
    while len(chosen) < config.FLAG_QUESTIONS_PER_GAME:
        chosen.append(random.choice(config.FLAG_COUNTRIES[mode]))

    now = datetime.datetime.utcnow()
    deadline = (now + datetime.timedelta(seconds=config.FLAG_SECONDS_PER_QUESTION)).isoformat()

    game = {
        "mode": mode,
        "questions": [{"country": c[0], "iso_code": c[1]} for c in chosen],
        "current_index": 0,
        "current_attempts": 0,
        "current_deadline": deadline,
        "correct_count": 0,
        "answered": [False] * config.FLAG_QUESTIONS_PER_GAME,
        "created_at": now.isoformat(),
        "finished": False,
    }
    _flag_game_ref(user_id).set(game)
    return game

def delete_flag_game(user_id: int) -> None:
    _flag_game_ref(user_id).delete()

def _flag_answer_matches(guess: str, country_name: str, mode: str) -> bool:
    guess_norm = _normalize_guess(guess)
    if guess_norm == _normalize_guess(country_name):
        return True
    for name, _iso, aliases in config.FLAG_COUNTRIES[mode]:
        if name == country_name:
            return guess_norm in [_normalize_guess(a) for a in aliases]
    return False

def _update_flag_streak(user_id: int, mode: str, correct_count: int) -> dict:
    ref = _flag_stats_ref(user_id)
    mode_order = config.FLAG_MODE_ORDER.index(mode)
    result_holder = {"achieved": False}

    def _txn(stats):
        stats = stats or {"recent_correct_streak": 0, "streak_role_claimed": False, "games_in_window": 0}

        if mode_order < config.FLAG_STREAK_MIN_MODE_ORDER:
            stats["recent_correct_streak"] = 0
            stats["games_in_window"] = 0
            return stats

        stats["recent_correct_streak"] = stats.get("recent_correct_streak", 0) + correct_count
        stats["games_in_window"] = stats.get("games_in_window", 0) + 1

        if stats["games_in_window"] > config.FLAG_STREAK_WINDOW_GAMES:
            stats["recent_correct_streak"] = correct_count
            stats["games_in_window"] = 1

        if (stats["recent_correct_streak"] >= config.FLAG_STREAK_REQUIRED
                and not stats.get("streak_role_claimed")
                and stats["games_in_window"] <= config.FLAG_STREAK_WINDOW_GAMES):
            stats["streak_role_claimed"] = True
            result_holder["achieved"] = True

        return stats

    ref.transaction(_txn)
    return result_holder

def submit_flag_guess(user_id: int, guess: str) -> dict:
    ref = _flag_game_ref(user_id)
    result_holder = {
        "status": "no_game", "question_index": 0, "country": None, "attempts_left": 0,
        "correct_count": 0, "reward": 0, "is_last_question": False, "mode": None,
    }

    def _txn(game):
        if game is None or game.get("finished"):
            result_holder["status"] = "no_game"
            return game

        idx = game["current_index"]
        question = game["questions"][idx]
        mode = game["mode"]
        is_last = idx == config.FLAG_QUESTIONS_PER_GAME - 1

        is_correct = _flag_answer_matches(guess, question["country"], mode)
        game["current_attempts"] += 1

        if is_correct:
            game["correct_count"] += 1
            game["answered"][idx] = True
            result_holder["status"] = "correct"
            result_holder["reward"] = config.FLAG_MODE_REWARD_PER_QUESTION[mode]
            _advance_flag_question(game, is_last)
        elif game["current_attempts"] >= config.FLAG_ATTEMPTS_PER_QUESTION:
            game["answered"][idx] = True
            result_holder["status"] = "wrong_final"
            _advance_flag_question(game, is_last)
        else:
            result_holder["status"] = "wrong_retry"

        result_holder["question_index"] = idx
        result_holder["country"] = question["country"]
        result_holder["attempts_left"] = max(0, config.FLAG_ATTEMPTS_PER_QUESTION - game["current_attempts"])
        result_holder["correct_count"] = game["correct_count"]
        result_holder["is_last_question"] = is_last
        result_holder["mode"] = mode
        return game

    ref.transaction(_txn)

    if result_holder["status"] == "correct":
        result_holder["reward"] = apply_coins_mult(user_id, result_holder["reward"], command="flag")

    result_holder["streak_achieved"] = False
    if result_holder["status"] in ("correct", "wrong_final") and result_holder["is_last_question"]:
        game_after = _flag_game_ref(user_id).get()
        if game_after and game_after.get("finished"):
            streak_result = _update_flag_streak(user_id, result_holder["mode"], result_holder["correct_count"])
            result_holder["streak_achieved"] = streak_result["achieved"]

    return result_holder

def _advance_flag_question(game: dict, is_last: bool) -> None:
    if is_last:
        game["finished"] = True
        return
    game["current_index"] += 1
    game["current_attempts"] = 0
    now = datetime.datetime.utcnow()
    game["current_deadline"] = (now + datetime.timedelta(seconds=config.FLAG_SECONDS_PER_QUESTION)).isoformat()

def check_and_expire_flag_question(user_id: int) -> dict | None:
    ref = _flag_game_ref(user_id)
    result_holder = {"expired": False}

    def _txn(game):
        if game is None or game.get("finished"):
            return game
        deadline = parse_iso(game["current_deadline"])
        if datetime.datetime.utcnow() < deadline:
            return game

        idx = game["current_index"]
        is_last = idx == config.FLAG_QUESTIONS_PER_GAME - 1
        game["answered"][idx] = True
        result_holder["expired"] = True
        result_holder["question_index"] = idx
        result_holder["country"] = game["questions"][idx]["country"]
        result_holder["is_last_question"] = is_last
        result_holder["mode"] = game["mode"]
        result_holder["correct_count"] = game["correct_count"]
        _advance_flag_question(game, is_last)
        return game

    ref.transaction(_txn)

    if not result_holder["expired"]:
        return None

    if result_holder["is_last_question"]:
        game_after = ref.get()
        if game_after and game_after.get("finished"):
            _update_flag_streak(user_id, result_holder["mode"], result_holder["correct_count"])

    return result_holder

# Danh Gia (attachment review)
def score_attachment(file_bytes: bytes, filename: str) -> dict:
    """
    Chấm điểm giả lập dựa trên hash nội dung file + metadata cơ bản.
    Deterministic: cùng file luôn ra cùng kết quả.
    Trả về: {"total": float, "criteria": {name: float}, "tier": str}
    """
    digest = hashlib.sha256(file_bytes).hexdigest()
    rnd = random.Random(digest)

    criteria_scores = {}
    for name in config.DANHGIA_CRITERIA:
        # mỗi tiêu chí 0.0 - 10.0, lệch nhẹ theo digest để tránh đồng đều máy móc
        criteria_scores[name] = round(rnd.uniform(0, 10), 1)

    total = round(sum(criteria_scores.values()) / len(criteria_scores), 1)

    if total < 3:
        tier = "low"
    elif total < 6:
        tier = "mid"
    elif total < 8.5:
        tier = "high"
    else:
        tier = "top"

    comment = rnd.choice(config.DANHGIA_COMMENTS[tier])

    return {
        "total": total,
        "criteria": criteria_scores,
        "tier": tier,
        "comment": comment,
        "hash_short": digest[:8],
    }

# Reset command
# Đăng ký các loại game có thể bị kẹt tại đây — thêm minigame mới chỉ cần thêm 1 dòng
RESETTABLE_GAME_ROOTS = {
    "wordle": "wordle_games",
    "flag": "flag_games",
    "minesweeper": "minesweeper_games",
}
RESETTABLE_GAME_LABELS = {
    "wordle": "Đoán từ (/wordle)",
    "flag": "Đoán cờ (/flag)",
    "minesweeper": "Dò mìn (/minesweeper)",
    "meme": "Đoán Meme (/meme)",
    "car": "Đoán Xe (/car)",
    "country": "Đoán Quốc Gia (/country)",
    "hoahoc": "Hoá Học (/hoahoc)",
    "language": "Đoán Ngôn Ngữ (/language)",
}
# minigame_games/{kind}/{uid} có cấu trúc khác (root theo kind) -> xử lý riêng bên dưới
MINIGAME_KINDS = ("meme", "car", "country", "hoahoc", "language")

def _resettable_ref(user_id: int, game_key: str):
    if game_key in MINIGAME_KINDS:
        return db.reference(f"minigame_games/{game_key}/{user_id}")
    path = RESETTABLE_GAME_ROOTS.get(game_key)
    if path is None:
        return None
    return db.reference(f"{path}/{user_id}")

def get_stuck_game_types(user_id: int) -> list[str]:
    """Trả về danh sách key game đang có ván chưa kết thúc cho user."""
    stuck = []
    for key in list(RESETTABLE_GAME_ROOTS) + list(MINIGAME_KINDS):
        data = _resettable_ref(user_id, key).get()
        if data and not data.get("finished", False):
            stuck.append(key)
    return stuck

def reset_game_for_user(user_id: int, game_key: str) -> bool:
    """Xoá ván game bị kẹt của 1 user. Trả về True nếu có ván để xoá."""
    ref = _resettable_ref(user_id, game_key)
    if ref is None:
        return False
    existed = ref.get() is not None
    if existed:
        ref.delete()
    return existed

def reset_all_games_for_user(user_id: int) -> list[str]:
    """Xoá toàn bộ ván đang kẹt của user, trả về danh sách key đã xoá."""
    cleared = []
    for key in list(RESETTABLE_GAME_ROOTS) + list(MINIGAME_KINDS):
        if reset_game_for_user(user_id, key):
            cleared.append(key)
    return cleared

def reset_all_games_everyone() -> dict:
    """Chỉ chủ bot: xoá toàn bộ ván đang kẹt của TẤT CẢ user cho mọi loại game.
    Trả về {game_key: số lượng ván đã xoá}."""
    result = {}
    for key, path in RESETTABLE_GAME_ROOTS.items():
        data = db.reference(path).get() or {}
        count = 0
        for uid, game in data.items():
            if isinstance(game, dict) and not game.get("finished", False):
                db.reference(f"{path}/{uid}").delete()
                count += 1
        result[key] = count

    for kind in MINIGAME_KINDS:
        data = db.reference(f"minigame_games/{kind}").get() or {}
        count = 0
        for uid, game in data.items():
            if isinstance(game, dict) and not game.get("finished", False):
                db.reference(f"minigame_games/{kind}/{uid}").delete()
                count += 1
        result[kind] = count

    return result

# Code system
def _code_ref(code: str | None = None):
    if code:
        return db.reference(f"codes/{code}")
    return db.reference("codes")

def create_code(
    code: str,
    created_by: int,
    coins: int = 0,
    role_id: int | None = None,
    max_uses: int = 1,
    duration_hours: int | None = None,
) -> tuple[bool, str]:
    code = code.strip()
    if not code:
        return False, "Code không hợp lệ."

    ref = _code_ref(code)
    if ref.get() is not None:
        return False, "Code này đã tồn tại."

    now = datetime.datetime.utcnow()
    expires_at = None
    if duration_hours is not None and duration_hours > 0:
        expires_at = (now + datetime.timedelta(hours=duration_hours)).isoformat()

    ref.set({
        "reward": {
            "coins": max(0, int(coins)),
            "role_id": int(role_id) if role_id else None,
        },
        "created_by": created_by,
        "created_at": now.isoformat(),
        "expires_at": expires_at,
        "max_uses": max(1, int(max_uses)),
        "used_by": [],
    })
    return True, ""

def redeem_code(code: str, user_id: int) -> dict:
    """
    {"ok": bool, "message": str, "reward": {coins, role_id} | None}
    """
    code = code.strip()
    ref = _code_ref(code)
    result_holder = {"ok": False, "message": "", "reward": None}

    def _txn(entry):
        if entry is None:
            result_holder["message"] = "Code không tồn tại."
            return entry

        expires_at = entry.get("expires_at")
        if expires_at:
            parsed = parse_iso(expires_at)
            if parsed and datetime.datetime.utcnow() >= parsed:
                result_holder["message"] = "Code đã hết hạn."
                return entry

        used_by = entry.get("used_by", [])
        if str(user_id) in used_by or user_id in used_by:
            result_holder["message"] = "Bạn đã dùng code này rồi."
            return entry

        if len(used_by) >= entry.get("max_uses", 1):
            result_holder["message"] = "Code đã hết lượt sử dụng."
            return entry

        used_by = list(used_by)
        used_by.append(str(user_id))
        entry["used_by"] = used_by

        result_holder["ok"] = True
        result_holder["reward"] = dict(entry.get("reward", {}))
        return entry

    ref.transaction(_txn)

    if not result_holder["ok"]:
        return result_holder

    reward = result_holder["reward"] or {}
    coins = reward.get("coins", 0)
    if coins:
        transaction_coins(user_id, coins)

    return result_holder

def get_code_info(code: str) -> dict | None:
    return _code_ref(code.strip()).get()

# Title system
def _titles_ref(user_id: int):
    return db.reference(f"users/{user_id}/titles")

def get_user_titles(user_id: int) -> dict:
    """Trả về {"owned": [key,...], "equipped": [key,...]}"""
    data = _titles_ref(user_id).get() or {}
    return {
        "owned": data.get("owned", []),
        "equipped": data.get("equipped", []),
    }

def give_title(user_id: int, title_key: str) -> bool:
    """Cấp title cho user. Trả về False nếu user đã có title đó."""
    if title_key not in config.TITLES:
        return False

    ref = _titles_ref(user_id)
    result_holder = {"granted": False}

    def _txn(data):
        data = data or {"owned": [], "equipped": []}
        owned = list(data.get("owned", []))
        if title_key in owned:
            result_holder["granted"] = False
            return data
        owned.append(title_key)
        data["owned"] = owned
        data.setdefault("equipped", [])
        result_holder["granted"] = True
        return data

    ref.transaction(_txn)
    return result_holder["granted"]

def revoke_title(user_id: int, title_key: str) -> bool:
    """Thu hồi title khỏi user (cả owned lẫn equipped). Trả về False nếu user không có title đó."""
    ref = _titles_ref(user_id)
    result_holder = {"revoked": False}

    def _txn(data):
        data = data or {"owned": [], "equipped": []}
        owned = list(data.get("owned", []))
        if title_key not in owned:
            result_holder["revoked"] = False
            return data
        owned.remove(title_key)
        data["owned"] = owned
        equipped = list(data.get("equipped", []))
        if title_key in equipped:
            equipped.remove(title_key)
        data["equipped"] = equipped
        result_holder["revoked"] = True
        return data

    ref.transaction(_txn)
    return result_holder["revoked"]

def set_equipped_titles(user_id: int, title_keys: list[str]) -> tuple[bool, str]:
    """Trang bị danh sách title (thay thế toàn bộ). Tối đa TITLE_MAX_EQUIPPED."""
    if len(title_keys) > config.TITLE_MAX_EQUIPPED:
        return False, f"Chỉ được trang bị tối đa {config.TITLE_MAX_EQUIPPED} danh hiệu."

    owned = get_user_titles(user_id)["owned"]
    for key in title_keys:
        if key not in owned:
            return False, f"Bạn chưa sở hữu danh hiệu này: {config.TITLES.get(key, {}).get('name', key)}"

    _titles_ref(user_id).update({"equipped": title_keys})
    return True, ""

# Daily
def _daily_ref(user_id: int):
    return db.reference(f"users/{user_id}/daily")

def _vn_date_str(dt: datetime.datetime) -> str:
    vn_dt = dt + datetime.timedelta(hours=config.DAILY_TZ_OFFSET_HOURS)
    return vn_dt.strftime("%Y-%m-%d")

def get_daily_cooldown_remaining_sec(user_id: int) -> int:
    data = _daily_ref(user_id).get() or {}
    last_claim = data.get("last_claim_date")
    if not last_claim:
        return 0

    now = datetime.datetime.utcnow()
    today_str = _vn_date_str(now)
    if last_claim != today_str:
        return 0

    # đã claim hôm nay (giờ VN) -> tính giây còn lại đến 0h VN ngày mai
    vn_now = now + datetime.timedelta(hours=config.DAILY_TZ_OFFSET_HOURS)
    vn_tomorrow_midnight = (vn_now + datetime.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    remaining = (vn_tomorrow_midnight - vn_now).total_seconds()
    return max(0, int(remaining))

def claim_daily(user_id: int) -> dict:
    """
    {"ok": bool, "message": str, "amount": int, "streak_days": int}
    """
    now = datetime.datetime.utcnow()
    today_str = _vn_date_str(now)
    yesterday_str = _vn_date_str(now - datetime.timedelta(days=1))

    ref = _daily_ref(user_id)
    result_holder = {"ok": False, "message": "", "amount": 0, "streak_days": 0}

    def _txn(data):
        data = data or {"last_claim_date": None, "streak_days": 0}
        last_claim = data.get("last_claim_date")

        if last_claim == today_str:
            result_holder["message"] = "cooldown"
            return data

        streak_days = data.get("streak_days", 0)
        if last_claim == yesterday_str:
            streak_days += 1
        else:
            streak_days = 1

        base = random.randint(config.DAILY_MIN_REWARD, config.DAILY_MAX_REWARD)
        streak_weeks = streak_days // 7
        mult = 1.0 + streak_weeks * config.DAILY_STREAK_BONUS_PER_WEEK
        amount = max(1, round(base * mult))

        data["last_claim_date"] = today_str
        data["streak_days"] = streak_days

        result_holder["ok"] = True
        result_holder["amount"] = amount
        result_holder["streak_days"] = streak_days
        return data

    ref.transaction(_txn)

    if result_holder["ok"]:
        result_holder["amount"] = apply_coins_mult(user_id, result_holder["amount"], command="daily")
        transaction_coins(user_id, result_holder["amount"])

    return result_holder

# Jackpot
def _jackpot_stats_ref(user_id: int):
    return db.reference(f"users/{user_id}/jackpot_stats")

def _jackpot_big_win_chance(bet: int) -> float:
    """Nội suy log-scale giữa chance ở min bet và chance ở max bet."""
    lo, hi = config.JACKPOT_MIN_BET, config.JACKPOT_MAX_BET
    bet = max(lo, min(bet, hi))

    log_lo, log_hi, log_bet = math.log(lo), math.log(hi), math.log(bet)
    if log_hi == log_lo:
        t = 0.0
    else:
        t = (log_bet - log_lo) / (log_hi - log_lo)

    chance_lo = config.JACKPOT_BIG_WIN_CHANCE_LOW_BET
    chance_hi = config.JACKPOT_BIG_WIN_CHANCE_HIGH_BET
    return chance_lo + (chance_hi - chance_lo) * t

def play_jackpot(user_id: int, bet: int) -> dict:
    """
    {"ok": bool, "message": str, "outcome": "big_win"|"small_win"|"small_loss",
     "multiplier": float, "payout": int, "net": int}
    """
    if bet < config.JACKPOT_MIN_BET or bet > config.JACKPOT_MAX_BET:
        return {"ok": False, "message": f"Mức cược phải từ {config.JACKPOT_MIN_BET} đến {config.JACKPOT_MAX_BET} xu."}

    new_balance = transaction_coins(user_id, -bet)
    if new_balance is None:
        return {"ok": False, "message": "Không đủ xu."}

    big_chance = _jackpot_big_win_chance(bet) + get_jackpot_luck_bonus(user_id)
    big_chance = min(big_chance, 0.95)  # cap để luôn còn khả năng thua
    roll = random.random()

    if roll < big_chance:
        outcome = "big_win"
        mult = random.choices(
            config.JACKPOT_BIG_WIN_MULTIPLIERS,
            weights=config.JACKPOT_BIG_WIN_WEIGHTS,
        )[0]
    elif roll < big_chance + config.JACKPOT_SMALL_WIN_CHANCE:
        outcome = "small_win"
        mult = config.JACKPOT_SMALL_WIN_MULTIPLIER
    else:
        outcome = "small_loss"
        mult = random.choices(
            config.JACKPOT_SMALL_LOSS_MULTIPLIERS,
            weights=config.JACKPOT_SMALL_LOSS_WEIGHTS,
        )[0]

    payout = max(0, round(bet * mult))
    if outcome in ("big_win", "small_win"):
        payout = apply_coins_mult(user_id, payout, command="jackpot")
    net = payout - bet

    if payout > 0:
        transaction_coins(user_id, payout)

    _update_jackpot_stats(user_id, bet, outcome, net)

    return {
        "ok": True,
        "message": "",
        "outcome": outcome,
        "multiplier": mult,
        "payout": payout,
        "net": net,
    }

def _update_jackpot_stats(user_id: int, bet: int, outcome: str, net: int) -> None:
    ref = _jackpot_stats_ref(user_id)

    def _txn(stats):
        stats = stats or {
            "total_plays": 0, "total_wagered": 0, "total_won": 0,
            "current_win_streak": 0, "max_win_streak": 0, "big_wins": 0,
        }
        stats["total_plays"] = stats.get("total_plays", 0) + 1
        stats["total_wagered"] = stats.get("total_wagered", 0) + bet

        if outcome in ("big_win", "small_win"):
            stats["current_win_streak"] = stats.get("current_win_streak", 0) + 1
            stats["max_win_streak"] = max(stats.get("max_win_streak", 0), stats["current_win_streak"])
        else:
            stats["current_win_streak"] = 0

        if outcome == "big_win":
            stats["big_wins"] = stats.get("big_wins", 0) + 1

        if net > 0:
            stats["total_won"] = stats.get("total_won", 0) + net

        return stats

    ref.transaction(_txn)

def get_jackpot_stats(user_id: int) -> dict:
    return _jackpot_stats_ref(user_id).get() or {}

# Minesweeper
def _minesweeper_game_ref(user_id: int):
    return db.reference(f"minesweeper_games/{user_id}")

def get_active_minesweeper_game(user_id: int) -> dict | None:
    game = _minesweeper_game_ref(user_id).get()
    if game and not game.get("finished"):
        return game
    return None

def _count_adjacent_mines(mine_set: set, rows: int, cols: int, r: int, c: int) -> int:
    count = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) in mine_set:
                count += 1
    return count

def parse_minesweeper_coord(text: str, rows: int, cols: int) -> tuple[int, int] | None:
    """
    Chấp nhận dạng "A5" (cột chữ, hàng số) hoặc "3,5" (hàng,cột số 1-based).
    Trả về (row_idx, col_idx) 0-based, hoặc None nếu không hợp lệ / ngoài phạm vi.
    """
    text = text.strip().upper().replace(" ", "")
    if not text:
        return None

    # Dạng "3,5" hoặc "3-5" -> hàng,cột 1-based
    for sep in (",", "-", "x", "X"):
        if sep in text:
            parts = text.split(sep)
            if len(parts) == 2 and all(p.lstrip("-").isdigit() for p in parts):
                r, c = int(parts[0]) - 1, int(parts[1]) - 1
                if 0 <= r < rows and 0 <= c < cols:
                    return r, c
                return None

    # Dạng "A5" -> cột chữ cái, hàng số
    col_chars = ""
    i = 0
    while i < len(text) and text[i].isalpha():
        col_chars += text[i]
        i += 1
    row_digits = text[i:]

    if not col_chars or not row_digits or not row_digits.isdigit():
        return None

    col_idx = 0
    for ch in col_chars:
        col_idx = col_idx * 26 + (ord(ch) - ord("A") + 1)
    col_idx -= 1
    row_idx = int(row_digits) - 1

    if 0 <= row_idx < rows and 0 <= col_idx < cols:
        return row_idx, col_idx
    return None

def create_minesweeper_game(
    user_id: int, rows: int, cols: int, mines: int | None, seed: str | None
) -> dict:
    total_tiles = rows * cols
    if mines is None:
        mines = max(1, round(total_tiles * config.MINESWEEPER_MINE_RATIO))
    mines = min(mines, total_tiles - 1)

    rnd = random.Random(seed) if seed else random.Random()

    all_positions = [(r, c) for r in range(rows) for c in range(cols)]
    mine_positions = set(rnd.sample(all_positions, mines))
    mine_indices = [r * cols + c for (r, c) in mine_positions]

    adjacency = {}
    for r in range(rows):
        for c in range(cols):
            if (r, c) not in mine_positions:
                idx = r * cols + c
                adjacency[str(idx)] = _count_adjacent_mines(mine_positions, rows, cols, r, c)

    game = {
        "rows": rows,
        "cols": cols,
        "mine_indices": mine_indices,
        "mine_count": mines,
        "adjacency": adjacency,
        "revealed": [],
        "flagged": [],
        "safe_tiles_total": total_tiles - mines,
        "seed": seed,
        "finished": False,
        "won": False,
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    _minesweeper_game_ref(user_id).set(game)
    return game

def delete_minesweeper_game(user_id: int) -> None:
    _minesweeper_game_ref(user_id).delete()

def _flood_reveal(game: dict, start_idx: int) -> None:
    rows, cols = game["rows"], game["cols"]
    mine_set = set(game["mine_indices"])
    revealed = set(game["revealed"])
    adjacency = game["adjacency"]

    stack = [start_idx]
    while stack:
        idx = stack.pop()
        if idx in revealed or idx in mine_set:
            continue
        revealed.add(idx)
        if adjacency.get(str(idx), -1) == 0:
            r, c = divmod(idx, cols)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        nidx = nr * cols + nc
                        if nidx not in revealed and nidx not in mine_set:
                            stack.append(nidx)

    game["revealed"] = list(revealed)

def reveal_minesweeper_tile(user_id: int, row: int, col: int) -> dict:
    """
    {"status": "no_game"|"already_revealed"|"boom"|"continue"|"win"}
    """
    ref = _minesweeper_game_ref(user_id)
    result_holder = {"status": "no_game"}

    def _txn(game):
        if game is None or game.get("finished"):
            result_holder["status"] = "no_game"
            return game

        idx = row * game["cols"] + col
        if idx in game.get("revealed", []):
            result_holder["status"] = "already_revealed"
            return game

        mine_set = set(game["mine_indices"])
        if idx in mine_set:
            game["finished"] = True
            game["won"] = False
            result_holder["status"] = "boom"
            return game

        _flood_reveal(game, idx)

        if len(game["revealed"]) >= game["safe_tiles_total"]:
            game["finished"] = True
            game["won"] = True
            result_holder["status"] = "win"
        else:
            result_holder["status"] = "continue"

        return game

    ref.transaction(_txn)
    return result_holder

def toggle_minesweeper_flag(user_id: int, row: int, col: int) -> dict:
    """
    {"status": "no_game"|"toggled"|"win", "is_flagged": bool, "correct": bool}
    """
    ref = _minesweeper_game_ref(user_id)
    result_holder = {"status": "no_game", "is_flagged": False, "correct": False}

    def _txn(game):
        if game is None or game.get("finished"):
            result_holder["status"] = "no_game"
            return game

        idx = row * game["cols"] + col
        if idx in game.get("revealed", []):
            result_holder["status"] = "no_game"  # đã mở, không đặt cờ được
            return game

        flagged = set(game.get("flagged", []))
        mine_set = set(game["mine_indices"])

        if idx in flagged:
            flagged.discard(idx)
            result_holder["is_flagged"] = False
        else:
            flagged.add(idx)
            result_holder["is_flagged"] = True

        game["flagged"] = list(flagged)
        result_holder["correct"] = idx in mine_set
        result_holder["status"] = "toggled"

        if mine_set and flagged >= mine_set and result_holder["is_flagged"]:
            # cần đặt đúng TẤT CẢ mìn (flagged phải chứa toàn bộ mine_set) và không thừa cờ sai quá nhiều là chấp nhận được
            if flagged == mine_set:
                game["finished"] = True
                game["won"] = True
                result_holder["status"] = "win"

        return game

    ref.transaction(_txn)
    return result_holder

def render_minesweeper_image(game: dict, reveal_all_mines: bool = False):
    """Render bàn dò mìn thành ảnh PNG (PIL Image). Import PIL cục bộ để tránh phụ thuộc cứng ở module load."""
    from PIL import Image, ImageDraw, ImageFont

    rows, cols = game["rows"], game["cols"]
    cell = config.MINESWEEPER_CELL_PX
    label_size = cell  # vùng cho label hàng/cột

    width = label_size + cols * cell
    height = label_size + rows * cell

    img = Image.new("RGB", (width, height), (49, 51, 56))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(cell * 0.45))
        font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", int(cell * 0.35))
    except Exception:
        font = ImageFont.load_default()
        font_small = font

    revealed = set(game.get("revealed", []))
    flagged = set(game.get("flagged", []))
    mine_set = set(game.get("mine_indices", []))
    adjacency = game.get("adjacency", {})

    number_colors = {
        1: (79, 148, 255), 2: (94, 184, 100), 3: (255, 99, 99),
        4: (156, 110, 255), 5: (255, 170, 60), 6: (60, 200, 200),
        7: (230, 230, 230), 8: (150, 150, 150),
    }

    def col_label(c: int) -> str:
        label = ""
        c += 1
        while c > 0:
            c, rem = divmod(c - 1, 26)
            label = chr(65 + rem) + label
        return label

    # Header labels
    for c in range(cols):
        x0 = label_size + c * cell
        text = col_label(c)
        bbox = draw.textbbox((0, 0), text, font=font_small)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((x0 + cell / 2 - tw / 2, label_size / 2 - th / 2 - bbox[1]), text, font=font_small, fill=(200, 200, 200))

    for r in range(rows):
        y0 = label_size + r * cell
        text = str(r + 1)
        bbox = draw.textbbox((0, 0), text, font=font_small)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((label_size / 2 - tw / 2, y0 + cell / 2 - th / 2 - bbox[1]), text, font=font_small, fill=(200, 200, 200))

    # Grid
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            x0 = label_size + c * cell
            y0 = label_size + r * cell
            x1, y1 = x0 + cell, y0 + cell

            is_mine = idx in mine_set
            is_revealed = idx in revealed
            is_flagged = idx in flagged

            if reveal_all_mines and is_mine:
                fill = (200, 60, 60) if is_flagged else (60, 60, 60)
            elif is_revealed:
                fill = (230, 230, 230)
            else:
                fill = (90, 94, 102)

            draw.rectangle([x0 + 1, y0 + 1, x1 - 1, y1 - 1], fill=fill, outline=(30, 31, 34), width=1)

            if reveal_all_mines and is_mine:
                text = "*"  # ký hiệu mìn (emoji không render ổn định trong PIL mặc định)
                bbox = draw.textbbox((0, 0), text, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text((x0 + cell / 2 - tw / 2, y0 + cell / 2 - th / 2 - bbox[1]), text, font=font, fill=(20, 20, 20))
            elif is_flagged and not is_revealed:
                text = "F"
                bbox = draw.textbbox((0, 0), text, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text((x0 + cell / 2 - tw / 2, y0 + cell / 2 - th / 2 - bbox[1]), text, font=font, fill=(230, 60, 60))
            elif is_revealed:
                val = adjacency.get(str(idx), 0)
                if val:
                    text = str(val)
                    color = number_colors.get(val, (0, 0, 0))
                    bbox = draw.textbbox((0, 0), text, font=font)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    draw.text((x0 + cell / 2 - tw / 2, y0 + cell / 2 - th / 2 - bbox[1]), text, font=font, fill=color)

    return img

# Minigame chung (meme / car / country / hoahoc)
_MINIGAME_POOLS = {
    "meme": config.MEME_POOL,
    "car": config.CAR_POOL,
    "country": config.COUNTRY_POOL,
}

def _minigame_game_ref(user_id: int, kind: str):
    return db.reference(f"minigame_games/{kind}/{user_id}")

def get_active_minigame_game(user_id: int, kind: str) -> dict | None:
    game = _minigame_game_ref(user_id, kind).get()
    if game and not game.get("finished"):
        return game
    return None

def _normalize_minigame_answer(text: str) -> str:
    return text.strip().lower()

def build_minigame_questions(kind: str) -> list[dict]:
    """
    Chọn ngẫu nhiên MINIGAME_QUESTIONS_PER_GAME câu cho ván mới.
    Với meme/car/country: mỗi câu có "wiki_title" cần resolve ảnh ở tầng gọi (games.py, async).
    Với hoahoc: mỗi câu có "text" hiển thị trực tiếp, không cần ảnh.
    Với language: mỗi câu có "image_url" build sẵn từ flagcdn (không cần resolve async).
    """
    n = config.MINIGAME_QUESTIONS_PER_GAME

    if kind == "hoahoc":
        pool = list(config.HOAHOC_QUESTIONS)
        random.shuffle(pool)
        chosen = pool[:n]
        while len(chosen) < n:
            chosen.append(random.choice(config.HOAHOC_QUESTIONS))
        return [
            {"text": item["q"], "answers": item["answers"], "image_url": None}
            for item in chosen
        ]

    if kind == "language":
        pool = list(config.LANGUAGE_POOL)
        random.shuffle(pool)
        chosen = pool[:n]
        while len(chosen) < n:
            chosen.append(random.choice(config.LANGUAGE_POOL))
        return [
            {"answers": answers, "image_url": f"https://flagcdn.com/w320/{iso}.png"}
            for _country, iso, answers in chosen
        ]

    pool = list(_MINIGAME_POOLS[kind])
    random.shuffle(pool)
    chosen = pool[:n]
    while len(chosen) < n:
        chosen.append(random.choice(_MINIGAME_POOLS[kind]))
    return [
        {"wiki_title": title, "answers": answers, "image_url": None}
        for title, answers in chosen
    ]

def create_minigame_game(user_id: int, kind: str, questions: list[dict]) -> dict:
    now = datetime.datetime.utcnow()
    deadline = (now + datetime.timedelta(seconds=config.MINIGAME_SECONDS_PER_QUESTION)).isoformat()

    game = {
        "kind": kind,
        "questions": questions,
        "current_index": 0,
        "current_attempts": 0,
        "current_deadline": deadline,
        "correct_count": 0,
        "finished": False,
        "created_at": now.isoformat(),
    }
    _minigame_game_ref(user_id, kind).set(game)
    return game

def delete_minigame_game(user_id: int, kind: str) -> None:
    _minigame_game_ref(user_id, kind).delete()

def _minigame_answer_matches(guess: str, answers: list[str]) -> bool:
    guess_norm = _normalize_minigame_answer(guess)
    return guess_norm in [_normalize_minigame_answer(a) for a in answers]

def _advance_minigame_question(game: dict, is_last: bool) -> None:
    if is_last:
        game["finished"] = True
        return
    game["current_index"] += 1
    game["current_attempts"] = 0
    now = datetime.datetime.utcnow()
    game["current_deadline"] = (now + datetime.timedelta(seconds=config.MINIGAME_SECONDS_PER_QUESTION)).isoformat()

def submit_minigame_guess(user_id: int, kind: str, guess: str) -> dict:
    ref = _minigame_game_ref(user_id, kind)
    result_holder = {
        "status": "no_game", "correct_count": 0, "reward": 0,
        "is_last_question": False, "answer_text": None,
    }

    def _txn(game):
        if game is None or game.get("finished"):
            result_holder["status"] = "no_game"
            return game

        idx = game["current_index"]
        question = game["questions"][idx]
        is_last = idx == config.MINIGAME_QUESTIONS_PER_GAME - 1

        is_correct = _minigame_answer_matches(guess, question["answers"])
        game["current_attempts"] += 1

        if is_correct:
            game["correct_count"] += 1
            result_holder["status"] = "correct"
            result_holder["reward"] = config.MINIGAME_REWARD_PER_QUESTION[kind]
            _advance_minigame_question(game, is_last)
        elif game["current_attempts"] >= config.MINIGAME_ATTEMPTS_PER_QUESTION:
            result_holder["status"] = "wrong_final"
            _advance_minigame_question(game, is_last)
        else:
            result_holder["status"] = "wrong_retry"

        result_holder["correct_count"] = game["correct_count"]
        result_holder["is_last_question"] = is_last
        result_holder["answer_text"] = question["answers"][0]
        result_holder["attempts_left"] = max(0, config.MINIGAME_ATTEMPTS_PER_QUESTION - game["current_attempts"])
        return game

    ref.transaction(_txn)

    if result_holder["status"] == "correct":
        result_holder["reward"] = apply_coins_mult(user_id, result_holder["reward"], command=kind)

    return result_holder

def check_and_expire_minigame_question(user_id: int, kind: str) -> dict | None:
    ref = _minigame_game_ref(user_id, kind)
    result_holder = {"expired": False}

    def _txn(game):
        if game is None or game.get("finished"):
            return game
        deadline = parse_iso(game["current_deadline"])
        if datetime.datetime.utcnow() < deadline:
            return game

        idx = game["current_index"]
        is_last = idx == config.MINIGAME_QUESTIONS_PER_GAME - 1
        result_holder["expired"] = True
        result_holder["answer_text"] = game["questions"][idx]["answers"][0]
        result_holder["is_last_question"] = is_last
        result_holder["correct_count"] = game["correct_count"]
        _advance_minigame_question(game, is_last)
        return game

    ref.transaction(_txn)

    if not result_holder["expired"]:
        return None
    return result_holder

# Nối từ (word chain)
_NOITU_VOCAB_SET = None      # set[str] toàn bộ từ hợp lệ
_NOITU_BY_FIRST_SYLLABLE = None  # dict[str, list[str]] tiếng đầu -> danh sách từ

def _load_noitu_vocab():
    global _NOITU_VOCAB_SET, _NOITU_BY_FIRST_SYLLABLE
    if _NOITU_VOCAB_SET is not None:
        return

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.NOITU_VOCAB_FILE)
    with open(path, encoding="utf-8") as f:
        words = json.load(f)

    _NOITU_VOCAB_SET = set(words)
    by_first = {}
    for w in words:
        first = w.split()[0]
        by_first.setdefault(first, []).append(w)
    _NOITU_BY_FIRST_SYLLABLE = by_first

def _noitu_last_syllable(word: str) -> str:
    return word.strip().lower().split()[-1]

def _noitu_first_syllable(word: str) -> str:
    return word.strip().lower().split()[0]

def is_valid_noitu_word(word: str) -> bool:
    _load_noitu_vocab()
    word = word.strip().lower()
    return word in _NOITU_VOCAB_SET

def _noitu_game_ref(channel_id: int):
    return db.reference(f"noitu_games/{channel_id}")

def _noitu_channel_state_ref(channel_id: int):
    """Lưu trạng thái xuyên suốt nhiều ván trong 1 kênh: tổng số ván đã chơi + lịch sử khoá từ."""
    return db.reference(f"noitu_channel_state/{channel_id}")

def get_noitu_game(channel_id: int) -> dict | None:
    return _noitu_game_ref(channel_id).get()

def _noitu_get_locked_words(channel_id: int) -> dict:
    """Trả về {word: unlock_at_game_number} — từ đang bị khoá và số ván sẽ mở khoá."""
    state = _noitu_channel_state_ref(channel_id).get() or {}
    return state.get("locked_words", {})

def _noitu_word_is_locked(channel_id: int, word: str, current_game_number: int) -> bool:
    locked = _noitu_get_locked_words(channel_id)
    unlock_at = locked.get(word)
    if unlock_at is None:
        return False
    return current_game_number < unlock_at

def noitu_has_remaining_words(channel_id: int, last_syllable: str, current_game_number: int) -> bool:
    """Kiểm tra còn từ nào trong từ điển bắt đầu bằng last_syllable mà chưa bị khoá cooldown không."""
    _load_noitu_vocab()
    candidates = _NOITU_BY_FIRST_SYLLABLE.get(last_syllable, [])
    locked = _noitu_get_locked_words(channel_id)
    for w in candidates:
        unlock_at = locked.get(w)
        if unlock_at is None or current_game_number >= unlock_at:
            return True
    return False

def _noitu_pick_start_pair(channel_id: int, current_game_number: int) -> str:
    """Chọn ngẫu nhiên 1 từ 2 tiếng làm cặp khởi đầu, ưu tiên từ chưa bị khoá."""
    _load_noitu_vocab()
    locked = _noitu_get_locked_words(channel_id)
    available = [
        w for w in _NOITU_VOCAB_SET
        if locked.get(w) is None or current_game_number >= locked.get(w)
    ]
    pool = available if available else list(_NOITU_VOCAB_SET)
    return random.choice(pool)

def start_noitu_game(channel_id: int) -> dict:
    state_ref = _noitu_channel_state_ref(channel_id)
    state = state_ref.get() or {"total_games_played": 0, "locked_words": {}}
    game_number = state.get("total_games_played", 0) + 1

    start_word = _noitu_pick_start_pair(channel_id, game_number)

    game = {
        "game_number": game_number,
        "current_word": start_word,
        "used_words_this_game": [start_word],
        "last_player_id": None,
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    _noitu_game_ref(channel_id).set(game)

    state["total_games_played"] = game_number
    state_ref.set(state)
    return game

def delete_noitu_game(channel_id: int) -> None:
    _noitu_game_ref(channel_id).delete()

def submit_noitu_word(channel_id: int, user_id: int, word: str) -> dict:
    """
    {"status": "invalid_format"|"not_in_dict"|"wrong_chain"|"locked_cooldown"|"same_player"|"ok"|"bingo",
     "current_word": str, "winner_id": int|None, "unlock_in_games": int|None}
    """
    word_norm = word.strip().lower()
    parts = word_norm.split()

    if len(parts) != 2:
        return {"status": "invalid_format"}

    game_ref = _noitu_game_ref(channel_id)
    state_ref = _noitu_channel_state_ref(channel_id)

    result_holder = {"status": "no_game"}

    def _txn(game):
        if game is None:
            result_holder["status"] = "no_game"
            return game

        game_number = game.get("game_number", 1)
        current_word = game["current_word"]
        expected_first = _noitu_last_syllable(current_word)

        if game.get("last_player_id") == user_id:
            result_holder["status"] = "same_player"
            return game

        if _noitu_first_syllable(word_norm) != expected_first:
            result_holder["status"] = "wrong_chain"
            return game

        if not is_valid_noitu_word(word_norm):
            result_holder["status"] = "not_in_dict"
            return game

        if _noitu_word_is_locked(channel_id, word_norm, game_number):
            locked = _noitu_get_locked_words(channel_id)
            unlock_at = locked.get(word_norm, game_number)
            result_holder["status"] = "locked_cooldown"
            result_holder["unlock_in_games"] = max(0, unlock_at - game_number)
            return game

        used_this_game = list(game.get("used_words_this_game", []))
        used_this_game.append(word_norm)
        game["used_words_this_game"] = used_this_game
        game["current_word"] = word_norm
        game["last_player_id"] = user_id

        # Khoá từ vừa dùng trong NOITU_WORD_COOLDOWN_GAMES ván tiếp theo
        state = state_ref.get() or {"total_games_played": game_number, "locked_words": {}}
        locked_words = dict(state.get("locked_words", {}))
        locked_words[word_norm] = game_number + config.NOITU_WORD_COOLDOWN_GAMES
        state["locked_words"] = locked_words
        state_ref.set(state)

        last_syl = _noitu_last_syllable(word_norm)
        if not noitu_has_remaining_words(channel_id, last_syl, game_number):
            result_holder["status"] = "bingo"
            result_holder["winner_id"] = user_id
        else:
            result_holder["status"] = "ok"

        result_holder["current_word"] = word_norm
        return game

    game_ref.transaction(_txn)
    return result_holder

# Level system
def _level_ref(user_id: int):
    return db.reference(f"users/{user_id}/level")

DEFAULT_LEVEL_DATA = {
    "level": 0,
    "xp": 0,
    "last_message_xp_at": None,
    "recent_message_timestamps": [],  # dùng để phát hiện spam
}

def get_level_data(user_id: int) -> dict:
    data = _level_ref(user_id).get()
    if data is None:
        return dict(DEFAULT_LEVEL_DATA)
    merged = dict(DEFAULT_LEVEL_DATA)
    merged.update(data)
    return merged

def xp_needed_for_level(level: int) -> int:
    return config.LEVEL_XP_NEEDED_BASE + level * config.LEVEL_XP_NEEDED_PER_LEVEL

def _xp_for_action(level: int, base: int) -> int:
    return max(1, round(base * (1 + level * config.LEVEL_XP_GROWTH_PER_LEVEL)))

def _apply_xp(data: dict, amount: int) -> dict:
    """Cộng XP vào data, xử lý lên level (có thể lên nhiều cấp cùng lúc). Trả về {"leveled_up": bool, "new_level": int, "levels_gained": int}."""
    level = data.get("level", 0)
    xp = data.get("xp", 0) + amount
    levels_gained = 0

    while level < config.LEVEL_MAX and xp >= xp_needed_for_level(level + 1):
        xp -= xp_needed_for_level(level + 1)
        level += 1
        levels_gained += 1

    if level >= config.LEVEL_MAX:
        level = config.LEVEL_MAX
        xp = 0

    data["level"] = level
    data["xp"] = xp
    return {"leveled_up": levels_gained > 0, "new_level": level, "levels_gained": levels_gained}

def add_message_xp(user_id: int) -> dict:
    """
    Cộng XP cho 1 tin nhắn nếu qua cooldown (chống spam động: 5s bình thường, 10s nếu spam).
    Trả về {"granted": bool, "leveled_up": bool, "new_level": int} — granted=False nếu đang cooldown.
    """
    now = datetime.datetime.utcnow()
    ref = _level_ref(user_id)
    result_holder = {"granted": False, "leveled_up": False, "new_level": 0}

    def _txn(data):
        data = data or dict(DEFAULT_LEVEL_DATA)
        for k, v in DEFAULT_LEVEL_DATA.items():
            data.setdefault(k, copy.deepcopy(v))

        recent = data.get("recent_message_timestamps", [])
        # giữ lại các mốc trong cửa sổ spam window
        recent = [
            t for t in recent
            if (now - parse_iso(t)).total_seconds() <= config.LEVEL_MESSAGE_SPAM_WINDOW_SEC
        ]
        is_spam = len(recent) >= config.LEVEL_MESSAGE_SPAM_THRESHOLD
        cooldown_sec = config.LEVEL_MESSAGE_SPAM_COOLDOWN_SEC if is_spam else config.LEVEL_MESSAGE_COOLDOWN_SEC

        last_xp_at = data.get("last_message_xp_at")
        if last_xp_at:
            elapsed = (now - parse_iso(last_xp_at)).total_seconds()
            if elapsed < cooldown_sec:
                recent.append(now.isoformat())
                data["recent_message_timestamps"] = recent[-10:]
                result_holder["granted"] = False
                return data

        recent.append(now.isoformat())
        data["recent_message_timestamps"] = recent[-10:]
        data["last_message_xp_at"] = now.isoformat()

        xp_gain = _xp_for_action(data.get("level", 0), config.LEVEL_MESSAGE_XP_BASE)
        level_result = _apply_xp(data, xp_gain)

        result_holder["granted"] = True
        result_holder["leveled_up"] = level_result["leveled_up"]
        result_holder["new_level"] = level_result["new_level"]
        result_holder["xp_gained"] = xp_gain
        return data

    ref.transaction(_txn)
    return result_holder

def add_minigame_win_xp(user_id: int) -> dict:
    """Cộng XP khi thắng 1 minigame bất kỳ (không cooldown riêng, việc thắng game đã tự nhiên giới hạn tần suất)."""
    ref = _level_ref(user_id)
    result_holder = {"leveled_up": False, "new_level": 0, "xp_gained": 0}

    def _txn(data):
        data = data or dict(DEFAULT_LEVEL_DATA)
        for k, v in DEFAULT_LEVEL_DATA.items():
            data.setdefault(k, copy.deepcopy(v))

        xp_gain = _xp_for_action(data.get("level", 0), config.LEVEL_MINIGAME_WIN_XP_BASE)
        level_result = _apply_xp(data, xp_gain)

        result_holder["leveled_up"] = level_result["leveled_up"]
        result_holder["new_level"] = level_result["new_level"]
        result_holder["xp_gained"] = xp_gain
        return data

    ref.transaction(_txn)
    return result_holder

# AI Chat (Gemini)
def _ai_chat_ref(user_id: int):
    return db.reference(f"users/{user_id}/ai_chat")

def get_ai_chat_cooldown_remaining_sec(user_id: int) -> int:
    data = _ai_chat_ref(user_id).get() or {}
    last_at = data.get("last_message_at")
    if not last_at:
        return 0
    elapsed = (datetime.datetime.utcnow() - parse_iso(last_at)).total_seconds()
    remaining = config.AI_CHAT_COOLDOWN_SEC - elapsed
    return max(0, int(remaining))

def get_ai_chat_history(user_id: int) -> list:
    """Trả về list [{"role": "user"|"model", "text": str}, ...] theo thứ tự cũ -> mới."""
    data = _ai_chat_ref(user_id).get() or {}
    return data.get("history", [])

def append_ai_chat_turn(user_id: int, user_text: str, model_text: str) -> None:
    ref = _ai_chat_ref(user_id)

    def _txn(data):
        data = data or {"history": [], "last_message_at": None}
        history = list(data.get("history", []))
        history.append({"role": "user", "text": user_text})
        history.append({"role": "model", "text": model_text})
        max_entries = config.AI_CHAT_HISTORY_LENGTH * 2
        data["history"] = history[-max_entries:]
        data["last_message_at"] = datetime.datetime.utcnow().isoformat()
        return data

    ref.transaction(_txn)

def clear_ai_chat_history(user_id: int) -> None:
    _ai_chat_ref(user_id).delete()


# Chess
def _chess_game_ref(game_id: str):
    return db.reference(f"chess_games/{game_id}")

def _chess_user_active_ref(user_id: int):
    return db.reference(f"users/{user_id}/active_chess_game")

def _chess_elo_ref(user_id: int):
    return db.reference(f"users/{user_id}/chess_elo")

def get_chess_elo(user_id: int) -> int:
    val = _chess_elo_ref(user_id).get()
    return val if isinstance(val, int) else config.CHESS_STARTING_ELO

def _set_chess_elo(user_id: int, elo: int) -> None:
    _chess_elo_ref(user_id).set(max(0, round(elo)))

def _elo_expected_score(rating_a: int, rating_b: int) -> float:
    """Xác suất kỳ vọng A thắng B theo công thức Elo chuẩn."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def _elo_update(rating: int, expected: float, actual_score: float) -> int:
    """actual_score: 1.0 thắng, 0.5 hoà, 0.0 thua."""
    return round(rating + config.CHESS_ELO_K_FACTOR * (actual_score - expected))

def apply_chess_elo_result(white_id: int, black_elo_or_id, black_is_bot: bool, result: str) -> dict:
    """
    Cập nhật ELO sau khi ván kết thúc.
    result: "white_win"|"black_win"|"draw"
    black_elo_or_id: nếu black_is_bot=True thì đây là ELO cố định của bot (int),
                      nếu False thì đây là user_id của người chơi đen.
    Trả về {"white_elo_before", "white_elo_after", "black_elo_before", "black_elo_after"}
    """
    white_elo = get_chess_elo(white_id)
    black_elo = black_elo_or_id if black_is_bot else get_chess_elo(black_elo_or_id)

    expected_white = _elo_expected_score(white_elo, black_elo)
    expected_black = 1 - expected_white

    if result == "white_win":
        score_white, score_black = 1.0, 0.0
    elif result == "black_win":
        score_white, score_black = 0.0, 1.0
    else:
        score_white, score_black = 0.5, 0.5

    new_white_elo = _elo_update(white_elo, expected_white, score_white)
    _set_chess_elo(white_id, new_white_elo)

    new_black_elo = black_elo
    if not black_is_bot:
        new_black_elo = _elo_update(black_elo, expected_black, score_black)
        _set_chess_elo(black_elo_or_id, new_black_elo)

    return {
        "white_elo_before": white_elo, "white_elo_after": new_white_elo,
        "black_elo_before": black_elo, "black_elo_after": new_black_elo,
    }

def get_user_active_chess_game_id(user_id: int) -> str | None:
    return _chess_user_active_ref(user_id).get()

def get_chess_game(game_id: str) -> dict | None:
    return _chess_game_ref(game_id).get()

def create_chess_game(
    white_id: int, black_id: int | None, mode: str, difficulty: str | None = None
) -> tuple[str, dict]:
    """
    mode: "pvp" hoặc "bot". Với "bot", black_id=None (bot chơi quân đen).
    """
    import chess

    game_id = uuid.uuid4().hex[:12]
    board = chess.Board()

    game = {
        "white_id": white_id,
        "black_id": black_id,
        "mode": mode,
        "difficulty": difficulty,
        "fen": board.fen(),
        "move_history": [],
        "finished": False,
        "result": None,  # "white_win"|"black_win"|"draw"
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    _chess_game_ref(game_id).set(game)
    _chess_user_active_ref(white_id).set(game_id)
    if black_id:
        _chess_user_active_ref(black_id).set(game_id)
    return game_id, game

def delete_chess_game(game_id: str) -> None:
    game = get_chess_game(game_id)
    if game:
        _chess_user_active_ref(game["white_id"]).delete()
        if game.get("black_id"):
            _chess_user_active_ref(game["black_id"]).delete()
    _chess_game_ref(game_id).delete()

def resign_chess_game(game_id: str, resigning_user_id: int) -> dict | None:
    """Người chơi đầu hàng. Trả về game đã cập nhật (finished=True) hoặc None nếu không hợp lệ."""
    game = get_chess_game(game_id)
    if game is None or game.get("finished"):
        return None

    if resigning_user_id == game["white_id"]:
        game["result"] = "black_win"
    elif resigning_user_id == game.get("black_id"):
        game["result"] = "white_win"
    else:
        return None

    game["finished"] = True
    _chess_game_ref(game_id).set(game)
    _chess_user_active_ref(game["white_id"]).delete()
    if game.get("black_id"):
        _chess_user_active_ref(game["black_id"]).delete()
    return game

def get_chess_legal_moves_by_piece(game_id: str) -> dict:
    """Trả về {square_name: [dest_square_name, ...]} cho các quân của bên đang đi."""
    import chess

    game = get_chess_game(game_id)
    if game is None:
        return {}

    board = chess.Board(game["fen"])
    grouped = {}
    for move in board.legal_moves:
        from_sq = chess.square_name(move.from_square)
        to_sq = chess.square_name(move.to_square)
        grouped.setdefault(from_sq, []).append(to_sq)
    return grouped

def submit_chess_move(game_id: str, from_sq: str, to_sq: str, promotion: str | None = None) -> dict:
    """
    {"status": "no_game"|"illegal"|"ok"|"checkmate"|"stalemate"|"draw",
     "winner_id": int|None, "fen": str, "san": str|None}
    """
    import chess

    game = get_chess_game(game_id)
    if game is None or game.get("finished"):
        return {"status": "no_game"}

    board = chess.Board(game["fen"])

    try:
        from_square = chess.parse_square(from_sq)
        to_square = chess.parse_square(to_sq)
    except ValueError:
        return {"status": "illegal"}

    promo_piece = None
    if promotion:
        promo_map = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}
        promo_piece = promo_map.get(promotion.lower())

    move = chess.Move(from_square, to_square, promotion=promo_piece)

    # Tự động phong hậu nếu là nước đi tốt lên hàng cuối mà không chỉ định promotion
    if move not in board.legal_moves:
        auto_queen = chess.Move(from_square, to_square, promotion=chess.QUEEN)
        if auto_queen in board.legal_moves:
            move = auto_queen
        else:
            return {"status": "illegal"}

    san = board.san(move)
    board.push(move)

    game["fen"] = board.fen()
    game["move_history"] = list(game.get("move_history", [])) + [san]

    result = {"status": "ok", "winner_id": None, "fen": game["fen"], "san": san}

    if board.is_checkmate():
        game["finished"] = True
        loser_is_white = board.turn == chess.WHITE
        winner_id = game["black_id"] if loser_is_white else game["white_id"]
        game["result"] = "black_win" if loser_is_white else "white_win"
        result["status"] = "checkmate"
        result["winner_id"] = winner_id
    elif board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        game["finished"] = True
        game["result"] = "draw"
        result["status"] = "draw"

    _chess_game_ref(game_id).set(game)

    if game["finished"]:
        _chess_user_active_ref(game["white_id"]).delete()
        if game.get("black_id"):
            _chess_user_active_ref(game["black_id"]).delete()

    return result

_CHESS_PIECE_VALUES = None

def _chess_piece_values():
    import chess
    global _CHESS_PIECE_VALUES
    if _CHESS_PIECE_VALUES is None:
        _CHESS_PIECE_VALUES = {
            chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
            chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0,
        }
    return _CHESS_PIECE_VALUES

def _chess_evaluate(board) -> int:
    """Đánh giá vị trí theo material, dương = tốt cho bên trắng."""
    import chess
    values = _chess_piece_values()
    score = 0
    for piece_type, value in values.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * value
        score -= len(board.pieces(piece_type, chess.BLACK)) * value
    return score

def _chess_minimax(board, depth: int, alpha: int, beta: int, maximizing: bool):
    import chess

    if depth == 0 or board.is_game_over():
        return _chess_evaluate(board), None

    best_move = None
    legal_moves = list(board.legal_moves)

    if maximizing:
        max_eval = -10**9
        for move in legal_moves:
            board.push(move)
            eval_score, _ = _chess_minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = 10**9
        for move in legal_moves:
            board.push(move)
            eval_score, _ = _chess_minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval, best_move

def compute_chess_bot_move(fen: str, difficulty: str) -> str | None:
    """Trả về nước đi bot dạng UCI (vd 'e7e5'), hoặc None nếu hết nước đi."""
    import chess

    board = chess.Board(fen)
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None

    depth = config.CHESS_BOT_DIFFICULTY_DEPTH.get(difficulty, 0)

    if depth == 0:
        move = random.choice(legal_moves)
        return move.uci()

    maximizing = board.turn == chess.WHITE
    _, best_move = _chess_minimax(board, depth, -10**9, 10**9, maximizing)
    if best_move is None:
        best_move = random.choice(legal_moves)
    return best_move.uci()

def render_chess_board_image(fen: str, flipped: bool = False):
    """Render bàn cờ thành ảnh PIL đơn giản (hình học + ký tự quân, không cần font đặc biệt)."""
    import chess
    from PIL import Image, ImageDraw, ImageFont

    board = chess.Board(fen)
    cell = config.CHESS_CELL_PX
    size = cell * 8

    img = Image.new("RGB", (size, size), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    light = (240, 217, 181)
    dark = (181, 136, 99)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(cell * 0.55))
    except Exception:
        font = ImageFont.load_default()

    piece_symbols = {
        chess.PAWN: "P", chess.KNIGHT: "N", chess.BISHOP: "B",
        chess.ROOK: "R", chess.QUEEN: "Q", chess.KING: "K",
    }

    for rank in range(8):
        for file in range(8):
            display_rank = rank if flipped else 7 - rank
            display_file = 7 - file if flipped else file

            x0, y0 = file * cell, rank * cell
            x1, y1 = x0 + cell, y0 + cell
            is_light = (display_rank + display_file) % 2 == 1
            draw.rectangle([x0, y0, x1, y1], fill=light if is_light else dark)

            square = chess.square(display_file, display_rank)
            piece = board.piece_at(square)
            if piece:
                symbol = piece_symbols[piece.piece_type]
                color = (255, 255, 255) if piece.color == chess.WHITE else (20, 20, 20)
                outline = (20, 20, 20) if piece.color == chess.WHITE else (255, 255, 255)
                bbox = draw.textbbox((0, 0), symbol, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                tx = x0 + cell / 2 - tw / 2
                ty = y0 + cell / 2 - th / 2 - bbox[1]
                for dx in (-1, 1):
                    for dy in (-1, 1):
                        draw.text((tx + dx, ty + dy), symbol, font=font, fill=outline)
                draw.text((tx, ty), symbol, font=font, fill=color)

    return img


# Title buff aggregation
def get_equipped_title_buffs(user_id: int) -> dict:
    """Cộng dồn buffs từ các title đang trang bị. Trả về dict tổng hợp, ví dụ:
    {"coins_mult_global": 0.5, "coins_mult_work": 0.2, "jackpot_luck": 0.1, "extra_plays_wordle": 2, ...}
    """
    equipped = get_user_titles(user_id)["equipped"]
    total = {}
    for key in equipped:
        meta = config.TITLES.get(key)
        if not meta:
            continue
        for buff_key, value in meta.get("buffs", {}).items():
            total[buff_key] = total.get(buff_key, 0) + value
    return total

def apply_coins_mult(user_id: int, base_amount: int, command: str | None = None) -> int:
    """Áp dụng multiplier coins (global + theo lệnh cụ thể nếu có) vào 1 khoản thưởng."""
    buffs = get_equipped_title_buffs(user_id)
    total_pct = buffs.get("coins_mult_global", 0)
    if command:
        total_pct += buffs.get(f"coins_mult_{command}", 0)
    return max(0, round(base_amount * (1 + total_pct)))

def get_extra_plays(user_id: int, command: str) -> int:
    buffs = get_equipped_title_buffs(user_id)
    return int(buffs.get(f"extra_plays_{command}", 0))

def get_jackpot_luck_bonus(user_id: int) -> float:
    buffs = get_equipped_title_buffs(user_id)
    return buffs.get("jackpot_luck", 0)

def get_work_bad_event_reduction(user_id: int) -> float:
    buffs = get_equipped_title_buffs(user_id)
    return min(0.9, buffs.get("work_bad_event_reduction", 0))  # cap 90% để tránh miễn nhiễm hoàn toàn

def get_shop_discount(user_id: int) -> float:
    buffs = get_equipped_title_buffs(user_id)
    return min(0.5, buffs.get("shop_discount", 0))  # cap 50%

# ELO chung (dùng cho shop, tách biệt với chess_elo)
def get_elo(user_id: int) -> int:
    """ELO chung dùng để mua sắm trong shop — CHÚ Ý: khác với chess_elo (ELO thi đấu cờ vua)."""
    val = db.reference(f"users/{user_id}/shop_elo").get()
    return val if isinstance(val, int) else 0

def add_elo(user_id: int, amount: int) -> int:
    ref = db.reference(f"users/{user_id}/shop_elo")
    result_holder = {"new_val": 0}

    def _txn(current):
        current = current or 0
        new_val = max(0, current + amount)
        result_holder["new_val"] = new_val
        return new_val

    ref.transaction(_txn)
    return result_holder["new_val"]

def spend_elo(user_id: int, amount: int) -> bool:
    """Trừ ELO chung nếu đủ. Trả về False nếu không đủ."""
    ref = db.reference(f"users/{user_id}/shop_elo")
    result_holder = {"ok": False}

    def _txn(current):
        current = current or 0
        if current < amount:
            result_holder["ok"] = False
            return current
        result_holder["ok"] = True
        return current - amount

    ref.transaction(_txn)
    return result_holder["ok"]

# Shop
def _shop_state_ref():
    return db.reference("shop_state")

def _shop_inventory_ref(user_id: int):
    return db.reference(f"users/{user_id}/shop_inventory")

def _shop_bonus_plays_ref(user_id: int):
    return db.reference(f"users/{user_id}/shop_bonus_plays")

def get_shop_bonus_plays(user_id: int) -> int:
    val = _shop_bonus_plays_ref(user_id).get()
    return val if isinstance(val, int) else 0

def _consume_shop_bonus_play(user_id: int) -> bool:
    ref = _shop_bonus_plays_ref(user_id)
    result_holder = {"ok": False}

    def _txn(current):
        current = current or 0
        if current <= 0:
            result_holder["ok"] = False
            return current
        result_holder["ok"] = True
        return current - 1

    ref.transaction(_txn)
    return result_holder["ok"]

def _add_shop_bonus_plays(user_id: int, amount: int) -> None:
    ref = _shop_bonus_plays_ref(user_id)

    def _txn(current):
        return (current or 0) + amount

    ref.transaction(_txn)

def get_current_shop_rotation() -> dict:
    """
    Trả về {"items": {item_key: stock}, "refreshed_at": iso, "next_refresh_at": iso}.
    Tự động random tập con item mới nếu đã hết hạn 10 phút.
    """
    state = _shop_state_ref().get()
    now = datetime.datetime.utcnow()

    needs_refresh = True
    if state:
        refreshed_at = parse_iso(state.get("refreshed_at"))
        if refreshed_at:
            elapsed_min = (now - refreshed_at).total_seconds() / 60
            if elapsed_min < config.SHOP_REFRESH_INTERVAL_MIN:
                needs_refresh = False

    if not needs_refresh:
        return state

    all_keys = list(config.SHOP_ITEMS.keys())
    n = min(config.SHOP_ITEMS_PER_ROTATION, len(all_keys))
    chosen_keys = random.sample(all_keys, n)

    items = {}
    for key in chosen_keys:
        rarity = config.SHOP_ITEMS[key]["rarity"]
        lo, hi = config.SHOP_RARITY_STOCK_RANGE.get(rarity, (1, 1))
        items[key] = random.randint(lo, hi)

    next_refresh = now + datetime.timedelta(minutes=config.SHOP_REFRESH_INTERVAL_MIN)
    new_state = {
        "items": items,
        "refreshed_at": now.isoformat(),
        "next_refresh_at": next_refresh.isoformat(),
    }
    _shop_state_ref().set(new_state)
    return new_state

def get_shop_inventory(user_id: int) -> dict:
    """Kho đồ user (item category='inventory' đã mua, chưa dùng). {item_key: count}"""
    return _shop_inventory_ref(user_id).get() or {}

def _add_to_inventory(user_id: int, item_key: str, count: int = 1) -> None:
    ref = _shop_inventory_ref(user_id)

    def _txn(current):
        current = current or {}
        current[item_key] = current.get(item_key, 0) + count
        return current

    ref.transaction(_txn)

def consume_inventory_item(user_id: int, item_key: str) -> bool:
    """Dùng 1 item trong kho đồ (giảm số lượng). Trả về False nếu không có."""
    ref = _shop_inventory_ref(user_id)
    result_holder = {"ok": False}

    def _txn(current):
        current = current or {}
        count = current.get(item_key, 0)
        if count <= 0:
            result_holder["ok"] = False
            return current
        current[item_key] = count - 1
        if current[item_key] <= 0:
            del current[item_key]
        result_holder["ok"] = True
        return current

    ref.transaction(_txn)
    return result_holder["ok"]

def buy_shop_item(user_id: int, item_key: str) -> dict:
    """
    {"ok": bool, "message": str, "item_name": str, "effect_summary": str, "got_bonus_title": bool, "failed_title": bool}
    """
    item = config.SHOP_ITEMS.get(item_key)
    if item is None:
        return {"ok": False, "message": "Vật phẩm không tồn tại."}

    rotation = get_current_shop_rotation()
    stock = rotation.get("items", {}).get(item_key)
    if stock is None:
        return {"ok": False, "message": "Vật phẩm này hiện không có trong shop, hãy đợi lượt làm mới tiếp theo."}
    if stock <= 0:
        return {"ok": False, "message": "Vật phẩm này đã hết hàng trong lượt này."}

    price = item["price"]
    currency = item["currency"]
    discount = get_shop_discount(user_id)
    final_price = max(0, round(price * (1 - discount)))

    if currency == "coins":
        new_balance = transaction_coins(user_id, -final_price)
        if new_balance is None:
            return {"ok": False, "message": f"Không đủ xu (cần {final_price})."}
    else:  # elo
        if not spend_elo(user_id, final_price):
            return {"ok": False, "message": f"Không đủ ELO (cần {final_price})."}

    # Trừ tồn kho rotation hiện tại
    state = _shop_state_ref().get() or rotation
    items = dict(state.get("items", {}))
    items[item_key] = max(0, items.get(item_key, 1) - 1)
    state["items"] = items
    _shop_state_ref().set(state)

    log_purchase(user_id, item["name"], final_price, currency)

    result = {"ok": True, "message": "", "item_name": item["name"], "got_bonus_title": False, "failed_title": False}
    effect = item.get("effect", {})

    if item["category"] == "inventory":
        _add_to_inventory(user_id, item_key, 1)
        result["effect_summary"] = "Đã thêm vào kho đồ, dùng sau tại lệnh liên quan."
        return result

    # category == "instant": áp dụng ngay
    summary_parts = []

    if "coins" in effect:
        transaction_coins(user_id, effect["coins"])
        summary_parts.append(f"+{effect['coins']} xu")

    if "elo" in effect:
        add_elo(user_id, effect["elo"])
        summary_parts.append(f"+{effect['elo']} ELO")

    if "game_plays" in effect:
        _add_shop_bonus_plays(user_id, effect["game_plays"])
        summary_parts.append(f"+{effect['game_plays']} lượt chơi (mọi game giới hạn/ngày)")

    if "role_id" in effect:
        summary_parts.append("Role đặc biệt (bot sẽ gán ở tầng Discord)")

    if "title_key" in effect:
        fail_chance = item.get("fail_chance", 0)
        if fail_chance > 0 and random.random() < fail_chance:
            result["failed_title"] = True
            summary_parts.append(f"❌ Không may mắn, không nhận được danh hiệu lần này.")
        else:
            granted = give_title(user_id, effect["title_key"])
            if granted:
                summary_parts.append(f"Nhận danh hiệu **{config.TITLES.get(effect['title_key'], {}).get('name', effect['title_key'])}**")
            else:
                summary_parts.append("Bạn đã sở hữu danh hiệu này rồi.")

    title_chance_cfg = item.get("title_chance")
    if title_chance_cfg:
        title_key = title_chance_cfg["title_key"]
        chance = title_chance_cfg["chance"]
        already_has = title_key in get_user_titles(user_id)["owned"]
        if not already_has and random.random() < chance:
            give_title(user_id, title_key)
            result["got_bonus_title"] = True
            summary_parts.append(f"🎉 May mắn! Nhận thêm danh hiệu **{config.TITLES.get(title_key, {}).get('name', title_key)}**")

    result["effect_summary"] = "\n".join(summary_parts) if summary_parts else "Đã mua thành công."
    return result

# Quest (nhiệm vụ ngày/tuần)
def _quest_daily_ref(user_id: int):
    return db.reference(f"users/{user_id}/quest_daily")

def _quest_weekly_ref(user_id: int):
    return db.reference(f"users/{user_id}/quest_weekly")

def _quest_ticket_ref(user_id: int):
    return db.reference(f"users/{user_id}/quest_game_tickets")

def _vn_date_str_now() -> str:
    return _vn_date_str(datetime.datetime.utcnow())

def _vn_week_key_now() -> str:
    """Trả về khoá tuần dạng 'YYYY-WW' theo ISO week, tính theo giờ VN."""
    vn_now = datetime.datetime.utcnow() + datetime.timedelta(hours=config.WORK_TZ_OFFSET_HOURS)
    iso_year, iso_week, _ = vn_now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"

def _roll_quest_set(pool: list, reward_pool: list, count: int) -> list:
    chosen_defs = random.sample(pool, min(count, len(pool)))
    quests = []
    for qdef in chosen_defs:
        reward = random.choice(reward_pool)
        quests.append({
            "id": qdef["id"],
            "desc": qdef["desc"],
            "goal_type": qdef["goal_type"],
            "target": qdef["target"],
            "progress": 0,
            "completed": False,
            "claimed": False,
            "reward": reward,
        })
    return quests

def get_daily_quests(user_id: int) -> dict:
    """Trả về {"date": str, "quests": [...]}. Tự tạo mới nếu đã sang ngày mới."""
    ref = _quest_daily_ref(user_id)
    data = ref.get()
    today = _vn_date_str_now()

    if data is None or data.get("date") != today:
        quests = _roll_quest_set(config.QUEST_POOL_DAILY, config.QUEST_REWARD_POOL_DAILY, config.QUEST_DAILY_COUNT)
        data = {"date": today, "quests": quests}
        ref.set(data)

    return data

def get_weekly_quests(user_id: int) -> dict:
    ref = _quest_weekly_ref(user_id)
    data = ref.get()
    week_key = _vn_week_key_now()

    if data is None or data.get("week") != week_key:
        quests = _roll_quest_set(config.QUEST_POOL_WEEKLY, config.QUEST_REWARD_POOL_WEEKLY, config.QUEST_WEEKLY_COUNT)
        data = {"week": week_key, "quests": quests}
        ref.set(data)

    return data

def _apply_quest_progress(ref, goal_type: str, amount: int) -> list:
    """Cập nhật progress cho các quest khớp goal_type trong 1 ref (daily hoặc weekly). Trả về list quest vừa hoàn thành lần này."""
    newly_completed = []

    def _txn(data):
        if data is None:
            return data
        quests = data.get("quests", [])
        for q in quests:
            if q["goal_type"] == goal_type and not q["completed"]:
                q["progress"] = min(q["target"], q.get("progress", 0) + amount)
                if q["progress"] >= q["target"]:
                    q["completed"] = True
                    newly_completed.append(dict(q))
        data["quests"] = quests
        return data

    ref.transaction(_txn)
    return newly_completed

def track_quest_progress(user_id: int, goal_type: str, amount: int = 1) -> list:
    """
    Gọi hàm này ở MỌI điểm hành động liên quan trong toàn bộ codebase (thắng minigame, kiếm xu, gửi tin nhắn...).
    Đảm bảo daily/weekly quest đã được khởi tạo trước khi cộng dồn.
    Trả về list các quest vừa hoàn thành lần gọi này (để games.py có thể thông báo).
    """
    get_daily_quests(user_id)   # đảm bảo tồn tại / đã reset đúng ngày
    get_weekly_quests(user_id)  # đảm bảo tồn tại / đã reset đúng tuần

    completed_daily = _apply_quest_progress(_quest_daily_ref(user_id), goal_type, amount)
    completed_weekly = _apply_quest_progress(_quest_weekly_ref(user_id), goal_type, amount)

    return completed_daily + completed_weekly

def claim_quest_reward(user_id: int, quest_id: str, period: str) -> dict:
    """
    period: "daily" hoặc "weekly"
    {"ok": bool, "message": str, "reward": dict|None}
    """
    ref = _quest_daily_ref(user_id) if period == "daily" else _quest_weekly_ref(user_id)
    result_holder = {"ok": False, "message": "", "reward": None}

    def _txn(data):
        if data is None:
            result_holder["message"] = "Không tìm thấy nhiệm vụ."
            return data
        quests = data.get("quests", [])
        for q in quests:
            if q["id"] == quest_id:
                if not q["completed"]:
                    result_holder["message"] = "Nhiệm vụ chưa hoàn thành."
                    return data
                if q["claimed"]:
                    result_holder["message"] = "Bạn đã nhận thưởng nhiệm vụ này rồi."
                    return data
                q["claimed"] = True
                result_holder["ok"] = True
                result_holder["reward"] = dict(q["reward"])
                break
        else:
            result_holder["message"] = "Không tìm thấy nhiệm vụ."
        data["quests"] = quests
        return data

    ref.transaction(_txn)

    if not result_holder["ok"]:
        return result_holder

    reward = result_holder["reward"]
    if reward["type"] == "coins":
        transaction_coins(user_id, reward["amount"])
    elif reward["type"] == "elo":
        add_elo(user_id, reward["amount"])
    elif reward["type"] == "xp":
        data = get_level_data(user_id)
        _apply_xp(data, reward["amount"])
        _level_ref(user_id).set(data)
    elif reward["type"] == "game_ticket":
        _add_quest_game_tickets(user_id, reward["amount"])

    return result_holder

def _add_quest_game_tickets(user_id: int, amount: int) -> None:
    """Vé quest có hạn dùng, lưu kèm ngày hết hạn (0h VN hôm sau)."""
    now = datetime.datetime.utcnow()
    expires_at = (now + datetime.timedelta(hours=config.QUEST_DAILY_TICKET_EXPIRE_HOURS)).isoformat()
    ref = _quest_ticket_ref(user_id)

    def _txn(current):
        current = current or {"count": 0, "expires_at": None}
        # nếu vé cũ đã hết hạn, reset về 0 trước khi cộng thêm
        old_expires = current.get("expires_at")
        if old_expires and parse_iso(old_expires) < now:
            current["count"] = 0
        current["count"] = current.get("count", 0) + amount
        current["expires_at"] = expires_at
        return current

    ref.transaction(_txn)

def get_quest_game_tickets(user_id: int) -> int:
    data = _quest_ticket_ref(user_id).get()
    if not data:
        return 0
    expires_at = data.get("expires_at")
    if expires_at and parse_iso(expires_at) < datetime.datetime.utcnow():
        return 0
    return data.get("count", 0)

def _consume_quest_game_ticket(user_id: int) -> bool:
    ref = _quest_ticket_ref(user_id)
    result_holder = {"ok": False}
    now = datetime.datetime.utcnow()

    def _txn(current):
        if not current:
            result_holder["ok"] = False
            return current
        expires_at = current.get("expires_at")
        if expires_at and parse_iso(expires_at) < now:
            result_holder["ok"] = False
            current["count"] = 0
            return current
        if current.get("count", 0) <= 0:
            result_holder["ok"] = False
            return current
        current["count"] -= 1
        result_holder["ok"] = True
        return current

    ref.transaction(_txn)
    return result_holder["ok"]

# AI Chat nâng cao
def _ai_autochat_config_ref():
    return db.reference("bot_config/ai_autochat")

def set_autochat_channel(channel_id: int | None) -> None:
    """channel_id=None để tắt auto-chat."""
    _ai_autochat_config_ref().set({"channel_id": channel_id})

def get_autochat_channel() -> int | None:
    data = _ai_autochat_config_ref().get()
    return data.get("channel_id") if data else None

def _ai_channel_activity_ref(channel_id: int):
    return db.reference(f"ai_channel_activity/{channel_id}")

def mark_channel_activity(channel_id: int) -> None:
    _ai_channel_activity_ref(channel_id).set(datetime.datetime.utcnow().isoformat())

def get_channel_idle_minutes(channel_id: int) -> float:
    """Số phút kênh đã im lặng (không có tin nhắn) kể từ lần hoạt động cuối được ghi nhận."""
    last_activity = _ai_channel_activity_ref(channel_id).get()
    if not last_activity:
        return 0.0
    parsed = parse_iso(last_activity)
    if parsed is None:
        return 0.0
    return (datetime.datetime.utcnow() - parsed).total_seconds() / 60

def is_ai_quiet_hours() -> bool:
    """True nếu đang trong khung giờ cấm AI trả lời (giờ VN)."""
    vn_now = datetime.datetime.utcnow() + datetime.timedelta(hours=config.WORK_TZ_OFFSET_HOURS)
    hour = vn_now.hour
    start, end = config.AI_CHAT_QUIET_HOURS_START, config.AI_CHAT_QUIET_HOURS_END
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end  # trường hợp khung giờ vắt qua nửa đêm ngược (không dùng ở đây nhưng an toàn)
