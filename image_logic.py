import random

import image_config


def pick_random_image(approved_images: list[tuple[str, dict]]) -> tuple[str, dict] | None:
    if not approved_images:
        return None
    return random.choice(approved_images)


def compute_reward(new_image_id: str, last_image_id: str | None) -> int:
    """Trả về số mango: 10 nếu trùng ảnh gần nhất user này từng nhận, ngược lại 5."""
    if last_image_id is not None and new_image_id == last_image_id:
        return image_config.RANDOMIMAGE_REWARD_DUPLICATE
    return image_config.RANDOMIMAGE_REWARD_NORMAL
