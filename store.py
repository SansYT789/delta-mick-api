import datetime
import random
import uuid
import copy

from firebase_admin import db

import config

OWNER_IDS = {985004175110848512}
MAX_LOG_ENTRIES = 10
LIXI_DURATION_MIN = 10

MANGO_TO_PLUS_RATE = 0.1       # 1 mango -> 0.1 mango+
PLUS_TO_MANGO_RATE = 7         # 1 mango+ -> 7 mango

WORK_COOLDOWN_HOURS = 24
STREAK_BONUS_PER_WEEK = 0.02   # +2%/tuần

# Utility
def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()

def parse_iso(s: str) -> datetime.datetime:
    if not s:
        return None
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    if '.' not in s and '+' not in s:
        s = s + '+00:00'
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
    ref = _mango_plus_ref(user_id) if use_plus else _mango_ref(user_id)
    failed = {"insufficient": False}

    def _txn(current):
        current = current or 0
        new_val = current + delta
        if new_val < 0:
            failed["insufficient"] = True
            return current  # giữ nguyên, không cho phép âm
        return new_val

    result, snapshot = ref.transaction(_txn)
    if failed["insufficient"]:
        return None
    return snapshot.val() if snapshot else None

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
    try:
        data = _work_ref(user_id).get()
        if data is None:
            return dict(DEFAULT_WORK_DATA)
        merged = dict(DEFAULT_WORK_DATA)
        merged.update(data)
        merged.setdefault("company_cooldown_until", {})
        return merged
    except Exception as e:
        print(f"Error getting work data for user {user_id}: {e}")
        return dict(DEFAULT_WORK_DATA)

def get_work_cooldown_remaining_sec(user_id: int) -> int:
    try:
        data = get_work_data(user_id)
        last = data.get("last_worked_at")
        if not last:
            return 0
        parsed = parse_iso(last)
        if parsed is None:
            return 0
        elapsed = (datetime.datetime.utcnow() - parsed).total_seconds()
        remaining = WORK_COOLDOWN_HOURS * 3600 - elapsed
        return max(0, int(remaining))
    except Exception as e:
        print(f"Error getting cooldown for user {user_id}: {e}")
        return 0

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

def do_work(user_id: int, company_id: str) -> dict:
    if company_id not in config.COMPANIES:
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
    for event in config.BAD_EVENTS:
        if random.random() < event["chance"]:
            triggered_event = event
            break

    company_cooldowns = dict(data.get("company_cooldown_until", {}))

    if triggered_event:
        penalty_until = (now + datetime.timedelta(hours=triggered_event["penalty_hours"])).isoformat()
        company_cooldowns[company_id] = penalty_until

        def _apply_event(d):
            work = d.setdefault("work", {})
            for k, v in DEFAULT_WORK_DATA.items():
                work.setdefault(k, copy.deepcopy(v))
            work["last_worked_at"] = now.isoformat()
            work["current_company"] = company_id
            work["streak_weeks"] = 0
            work["position_level"] = position_level
            work["company_cooldown_until"] = company_cooldowns
            return d

        _update_work_data(user_id, _apply_event)
        return {
            "ok": True,
            "pay": 0,
            "event": triggered_event,
            "streak_weeks": 0,
            "position_level": position_level,
            "company_name": config.COMPANIES[company_id]["name"],
        }

    lo, hi = config.COMPANIES[company_id]["base_pay"]
    base_pay = random.randint(lo, hi)
    streak_mult = 1.0 + streak_weeks * STREAK_BONUS_PER_WEEK
    level = min(position_level, len(config.POSITION_BUFFS)-1)
    position_mult = 1.0 + config.POSITION_BUFFS[level]
    pay = max(1, round(base_pay * streak_mult * position_mult))

    def _apply(d):
        work = d.setdefault("work", {})
        for k, v in DEFAULT_WORK_DATA.items():
            work.setdefault(k, copy.deepcopy(v))
        work["last_worked_at"] = now.isoformat()
        work["current_company"] = company_id
        work["streak_weeks"] = streak_weeks
        work["position_level"] = position_level
        work["company_cooldown_until"] = company_cooldowns
        return d

    _update_work_data(user_id, _apply)
    try:
        new_balance = transaction_mango(user_id, pay)
        if new_balance is None:
            print(f"Warning: transaction_mango returned None for user {user_id}")
    except Exception as e:
        print(f"Error in transaction_mango: {e}")

    return {
        "ok": True,
        "pay": pay,
        "event": None,
        "streak_weeks": streak_weeks,
        "position_level": position_level,
        "company_name": config.COMPANIES[company_id]["name"],
    }

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
    result_holder = {"refund": 0, "creator_id": None, "currency": "mango", "already_closed": False}

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

    ref.delete()

    return refund

# Bill
def _log_ref(user_id: int):
    return db.reference(f"users/{user_id}/purchase_log")

def log_purchase(user_id: int, label: str, cost: int, currency: str = "mango") -> None:
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

# Wordle
WORDLE_MAX_GUESSES = 5
WORDLE_DAILY_LIMIT = 6
WORDLE_WIN_REWARD_MANGO = 20
WORDLE_PARTICIPATE_REWARD_PLUS = 1

WORDLE_WIN_STREAK_REQUIRED = 3
WORDLE_TOTAL_WINS_REQUIRED = 5

def _wordle_play_ref(user_id: int):
    return db.reference(f"users/{user_id}/wordle_plays_today")

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
            if current["current_streak"] >= WORDLE_WIN_STREAK_REQUIRED:
                result["achievement"] = "streak"
            elif current["total_wins"] == WORDLE_TOTAL_WINS_REQUIRED:
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
    if data.get("date") != today:
        return WORDLE_DAILY_LIMIT
    return max(0, WORDLE_DAILY_LIMIT - data.get("count", 0))

def consume_wordle_play(user_id: int) -> bool:
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    ref = _wordle_play_ref(user_id)
    result_holder = {"ok": False}

    def _txn(current):
        current = current or {}
        if current.get("date") != today:
            current = {"date": today, "count": 0}
        if current["count"] >= WORDLE_DAILY_LIMIT:
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
    'absent' (⬜ không có trong từ). Xử lý đúng chuẩn Wordle cho chữ cái lặp lại.
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
    Trả về dict:
    {status: 'no_game'|'win'|'continue'|'lose', result: [...], guesses_left: int, word: str|None}
    """
    ref = _wordle_game_ref(user_id)
    result_holder = {"status": "no_game", "result": None, "guesses_left": 0, "word": None}

    def _txn(game):
        if game is None or game.get("finished"):
            result_holder["status"] = "no_game"
            return game

        if len(game.get("guesses", [])) >= WORDLE_MAX_GUESSES:
            result_holder["status"] = "no_game"
            return game

        secret = game["word"]
        score = score_wordle_guess(secret, guess)
        game.setdefault("guesses", []).append({"word": guess.upper(), "result": score})

        is_win = all(r == "correct" for r in score)
        guesses_left = WORDLE_MAX_GUESSES - len(game["guesses"])

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

# Mango Mustard Day
def has_claimed_mango_mustard_day(user_id: int) -> bool:
    ref = db.reference(f"users/{user_id}/mango_mustard_day_claimed")
    return ref.get() == True

def claim_mango_mustard_day(user_id: int) -> bool:
    ref = db.reference(f"users/{user_id}/mango_mustard_day_claimed")
    
    # Kiểm tra đã claim chưa
    if ref.get():
        return False
    
    # Cộng thưởng
    transaction_mango(user_id, config.MANGO_MUSTARD_DAY["reward_mango"])
    transaction_mango(user_id, config.MANGO_MUSTARD_DAY["reward_plus"], use_plus=True)
    
    # Đánh dấu đã claim
    ref.set(True)
    return True

def is_mango_mustard_day() -> bool:
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return today == config.MANGO_MUSTARD_DAY["date"]

# ===== Meme Achievement =====
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
        print(f"Lỗi increment_meme_count: {e}")
        return 0

def has_meme_role(user_id: int, guild_id: int) -> bool:
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