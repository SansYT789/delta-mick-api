"""
Data layer cho hệ thống thu thập/duyệt/random ảnh.

Schema:
guilds/{guild_id}/image_collect_enabled: bool

guilds/{guild_id}/image_pool/{image_id}/
    url: str
    content_hash: str          # sha256 hex của nội dung file — dùng chống trùng nội dung
    submitted_by: int (user_id)
    submitted_at: iso
    status: "pending" | "approved" | "rejected"
    channel_id: int
    message_id: int

guilds/{guild_id}/image_hash_index/{content_hash}: image_id
    # index ngược hash -> image_id, dùng để check trùng nội dung O(1) thay vì quét cả pool

guilds/{guild_id}/users/{user_id}/randomimage/
    daily_count: int
    daily_date: "YYYY-MM-DD"        # ngày UTC — reset daily_count khi khác ngày hiện tại
    last_image_id: str | None       # ảnh gần nhất user này nhận từ /randomimage

image_id = str(attachment.id) — Discord gán ID cố định cho mỗi attachment.
content_hash = sha256 nội dung file — chống trùng theo NỘI DUNG (khác người up, khác
attachment ID nhưng cùng file byte-for-byte vẫn bị coi là trùng).
Pool giới hạn image_config.POOL_MAX_SIZE — khi vượt, tự xoá ảnh CŨ NHẤT cho tới khi
về dưới ngưỡng (xem enforce_pool_limit).
"""

import datetime

from firebase_admin import db

import image_config


def _guild_ref(guild_id: int):
    return db.reference(f"guilds/{guild_id}")


def _image_pool_ref(guild_id: int):
    return db.reference(f"guilds/{guild_id}/image_pool")


def _image_ref(guild_id: int, image_id: str):
    return db.reference(f"guilds/{guild_id}/image_pool/{image_id}")


def _hash_index_ref(guild_id: int):
    return db.reference(f"guilds/{guild_id}/image_hash_index")


def _randomimage_ref(guild_id: int, user_id: int):
    return db.reference(f"guilds/{guild_id}/users/{user_id}/randomimage")


def _mango_ref(guild_id: int, user_id: int):
    return db.reference(f"guilds/{guild_id}/users/{user_id}/tornado/mango")


def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def today_str() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


# ---------------- COLLECT TOGGLE ----------------

def is_collect_enabled(guild_id: int) -> bool:
    return bool(_guild_ref(guild_id).child("image_collect_enabled").get())


def set_collect_enabled(guild_id: int, enabled: bool):
    _guild_ref(guild_id).child("image_collect_enabled").set(enabled)



# ---------------- POOL ----------------

def find_image_id_by_hash(guild_id: int, content_hash: str) -> str | None:
    """Tra cứu O(1) qua hash index xem nội dung này đã có trong pool chưa."""
    return _hash_index_ref(guild_id).child(content_hash).get()


def add_image(
    guild_id: int, image_id: str, url: str, content_hash: str,
    submitted_by: int, channel_id: int, message_id: int,
) -> bool:
    """
    Thêm ảnh vào pool nếu chưa tồn tại — chống trùng theo CẢ 2: attachment ID
    (image_id) và nội dung file (content_hash). Trả về True nếu vừa thêm mới,
    False nếu bị bỏ qua vì đã trùng (theo ID hoặc theo nội dung).

    Sau khi thêm, tự enforce giới hạn pool (xoá ảnh cũ nhất nếu vượt ngưỡng).
    """
    # check trùng nội dung trước — rẻ hơn transaction ghi
    existing_id = find_image_id_by_hash(guild_id, content_hash)
    if existing_id is not None:
        return False

    ref = _image_ref(guild_id, image_id)
    was_created = {"value": False}

    def _txn(current):
        if current is not None:
            was_created["value"] = False
            return current
        was_created["value"] = True
        return {
            "url": url,
            "content_hash": content_hash,
            "submitted_by": submitted_by,
            "submitted_at": now_iso(),
            "status": "pending",
            "channel_id": channel_id,
            "message_id": message_id,
        }

    ref.transaction(_txn)

    if not was_created["value"]:
        return False

    # ghi index hash -> image_id (best-effort; nếu 2 request đua nhau ghi cùng hash
    # trong khoảnh khắc giữa check và ghi, ảnh sau vẫn được lưu nhưng index chỉ giữ 1 —
    # chấp nhận được vì đây chỉ là chống trùng, không phải yêu cầu tuyệt đối chính xác)
    _hash_index_ref(guild_id).child(content_hash).set(image_id)

    enforce_pool_limit(guild_id)
    return True


def enforce_pool_limit(guild_id: int):
    """Nếu pool vượt POOL_MAX_SIZE, xoá ảnh CŨ NHẤT (theo submitted_at) cho tới khi về đúng ngưỡng."""
    pool = _image_pool_ref(guild_id).get() or {}
    overflow = len(pool) - image_config.POOL_MAX_SIZE
    if overflow <= 0:
        return

    items = sorted(pool.items(), key=lambda x: x[1].get("submitted_at", ""))
    for image_id, _data in items[:overflow]:
        delete_image(guild_id, image_id)


def delete_image(guild_id: int, image_id: str):
    """Xoá hẳn 1 ảnh khỏi pool VÀ khỏi hash index (dùng khi: admin từ chối, phát hiện
    bug trùng ảnh, hoặc dọn bớt khi pool đầy)."""
    data = _image_ref(guild_id, image_id).get()
    if data is None:
        return
    content_hash = data.get("content_hash")
    _image_ref(guild_id, image_id).set(None)
    if content_hash:
        _hash_index_ref(guild_id).child(content_hash).set(None)


def get_pending_images(guild_id: int, limit: int = 50) -> list[tuple[str, dict]]:
    """Trả về list (image_id, data) các ảnh đang chờ duyệt, cũ nhất trước."""
    pool = _image_pool_ref(guild_id).get() or {}
    pending = [(iid, data) for iid, data in pool.items() if data.get("status") == "pending"]
    pending.sort(key=lambda x: x[1].get("submitted_at", ""))
    return pending[:limit]


def set_image_status(guild_id: int, image_id: str, status: str):
    _image_ref(guild_id, image_id).child("status").set(status)


def get_approved_images(guild_id: int) -> list[tuple[str, dict]]:
    pool = _image_pool_ref(guild_id).get() or {}
    return [(iid, data) for iid, data in pool.items() if data.get("status") == "approved"]


def get_image(guild_id: int, image_id: str) -> dict | None:
    return _image_ref(guild_id, image_id).get()


def find_duplicate_content_in_pool(guild_id: int, image_id: str) -> str | None:
    """
    Kiểm tra ảnh image_id có trùng NỘI DUNG với 1 ảnh KHÁC trong pool không.
    Dùng khi phát hiện bug random trùng ảnh — nếu ảnh đó thật sự có bản sao nội dung
    trong pool (không phải chính nó), trả về image_id của bản trùng đó để xoá.
    Trả về None nếu không tìm thấy trùng nào khác ngoài chính nó.
    """
    data = get_image(guild_id, image_id)
    if data is None:
        return None
    content_hash = data.get("content_hash")
    if not content_hash:
        return None
    found_id = find_image_id_by_hash(guild_id, content_hash)
    if found_id is not None and found_id != image_id:
        return found_id
    return None



# ---------------- MANGO (dùng chung với tornado) ----------------

def get_mango(guild_id: int, user_id: int) -> int:
    return _mango_ref(guild_id, user_id).get() or 0


def add_mango(guild_id: int, user_id: int, amount: int) -> int:
    ref = _mango_ref(guild_id, user_id)

    def _txn(current):
        current = current or 0
        return current + amount

    return ref.transaction(_txn)


# ---------------- RANDOMIMAGE DAILY LIMIT / DUPLICATE CHECK ----------------

def get_randomimage_state(guild_id: int, user_id: int) -> dict:
    data = _randomimage_ref(guild_id, user_id).get()
    if data is None:
        return {"daily_count": 0, "daily_date": today_str(), "last_image_id": None}
    if data.get("daily_date") != today_str():
        # đã sang ngày mới -> reset đếm, nhưng GIỮ last_image_id (check trùng ảnh không theo ngày)
        return {"daily_count": 0, "daily_date": today_str(), "last_image_id": data.get("last_image_id")}
    return dict(data)


def remaining_randomimage_today(guild_id: int, user_id: int) -> int:
    state = get_randomimage_state(guild_id, user_id)
    return max(0, image_config.RANDOMIMAGE_DAILY_LIMIT - state["daily_count"])


def record_randomimage_use(guild_id: int, user_id: int, new_image_id: str) -> dict:
    """
    Ghi nhận 1 lần dùng /randomimage — atomic, gồm cả kiểm tra daily limit BÊN TRONG
    transaction để 2 request đồng thời không thể cùng vượt giới hạn (mỗi request đọc
    và ghi trong cùng 1 lần transaction, không tách đọc-rồi-ghi).

    Trả về:
        allowed: bool — False nếu đã đạt giới hạn ngày, không có gì được ghi
        previous_last_image_id: ảnh gần nhất TRƯỚC lần này (dùng tính thưởng trùng ảnh)
        daily_count: số lần đã dùng SAU khi cộng lần này (chỉ có giá trị nếu allowed=True)
    """
    ref = _randomimage_ref(guild_id, user_id)
    today = today_str()
    result_holder = {"allowed": False, "previous_last_image_id": None, "daily_count": None}

    def _txn(current):
        if current is None or current.get("daily_date") != today:
            # ngày mới hoặc chưa từng dùng -> count bắt đầu từ 0 trước khi cộng lần này
            prev_last = current.get("last_image_id") if current else None
            if image_config.RANDOMIMAGE_DAILY_LIMIT <= 0:
                result_holder["allowed"] = False
                return current if current is not None else {}
            result_holder["allowed"] = True
            result_holder["previous_last_image_id"] = prev_last
            result_holder["daily_count"] = 1
            return {"daily_count": 1, "daily_date": today, "last_image_id": new_image_id}

        current_count = current.get("daily_count", 0)
        if current_count >= image_config.RANDOMIMAGE_DAILY_LIMIT:
            result_holder["allowed"] = False
            return current  # không đổi gì — đã đạt giới hạn

        result_holder["allowed"] = True
        result_holder["previous_last_image_id"] = current.get("last_image_id")
        result_holder["daily_count"] = current_count + 1
        return {
            "daily_count": current_count + 1,
            "daily_date": today,
            "last_image_id": new_image_id,
        }

    ref.transaction(_txn)
    return result_holder
