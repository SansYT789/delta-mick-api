"""
Data layer cho Firebase Realtime Database.

Schema:
guilds/{guild_id}/users/{user_id}/tornado/
    money: int
    mango: int
    cars: { car_id: { "durability_level": int, "cooldown_level": int, "owned": bool } }
    active_car: str | None            # car_id đang chọn để săn
    upgrades: {
        "radar_level": int,
        "armor_level": int,
    }
    cooldowns: { car_id: iso_timestamp_khi_het_cooldown }
    session: {                        # session đang chạy (None nếu không săn)
        "car_id": str,
        "ef": int,
        "durability_current": float,
        "durability_max": float,
        "started_at": iso_timestamp,
        "session_length_sec": int,
        "elapsed_sec": int,
        "tornado_state": "steady" | "approach" | "recede",
        "channel_id": int,
        "message_id": int,
        "log": [str, ...]             # vài dòng log gần nhất để hiện trong embed
    }
"""

import datetime
from firebase_admin import db

DEFAULT_USER_DATA = {
    "money": 1000,   # tiền khởi điểm cho người mới
    "mango": 0,
    "cars": {
        "rookie_truck": {"durability_level": 0, "cooldown_level": 0, "owned": True}
    },
    "active_car": "rookie_truck",
    "upgrades": {"radar_level": 0, "armor_level": 0},
    "cooldowns": {},
    "session": None,
}


def _ref(guild_id: int, user_id: int):
    return db.reference(f"guilds/{guild_id}/users/{user_id}/tornado")


def get_user_data(guild_id: int, user_id: int) -> dict:
    ref = _ref(guild_id, user_id)
    data = ref.get()
    if data is None:
        ref.set(DEFAULT_USER_DATA)
        return dict(DEFAULT_USER_DATA)
    # merge để tránh KeyError nếu sau này thêm field mới vào DEFAULT_USER_DATA
    merged = dict(DEFAULT_USER_DATA)
    merged.update(data)
    if "cars" not in data:
        merged["cars"] = dict(DEFAULT_USER_DATA["cars"])
    if "upgrades" not in data:
        merged["upgrades"] = dict(DEFAULT_USER_DATA["upgrades"])
    return merged


def set_user_data(guild_id: int, user_id: int, data: dict):
    _ref(guild_id, user_id).set(data)


def update_user_data(guild_id: int, user_id: int, patch: dict):
    """Cập nhật nhiều field cùng lúc (multi-path update, atomic ở mức field)."""
    _ref(guild_id, user_id).update(patch)


def transaction_user_data(guild_id: int, user_id: int, fn):
    """
    Chạy transaction an toàn với concurrent writes.
    fn nhận dict data hiện tại, trả về dict data mới.
    """
    ref = _ref(guild_id, user_id)

    def _txn(current):
        if current is None:
            current = dict(DEFAULT_USER_DATA)
        merged = dict(DEFAULT_USER_DATA)
        merged.update(current)
        return fn(merged)

    result = ref.transaction(_txn)
    return result


def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def parse_iso(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s)
