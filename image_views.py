import discord

import image_config
import image_store
import image_logic


# ==================== REVIEW (admin duyệt từng ảnh) ====================

def build_review_embed_and_view(guild_id: int):
    pending = image_store.get_pending_images(guild_id)

    if not pending:
        embed = discord.Embed(
            title="📋 Duyệt ảnh",
            description="Không còn ảnh nào đang chờ duyệt.",
            color=image_config.REVIEW_EMBED_COLOR_PENDING,
        )
        return embed, None

    image_id, data = pending[0]
    embed = discord.Embed(
        title="📋 Duyệt ảnh",
        description=f"Còn **{len(pending)}** ảnh đang chờ.",
        color=image_config.REVIEW_EMBED_COLOR_PENDING,
    )
    embed.set_image(url=data["url"])
    embed.add_field(name="Người gửi", value=f"<@{data['submitted_by']}>", inline=True)
    embed.add_field(name="Gửi lúc", value=data.get("submitted_at", "?"), inline=True)

    view = ReviewView(guild_id, image_id)
    return embed, view


class ReviewView(discord.ui.View):
    def __init__(self, guild_id: int, image_id: str):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.image_id = image_id

    @discord.ui.button(label="✅ Duyệt", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        image_store.set_image_status(self.guild_id, self.image_id, "approved")
        embed, view = build_review_embed_and_view(self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="❌ Từ chối", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        image_store.set_image_status(self.guild_id, self.image_id, "rejected")
        embed, view = build_review_embed_and_view(self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)


# ==================== RANDOMIMAGE ====================

def use_randomimage(guild_id: int, user_id: int) -> dict:
    """
    Thực hiện 1 lần /randomimage đầy đủ: check limit, chọn ảnh, tính thưởng, ghi nhận.

    "Trùng ảnh" chỉ tính khi CÙNG user này random trúng đúng ảnh mà chính họ vừa
    nhận ở lần dùng trước (không liên quan tới user khác) — đây được coi là bug hệ
    thống. Khi phát hiện: thưởng 10 mango thay vì 5 (thưởng vì phát hiện lỗi), sau đó
    kiểm tra xem ảnh đó có đang trùng NỘI DUNG với 1 ảnh khác trong pool không — nếu
    có, xoá bản trùng đó để dọn pool sạch lại (không xoá chính ảnh vừa nhận).

    Trả về dict mô tả kết quả để build embed:
        {"ok": bool, "reason": str | None, "image_url": str | None,
         "reward": int | None, "is_duplicate": bool, "remaining_today": int}
    """
    approved = image_store.get_approved_images(guild_id)
    if not approved:
        return {"ok": False, "reason": "no_images"}

    picked_id, picked_data = image_logic.pick_random_image(approved)

    result = image_store.record_randomimage_use(guild_id, user_id, picked_id)
    if not result["allowed"]:
        return {"ok": False, "reason": "daily_limit"}

    reward = image_logic.compute_reward(picked_id, result["previous_last_image_id"])
    image_store.add_mango(guild_id, user_id, reward)

    is_duplicate = result["previous_last_image_id"] == picked_id

    duplicate_removed = False
    if is_duplicate:
        # phát hiện bug: ảnh vừa nhận trùng với chính lần trước của user này.
        # Kiểm tra thêm: ảnh này có bản sao NỘI DUNG khác trong pool không —
        # nếu có, đó chính là "ảnh trùng" cần dọn (không phải chính ảnh vừa nhận).
        duplicate_content_id = image_store.find_duplicate_content_in_pool(guild_id, picked_id)
        if duplicate_content_id is not None:
            image_store.delete_image(guild_id, duplicate_content_id)
            duplicate_removed = True

    return {
        "ok": True,
        "image_url": picked_data["url"],
        "reward": reward,
        "is_duplicate": is_duplicate,
        "duplicate_removed": duplicate_removed,
        "daily_count": result["daily_count"],
    }


def build_randomimage_embed(result: dict) -> discord.Embed:
    if not result["ok"]:
        if result["reason"] == "no_images":
            return discord.Embed(
                title="📭 Không có ảnh",
                description="Chưa có ảnh nào được duyệt. Quay lại sau nhé.",
                color=discord.Color.greyple(),
            )
        if result["reason"] == "daily_limit":
            return discord.Embed(
                title="⏳ Đã hết lượt hôm nay",
                description=f"Bạn đã dùng hết **{image_config.RANDOMIMAGE_DAILY_LIMIT} lượt**/randomimage hôm nay. Quay lại vào ngày mai.",
                color=discord.Color.orange(),
            )

    embed = discord.Embed(title="🖼️ Ảnh ngẫu nhiên", color=discord.Color.blurple())
    embed.set_image(url=result["image_url"])
    reward_text = f"+{result['reward']} mango"
    if result["is_duplicate"]:
        reward_text += " ✨ (trùng ảnh lần trước — thưởng phát hiện lỗi!)"
    embed.add_field(name="Phần thưởng", value=reward_text, inline=True)
    embed.add_field(
        name="Lượt hôm nay",
        value=f"{result['daily_count']}/{image_config.RANDOMIMAGE_DAILY_LIMIT}",
        inline=True,
    )
    if result.get("duplicate_removed"):
        embed.add_field(
            name="🧹 Hệ thống tự dọn",
            value="Phát hiện 1 ảnh trùng nội dung trong hàng chờ — đã xoá bớt.",
            inline=False,
        )
    return embed
