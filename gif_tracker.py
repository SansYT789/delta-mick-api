import discord
from firebase_admin import db

ROLE_ID = 1529750231539908658  # ID role thưởng
MILESTONE_STEP = 100
REWARD_THRESHOLD = 1000

async def add_gif(member: discord.Member):
    guild_id = str(member.guild.id)
    user_id = str(member.id)

    ref = db.reference(f"guilds/{guild_id}/users/{user_id}")

    def _txn(current):
        if current is None:
            current = {}
        current["gif"] = current.get("gif", 0) + 1
        # đánh dấu ngay trong transaction để tránh 2 lần trao role
        if current["gif"] >= REWARD_THRESHOLD and not current.get("reward_1000_claimed"):
            current["reward_1000_claimed"] = True
            current["_just_claimed"] = True  # cờ tạm, chỉ dùng ở lần trả về này
        else:
            current["_just_claimed"] = False
        return current

    result = ref.transaction(_txn)
    count = result["gif"]
    just_claimed = result.pop("_just_claimed", False)

    # xoá cờ tạm khỏi DB (transaction đã ghi luôn field này, cần dọn lại)
    if "_just_claimed" in result:
        ref.child("_just_claimed").delete()

    channel = member.guild.system_channel

    # Mốc mỗi 100 GIF
    if count % MILESTONE_STEP == 0 and channel:
        msg = await channel.send(
            f"🎉 {member.mention} đã đạt **{count}** lần gửi GIF!"
        )
        await msg.delete(delay=5)

    # Nhận role khi đủ 1000 — chỉ chạy đúng 1 lần nhờ just_claimed
    if just_claimed:
        role = member.guild.get_role(ROLE_ID)
        if role:
            await member.add_roles(role)
            if channel:
                msg = await channel.send(
                    f"🏆 {member.mention} đã nhận role **{role.name}** vì gửi đủ **{REWARD_THRESHOLD} GIF**!"
                )
                await msg.delete(delay=5)
