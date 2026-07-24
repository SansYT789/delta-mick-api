"""
Quản lý session săn bão đang chạy (in-memory, theo asyncio task).
Mỗi user chỉ có 1 session cùng lúc. Session bị mất nếu bot restart giữa chừng
(chấp nhận đánh đổi này cho bản đầu — có thể thêm resume-from-Firebase sau).
"""

import asyncio
import datetime

import discord

import config
import logic
import store

# guild_id:user_id -> asyncio.Task
_active_sessions: dict[str, asyncio.Task] = {}


def session_key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}:{user_id}"


def is_session_active(guild_id: int, user_id: int) -> bool:
    key = session_key(guild_id, user_id)
    task = _active_sessions.get(key)
    return task is not None and not task.done()


def start_session(guild_id: int, user_id: int, coro) -> asyncio.Task:
    key = session_key(guild_id, user_id)
    task = asyncio.create_task(coro)
    _active_sessions[key] = task
    return task


def end_session(guild_id: int, user_id: int):
    key = session_key(guild_id, user_id)
    _active_sessions.pop(key, None)


async def run_hunt_session(
    interaction: discord.Interaction,
    car_id: str,
):
    """
    Vòng lặp chính của 1 lần săn bão. Chạy như background task,
    edit message mỗi tick cho tới khi session kết thúc.
    """
    import views  # import cục bộ để tránh circular import (views cũng import module này)

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    data = store.get_user_data(guild_id, user_id)
    car_entry = data["cars"][car_id]
    stats = logic.get_car_stats(car_id, car_entry["durability_level"], car_entry["cooldown_level"])
    radar_level = data["upgrades"]["radar_level"]
    armor_level = data["upgrades"]["armor_level"]

    # --- Giai đoạn chờ bão xuất hiện ---
    wait_sec = logic.wait_time_sec(radar_level)
    embed = discord.Embed(
        title="📡 Đang dò tìm lốc xoáy...",
        description=f"Radar đang quét khu vực. Dự kiến {wait_sec}s.",
        color=discord.Color.blurple(),
    )
    await interaction.edit_original_response(embed=embed, view=None)
    await asyncio.sleep(wait_sec)

    # --- Roll EF + độ dài session ---
    ef = logic.roll_ef(stats["max_ef"], radar_level)
    session_length_sec = logic.roll_session_length_sec(ef)
    durability = float(stats["max_durability"])
    max_durability = float(stats["max_durability"])
    elapsed = 0
    logs: list[str] = [f"🌪️ Lốc xoáy EF{ef} xuất hiện! Dự kiến tồn tại ~{session_length_sec // 60} phút."]

    destroyed = False

    while elapsed < session_length_sec and durability > 0:
        await asyncio.sleep(config.TICK_SECONDS)
        elapsed += config.TICK_SECONDS

        event = logic.roll_tick_event()
        result = logic.compute_tick(ef, event, armor_level)

        durability -= result["dmg"]
        durability += result["heal"]
        durability = max(0.0, min(max_durability, durability))

        logs.append(result["log"])
        logs = logs[-4:]  # chỉ giữ 4 dòng gần nhất

        if durability <= 0:
            destroyed = True
            break

        # cập nhật embed tiến trình
        progress_embed = _build_progress_embed(
            car_name=stats["name"],
            ef=ef,
            durability=durability,
            max_durability=max_durability,
            elapsed=elapsed,
            session_length_sec=session_length_sec,
            logs=logs,
        )
        try:
            await interaction.edit_original_response(embed=progress_embed, view=None)
        except discord.HTTPException:
            pass  # message có thể bị xoá/mất quyền — session vẫn chạy ngầm tới cuối

    # --- Kết thúc session: tính thưởng ---
    payout = logic.compute_payout(stats["base_rate"], ef, elapsed, destroyed)
    cooldown_until = (
        datetime.datetime.utcnow() + datetime.timedelta(minutes=stats["cooldown_min"])
    ).isoformat()

    def _apply(d):
        d["money"] = d.get("money", 0) + payout["money"]
        d["mango"] = d.get("mango", 0) + payout["mango"]
        if destroyed:
            d["cars"][car_id]["broken"] = True
        d.setdefault("cooldowns", {})[car_id] = cooldown_until
        return d

    store.transaction_user_data(guild_id, user_id, _apply)

    result_embed = _build_result_embed(
        car_name=stats["name"],
        ef=ef,
        elapsed=elapsed,
        destroyed=destroyed,
        payout=payout,
        cooldown_min=stats["cooldown_min"],
    )
    view = views.PostHuntView(guild_id, user_id)
    try:
        await interaction.edit_original_response(embed=result_embed, view=view)
    except discord.HTTPException:
        pass

    end_session(guild_id, user_id)


def _build_progress_embed(car_name, ef, durability, max_durability, elapsed, session_length_sec, logs):
    bar_len = 20
    filled = int(bar_len * durability / max_durability) if max_durability else 0
    bar = "🟩" * filled + "⬛" * (bar_len - filled)

    time_left = max(0, session_length_sec - elapsed)
    embed = discord.Embed(
        title=f"🌪️ Đang săn lốc xoáy EF{ef}",
        description=f"Xe: **{car_name}**",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Độ bền", value=f"{bar}\n{durability:.0f}/{max_durability:.0f}", inline=False)
    embed.add_field(name="Thời gian trụ", value=f"{elapsed // 60}p{elapsed % 60}s", inline=True)
    embed.add_field(name="Bão tan sau", value=f"~{time_left // 60}p{time_left % 60}s", inline=True)
    embed.add_field(name="Diễn biến gần đây", value="\n".join(logs) or "—", inline=False)
    return embed


def _build_result_embed(car_name, ef, elapsed, destroyed, payout, cooldown_min):
    color = discord.Color.red() if destroyed else discord.Color.green()
    title = "💥 Xe hỏng giữa cơn bão!" if destroyed else "✅ Bão đã tan — an toàn trở về!"

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Xe", value=car_name, inline=True)
    embed.add_field(name="EF", value=f"EF{ef}", inline=True)
    embed.add_field(name="Thời gian trụ", value=f"{elapsed // 60}p{elapsed % 60}s", inline=True)
    embed.add_field(name="💰 Money nhận được", value=f"${payout['money']:,}", inline=True)
    embed.add_field(name="🥭 Mango nhận được", value=f"{payout['mango']}", inline=True)
    if destroyed:
        embed.add_field(
            name="⚠️ Xe hỏng",
            value=f"Xe cần sửa (500$/5 độ bền) trước khi săn tiếp.",
            inline=False,
        )
    embed.set_footer(text=f"Cooldown xe: {cooldown_min} phút")
    return embed
