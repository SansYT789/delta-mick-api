import time
import asyncio
import datetime
import random
import urllib.parse
from typing import Optional, Dict, List, Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import store
import config

# Constants
MAX_CLEAR_AMOUNT = 2000
BOT_VERSION = "1.2.0"
BOT_DESCRIPTION = "Delta Mick Entertainment đa năng các hoạt động lệnh giải trí: kinh tế, mini-game và tiện ích."

# Helper functions
def _roll_fortune(target_user_id: int) -> dict:
    rnd = random.Random(target_user_id)
    total_weight = sum(f["weight"] for f in config._FORTUNES)
    pick = rnd.uniform(0, total_weight)
    cumulative = 0
    chosen = config._FORTUNES[-1]
    
    for f in config._FORTUNES:
        cumulative += f["weight"]
        if pick <= cumulative:
            chosen = f
            break
    
    percent = round(chosen["weight"] / total_weight * 100, 1)
    return {"title": chosen["title"], "desc": chosen["desc"], "percent": percent}

def _fmt_td(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    
    if h:
        return f"{h}h{m}p"
    if m:
        return f"{m}p{s}s"
    return f"{s}s"

_WIKI_IMAGE_HEADERS = {
    "User-Agent": "DeltaMickBot/1.0 (Discord bot; contact: killerdustsans307@gmail.com)",
}

async def _fetch_wiki_thumbnail(title: str) -> Optional[str]:
    encoded = urllib.parse.quote(title.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    try:
        async with aiohttp.ClientSession(headers=_WIKI_IMAGE_HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                thumb = data.get("thumbnail", {}).get("source") or data.get("originalimage", {}).get("source")
                return thumb
    except Exception:
        return None

async def _resolve_minigame_images(questions: List[dict]) -> None:
    for q in questions:
        wiki_title = q.get("wiki_title")
        if wiki_title:
            q["image_url"] = await _fetch_wiki_thumbnail(wiki_title)

async def _grant_win_xp_and_announce(channel, user) -> None:
    result = store.add_minigame_win_xp(user.id)
    if result["leveled_up"]:
        embed = discord.Embed(
            title="🎊 Lên cấp!",
            description=f"{user.mention} đã đạt **Level {result['new_level']}**!",
            color=discord.Color.gold(),
        )
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    await _track_quest_and_announce(channel, user, "win_minigame", 1)

async def _track_quest_and_announce(channel, user, goal_type: str, amount: int = 1) -> None:
    completed = store.track_quest_progress(user.id, goal_type, amount)
    for q in completed:
        embed = discord.Embed(
            title="🎯 Hoàn thành nhiệm vụ!",
            description=f"{user.mention} đã hoàn thành: **{q['desc']}**\nDùng `/quest` để nhận thưởng!",
            color=discord.Color.blurple(),
        )
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

async def _call_gemini(user_id: int, prompt: str, use_search: bool = True, use_history: bool = True) -> Optional[str]:
    import os

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    contents = [{"role": "user", "parts": [{"text": config.AI_CHAT_SYSTEM_PROMPT}]}]
    contents.append({"role": "model", "parts": [{"text": "Đã hiểu, mình sẵn sàng trò chuyện!"}]})

    if use_history:
        history = store.get_ai_chat_history(user_id)
        for turn in history:
            role = "user" if turn["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn["text"]}]})

    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": config.AI_CHAT_MAX_OUTPUT_TOKENS},
    }
    if use_search:
        payload["tools"] = [{"google_search": {}}]

    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                config.GEMINI_API_URL, json=payload, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return None
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()
                return text or None
    except Exception:
        return None

class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._setup_owners()
        self.autochat_check_loop.start()

    def _setup_owners(self):
        pass

    def cog_unload(self):
        self.autochat_check_loop.cancel()

    @tasks.loop(seconds=config.AI_AUTOCHAT_CHECK_INTERVAL_SEC)
    async def autochat_check_loop(self):
        try:
            channel_id = store.get_autochat_channel()
            if not channel_id:
                return
            if store.is_ai_quiet_hours():
                return

            idle_minutes = store.get_channel_idle_minutes(channel_id)
            if idle_minutes < config.AI_AUTOCHAT_IDLE_MINUTES:
                return

            channel = self.bot.get_channel(channel_id)
            if channel is None:
                return

            reply = await _call_gemini(0, config.AI_AUTOCHAT_PROMPT, use_search=False, use_history=False)
            if reply is None:
                return

            if len(reply) > 2000:
                reply = reply[:2000] + "..."

            await channel.send(reply)
            store.mark_channel_activity(channel_id)  # tránh spam
        except Exception as e:
            print(f"Lỗi autochat_check_loop: {e}")

    @autochat_check_loop.before_loop
    async def _before_autochat_loop(self):
        await self.bot.wait_until_ready()

    # ==================== MODERATION COMMANDS ====================
    @app_commands.command(name="purge", description="Xoá tin nhắn gần nhất trong kênh (tuỳ chọn lọc theo user)")
    @app_commands.describe(
        amount="Số lượng tin nhắn cần xoá (tối đa 2000)",
        user="Chỉ xoá tin nhắn của user này (bỏ trống = xoá tất cả)",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, MAX_CLEAR_AMOUNT],
        user: Optional[discord.Member] = None,
    ):
        perms = interaction.channel.permissions_for(interaction.guild.me)
        if not perms.manage_messages:
            await interaction.response.send_message(
                "Bot thiếu quyền **Quản lý tin nhắn** trong kênh này.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        def check(msg: discord.Message) -> bool:
            return user is None or msg.author.id == user.id

        try:
            deleted = await interaction.channel.purge(limit=amount, check=check)
        except discord.Forbidden:
            await interaction.followup.send("Bot không có quyền xoá tin nhắn ở đây.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"Lỗi khi xoá tin nhắn: {e}", ephemeral=True)
            return

        target_text = f" của {user.mention}" if user else ""
        await interaction.followup.send(
            f"✅ Đã xoá **{len(deleted)}** tin nhắn{target_text}.",
            delete_after=5
        )

    @clear.error
    async def clear_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "Bạn cần quyền **Quản lý tin nhắn** để dùng lệnh này.", ephemeral=True
            )
        else:
            await interaction.response.send_message(f"Lỗi: {error}", ephemeral=True)

    # ==================== OWNER COMMANDS ====================
    @app_commands.command(name="chinhxu", description="Chỉnh xu cho người dùng (chỉ chủ bot)")
    @app_commands.describe(
        amount="Số lượng xu cần chỉnh (số nguyên dương)",
        user="Chọn người dùng",
    )
    async def chinhxu(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 0],
        user: Optional[discord.Member] = None,
    ):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        user = user or interaction.user
        store.set_coins(user.id, amount)

        await interaction.response.send_message(
            f"✅ Đã chỉnh xu của {user.mention} thành **{amount}** xu",
            ephemeral=True
        )

    @app_commands.command(name="custom-status", description="Đổi trạng thái hiển thị của bot (chỉ chủ bot)")
    @app_commands.describe(
        status="Trạng thái online của bot",
        activity_type="Loại hoạt động hiển thị (bỏ trống nếu chỉ muốn đổi status)",
        text="Nội dung hiển thị sau loại hoạt động",
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(name="🟢 Online", value="online"),
            app_commands.Choice(name="🌙 Idle (Vắng mặt)", value="idle"),
            app_commands.Choice(name="⛔ Do Not Disturb", value="dnd"),
            app_commands.Choice(name="⚫ Invisible (Ẩn)", value="invisible"),
        ],
        activity_type=[
            app_commands.Choice(name="Playing (Đang chơi)", value="playing"),
            app_commands.Choice(name="Watching (Đang xem)", value="watching"),
            app_commands.Choice(name="Listening (Đang nghe)", value="listening"),
            app_commands.Choice(name="Streaming (Đang phát trực tiếp)", value="streaming"),
        ],
    )
    async def custom_status(
        self,
        interaction: discord.Interaction,
        status: app_commands.Choice[str],
        activity_type: Optional[app_commands.Choice[str]] = None,
        text: Optional[str] = None,
    ):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        # Set status
        discord_status = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }[status.value]

        # Set activity if provided
        activity = None
        if activity_type and text:
            activity_type_value = activity_type.value
            if activity_type_value == "playing":
                activity = discord.Game(name=text)
            elif activity_type_value == "watching":
                activity = discord.Activity(type=discord.ActivityType.watching, name=text)
            elif activity_type_value == "listening":
                activity = discord.Activity(type=discord.ActivityType.listening, name=text)
            elif activity_type_value == "streaming":
                activity = discord.Streaming(name=text, url="https://twitch.tv/discord")
        elif activity_type and not text:
            await interaction.response.send_message(
                "Cần nhập `text` khi đã chọn `activity_type`.", ephemeral=True
            )
            return

        await self.bot.change_presence(status=discord_status, activity=activity)

        summary = f"Trạng thái: **{status.name}**"
        if activity_type and text:
            summary += f"\nHoạt động: **{activity_type.name}** — {text}"
        
        await interaction.response.send_message(f"✅ Đã cập nhật trạng thái bot.\n{summary}")

    @app_commands.command(name="reset-meme", description="Đặt lại số lượng meme của user (chỉ chủ bot)")
    @app_commands.describe(user="Người dùng cần đặt lại", confirm="Gõ 'YES' để xác nhận")
    async def reset_meme(self, interaction: discord.Interaction, user: discord.Member, confirm: Optional[str] = None):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        if confirm != "YES":
            await interaction.response.send_message(
                f"⚠️ Bạn cần gõ `YES` để xác nhận reset.\n"
                f"Ví dụ: `/reset-meme user:{user.mention} confirm:YES`",
                ephemeral=True,
            )
            return

        store.reset_meme_count_for_user(user.id)

        role_id = config.MEME_CONFIG["role_id"]
        role = interaction.guild.get_role(role_id)
        if role and role in user.roles:
            try:
                await user.remove_roles(role, reason="Reset meme count")
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            f"✅ Đã đặt lại số lượng meme của {user.mention} và xoá role <@&{role_id}>",
            ephemeral=True
        )

    @app_commands.command(name="promote", description="Thăng chức cho người chơi (chỉ chủ bot)")
    @app_commands.describe(
        user="Người chơi cần thăng chức",
        level="Số cấp muốn thăng (mặc định: 1)"
    )
    async def promote(self, interaction: discord.Interaction, user: discord.Member, level: int = 1):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        if level < 1:
            await interaction.response.send_message(
                "Số cấp phải lớn hơn 0!", ephemeral=True
            )
            return

        # Get work data
        work_data = store.get_work_data(user.id)
        current_level = work_data.get("position_level", 0)
        new_level = min(current_level + level, config.MAX_POSITION_LEVEL)

        if current_level >= config.MAX_POSITION_LEVEL:
            await interaction.response.send_message(
                f"**{user.display_name}** đã đạt chức vụ cao nhất: **{config.POSITION_NAMES[-1]}**", ephemeral=True
            )
            return

        # Update position level
        def _promote(d):
            d.setdefault("work", dict(store.DEFAULT_WORK_DATA))
            d["work"]["position_level"] = new_level
            return d

        store._update_work_data(user.id, _promote)

        # Create result embed
        embed = discord.Embed(
            title="🎉 Thăng chức thành công!",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="Người chơi",
            value=f"{user.mention}",
            inline=True
        )
        embed.add_field(
            name="Chức vụ cũ → Chức vụ mới",
            value=f"`{config.POSITION_NAMES[current_level]}` → `{config.POSITION_NAMES[new_level]}` (+{level} cấp)",
            inline=True
        )
        embed.add_field(
            name="Tiến độ",
            value=f"`{new_level}/{config.MAX_POSITION_LEVEL}`",
            inline=True
        )
        embed.set_footer(text=f"Được thực hiện bởi {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

        # Send DM notification
        try:
            dm_embed = discord.Embed(
                title="🎊 Bạn đã được thăng chức!",
                description=f"Bạn đã được thăng chức từ **{config.POSITION_NAMES[current_level]}** lên **{config.POSITION_NAMES[new_level]}**",
                color=discord.Color.gold()
            )
            await user.send(embed=dm_embed)
        except discord.HTTPException:
            pass

    @app_commands.command(name="resetcooldown", description="Đặt lại thời gian làm việc cho người chơi (chỉ chủ bot)")
    @app_commands.describe(user="Người chơi cần đặt lại")
    async def resetcooldown(self, interaction: discord.Interaction, user: discord.Member):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        # Reset work data
        def _reset(d):
            d.setdefault("work", dict(store.DEFAULT_WORK_DATA))
            d["work"]["last_worked_at"] = None
            d["work"]["company_cooldown_until"] = {}
            return d

        store._update_work_data(user.id, _reset)

        embed = discord.Embed(
            title="✅ Đặt lại thời gian thành công",
            description=f"Đã đặt lại thời gian làm việc cho **{user.display_name}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="lock", description="Khoá 1 lệnh bất kì (chỉ chủ bot)")
    @app_commands.describe(command_name="Tên lệnh cần khoá")
    async def lock(self, interaction: discord.Interaction, command_name: str):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        command_name = command_name.lstrip("/").strip().lower()
        if not command_name:
            await interaction.response.send_message("Tên lệnh không hợp lệ.", ephemeral=True)
            return

        store.lock_command(command_name)
        await interaction.response.send_message(
            f"🔒 Đã khoá lệnh `/{command_name}` — mọi người (trừ bạn) sẽ thấy thông báo bảo trì.",
            ephemeral=True,
        )

    @app_commands.command(name="unlock", description="Mở khoá 1 lệnh đã khoá bất kì (chỉ chủ bot)")
    @app_commands.describe(command_name="Tên lệnh cần mở khoá")
    async def unlock(self, interaction: discord.Interaction, command_name: str):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        command_name = command_name.lstrip("/").strip().lower()
        store.unlock_command(command_name)
        await interaction.response.send_message(
            f"🔓 Đã mở khoá lệnh `/{command_name}`.", ephemeral=True
        )

    @app_commands.command(name="locklist", description="Xem danh sách lệnh đang bị khoá")
    async def locklist(self, interaction: discord.Interaction):
        locked = store.get_locked_commands()
        active_locked = [name for name, is_locked in locked.items() if is_locked]
        
        if not active_locked:
            await interaction.response.send_message(
                "Không có lệnh nào đang bị khoá.", ephemeral=True
            )
            return

        lines = "\n".join(f"🔒 `/{name}`" for name in active_locked)
        await interaction.response.send_message(
            f"**Lệnh đang bảo trì:**\n{lines}"
        )

    @app_commands.command(name="baotri", description="Bật/tắt chế độ bảo trì toàn bộ bot (chỉ chủ bot)")
    @app_commands.describe(
        trang_thai="Bật hoặc tắt chế độ bảo trì",
        ly_do="Lý do bảo trì (hiển thị cho người dùng, tuỳ chọn)",
    )
    @app_commands.choices(
        trang_thai=[
            app_commands.Choice(name="🔧 Bật bảo trì", value="on"),
            app_commands.Choice(name="✅ Tắt bảo trì", value="off"),
        ]
    )
    async def baotri(
        self,
        interaction: discord.Interaction,
        trang_thai: app_commands.Choice[str],
        ly_do: Optional[str] = None,
    ):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        enabled = trang_thai.value == "on"
        store.set_maintenance_mode(enabled, ly_do)

        if enabled:
            desc = "Toàn bộ lệnh (trừ chủ bot) sẽ hiển thị thông báo bảo trì."
            if ly_do:
                desc += f"\nLý do: {ly_do}"
            embed = discord.Embed(title="🔧 Đã bật chế độ bảo trì", description=desc, color=discord.Color.orange())
        else:
            embed = discord.Embed(title="✅ Đã tắt chế độ bảo trì", description="Bot hoạt động bình thường trở lại.", color=discord.Color.green())

        await interaction.response.send_message(embed=embed)

    # ==================== GAME COMMANDS ====================
    @app_commands.command(name="gay", description="Kiểm tra độ gay của bạn hoặc người khác 🌈")
    @app_commands.describe(user="Người muốn kiểm tra (bỏ trống = bạn)")
    async def gay(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user

        percent = random.Random(target.id + 69420).randint(0, 100)

        if percent == 0:
            comment = "🗿 Hoàn toàn thẳng."
            color = discord.Color.green()
        elif percent <= 20:
            comment = "🙂 Hơi có dấu hiệu..."
            color = discord.Color.blue()
        elif percent <= 40:
            comment = "😏 Có chút đáng ngờ."
            color = discord.Color.gold()
        elif percent <= 60:
            comment = "🌈 Cân bằng hoàn hảo."
            color = discord.Color.orange()
        elif percent <= 80:
            comment = "💅 Khá là rõ ràng."
            color = discord.Color.magenta()
        elif percent < 100:
            comment = "🏳️‍🌈 Gay cấp độ siêu cấp!"
            color = discord.Color.purple()
        else:
            comment = "👑 100% Gay. Không còn gì để bàn."
            color = discord.Color.red()

        bar_len = 20
        filled = round(percent / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        embed = discord.Embed(
            title="🌈 Máy đo Gay",
            color=color
        )
        embed.set_author(
            name=target.display_name,
            icon_url=target.display_avatar.url
        )
        embed.add_field(
            name="Kết quả",
            value=f"**{percent}%**\n`{bar}`",
            inline=False
        )
        embed.add_field(
            name="Đánh giá",
            value=comment,
            inline=False
        )
        embed.set_footer(text="⚠️ Chỉ mang tính giải trí.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="farm-aura", description="Kiểm tra mức độ farm aura của bạn hoặc người khác 😎")
    @app_commands.describe(user="Người muốn kiểm tra (bỏ trống = bạn)")
    async def farm_aura(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user

        aura = random.Random(target.id + 88888).randint(0, 100)

        if aura <= 10:
            rank = "💀 Aura âm, đi ngủ đi."
            color = discord.Color.red()
        elif aura <= 35:
            rank = "🥲 Farm hơi yếu."
            color = discord.Color.orange()
        elif aura <= 36:
            rank = "😋 36 thanh hoá ăn rau má"
            color = discord.Color.green()
        elif aura <= 45:
            rank = "🙂 Mới vào nghề."
            color = discord.Color.gold()
        elif aura <= 66:
            rank = "😎 Farm ổn áp."
            color = discord.Color.blue()
        elif aura <= 68:
            rank = "😱 Six seven"
            color = discord.Color.dark_grey()
        elif aura <= 69:
            rank = "😏 Tuyệt vời"
            color = discord.Color.red()
        elif aura <= 88:
            rank = "🔥 Aura rất mạnh."
            color = discord.Color.green()
        elif aura <= 89:
            rank = "🐧 Penguin Aura"
            color = discord.Color.blue()
        elif aura <= 99:
            rank = "⚡ Quái vật farm aura."
            color = discord.Color.purple()
        else:
            rank = "👑 100% THẦN THÁNH AURA"
            color = discord.Color.fuchsia()

        bar = "█" * (aura // 5) + "░" * (20 - aura // 5)

        embed = discord.Embed(
            title="😎 Kiểm tra Aura",
            color=color
        )
        embed.set_author(
            name=target.display_name,
            icon_url=target.display_avatar.url
        )
        embed.add_field(
            name="Aura",
            value=f"**{aura}%**\n`{bar}`",
            inline=False
        )
        embed.add_field(
            name="Đánh giá",
            value=rank,
            inline=False
        )
        embed.set_footer(text="Chỉ mang tính giải trí.")
        await interaction.response.send_message(embed=embed)

    async def _title_autocomplete(self, interaction: discord.Interaction, current: str):
        current_lower = current.lower()
        matches = [
            app_commands.Choice(name=meta["name"], value=key)
            for key, meta in config.TITLES.items()
            if current_lower in meta["name"].lower()
        ]
        return matches[:25]

    @app_commands.command(name="give-title", description="Cấp danh hiệu cho user (chỉ chủ bot)")
    @app_commands.describe(user="Người nhận danh hiệu", title="Tên danh hiệu")
    @app_commands.autocomplete(title=_title_autocomplete)
    async def give_title(self, interaction: discord.Interaction, user: discord.Member, title: str):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        if title not in config.TITLES:
            await interaction.response.send_message(
                "❌ Danh hiệu không tồn tại. Hãy chọn từ danh sách gợi ý.", ephemeral=True
            )
            return

        granted = store.give_title(user.id, title)
        title_name = config.TITLES[title]["name"]

        if not granted:
            await interaction.response.send_message(
                f"{user.mention} đã sở hữu danh hiệu **{title_name}** rồi.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🏅 Đã cấp danh hiệu!",
            description=f"{user.mention} vừa nhận được danh hiệu **{title_name}**",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Hiệu ứng", value=config.TITLES[title]["desc"], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="danhhieu", description="Xem và trang bị danh hiệu của bạn")
    async def danhhieu(self, interaction: discord.Interaction):
        data = store.get_user_titles(interaction.user.id)
        owned = data["owned"]
        equipped = data["equipped"]

        if not owned:
            await interaction.response.send_message(
                "Bạn chưa sở hữu danh hiệu nào.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🏅 Danh hiệu của {interaction.user.display_name}",
            color=discord.Color.purple(),
        )

        equipped_lines = []
        for key in equipped:
            meta = config.TITLES.get(key)
            if meta:
                equipped_lines.append(f"**{meta['name']}** — {meta['desc']}")
        embed.add_field(
            name=f"⭐ Đang trang bị ({len(equipped)}/{config.TITLE_MAX_EQUIPPED})",
            value="\n".join(equipped_lines) if equipped_lines else "_Chưa trang bị danh hiệu nào._",
            inline=False,
        )

        owned_lines = []
        for key in owned:
            meta = config.TITLES.get(key)
            if meta:
                mark = "⭐ " if key in equipped else ""
                owned_lines.append(f"{mark}**{meta['name']}** — {meta['desc']}")
        embed.add_field(
            name=f"📦 Sở hữu ({len(owned)})",
            value="\n".join(owned_lines)[:1024] if owned_lines else "_Trống_",
            inline=False,
        )

        if equipped:
            buffs = store.get_equipped_title_buffs(interaction.user.id)
            buff_lines = []
            if buffs.get("coins_mult_global"):
                buff_lines.append(f"💰 +{buffs['coins_mult_global']*100:.0f}% xu (mọi nguồn)")
            for cmd_key in ("work", "jackpot", "wordle", "flag", "meme", "car", "country", "hoahoc", "daily", "noitu", "chess", "minesweeper"):
                v = buffs.get(f"coins_mult_{cmd_key}")
                if v:
                    buff_lines.append(f"💰 +{v*100:.0f}% xu (/{cmd_key})")
            if buffs.get("jackpot_luck"):
                buff_lines.append(f"🍀 +{buffs['jackpot_luck']*100:.0f}% may mắn /jackpot")
            if buffs.get("work_bad_event_reduction"):
                buff_lines.append(f"🛡️ -{buffs['work_bad_event_reduction']*100:.0f}% sự kiện xui /work")
            if buffs.get("shop_discount"):
                buff_lines.append(f"🛒 -{buffs['shop_discount']*100:.0f}% giá shop")
            for cmd_key in ("wordle", "flag", "work", "meme", "car", "country"):
                v = buffs.get(f"extra_plays_{cmd_key}")
                if v:
                    buff_lines.append(f"🔄 +{int(v)} lượt /{cmd_key}")

            if buff_lines:
                embed.add_field(name="✨ Hiệu ứng đang áp dụng", value="\n".join(buff_lines), inline=False)

        embed.set_footer(text="Dùng nút bên dưới để chọn danh hiệu trang bị.")

        view = discord.ui.View(timeout=180)
        view.add_item(TitleEquipDropdown(interaction.user.id, owned, equipped))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="minesweeper", description="Chơi dò mìn để kiếm xu")
    @app_commands.describe(
        rows="Số hàng (5-16, mặc định 9)",
        cols="Số cột (5-16, mặc định 9)",
        mines="Số lượng mìn (bỏ trống = tự tính theo kích thước)",
        seed="Seed để tạo bàn giống lần trước (bỏ trống = ngẫu nhiên)",
    )
    async def minesweeper(
        self,
        interaction: discord.Interaction,
        rows: app_commands.Range[int, config.MINESWEEPER_MIN_DIM, config.MINESWEEPER_MAX_DIM] = config.MINESWEEPER_DEFAULT_DIM,
        cols: app_commands.Range[int, config.MINESWEEPER_MIN_DIM, config.MINESWEEPER_MAX_DIM] = config.MINESWEEPER_DEFAULT_DIM,
        mines: Optional[app_commands.Range[int, 1]] = None,
        seed: Optional[str] = None,
    ):
        if store.get_active_minesweeper_game(interaction.user.id):
            await interaction.response.send_message(
                "Bạn đang có ván dò mìn chưa kết thúc — dùng nút trên tin nhắn cũ, hoặc **Kết thúc** để huỷ ván.",
                ephemeral=True,
            )
            return

        total_tiles = rows * cols
        if mines is not None and mines >= total_tiles:
            await interaction.response.send_message(
                f"❌ Số mìn phải nhỏ hơn tổng số ô ({total_tiles}).", ephemeral=True
            )
            return

        await interaction.response.defer()

        game = store.create_minesweeper_game(interaction.user.id, rows, cols, mines, seed)
        embed = _build_minesweeper_embed(interaction.user, game)
        file = _render_minesweeper_file(game)
        embed.set_image(url="attachment://minesweeper.png")
        view = MinesweeperView()
        await interaction.followup.send(embed=embed, view=view, file=file)

    @app_commands.command(name="jackpot", description="Cược xu để nhân lên nhiều lần")
    @app_commands.describe(bet="Số xu muốn cược")
    async def jackpot(
        self,
        interaction: discord.Interaction,
        bet: app_commands.Range[int, config.JACKPOT_MIN_BET, config.JACKPOT_MAX_BET],
    ):
        result = store.play_jackpot(interaction.user.id, bet)

        if not result["ok"]:
            await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)
            return

        outcome = result["outcome"]
        mult = result["multiplier"]
        payout = result["payout"]
        net = result["net"]

        if outcome == "big_win":
            title = "🎰 TRÚNG LỚN!"
            color = discord.Color.gold()
            desc = f"Nhân **×{mult}**! Nhận về **{payout} xu** (lãi **+{net}**)"
        elif outcome == "small_win":
            title = "🎰 Thắng nhẹ"
            color = discord.Color.green()
            desc = f"Nhân **×{mult}**. Nhận về **{payout} xu** (lãi **+{net}**)"
        else:
            title = "🎰 Thua nhẹ"
            color = discord.Color.dark_grey()
            desc = f"Nhân **×{mult}**. Nhận về **{payout} xu** (lỗ **{net}**)"

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.add_field(name="Đã cược", value=f"{bet} xu", inline=True)
        embed.set_footer(text="Cược càng cao, tỉ lệ trúng lớn càng thấp.")
        await interaction.response.send_message(embed=embed)

        store.track_quest_progress(interaction.user.id, "play_jackpot", 1)
        if net > 0:
            store.track_quest_progress(interaction.user.id, "earn_coins", net)

    @app_commands.command(name="daily", description="Nhận thưởng hàng ngày")
    async def daily(self, interaction: discord.Interaction):
        remaining = store.get_daily_cooldown_remaining_sec(interaction.user.id)
        if remaining > 0:
            await interaction.response.send_message(
                f"⏱️ Bạn cần chờ **{_fmt_td(remaining)}** nữa mới nhận thưởng ngày tiếp theo (reset 0h giờ Việt Nam).",
                ephemeral=True,
            )
            return

        result = store.claim_daily(interaction.user.id)
        if not result["ok"]:
            await interaction.response.send_message(
                "Bạn đã nhận thưởng hôm nay rồi, quay lại sau nhé.", ephemeral=True
            )
            return

        streak_days = result["streak_days"]
        streak_weeks = streak_days // 7
        bonus_pct = streak_weeks * config.DAILY_STREAK_BONUS_PER_WEEK * 100

        embed = discord.Embed(
            title="🎁 Điểm danh hàng ngày",
            description=f"Bạn nhận được **{result['amount']} xu**!",
            color=discord.Color.green(),
        )
        embed.add_field(name="🔥 Streak", value=f"{streak_days} ngày liên tiếp", inline=True)
        if bonus_pct > 0:
            embed.add_field(name="Thưởng streak", value=f"+{bonus_pct:.0f}% xu", inline=True)
        embed.set_footer(text="Quay lại vào 0h giờ Việt Nam ngày mai để giữ streak.")
        await interaction.response.send_message(embed=embed)

        store.track_quest_progress(interaction.user.id, "claim_daily", 1)
        store.track_quest_progress(interaction.user.id, "earn_coins", result["amount"])

    @app_commands.command(name="enter_code", description="Nhập code để nhận phần thưởng")
    @app_commands.describe(code="Mã code cần nhập")
    async def enter_code(self, interaction: discord.Interaction, code: str):
        result = store.redeem_code(code, interaction.user.id)

        if not result["ok"]:
            await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)
            return

        reward = result["reward"] or {}
        coins = reward.get("coins", 0)
        role_id = reward.get("role_id")

        lines = []
        if coins:
            lines.append(f"💰 **{coins}** xu")

        role_granted = False
        if role_id and interaction.guild:
            role = interaction.guild.get_role(role_id)
            if role:
                member = interaction.guild.get_member(interaction.user.id)
                if member and role not in member.roles:
                    try:
                        await member.add_roles(role, reason=f"Nhập code: {code}")
                        role_granted = True
                    except discord.Forbidden:
                        pass
                if role_granted:
                    lines.append(f"🎭 Role <@&{role_id}>")

        if not lines:
            lines.append("_Không có phần thưởng nào._")

        embed = discord.Embed(
            title="🎁 Nhập code thành công!",
            description="\n".join(lines),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="release_code", description="Phát hành code mới (chỉ chủ bot)")
    @app_commands.describe(
        code="Mã code (người dùng sẽ nhập chính xác chuỗi này)",
        coins="Số xu thưởng khi nhập code",
        role="Role thưởng khi nhập code (bỏ trống = không có)",
        max_uses="Số lượt sử dụng tối đa (mặc định 1)",
        duration_hours="Thời hạn code tính bằng giờ (bỏ trống = không hết hạn)",
    )
    async def release_code(
        self,
        interaction: discord.Interaction,
        code: str,
        coins: app_commands.Range[int, 0] = 0,
        role: Optional[discord.Role] = None,
        max_uses: app_commands.Range[int, 1] = 1,
        duration_hours: Optional[app_commands.Range[int, 1]] = None,
    ):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        if coins <= 0 and role is None:
            await interaction.response.send_message(
                "Cần ít nhất 1 phần thưởng (coins hoặc role).", ephemeral=True
            )
            return

        ok, msg = store.create_code(
            code=code,
            created_by=interaction.user.id,
            coins=coins,
            role_id=role.id if role else None,
            max_uses=max_uses,
            duration_hours=duration_hours,
        )

        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        reward_lines = []
        if coins > 0:
            reward_lines.append(f"💰 {coins} xu")
        if role:
            reward_lines.append(f"🎭 Role {role.mention}")

        embed = discord.Embed(
            title="✅ Đã phát hành code",
            description=f"Code: `{code}`",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Phần thưởng", value="\n".join(reward_lines), inline=False)
        embed.add_field(name="Số lượt dùng tối đa", value=str(max_uses), inline=True)
        embed.add_field(
            name="Thời hạn",
            value=f"{duration_hours} giờ" if duration_hours else "Không giới hạn",
            inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reset", description="Reset ván trò chơi đang bị kẹt")
    @app_commands.describe(
        game="Trò chơi cần reset (bỏ trống = reset tất cả ván của bạn đang kẹt)",
        target="Chỉ chủ bot: reset cho user khác",
        all_users="Chỉ chủ bot: gõ 'YES' để reset TẤT CẢ user (ghi đè game/target)",
    )
    @app_commands.choices(
        game=[
            app_commands.Choice(name="Đoán từ (/wordle)", value="wordle"),
            app_commands.Choice(name="Đoán cờ (/flag)", value="flag"),
            app_commands.Choice(name="Dò mìn (/minesweeper)", value="minesweeper"),
            app_commands.Choice(name="Đoán Meme (/meme)", value="meme"),
            app_commands.Choice(name="Đoán Xe (/car)", value="car"),
            app_commands.Choice(name="Đoán Quốc Gia (/country)", value="country"),
            app_commands.Choice(name="Hoá Học (/hoahoc)", value="hoahoc"),
            app_commands.Choice(name="Đoán Ngôn Ngữ (/language)", value="language"),
        ]
    )
    async def reset(
        self,
        interaction: discord.Interaction,
        game: Optional[app_commands.Choice[str]] = None,
        target: Optional[discord.Member] = None,
        all_users: Optional[str] = None,
    ):
        is_owner = store.is_owner(interaction.user.id)

        # Reset all users (chỉ chủ bot)
        if all_users is not None:
            if not is_owner:
                await interaction.response.send_message(
                    "Chỉ chủ bot mới có thể reset tất cả user.", ephemeral=True
                )
                return
            if all_users != "YES":
                await interaction.response.send_message(
                    "⚠️ Gõ `all_users:YES` để xác nhận reset TẤT CẢ ván của mọi user.",
                    ephemeral=True,
                )
                return

            counts = store.reset_all_games_everyone()
            lines = "\n".join(
                f"• {store.RESETTABLE_GAME_LABELS[k]}: **{v}** ván"
                for k, v in counts.items()
            )
            await interaction.response.send_message(
                f"✅ Đã reset toàn bộ ván đang kẹt của mọi user:\n{lines}"
            )
            return

        # Reset cho user khác (chỉ chủ bot)
        if target is not None and target.id != interaction.user.id:
            if not is_owner:
                await interaction.response.send_message(
                    "Chỉ chủ bot mới có thể reset ván của người khác.", ephemeral=True
                )
                return

        target_user = target or interaction.user

        if game is not None:
            cleared = store.reset_game_for_user(target_user.id, game.value)
            if not cleared:
                await interaction.response.send_message(
                    f"{target_user.mention} không có ván **{game.name}** nào đang kẹt.",
                    ephemeral=(target_user.id == interaction.user.id),
                )
                return
            await interaction.response.send_message(
                f"✅ Đã reset ván **{game.name}** của {target_user.mention}."
            )
            return

        # Không chọn game cụ thể -> reset tất cả ván đang kẹt của target_user
        cleared_keys = store.reset_all_games_for_user(target_user.id)
        if not cleared_keys:
            await interaction.response.send_message(
                f"{target_user.mention} hiện không có ván nào bị kẹt.",
                ephemeral=(target_user.id == interaction.user.id),
            )
            return

        cleared_labels = ", ".join(store.RESETTABLE_GAME_LABELS[k] for k in cleared_keys)
        await interaction.response.send_message(
            f"✅ Đã reset các ván đang kẹt của {target_user.mention}: {cleared_labels}"
        )

    async def _start_minigame(self, interaction: discord.Interaction, kind: str):
        if store.get_active_minigame_game(interaction.user.id, kind):
            await interaction.response.send_message(
                "Bạn đang có ván chưa kết thúc — bấm nút **Đoán** trên tin nhắn cũ, hoặc **Kết thúc** để huỷ ván.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        questions = store.build_minigame_questions(kind)
        if kind in ("meme", "car", "country"):
            await _resolve_minigame_images(questions)

        game = store.create_minigame_game(interaction.user.id, kind, questions)
        embed = _build_minigame_embed(interaction.user, game)
        view = MinigameView(kind)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="language", description="Đoán ngôn ngữ chính thức của quốc gia qua lá cờ")
    async def language_game(self, interaction: discord.Interaction):
        await self._start_minigame(interaction, "language")

    @app_commands.command(name="chess", description="Chơi cờ vua với bot AI hoặc thách đấu người khác")
    @app_commands.describe(
        opponent="Thách đấu người chơi này (bỏ trống = chơi với bot AI)",
        difficulty="Độ khó bot AI (chỉ áp dụng khi không có opponent)",
    )
    @app_commands.choices(
        difficulty=[
            app_commands.Choice(name="Dễ", value="easy"),
            app_commands.Choice(name="Vừa", value="medium"),
            app_commands.Choice(name="Khó", value="hard"),
        ]
    )
    async def chess_cmd(
        self,
        interaction: discord.Interaction,
        opponent: Optional[discord.Member] = None,
        difficulty: Optional[app_commands.Choice[str]] = "easy",
    ):
        if store.get_user_active_chess_game_id(interaction.user.id):
            await interaction.response.send_message(
                "Bạn đang có ván cờ chưa kết thúc rồi! Dùng `/chess-end` để huỷ nếu muốn bắt đầu ván mới.",
                ephemeral=True,
            )
            return

        diff_value = difficulty.value if isinstance(difficulty, app_commands.Choice) else (difficulty or "easy")

        if opponent is not None:
            if opponent.bot:
                await interaction.response.send_message("Không thể thách đấu bot.", ephemeral=True)
                return
            if opponent.id == interaction.user.id:
                await interaction.response.send_message("Không thể tự thách đấu chính mình.", ephemeral=True)
                return
            if store.get_user_active_chess_game_id(opponent.id):
                await interaction.response.send_message(
                    f"{opponent.mention} đang có ván cờ khác chưa kết thúc.", ephemeral=True
                )
                return

            view = ChessChallengeView(interaction.user.id, opponent.id)
            embed = discord.Embed(
                title="♟️ Thách đấu cờ vua!",
                description=f"{interaction.user.mention} thách đấu {opponent.mention} chơi cờ vua!\n{opponent.mention} có {config.CHESS_CHALLENGE_TIMEOUT_SEC}s để chấp nhận.",
                color=discord.Color.blurple(),
            )
            await interaction.response.send_message(embed=embed, view=view)
            return

        await interaction.response.defer()
        game_id, game = store.create_chess_game(interaction.user.id, None, "bot", diff_value)
        embed, file = _build_chess_embed_and_file(interaction.user, None, game, game_id)
        view = ChessMoveView(game_id, interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, file=file)

    @app_commands.command(name="chess-end", description="Huỷ ván cờ đang chơi dở của bạn")
    async def chess_end(self, interaction: discord.Interaction):
        game_id = store.get_user_active_chess_game_id(interaction.user.id)
        if not game_id:
            await interaction.response.send_message("Bạn không có ván cờ nào đang chơi.", ephemeral=True)
            return
        store.delete_chess_game(game_id)
        await interaction.response.send_message("🛑 Đã huỷ ván cờ.", ephemeral=True)

    @app_commands.command(name="ai", description="Trò chuyện với AI")
    @app_commands.describe(message="Nội dung muốn hỏi AI")
    async def ai_command(self, interaction: discord.Interaction, message: str):
        if store.is_ai_quiet_hours():
            await interaction.response.send_message(
                f"😴 AI đang nghỉ ({config.AI_CHAT_QUIET_HOURS_START}h-{config.AI_CHAT_QUIET_HOURS_END}h sáng giờ VN), quay lại sau nhé.",
                ephemeral=True,
            )
            return

        remaining = store.get_ai_chat_cooldown_remaining_sec(interaction.user.id)
        if remaining > 0:
            await interaction.response.send_message(
                f"⏱️ Vui lòng chờ **{remaining}s** nữa để hỏi AI tiếp.", ephemeral=True
            )
            return

        await interaction.response.defer()

        reply = await _call_gemini(interaction.user.id, message)
        if reply is None:
            await interaction.followup.send("❌ AI hiện không phản hồi được, thử lại sau nhé.")
            return

        store.append_ai_chat_turn(interaction.user.id, message, reply)

        if len(reply) > 4000:
            reply = reply[:4000] + "..."

        embed = discord.Embed(description=reply, color=discord.Color.teal())
        embed.set_author(
            name=f"Trả lời cho {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setup-chat", description="Đặt kênh cho bot tự khuấy động khi im lặng lâu (chỉ chủ bot)")
    @app_commands.describe(channel="Kênh muốn bật auto-chat (bỏ trống = tắt tính năng)")
    async def setup_chat(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message("Bạn không có quyền dùng lệnh này.", ephemeral=True)
            return

        store.set_autochat_channel(channel.id if channel else None)

        if channel:
            store.mark_channel_activity(channel.id)
            await interaction.response.send_message(
                f"✅ Đã bật auto-chat tại {channel.mention} — bot sẽ tự nhắn nếu kênh im lặng "
                f"{config.AI_AUTOCHAT_IDLE_MINUTES} phút."
            )
        else:
            await interaction.response.send_message("🛑 Đã tắt tính năng auto-chat.")

    @app_commands.command(name="ai-reset", description="Xoá lịch sử trò chuyện AI của bạn")
    async def ai_reset(self, interaction: discord.Interaction):
        store.clear_ai_chat_history(interaction.user.id)
        await interaction.response.send_message("🗑️ Đã xoá lịch sử trò chuyện AI của bạn.", ephemeral=True)

    @app_commands.command(name="noitu", description="Bắt đầu trò chơi nối từ trong kênh này")
    async def noitu(self, interaction: discord.Interaction):
        if store.get_noitu_game(interaction.channel.id):
            await interaction.response.send_message(
                "Kênh này đang có ván nối từ chưa kết thúc rồi! Cứ nhắn từ tiếp theo thôi.",
                ephemeral=True,
            )
            return

        game = store.start_noitu_game(interaction.channel.id)
        cw = game["current_word"]
        embed = discord.Embed(
            title="🔤 Bắt đầu trò chơi nối từ!",
            description=(
                f"Cặp từ khởi đầu: **`{cw}`**\n"
                f"Hãy nối tiếp bằng 1 từ 2 tiếng bắt đầu bằng tiếng **`{cw.split()[-1]}`**.\n\n"
                f"Luật chơi:\n"
                f"• Người vừa nối lượt trước không được nối tiếp lượt kế.\n"
                f"• Từ đã dùng bị khoá **{config.NOITU_WORD_COOLDOWN_GAMES} ván** trước khi dùng lại được.\n"
                f"• Hết từ khả dụng để nối → ván kết thúc, người nối cuối nhận **{config.NOITU_BINGO_REWARD} xu** và ván mới tự bắt đầu!"
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="noitu-end", description="Kết thúc ván nối từ trong kênh này (chỉ chủ bot)")
    async def noitu_end(self, interaction: discord.Interaction):
        if not store.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        if not store.get_noitu_game(interaction.channel.id):
            await interaction.response.send_message("Kênh này không có ván nối từ nào.", ephemeral=True)
            return

        store.delete_noitu_game(interaction.channel.id)
        await interaction.response.send_message("🛑 Đã kết thúc ván nối từ trong kênh này.")

    @app_commands.command(name="meme", description="Đoán tên các meme nổi tiếng")
    async def meme_game(self, interaction: discord.Interaction):
        await self._start_minigame(interaction, "meme")

    @app_commands.command(name="car", description="Đoán tên các hãng xe nổi tiếng")
    async def car_game(self, interaction: discord.Interaction):
        await self._start_minigame(interaction, "car")

    @app_commands.command(name="country", description="Đoán quốc gia qua địa danh/món ăn/thủ đô nổi tiếng")
    async def country_game(self, interaction: discord.Interaction):
        await self._start_minigame(interaction, "country")

    @app_commands.command(name="hoahoc", description="Trả lời câu hỏi hoá học vui")
    async def hoahoc_game(self, interaction: discord.Interaction):
        await self._start_minigame(interaction, "hoahoc")

    @app_commands.command(name="danhgia", description="Đánh giá ảnh hoặc video đính kèm của bạn")
    @app_commands.describe(attachment="Ảnh hoặc video cần đánh giá")
    async def danhgia(self, interaction: discord.Interaction, attachment: discord.Attachment):
        filename_lower = attachment.filename.lower()
        if not filename_lower.endswith(config.DANHGIA_ALLOWED_EXT):
            await interaction.response.send_message(
                "❌ Chỉ hỗ trợ ảnh (png/jpg/jpeg/webp/gif) hoặc video (mp4/mov/webm).",
                ephemeral=True,
            )
            return

        MAX_SIZE = 25 * 1024 * 1024  # 25MB, tránh tải file khổng lồ vào RAM
        if attachment.size > MAX_SIZE:
            await interaction.response.send_message(
                "❌ File quá lớn (tối đa 25MB) để đánh giá.", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            file_bytes = await attachment.read()
        except discord.HTTPException:
            await interaction.followup.send("❌ Không thể tải file để đánh giá.")
            return

        result = store.score_attachment(file_bytes, attachment.filename)
        is_image = filename_lower.endswith(config.DANHGIA_IMAGE_EXT)

        stars_filled = round(result["total"] / 10 * 10)
        stars = "⭐" * stars_filled + "☆" * (10 - stars_filled)

        tier_colors = {
            "low": discord.Color.red(),
            "mid": discord.Color.orange(),
            "high": discord.Color.blue(),
            "top": discord.Color.gold(),
        }

        embed = discord.Embed(
            title="🔍 Kết quả đánh giá",
            description=f"{stars}\n**{result['total']}/10**",
            color=tier_colors[result["tier"]],
        )

        criteria_lines = "\n".join(
            f"• **{name}**: {score}/10" for name, score in result["criteria"].items()
        )
        embed.add_field(name="📊 Chi tiết", value=criteria_lines, inline=False)
        embed.add_field(name="💬 Nhận xét", value=result["comment"], inline=False)

        if is_image:
            embed.set_image(url=attachment.url)
        else:
            embed.add_field(name="📎 Tệp", value=f"`{attachment.filename}`", inline=False)

        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_footer(text=f"Mã đánh giá: {result['hash_short']}")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="boi-toan", description="Bói toán vui về thân phận của một người")
    @app_commands.describe(user="Người muốn bói (bỏ trống = bói chính bạn)")
    async def boi_toan(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        result = _roll_fortune(target.id)

        embed = discord.Embed(
            title=f"🔮 Bói toán: {target.display_name}",
            description=f"**Thân phận:** {result['title']}\n{result['desc']}",
            color=discord.Color.purple(),
        )
        embed.add_field(
            name="Độ hiếm",
            value=f"{result['percent']}% người có thân phận này",
            inline=True
        )
        embed.set_footer(text="Kết quả bói toán này không thể thay đổi cho người này")
        
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="wordle", description="Bắt đầu trò chơi đoán từ tiếng Anh 5 chữ cái")
    async def wordle(self, interaction: discord.Interaction):
        if store.get_active_wordle_game(interaction.user.id):
            await interaction.response.send_message(
                "Bạn đang có ván đoán từ chưa kết thúc — bấm nút **Đoán từ** trên tin nhắn cũ, hoặc **Kết thúc** để huỷ ván.",
                ephemeral=True,
            )
            return

        remaining = store.get_wordle_plays_remaining(interaction.user.id)
        if remaining <= 0:
            await interaction.response.send_message(
                f"Bạn đã dùng hết {config.WORDLE_DAILY_LIMIT} lượt `/wordle` hôm nay, hãy quay lại vào ngày mai.",
                ephemeral=True,
            )
            return

        if not store.consume_wordle_play(interaction.user.id):
            await interaction.response.send_message(
                f"Bạn đã dùng hết {config.WORDLE_DAILY_LIMIT} lượt `/wordle` hôm nay, hãy quay lại vào ngày mai.",
                ephemeral=True,
            )
            return

        store.create_wordle_game(interaction.user.id)

        embed = _build_wordle_embed(interaction.user, [], config.WORDLE_MAX_GUESSES)
        embed.set_footer(text=f"Bạn còn {remaining - 1} lượt tạo ván đoán từ hôm nay.")
        view = WordleView()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="flag", description="Đoán 5 lá cờ quốc gia liên tiếp — chọn độ khó để bắt đầu")
    async def flag(self, interaction: discord.Interaction):
        if store.get_active_flag_game(interaction.user.id):
            await interaction.response.send_message(
                "Bạn đang có ván đoán cờ chưa kết thúc — bấm nút **Đoán** trên tin nhắn cũ, hoặc **Kết thúc** để huỷ ván.",
                ephemeral=True,
            )
            return

        remaining = store.get_flag_plays_remaining(interaction.user.id)
        if remaining <= 0:
            await interaction.response.send_message(
                f"Bạn đã dùng hết {config.FLAG_DAILY_LIMIT} lượt `/flag` hôm nay, hãy quay lại vào ngày mai.",
                ephemeral=True,
            )
            return

        view = discord.ui.View(timeout=300)
        view.add_item(FlagModeDropdown())
        await interaction.response.send_message(
            f"Chọn độ khó để bắt đầu đoán cờ: (còn **{remaining}** lượt hôm nay)", view=view
        )

    @app_commands.command(name="wordle-stats", description="Xem thống kê trò chơi đoán từ của bạn")
    @app_commands.describe(user="Người chơi cần xem (mặc định: bạn)")
    async def wordle_stats(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        stats = store.get_wordle_stats(target.id)

        if not stats:
            await interaction.response.send_message(
                f"{target.mention} chưa chơi trò chơi đoán từ lần nào."
            )
            return

        embed = discord.Embed(
            title=f"📊 Thống kê trò chơi đoán từ của {target.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Số ván đã chơi",
            value=stats.get("total_plays", 0),
            inline=True
        )
        embed.add_field(
            name="Số ván thắng",
            value=stats.get("total_wins", 0),
            inline=True
        )
        embed.add_field(
            name="Tỉ lệ thắng",
            value=f"{stats.get('total_wins', 0) / max(stats.get('total_plays', 1), 1) * 100:.1f}%",
            inline=True
        )
        embed.add_field(
            name="Chuỗi thắng hiện tại",
            value=stats.get("current_streak", 0),
            inline=True
        )
        embed.add_field(
            name="Chuỗi thắng cao nhất",
            value=stats.get("max_streak", 0),
            inline=True
        )
        
        last_played = stats.get("last_played")
        if last_played:
            try:
                dt = datetime.datetime.fromisoformat(last_played)
                embed.add_field(
                    name="Lần chơi cuối",
                    value=discord.utils.format_dt(dt, style="R"),
                    inline=False
                )
            except ValueError:
                pass

        await interaction.response.send_message(embed=embed)

    # ==================== ECONOMY COMMANDS ====================
    @app_commands.command(name="coins", description="Xem số xu và ELO của bạn hoặc người khác")
    @app_commands.describe(user="Người muốn xem (bỏ trống = xem của bạn)")
    async def coins(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        coins = store.get_coins(target.id)
        elo = store.get_elo(target.id)
        embed = discord.Embed(
            title=f"💰 Ví của {target.display_name}",
            description=f"**{coins:,}**".replace(",", ".") + f" xu\n**{elo:,}**".replace(",", ".") + " ELO",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shop", description="Xem và mua vật phẩm trong shop (làm mới mỗi 10 phút)")
    async def shop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        rotation = store.get_current_shop_rotation()
        embed, view = _build_shop_embed_and_view(interaction.user.id, rotation)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="inventory", description="Xem kho đồ vật phẩm đã mua của bạn")
    async def inventory(self, interaction: discord.Interaction):
        inv = store.get_shop_inventory(interaction.user.id)
        if not inv:
            await interaction.response.send_message("Kho đồ của bạn đang trống.", ephemeral=True)
            return

        lines = []
        for key, count in inv.items():
            item = config.SHOP_ITEMS.get(key)
            if item:
                lines.append(f"**{item['name']}** ×{count} — _{item['desc']}_")

        embed = discord.Embed(
            title=f"🎒 Kho đồ của {interaction.user.display_name}",
            description="\n".join(lines) if lines else "Trống",
            color=discord.Color.dark_teal(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="quest", description="Xem và nhận thưởng nhiệm vụ ngày/tuần")
    async def quest(self, interaction: discord.Interaction):
        daily = store.get_daily_quests(interaction.user.id)
        weekly = store.get_weekly_quests(interaction.user.id)

        embed = discord.Embed(title=f"🎯 Nhiệm vụ của {interaction.user.display_name}", color=discord.Color.blurple())

        def _format_quest_line(q: dict) -> str:
            status = "✅" if q["claimed"] else ("🎁" if q["completed"] else "⏳")
            reward = q["reward"]
            reward_label = {
                "coins": f"{reward['amount']} xu",
                "elo": f"{reward['amount']} ELO",
                "xp": f"{reward['amount']} XP",
                "game_ticket": f"{reward['amount']} vé chơi game",
            }.get(reward["type"], "")
            return f"{status} **{q['desc']}** — {q['progress']}/{q['target']} _(thưởng: {reward_label})_"

        daily_lines = [_format_quest_line(q) for q in daily["quests"]]
        weekly_lines = [_format_quest_line(q) for q in weekly["quests"]]

        embed.add_field(name="📅 Nhiệm vụ ngày (reset 0h VN)", value="\n".join(daily_lines) or "Không có", inline=False)
        embed.add_field(name="🗓️ Nhiệm vụ tuần (reset thứ 2)", value="\n".join(weekly_lines) or "Không có", inline=False)

        claimable = [q for q in daily["quests"] + weekly["quests"] if q["completed"] and not q["claimed"]]
        view = discord.ui.View(timeout=180)
        if claimable:
            view.add_item(QuestClaimDropdown(daily["quests"], weekly["quests"]))
            embed.set_footer(text="Chọn nhiệm vụ đã hoàn thành bên dưới để nhận thưởng.")

        await interaction.response.send_message(embed=embed, view=view if claimable else None)

    @app_commands.command(name="bill", description="Xem hoá đơn — lịch sử mua sắm gần đây của bạn")
    async def bill(self, interaction: discord.Interaction):
        max_log = config.MAX_LOG_ENTRIES or 10
        log = store.get_purchase_log(interaction.user.id, limit=max_log)

        if not log:
            await interaction.response.send_message(
                "Bạn chưa có giao dịch mua sắm nào. Dùng `/shop` để mua sắm vật phẩm.",
                ephemeral=True,
            )
            return

        lines = []
        total_coins = 0
        
        for entry in log:
            at = store.parse_iso(entry["at"])
            unix_ts = int(at.timestamp())
            lines.append(f"<t:{unix_ts}:R> — **{entry['label']}** (giá {entry['cost']} xu)")

            total_coins += entry["cost"]

        embed = discord.Embed(
            title="🧾 Hoá đơn mua sắm",
            description="\n".join(lines),
            color=discord.Color.dark_gold(),
        )
        
        summary_parts = []
        if total_coins:
            summary_parts.append(f"{total_coins} xu")
        
        embed.set_footer(
            text=f"Tổng {len(log)} giao dịch gần nhất — đã chi: {' + '.join(summary_parts) if summary_parts else '0'}"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="work", description="Đi làm tại 1 công ty để nhận tiền thưởng")
    async def work(self, interaction: discord.Interaction):
        view = CompanyChooseView(interaction.user.id)
        embed = discord.Embed(
            title="💼 Chọn công ty để làm việc",
            description="\n".join(
                f"• **{cfg['name']}**" for cfg in config.COMPANIES.values()
            ),
            color=discord.Color.dark_blue(),
        )
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="workinfo", description="Xem thông tin công việc của bạn")
    @app_commands.describe(user="Người chơi cần xem (mặc định: bạn)")
    async def workinfo(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        await interaction.response.defer()

        target = user or interaction.user
        work_data = store.get_work_data(target.id)

        current_level = work_data.get("position_level", 0)
        streak_weeks = work_data.get("streak_weeks", 0)
        current_company = work_data.get("current_company", None)

        embed = discord.Embed(
            title=f"💼 Thông tin công việc của {target.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Chức vụ",
            value=f"`{config.POSITION_NAMES[current_level]}`",
            inline=True
        )
        embed.add_field(
            name="Chuỗi",
            value=f"`{streak_weeks} tuần`",
            inline=True
        )
        embed.add_field(
            name="Tiến độ thăng chức",
            value=f"`{current_level}/{config.MAX_POSITION_LEVEL}`",
            inline=True
        )

        if current_company and current_company in config.COMPANIES:
            company_name = config.COMPANIES[current_company]["name"]
            embed.add_field(name="Công ty hiện tại", value=f"`{company_name}`", inline=True)
        else:
            embed.add_field(name="Công ty hiện tại", value="`Chưa có`", inline=True)

        # Check cooldown
        cooldown = store.get_work_cooldown_remaining_sec(target.id)
        embed.add_field(
            name="⏱️ Thời gian làm việc",
            value=f"Còn `{_fmt_td(cooldown)}`" if cooldown > 0 else "`Sẵn sàng`",
            inline=True
        )
        embed.set_footer(text=f"Đi làm trước {config.WORK_START_HOUR}h sáng để không bị trừ lương do trễ.")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="resign", description="Từ chức khỏi công ty hiện tại")
    async def resign(self, interaction: discord.Interaction):
        work_data = store.get_work_data(interaction.user.id)
        current_company = work_data.get("current_company")

        if not current_company:
            await interaction.response.send_message("Bạn hiện không làm việc ở đâu cả.", ephemeral=True)
            return

        company_name = config.COMPANIES.get(current_company, {}).get("name", current_company)

        view = discord.ui.View(timeout=60)
        confirm_button = discord.ui.Button(label="✅ Xác nhận từ chức", style=discord.ButtonStyle.danger)
        cancel_button = discord.ui.Button(label="❌ Huỷ", style=discord.ButtonStyle.secondary)

        async def _confirm(inner_interaction: discord.Interaction):
            if inner_interaction.user.id != interaction.user.id:
                await inner_interaction.response.send_message("Không phải của bạn.", ephemeral=True)
                return
            result = store.resign_work(interaction.user.id)
            if not result["ok"]:
                await inner_interaction.response.edit_message(content=f"❌ {result['message']}", embed=None, view=None)
                return
            await inner_interaction.response.edit_message(
                content=(
                    f"📄 Bạn đã từ chức khỏi **{company_name}**.\n"
                    f"Mất **{config.WORK_RESIGN_FEE} xu**, chức vụ reset về **Thực tập sinh**.\n"
                    f"Cần chờ **{result['cooldown_days']} ngày** trước khi đi làm lại được."
                ),
                embed=None, view=None,
            )

        async def _cancel(inner_interaction: discord.Interaction):
            if inner_interaction.user.id != interaction.user.id:
                await inner_interaction.response.send_message("Không phải của bạn.", ephemeral=True)
                return
            await inner_interaction.response.edit_message(content="Đã huỷ.", embed=None, view=None)

        confirm_button.callback = _confirm
        cancel_button.callback = _cancel
        view.add_item(confirm_button)
        view.add_item(cancel_button)

        await interaction.response.send_message(
            f"⚠️ Bạn có chắc muốn từ chức khỏi **{company_name}**?\n"
            f"Sẽ mất **{config.WORK_RESIGN_FEE} xu**, chức vụ reset về Thực tập sinh, "
            f"và không thể đi làm trong **{config.WORK_RESIGN_COOLDOWN_DAYS} ngày**.",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="lixi", description="Lì xì xu cho mọi người trong kênh")
    @app_commands.describe(
        amount="Tổng số lượng muốn lì xì",
    )
    async def lixi(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1],
    ):
        ok, msg, envelope_id = store.create_lixi(
            interaction.guild.id, interaction.channel.id, 
            interaction.user.id, amount
        )
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=config.LIXI_DURATION_MIN)
        expires_unix = int(expires_at.timestamp())

        embed = discord.Embed(
            title="🧧 Lì xì!",
            description=(
                f"{interaction.user.mention} vừa lì xì **{amount} xu**!\n"
                f"Bấm nút bên dưới để nhận — mỗi người chỉ nhận được 1 lần.\n"
                f"Lì xì tự đóng lúc <t:{expires_unix}:t> (<t:{expires_unix}:R>)."
            ),
            color=discord.Color.red(),
        )
        embed.add_field(name="🎁 Người đã nhận", value="_Chưa có ai nhận._", inline=False)

        view = LixiClaimView(interaction.guild.id, envelope_id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        sent_message = await interaction.original_response()
        store.set_lixi_message_id(envelope_id, sent_message.id)

        # Gửi DM riêng cho người tạo lì xì kèm nút đóng sớm
        try:
            close_view = LixiCloseView(envelope_id, sent_message.jump_url)
            dm_embed = discord.Embed(
                title="🧧 Bạn vừa tạo lì xì!",
                description=(
                    f"Lì xì **{amount} xu** tại {interaction.channel.mention} đang chờ mọi người nhận.\n"
                    f"Bấm nút bên dưới nếu muốn **đóng sớm** (hoàn lại số dư chưa ai nhận)."
                ),
                color=discord.Color.red(),
            )
            await interaction.user.send(embed=dm_embed, view=close_view)
        except discord.HTTPException:
            pass  # user tắt DM, bỏ qua không chặn luồng chính

        async def _auto_expire():
            await asyncio.sleep(config.LIXI_DURATION_MIN * 60 + 2)
            store.refund_expired_lixi(envelope_id)
            view.stop()
            try:
                await interaction.delete_original_response()
            except discord.HTTPException:
                pass

        asyncio.create_task(_auto_expire())

    @app_commands.command(name="leaderboard", description="Xem bảng xếp hạng toàn server")
    @app_commands.describe(loai="Loại bảng xếp hạng muốn xem")
    @app_commands.choices(
        loai=[
            app_commands.Choice(name="💰 Xu", value="coins"),
            app_commands.Choice(name="⭐ Level", value="level"),
            app_commands.Choice(name="♟️ ELO Cờ vua", value="chess_elo"),
        ]
    )
    async def leaderboard(self, interaction: discord.Interaction, loai: app_commands.Choice[str] = "coins"):
        await interaction.response.defer()
        loai_value = loai.value if isinstance(loai, app_commands.Choice) else loai

        users_ref_data = store.get_all_users_data()
        entries = []

        for uid_str, udata in users_ref_data.items():
            if not isinstance(udata, dict):
                continue

            if loai_value == "coins":
                value = udata.get("coins")
                if isinstance(value, (int, float)) and value > 0:
                    entries.append((int(uid_str), int(value)))
            elif loai_value == "level":
                level_data = udata.get("level")
                if isinstance(level_data, dict):
                    lvl = level_data.get("level", 0)
                    if lvl > 0:
                        entries.append((int(uid_str), lvl))
            elif loai_value == "chess_elo":
                elo = udata.get("chess_elo")
                if isinstance(elo, int) and elo != config.CHESS_STARTING_ELO:
                    entries.append((int(uid_str), elo))

        entries.sort(key=lambda x: x[1], reverse=True)
        top = entries[:10]

        label_map = {"coins": "xu", "level": "level", "chess_elo": "ELO cờ vua"}
        title_map = {
            "coins": "🏆 Bảng xếp hạng xu",
            "level": "🏆 Bảng xếp hạng Level",
            "chess_elo": "🏆 Bảng xếp hạng ELO Cờ vua",
        }
        label = label_map[loai_value]
        title = title_map[loai_value]

        if not top:
            await interaction.followup.send(f"Chưa có dữ liệu {label} nào.")
            return

        user_cache = {}
        for uid, _ in top:
            user = self.bot.get_user(uid)
            if user is None:
                try:
                    user = await self.bot.fetch_user(uid)
                except (discord.NotFound, discord.HTTPException):
                    user = None
            user_cache[uid] = user

        medal = ["🥇", "🥈", "🥉"]
        suffix_map = {"coins": " xu", "level": " (Level)", "chess_elo": " ELO"}

        lines = []
        for i, (uid, amount) in enumerate(top):
            user = user_cache.get(uid)
            name = user.display_name if user else f"Người dùng {uid}"
            amount_str = f"{amount:,}".replace(",", ".") if loai_value == "coins" else str(amount)
            rank_icon = medal[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{rank_icon} **{name}** — {amount_str}{suffix_map[loai_value]}")

        user_rank = None
        user_amount = None
        for rank, (uid, amount) in enumerate(entries, start=1):
            if uid == interaction.user.id:
                user_rank = rank
                user_amount = amount
                break

        embed = discord.Embed(
            title=title,
            description="\n".join(lines) if lines else "Không có dữ liệu",
            color=discord.Color.gold()
        )

        if user_rank is not None and user_amount is not None:
            amount_str = f"{user_amount:,}".replace(",", ".") if loai_value == "coins" else str(user_amount)
            embed.set_footer(text=f"📍 Hạng của bạn: #{user_rank} • {amount_str}{suffix_map[loai_value]}")
        else:
            embed.set_footer(text="Bảng xếp hạng được tính chung toàn bộ máy chủ.")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="rank", description="Xem thông tin cấp độ và xếp hạng của bạn hoặc người khác")
    @app_commands.describe(user="Người chơi cần xem (mặc định: bạn)")
    async def rank(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        await interaction.response.defer()
        target = user or interaction.user

        level_data = store.get_level_data(target.id)
        lvl = level_data["level"]
        xp = level_data["xp"]
        coins = store.get_coins(target.id)

        # Tính hạng level trong toàn server
        users_ref_data = store.get_all_users_data()
        level_entries = []
        for uid_str, udata in users_ref_data.items():
            if isinstance(udata, dict):
                ld = udata.get("level")
                if isinstance(ld, dict) and ld.get("level", 0) > 0:
                    level_entries.append((int(uid_str), ld["level"]))
        level_entries.sort(key=lambda x: x[1], reverse=True)
        user_level_rank = next((i + 1 for i, (uid, _) in enumerate(level_entries) if uid == target.id), None)

        embed = discord.Embed(
            title=f"📇 Thông tin của {target.display_name}",
            color=discord.Color.blue(),
        )
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)

        if lvl >= config.LEVEL_MAX:
            embed.add_field(name="⭐ Level", value=f"**{lvl}** (MAX) 🏆", inline=True)
        else:
            needed = store.xp_needed_for_level(lvl + 1)
            progress = min(xp / needed, 1.0) if needed else 0
            bar_len = 15
            filled = int(progress * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            embed.add_field(name="⭐ Level", value=f"**{lvl}**\n`{bar}` {xp}/{needed}", inline=True)

        embed.add_field(name="💰 Xu", value=f"{coins:,}".replace(",", "."), inline=True)
        if user_level_rank:
            embed.add_field(name="🏅 Hạng Level", value=f"#{user_level_rank}", inline=True)

        shop_elo = store.get_elo(target.id)
        embed.add_field(name="✨ ELO (Shop)", value=f"{shop_elo:,}".replace(",", "."), inline=True)

        chess_elo = store.get_chess_elo(target.id)
        embed.add_field(name="♟️ ELO Cờ vua", value=str(chess_elo), inline=True)

        await interaction.followup.send(embed=embed)

    # ==================== UTILITY COMMANDS ====================
    @app_commands.command(name="help", description="Xem danh sách lệnh của bot")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer()
        pages = _build_help_pages(self.bot, interaction.user.id)
        
        if not pages:
            await interaction.followup.send("Hiện chưa có lệnh nào khả dụng.")
            return
            
        view = HelpView(pages)
        await interaction.followup.send(embed=pages[0], view=view)

    @app_commands.command(name="meme-count", description="Xem số lượng meme bạn đã gửi")
    @app_commands.describe(user="Người muốn xem (mặc định: bạn)")
    async def meme_count(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        count = store.get_meme_count(target.id)
        required = config.MEME_CONFIG["required_count"]

        embed = discord.Embed(
            title=f"🖼️ Số lượng meme của {target.display_name}",
            color=discord.Color.purple()
        )
        embed.add_field(name="Đã gửi", value=f"**{count}** meme", inline=True)
        embed.add_field(name="Mục tiêu", value=f"**{required}** meme", inline=True)

        progress = min(count / required * 100, 100)
        bar_length = 20
        filled = int(progress / 100 * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        embed.add_field(name="Tiến độ", value=f"`{bar}` {progress:.1f}%", inline=False)

        if count >= required:
            embed.add_field(
                name="✅ Trạng thái",
                value=f"Bạn đã đạt mục tiêu! Đã nhận role <@&{config.MEME_CONFIG['role_id']}>",
                inline=False,
            )
        else:
            embed.add_field(
                name="⏳ Trạng thái",
                value=f"Còn **{required - count}** meme nữa để nhận role <@&{config.MEME_CONFIG['role_id']}>",
                inline=False,
            )

        embed.set_footer(text="Chỉ tính meme có link ảnh/video trong kênh #meme")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Kiểm tra độ trễ của bot")
    async def ping(self, interaction: discord.Interaction):
        start = time.perf_counter()
        await interaction.response.send_message("🏓 Đang đo...")
        end = time.perf_counter()

        api_latency_ms = round(self.bot.latency * 1000)
        roundtrip_ms = round((end - start) * 1000)

        embed = discord.Embed(title="🏓 Pong!", color=discord.Color.blurple())
        embed.add_field(name="Độ trễ WebSocket", value=f"{api_latency_ms}ms", inline=True)
        embed.add_field(name="Độ trễ phản hồi", value=f"{roundtrip_ms}ms", inline=True)
        await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(name="about", description="Thông tin về bot")
    async def about(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 Về bot này",
            description=BOT_DESCRIPTION,
            color=discord.Color.blue()
        )
        embed.add_field(name="Phiên bản", value=BOT_VERSION, inline=True)
        embed.add_field(name="Server đang phục vụ", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(
            name="Người dùng",
            value=str(sum(g.member_count or 0 for g in self.bot.guilds)),
            inline=True,
        )
        embed.set_footer(text="Hỗ trợ chính thức tại server Delta Mick")
        
        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Xem ảnh đại diện của bạn hoặc người khác")
    @app_commands.describe(user="Người muốn xem (bỏ trống = xem của bạn)")
    async def avatar(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        avatar_asset = target.display_avatar

        sizes = [128, 256, 512, 1024, 2048]
        size_links = " | ".join(
            f"[{size}px]({avatar_asset.with_size(size).url})"
            for size in sizes
        )

        embed = discord.Embed(
            title=f"🖼️ Avatar của {target.display_name}",
            description=f"📥 **Tải xuống các size:**\n{size_links}",
            color=discord.Color.random()
        )
        embed.set_image(url=avatar_asset.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="server", description="Xem thông tin máy chủ hiện tại")
    async def server(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Lệnh này chỉ dùng được trong máy chủ.", ephemeral=True
            )
            return

        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        boosts = guild.premium_subscription_count or 0

        embed = discord.Embed(title=f"🏰 {guild.name}", color=discord.Color.green())
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        embed.add_field(
            name="Chủ server",
            value=f"{guild.owner.mention}" if guild.owner else "Không rõ",
            inline=True
        )
        embed.add_field(name="Thành viên", value=str(guild.member_count), inline=True)
        embed.add_field(
            name="Ngày tạo",
            value=discord.utils.format_dt(guild.created_at, style="D"),
            inline=True
        )
        embed.add_field(name="Kênh chữ", value=str(text_channels), inline=True)
        embed.add_field(name="Kênh thoại", value=str(voice_channels), inline=True)
        embed.add_field(name="Vai trò", value=str(len(guild.roles)), inline=True)
        embed.add_field(
            name="Cấp boost",
            value=f"Cấp {guild.premium_tier} ({boosts} boost)",
            inline=True
        )
        embed.add_field(name="Emoji", value=str(len(guild.emojis)), inline=True)
        embed.set_footer(text=f"ID: {guild.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invite", description="Tạo link mời của máy chủ")
    async def invite(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Lệnh này chỉ dùng được trong máy chủ.", ephemeral=True
            )
            return

        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
            await interaction.response.send_message(
                "Không thể tạo lời mời tại kênh này.", ephemeral=True
            )
            return

        perms = channel.permissions_for(guild.me)
        if not perms.create_instant_invite:
            await interaction.response.send_message(
                "Bot thiếu quyền **Tạo lời mời** trong kênh này.", ephemeral=True
            )
            return

        try:
            invite = await channel.create_invite(
                max_age=0, max_uses=0, unique=False,
                reason=f"Lời mời từ {interaction.user.display_name}"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Bot không có quyền tạo lời mời.", ephemeral=True
            )
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Lỗi khi tạo lời mời: {e}", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📨 Lời mời vào {guild.name}",
            description=f"{invite.url}\n\nLời mời này không giới hạn thời gian và số lượt dùng.",
            color=discord.Color.blurple(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        await interaction.response.send_message(embed=embed)

    # ==================== EVENT LISTENERS ====================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        content = message.content.strip()

        # Meme tracking
        if message.channel.id == config.MEME_CONFIG["channel_id"]:
            await self._handle_meme_message(message)

        # Nối từ (chỉ xử lý nếu kênh đang có ván đang chạy)
        if store.get_noitu_game(message.channel.id):
            await self._handle_noitu_message(message)

        # Level XP từ tin nhắn
        await self._handle_level_message(message)

        # Quest: đếm tin nhắn (không phụ thuộc cooldown XP)
        store.track_quest_progress(message.author.id, "send_messages", 1)

        # Auto-chat: đánh dấu kênh vừa có hoạt động (reset bộ đếm im lặng)
        autochat_channel_id = store.get_autochat_channel()
        if autochat_channel_id and message.channel.id == autochat_channel_id:
            store.mark_channel_activity(message.channel.id)

        # AI chat khi được mention hoặc reply
        await self._handle_ai_chat_trigger(message)

    async def _handle_ai_chat_trigger(self, message: discord.Message):
        is_mentioned = self.bot.user in message.mentions if self.bot.user else False

        is_reply_to_bot = False
        if message.reference and message.reference.resolved:
            resolved = message.reference.resolved
            if isinstance(resolved, discord.Message) and resolved.author.id == (self.bot.user.id if self.bot.user else None):
                is_reply_to_bot = True

        if not is_mentioned and not is_reply_to_bot:
            return

        if store.is_ai_quiet_hours():
            return  # im lặng bỏ qua trong giờ cấm, tránh làm phiền

        prompt = message.content
        if self.bot.user:
            prompt = prompt.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()

        if not prompt:
            return

        remaining = store.get_ai_chat_cooldown_remaining_sec(message.author.id)
        if remaining > 0:
            return  # im lặng bỏ qua khi đang cooldown, tránh spam thông báo trong kênh chat thường

        async with message.channel.typing():
            reply = await _call_gemini(message.author.id, prompt)

        if reply is None:
            return

        store.append_ai_chat_turn(message.author.id, prompt, reply)

        if len(reply) > 2000:
            reply = reply[:2000] + "..."

        try:
            await message.reply(reply, mention_author=False)
        except discord.HTTPException:
            pass

    async def _handle_level_message(self, message: discord.Message):
        result = store.add_message_xp(message.author.id)
        if result["granted"] and result["leveled_up"]:
            embed = discord.Embed(
                title="🎊 Lên cấp!",
                description=f"{message.author.mention} đã đạt **Level {result['new_level']}**!",
                color=discord.Color.gold(),
            )
            try:
                await message.channel.send(embed=embed)
            except discord.HTTPException:
                pass

    async def _handle_noitu_message(self, message: discord.Message):
        content = message.content.strip()
        parts = content.lower().split()
        if len(parts) != 2:
            return  # không phải định dạng từ 2 tiếng -> bỏ qua, không làm phiền chat thường

        result = store.submit_noitu_word(message.channel.id, message.author.id, content)
        status = result["status"]

        if status == "no_game":
            return
        if status in ("invalid_format",):
            return
        if status == "same_player":
            try:
                await message.reply("Bạn vừa nối lượt trước, hãy đợi người khác nối trước đã.", mention_author=False, delete_after=6)
            except discord.HTTPException:
                pass
            return
        if status == "wrong_chain":
            await message.add_reaction("❌")
            return
        if status == "not_in_dict":
            await message.add_reaction("📖")
            return
        if status == "locked_cooldown":
            games_left = result.get("unlock_in_games", config.NOITU_WORD_COOLDOWN_GAMES)
            await message.add_reaction("🔁")
            try:
                await message.reply(
                    f"Từ này vừa được dùng gần đây, cần đợi thêm **{games_left}** ván nữa mới dùng lại được.",
                    mention_author=False, delete_after=8
                )
            except discord.HTTPException:
                pass
            return

        if status == "ok":
            await message.add_reaction("✅")
            await _track_quest_and_announce(message.channel, message.author, "noitu_correct", 1)
            return

        if status == "bingo":
            reward = store.apply_coins_mult(message.author.id, config.NOITU_BINGO_REWARD, command="noitu")
            store.transaction_coins(message.author.id, reward)
            await message.add_reaction("🏆")
            await _grant_win_xp_and_announce(message.channel, message.author)

            embed = discord.Embed(
                title="🎉 Bí từ!",
                description=(
                    f"{message.author.mention} đã khiến mọi người **bí từ** với từ cuối "
                    f"**`{result['current_word']}`**!\n"
                    f"Nhận **{reward} xu**!"
                ),
                color=discord.Color.gold(),
            )
            await message.channel.send(embed=embed)

            store.delete_noitu_game(message.channel.id)
            new_game = store.start_noitu_game(message.channel.id)
            new_cw = new_game["current_word"]
            start_embed = discord.Embed(
                title="🔤 Ván nối từ mới bắt đầu!",
                description=(
                    f"Cặp từ khởi đầu: **`{new_cw}`**\n"
                    f"Hãy nối tiếp bằng 1 từ 2 tiếng bắt đầu bằng tiếng **`{new_cw.split()[-1]}`**."
                ),
                color=discord.Color.blurple(),
            )
            await message.channel.send(embed=start_embed)

    async def _handle_meme_message(self, message: discord.Message):
        content_lower = message.content.lower()
        has_link = any(kw in content_lower for kw in (
            "http://", "https://", ".jpg", ".png", ".gif", ".mp4",
            "tenor.com", "giphy.com", "imgur.com", "youtu.be", "youtube.com",
        ))
        
        if not has_link:
            return

        user = message.author
        guild = message.guild
        new_count = store.increment_meme_count(user.id)

        if new_count >= config.MEME_CONFIG["required_count"] and not store.has_meme_role(user.id, guild.id):
            role_id = config.MEME_CONFIG["role_id"]
            role = guild.get_role(role_id)
            
            if role:
                try:
                    await user.add_roles(role, reason=f"Đã gửi {new_count} meme trong kênh meme")
                    store.claim_meme_role(user.id)

                    embed = discord.Embed(
                        title="🎉 **Thành tích Bậc Thầy Meme!**",
                        description=f"{user.mention} đã gửi **{new_count} meme** trong kênh <#{config.MEME_CONFIG['channel_id']}>!",
                        color=discord.Color.gold(),
                    )
                    embed.add_field(
                        name="🏆 Phần thưởng",
                        value=f"Đã nhận role <@&{role_id}>",
                        inline=True
                    )
                    embed.set_footer(text="Tiếp tục gửi meme để giữ vững danh hiệu!")
                    
                    await message.channel.send(
                        content=f"🎊 Chúc mừng {user.mention}!",
                        embed=embed
                    )
                except discord.Forbidden:
                    print(f"Bot thiếu quyền thêm role {role_id} cho user {user.id}")
                except discord.HTTPException as e:
                    print(f"Lỗi khi thêm role: {e}")

# ==================== UI COMPONENTS ====================
def _build_minesweeper_embed(user: discord.User, game: dict, finished_text: Optional[str] = None) -> discord.Embed:
    revealed_count = len(game.get("revealed", []))
    flagged_count = len(game.get("flagged", []))
    total_safe = game["safe_tiles_total"]
    mine_count = game["mine_count"]

    description = (
        f"Kích thước: **{game['rows']}×{game['cols']}** — Mìn: **{mine_count}**\n"
        f"Đã mở: **{revealed_count}/{total_safe}** ô an toàn — Đã cắm cờ: **{flagged_count}**"
    )
    if finished_text:
        description += f"\n\n{finished_text}"

    embed = discord.Embed(
        title=f"💣 Dò mìn của {user.display_name}",
        description=description,
        color=discord.Color.dark_grey() if finished_text else discord.Color.blurple(),
    )
    return embed

def _render_minesweeper_file(game: dict, reveal_all_mines: bool = False) -> discord.File:
    import io
    img = store.render_minesweeper_image(game, reveal_all_mines=reveal_all_mines)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="minesweeper.png")

async def _finish_minesweeper_win(interaction: discord.Interaction, owner_id: int, game: dict, via_flags: bool, edit: bool):
    reward = config.MINESWEEPER_REWARD_PER_SAFE_TILE * game["safe_tiles_total"]
    reward = store.apply_coins_mult(owner_id, reward, command="minesweeper")
    store.transaction_coins(owner_id, reward)
    store.delete_minesweeper_game(owner_id)
    await _grant_win_xp_and_announce(interaction.channel, interaction.user)
    await _track_quest_and_announce(interaction.channel, interaction.user, "win_minesweeper", 1)

    reason = "cắm cờ đúng hết mìn" if via_flags else "mở hết ô an toàn"
    embed = _build_minesweeper_embed(
        interaction.user, game, finished_text=f"🎉 **Thắng!** ({reason}) Bạn nhận **{reward} xu**!"
    )
    file = _render_minesweeper_file(game, reveal_all_mines=True)
    embed.set_image(url="attachment://minesweeper.png")
    view = MinesweeperView(finished=True)
    if edit:
        await interaction.response.edit_message(embed=embed, view=view, attachments=[file])
    else:
        await interaction.response.send_message(embed=embed, view=view, file=file)

async def _finish_minesweeper_boom(interaction: discord.Interaction, owner_id: int, game: dict, edit: bool):
    store.delete_minesweeper_game(owner_id)
    embed = _build_minesweeper_embed(
        interaction.user, game, finished_text="💥 **Trúng mìn!** Ván kết thúc, không nhận thưởng."
    )
    file = _render_minesweeper_file(game, reveal_all_mines=True)
    embed.set_image(url="attachment://minesweeper.png")
    view = MinesweeperView(finished=True)
    if edit:
        await interaction.response.edit_message(embed=embed, view=view, attachments=[file])
    else:
        await interaction.response.send_message(embed=embed, view=view, file=file)

class MinesweeperCoordModal(discord.ui.Modal):
    def __init__(self, action: str, is_owner_of_message: bool):
        # action: "reveal" hoặc "flag"
        title = "Mở ô" if action == "reveal" else "Đặt/Gỡ cờ"
        super().__init__(title=title)
        self.action = action
        self.is_owner_of_message = is_owner_of_message
        self.coord_input = discord.ui.TextInput(
            label="Toạ độ ô (VD: A5 hoặc 3,5)",
            placeholder="A5",
            max_length=10,
        )
        self.add_item(self.coord_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        game = store.get_active_minesweeper_game(user_id)
        if game is None:
            await interaction.response.send_message("Ván này đã kết thúc rồi.", ephemeral=True)
            return

        coord = store.parse_minesweeper_coord(self.coord_input.value, game["rows"], game["cols"])
        if coord is None:
            await interaction.response.send_message(
                "❌ Toạ độ không hợp lệ hoặc ngoài phạm vi bàn.", ephemeral=True
            )
            return

        row, col = coord
        edit = self.is_owner_of_message

        if self.action == "reveal":
            result = store.reveal_minesweeper_tile(user_id, row, col)

            if result["status"] == "no_game":
                await interaction.response.send_message("Ván này đã kết thúc rồi.", ephemeral=True)
                return
            if result["status"] == "already_revealed":
                await interaction.response.send_message("Ô này đã được mở rồi.", ephemeral=True)
                return

            if result["status"] == "boom":
                game_final = store._minesweeper_game_ref(user_id).get() or game
                await _finish_minesweeper_boom(interaction, user_id, game_final, edit)
                return

            if result["status"] == "win":
                game_final = store._minesweeper_game_ref(user_id).get() or game
                await _finish_minesweeper_win(interaction, user_id, game_final, via_flags=False, edit=edit)
                return

            # continue
            game_updated = store.get_active_minesweeper_game(user_id)
            embed = _build_minesweeper_embed(interaction.user, game_updated)
            file = _render_minesweeper_file(game_updated)
            embed.set_image(url="attachment://minesweeper.png")
            view = MinesweeperView()
            if edit:
                await interaction.response.edit_message(embed=embed, view=view, attachments=[file])
            else:
                await interaction.response.send_message(embed=embed, view=view, file=file)

        else:  # flag
            result = store.toggle_minesweeper_flag(user_id, row, col)

            if result["status"] == "no_game":
                await interaction.response.send_message(
                    "Không thể đặt cờ ở đây (ván đã kết thúc hoặc ô đã được mở).", ephemeral=True
                )
                return

            if result["status"] == "win":
                game_final = store._minesweeper_game_ref(user_id).get() or game
                await _finish_minesweeper_win(interaction, user_id, game_final, via_flags=True, edit=edit)
                return

            game_updated = store.get_active_minesweeper_game(user_id)
            embed = _build_minesweeper_embed(interaction.user, game_updated)
            file = _render_minesweeper_file(game_updated)
            embed.set_image(url="attachment://minesweeper.png")
            view = MinesweeperView()
            if edit:
                await interaction.response.edit_message(embed=embed, view=view, attachments=[file])
            else:
                await interaction.response.send_message(embed=embed, view=view, file=file)

class MinesweeperView(discord.ui.View):
    """Ai bấm nấy chơi: mỗi user thao tác trên ván riêng của mình.
    Nếu người bấm là chủ sở hữu message hiện tại, edit trực tiếp; nếu không, gửi message mới riêng cho họ."""
    def __init__(self, finished: bool = False):
        super().__init__(timeout=None)
        self.reveal_button.custom_id = f"ms:reveal"
        self.flag_button.custom_id = f"ms:flag"
        self.end_button.custom_id = f"ms:end"
        if finished:
            for item in self.children:
                item.disabled = True

    @discord.ui.button(label="🔓 Mở ô", style=discord.ButtonStyle.primary, custom_id="ms:reveal:template")
    async def reveal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_owner = interaction.message and interaction.message.interaction_metadata and interaction.message.interaction_metadata.user.id == interaction.user.id
        game = store.get_active_minesweeper_game(interaction.user.id)
        if game is None:
            game = store.create_minesweeper_game(
                interaction.user.id, config.MINESWEEPER_DEFAULT_DIM, config.MINESWEEPER_DEFAULT_DIM, None, None
            )
        await interaction.response.send_modal(MinesweeperCoordModal("reveal", bool(is_owner)))

    @discord.ui.button(label="🚩 Đặt/Gỡ cờ", style=discord.ButtonStyle.secondary, custom_id="ms:flag:template")
    async def flag_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_owner = interaction.message and interaction.message.interaction_metadata and interaction.message.interaction_metadata.user.id == interaction.user.id
        game = store.get_active_minesweeper_game(interaction.user.id)
        if game is None:
            game = store.create_minesweeper_game(
                interaction.user.id, config.MINESWEEPER_DEFAULT_DIM, config.MINESWEEPER_DEFAULT_DIM, None, None
            )
        await interaction.response.send_modal(MinesweeperCoordModal("flag", bool(is_owner)))

    @discord.ui.button(label="🛑 Kết thúc", style=discord.ButtonStyle.danger, custom_id="ms:end:template")
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        store.delete_minesweeper_game(interaction.user.id)

        is_owner = interaction.message and interaction.message.interaction_metadata and interaction.message.interaction_metadata.user.id == interaction.user.id

        embed = discord.Embed(
            title="🛑 Đã kết thúc ván dò mìn",
            description="Tin nhắn này sẽ tự xoá sau 15 giây." if is_owner else "Ván của bạn đã kết thúc.",
            color=discord.Color.dark_grey(),
        )

        if is_owner:
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=embed, view=self, attachments=[])

            async def _auto_delete():
                await asyncio.sleep(15)
                try:
                    await interaction.delete_original_response()
                except discord.HTTPException:
                    pass
            asyncio.create_task(_auto_delete())
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

def _build_minigame_embed(user, game: dict, extra_text: str | None = None) -> discord.Embed:
    kind = game["kind"]
    idx = game["current_index"]
    question = game["questions"][idx]
    attempts_used = game["current_attempts"]
    attempts_left = config.MINIGAME_ATTEMPTS_PER_QUESTION - attempts_used
    kind_name = config.MINIGAME_NAMES[kind]

    if kind == "hoahoc":
        body = f"**{question['text']}**\n\n"
    elif kind == "language":
        body = "Quốc gia này chính thức dùng ngôn ngữ gì?\n\n"
    else:
        body = "Đây là ảnh của gì?\n\n"

    embed = discord.Embed(
        title=f"❓ {kind_name} — {user.display_name}",
        description=(
            f"**Câu {idx + 1}/{config.MINIGAME_QUESTIONS_PER_GAME}**\n"
            f"{body}"
            f"Lượt thử còn lại: **{attempts_left}/{config.MINIGAME_ATTEMPTS_PER_QUESTION}**\n"
            f"Đúng đến hiện tại: **{game['correct_count']}/{config.MINIGAME_QUESTIONS_PER_GAME}**"
        ),
        color=discord.Color.blue(),
    )
    if question.get("image_url"):
        embed.set_image(url=question["image_url"])
    if extra_text:
        embed.add_field(name="Kết quả", value=extra_text, inline=False)
    embed.set_footer(text=f"Mỗi câu đúng: {config.MINIGAME_REWARD_PER_QUESTION[kind]} xu · {config.MINIGAME_SECONDS_PER_QUESTION}s/câu")
    return embed

def _build_minigame_finished_embed(user, kind: str, correct_count: int) -> discord.Embed:
    total_reward = correct_count * config.MINIGAME_REWARD_PER_QUESTION[kind]
    kind_name = config.MINIGAME_NAMES[kind]
    embed = discord.Embed(
        title=f"🏁 Kết thúc — {kind_name} — {user.display_name}",
        description=(
            f"Kết quả: **{correct_count}/{config.MINIGAME_QUESTIONS_PER_GAME}** câu đúng\n"
            f"Tổng nhận: **{total_reward} xu**"
        ),
        color=discord.Color.green() if correct_count >= 3 else discord.Color.dark_grey(),
    )
    return embed

class MinigameView(discord.ui.View):
    """Ai bấm nấy chơi: mỗi user thao tác trên ván riêng của mình."""
    def __init__(self, kind: str, finished: bool = False):
        super().__init__(timeout=None)
        self.kind = kind
        self.guess_button.custom_id = f"mg:{kind}:guess"
        self.end_button.custom_id = f"mg:{kind}:end"
        if finished:
            for item in self.children:
                item.disabled = True

    @discord.ui.button(label="✏️ Đoán", style=discord.ButtonStyle.primary, custom_id="mg:guess:template")
    async def guess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        is_owner = bool(interaction.message and interaction.message.interaction_metadata and interaction.message.interaction_metadata.user.id == user_id)

        expired = store.check_and_expire_minigame_question(user_id, self.kind)
        if expired:
            await self._render_after_expire(interaction, expired, is_owner)
            return

        game = store.get_active_minigame_game(user_id, self.kind)
        if game is None:
            await interaction.response.send_message(
                f"Bạn chưa có ván nào — dùng lệnh `/{self.kind}` để bắt đầu.", ephemeral=True
            )
            return
        await interaction.response.send_modal(MinigameGuessModal(self.kind, is_owner))

    @discord.ui.button(label="🛑 Kết thúc", style=discord.ButtonStyle.danger, custom_id="mg:end:template")
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        is_owner = bool(interaction.message and interaction.message.interaction_metadata and interaction.message.interaction_metadata.user.id == user_id)

        store.delete_minigame_game(user_id, self.kind)
        embed = discord.Embed(
            title="🛑 Đã kết thúc ván",
            description="Tin nhắn này sẽ tự xoá sau 15 giây." if is_owner else "Ván của bạn đã kết thúc.",
            color=discord.Color.dark_grey(),
        )

        if is_owner:
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)

            async def _auto_delete():
                await asyncio.sleep(15)
                try:
                    await interaction.delete_original_response()
                except discord.HTTPException:
                    pass
            asyncio.create_task(_auto_delete())
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _render_after_expire(self, interaction: discord.Interaction, result: dict, is_owner: bool):
        user = interaction.user
        if result["is_last_question"]:
            embed = _build_minigame_finished_embed(user, self.kind, result["correct_count"])
            view = MinigameView(self.kind, finished=True)
            if is_owner:
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view)
        else:
            game = store.get_active_minigame_game(interaction.user.id, self.kind)
            embed = _build_minigame_embed(user, game, extra_text=f"⏱️ Hết giờ! Đáp án là **{result['answer_text']}**.")
            if is_owner:
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.send_message(embed=embed, view=MinigameView(self.kind))

class MinigameGuessModal(discord.ui.Modal, title="Nhập câu trả lời"):
    guess_input = discord.ui.TextInput(
        label="Câu trả lời",
        placeholder="Nhập đáp án...",
        max_length=100,
    )

    def __init__(self, kind: str, is_owner_of_message: bool):
        super().__init__()
        self.kind = kind
        self.is_owner_of_message = is_owner_of_message

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        edit = self.is_owner_of_message
        guess = self.guess_input.value.strip()
        result = store.submit_minigame_guess(user_id, self.kind, guess)

        if result["status"] == "no_game":
            await interaction.response.send_message("Ván này đã kết thúc rồi.", ephemeral=True)
            return

        user = interaction.user

        async def _send(embed, view=None):
            if edit:
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view or discord.utils.MISSING)

        if result["status"] == "correct":
            store.transaction_coins(user_id, result["reward"])
            await _grant_win_xp_and_announce(interaction.channel, user)
            await _track_quest_and_announce(interaction.channel, user, "win_flag", 1)

        if result["status"] in ("correct", "wrong_final") and result["is_last_question"]:
            game_check = store.get_active_minigame_game(user_id, self.kind)
            if game_check is None:  # ván đã hết
                embed = _build_minigame_finished_embed(user, self.kind, result["correct_count"])
                view = MinigameView(self.kind, finished=True)
                await _send(embed, view)
                return

        game = store.get_active_minigame_game(user_id, self.kind)
        if result["status"] == "correct":
            extra = f"✅ Chính xác! Nhận **{result['reward']} xu**."
        elif result["status"] == "wrong_retry":
            extra = f"❌ Sai rồi, còn **{result['attempts_left']}** lượt thử."
        else:  # wrong_final
            extra = f"❌ Hết lượt! Đáp án là **{result['answer_text']}**."

        embed = _build_minigame_embed(user, game, extra_text=extra)
        await _send(embed, MinigameView(self.kind))

def _chess_player_label(user_id: int | None, bot_side: bool = False) -> str:
    if bot_side:
        return "🤖 Bot AI"
    return f"<@{user_id}>" if user_id else "?"

def _build_chess_embed_and_file(user, opponent, game: dict, game_id: str):
    mode = game["mode"]
    is_bot_game = mode == "bot"
    white_label = _chess_player_label(game["white_id"])
    black_label = _chess_player_label(game.get("black_id"), bot_side=is_bot_game)

    import chess
    board = chess.Board(game["fen"])
    turn_label = "Trắng" if board.turn == chess.WHITE else "Đen"

    status_lines = [f"⚪ Trắng: {white_label}", f"⚫ Đen: {black_label}", f"Lượt đi: **{turn_label}**"]
    if board.is_check():
        status_lines.append("⚠️ **Đang bị chiếu!**")

    embed = discord.Embed(
        title="♟️ Ván cờ vua",
        description="\n".join(status_lines),
        color=discord.Color.dark_grey(),
    )

    import io
    img = store.render_chess_board_image(game["fen"])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    file = discord.File(buf, filename="chess.png")
    embed.set_image(url="attachment://chess.png")

    if game.get("move_history"):
        last_moves = game["move_history"][-6:]
        embed.set_footer(text="Nước gần đây: " + " ".join(last_moves))

    return embed, file

def _build_chess_finished_embed(game: dict) -> discord.Embed:
    result = game.get("result")
    is_bot_game = game["mode"] == "bot"

    if result == "draw":
        desc = "🤝 Ván cờ kết thúc **hoà**!"
        color = discord.Color.light_grey()
    else:
        winner_id = game["white_id"] if result == "white_win" else game.get("black_id")
        if is_bot_game and winner_id is None:
            desc = "🤖 **Bot AI thắng!**"
        else:
            desc = f"🏆 <@{winner_id}> đã **thắng ván cờ**!"
        color = discord.Color.gold()

    embed = discord.Embed(title="🏁 Ván cờ kết thúc", description=desc, color=color)
    if game.get("move_history"):
        embed.set_footer(text=f"Tổng {len(game['move_history'])} nước đi")
    return embed

async def _apply_chess_bot_move_if_needed(interaction_or_channel, game_id: str) -> dict | None:
    """Nếu đến lượt bot đi (mode=bot, quân đen), tính và thực hiện nước đi. Trả về game mới nhất hoặc None."""
    game = store.get_chess_game(game_id)
    if game is None or game.get("finished") or game["mode"] != "bot":
        return game

    import chess
    board = chess.Board(game["fen"])
    if board.turn != chess.BLACK:
        return game

    bot_move_uci = store.compute_chess_bot_move(game["fen"], game.get("difficulty", "easy"))
    if bot_move_uci is None:
        return game

    from_sq, to_sq = bot_move_uci[:2], bot_move_uci[2:4]
    promo = bot_move_uci[4:5] if len(bot_move_uci) > 4 else None
    store.submit_chess_move(game_id, from_sq, to_sq, promotion=promo)
    return store.get_chess_game(game_id)

async def _finish_chess_game(interaction: discord.Interaction, game_id: str, game: dict):
    is_bot_game = game["mode"] == "bot"

    if is_bot_game:
        bot_elo = config.CHESS_BOT_DIFFICULTY_ELO.get(game.get("difficulty", "easy"), 800)
        elo_result = store.apply_chess_elo_result(game["white_id"], bot_elo, black_is_bot=True, result=game["result"])
    else:
        elo_result = store.apply_chess_elo_result(game["white_id"], game["black_id"], black_is_bot=False, result=game["result"])

    embed = _build_chess_finished_embed(game)

    white_delta = elo_result["white_elo_after"] - elo_result["white_elo_before"]
    white_sign = "+" if white_delta >= 0 else ""
    elo_lines = [f"⚪ <@{game['white_id']}>: {elo_result['white_elo_before']} → {elo_result['white_elo_after']} ({white_sign}{white_delta})"]

    if not is_bot_game:
        black_delta = elo_result["black_elo_after"] - elo_result["black_elo_before"]
        black_sign = "+" if black_delta >= 0 else ""
        elo_lines.append(f"⚫ <@{game['black_id']}>: {elo_result['black_elo_before']} → {elo_result['black_elo_after']} ({black_sign}{black_delta})")

    embed.add_field(name="📊 Thay đổi ELO", value="\n".join(elo_lines), inline=False)

    winner_id = None
    if game["result"] == "white_win":
        winner_id = game["white_id"]
    elif game["result"] == "black_win":
        winner_id = game.get("black_id")

    if winner_id:
        await _grant_win_xp_and_announce(interaction.channel, interaction.user)

    store.track_quest_progress(game["white_id"], "play_chess", 1)
    if game.get("black_id") and not is_bot_game:
        store.track_quest_progress(game["black_id"], "play_chess", 1)

    store.delete_chess_game(game_id)
    view = discord.ui.View()

    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view, attachments=[])

class ChessDestinationDropdown(discord.ui.Select):
    def __init__(self, game_id: str, owner_id: int, from_sq: str, destinations: List[str]):
        self.game_id = game_id
        self.owner_id = owner_id
        self.from_sq = from_sq
        options = [discord.SelectOption(label=dest.upper(), value=dest) for dest in destinations[:25]]
        super().__init__(placeholder=f"Đi quân tại {from_sq.upper()} đến đâu?", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Không phải ván của bạn.", ephemeral=True)
            return

        to_sq = self.values[0]
        result = store.submit_chess_move(self.game_id, self.from_sq, to_sq)

        if result["status"] == "no_game":
            await interaction.response.send_message("Ván này đã kết thúc rồi.", ephemeral=True)
            return
        if result["status"] == "illegal":
            await interaction.response.send_message("Nước đi không hợp lệ.", ephemeral=True)
            return

        game = store.get_chess_game(self.game_id)

        if game["finished"]:
            await _finish_chess_game(interaction, self.game_id, game)
            return

        # Nếu là ván bot và giờ đến lượt bot, tự động đi luôn
        if game["mode"] == "bot":
            game = await _apply_chess_bot_move_if_needed(interaction, self.game_id)
            if game and game["finished"]:
                await _finish_chess_game(interaction, self.game_id, game)
                return

        embed, file = _build_chess_embed_and_file(interaction.user, None, game, self.game_id)
        next_turn_id = _chess_current_turn_user_id(game) or self.owner_id
        view = ChessMoveView(self.game_id, next_turn_id)
        await interaction.response.edit_message(embed=embed, view=view, attachments=[file])

class ChessPieceDropdown(discord.ui.Select):
    def __init__(self, game_id: str, owner_id: int, moves_by_piece: dict):
        self.game_id = game_id
        self.owner_id = owner_id
        self.moves_by_piece = moves_by_piece
        options = [
            discord.SelectOption(label=f"{sq.upper()} ({len(dests)} nước)", value=sq)
            for sq, dests in list(moves_by_piece.items())[:25]
        ]
        super().__init__(placeholder="Chọn quân cờ muốn đi...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Không phải ván của bạn.", ephemeral=True)
            return

        from_sq = self.values[0]
        destinations = self.moves_by_piece.get(from_sq, [])

        view = discord.ui.View(timeout=120)
        view.add_item(ChessDestinationDropdown(self.game_id, self.owner_id, from_sq, destinations))
        await interaction.response.send_message(
            f"Chọn ô đích cho quân tại **{from_sq.upper()}**:", view=view, ephemeral=True
        )

class ChessResignButton(discord.ui.Button):
    def __init__(self, game_id: str):
        super().__init__(label="🏳️ Đầu hàng", style=discord.ButtonStyle.danger, row=1, custom_id=f"chess_resign:{game_id}")
        self.game_id = game_id

    async def callback(self, interaction: discord.Interaction):
        game = store.get_chess_game(self.game_id)
        if game is None or game.get("finished"):
            await interaction.response.send_message("Ván này đã kết thúc rồi.", ephemeral=True)
            return

        if interaction.user.id not in (game["white_id"], game.get("black_id")):
            await interaction.response.send_message("Bạn không tham gia ván này.", ephemeral=True)
            return

        updated_game = store.resign_chess_game(self.game_id, interaction.user.id)
        if updated_game is None:
            await interaction.response.send_message("Không thể đầu hàng lúc này.", ephemeral=True)
            return

        await _finish_chess_game(interaction, self.game_id, updated_game)

class ChessMoveView(discord.ui.View):
    def __init__(self, game_id: str, owner_id: int):
        super().__init__(timeout=None)
        self.game_id = game_id
        self.owner_id = owner_id

        moves_by_piece = store.get_chess_legal_moves_by_piece(game_id)
        if moves_by_piece:
            self.add_item(ChessPieceDropdown(game_id, owner_id, moves_by_piece))
        self.add_item(ChessResignButton(game_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        game = store.get_chess_game(self.game_id)
        is_player = game and interaction.user.id in (game["white_id"], game.get("black_id"))

        # Nút đầu hàng luôn cho phép bất kỳ người chơi nào trong ván, bất kể lượt
        if isinstance(interaction.data, dict) and str(interaction.data.get("custom_id", "")).startswith("chess_resign:"):
            if not is_player:
                await interaction.response.send_message("Bạn không tham gia ván này.", ephemeral=True)
                return False
            return True

        if interaction.user.id != self.owner_id:
            if is_player:
                await interaction.response.send_message("Chưa đến lượt của bạn.", ephemeral=True)
            else:
                await interaction.response.send_message(
                    "Ván này không dành cho bạn. Dùng `/chess` để tạo ván riêng.", ephemeral=True
                )
            return False
        return True

def _chess_current_turn_user_id(game: dict) -> int | None:
    import chess
    board = chess.Board(game["fen"])
    if board.turn == chess.WHITE:
        return game["white_id"]
    return game.get("black_id")  # None nếu mode=bot và bot đang cầm quân đen

class ChessChallengeView(discord.ui.View):
    def __init__(self, challenger_id: int, opponent_id: int):
        super().__init__(timeout=config.CHESS_CHALLENGE_TIMEOUT_SEC)
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("Lời thách đấu này không dành cho bạn.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Chấp nhận", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if store.get_user_active_chess_game_id(self.challenger_id):
            await interaction.response.send_message(
                "Người thách đấu hiện đang có ván cờ khác rồi.", ephemeral=True
            )
            return

        game_id, game = store.create_chess_game(self.challenger_id, self.opponent_id, "pvp")
        embed, file = _build_chess_embed_and_file(interaction.user, None, game, game_id)
        view = ChessMoveView(game_id, self.challenger_id)  # Trắng đi trước
        await interaction.response.edit_message(content=None, embed=embed, view=view, attachments=[file])

    @discord.ui.button(label="❌ Từ chối", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Đã từ chối thách đấu",
            color=discord.Color.dark_grey(),
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)

_SHOP_RARITY_LABELS = {"common": "⚪ Thường", "rare": "🔵 Hiếm", "epic": "🟣 Siêu hiếm"}
_SHOP_CURRENCY_LABELS = {"coins": "xu", "elo": "ELO"}

def _build_shop_embed_and_view(user_id: int, rotation: dict) -> tuple[discord.Embed, discord.ui.View]:
    items = rotation.get("items", {})
    next_refresh = store.parse_iso(rotation.get("next_refresh_at"))
    discount = store.get_shop_discount(user_id)

    lines = []
    for key, stock in items.items():
        item = config.SHOP_ITEMS.get(key)
        if not item:
            continue
        price = item["price"]
        final_price = max(0, round(price * (1 - discount))) if discount else price
        price_text = f"~~{price}~~ **{final_price}**" if discount else f"**{price}**"
        rarity_label = _SHOP_RARITY_LABELS.get(item["rarity"], item["rarity"])
        currency_label = _SHOP_CURRENCY_LABELS.get(item["currency"], item["currency"])
        lines.append(
            f"{rarity_label} **{item['name']}** — {price_text} {currency_label} (còn {stock})\n_{item['desc']}_"
        )

    embed = discord.Embed(
        title="🛒 Cửa hàng",
        description="\n\n".join(lines) if lines else "Hiện không có vật phẩm nào.",
        color=discord.Color.dark_gold(),
    )
    if next_refresh:
        unix_ts = int(next_refresh.timestamp())
        embed.set_footer(text=f"Làm mới lúc <t:{unix_ts}:t> (<t:{unix_ts}:R>)")

    view = discord.ui.View(timeout=300)
    if items:
        view.add_item(ShopBuyDropdown(items))
    return embed, view

class QuestClaimDropdown(discord.ui.Select):
    def __init__(self, daily_quests: list, weekly_quests: list):
        self.quest_period_map = {}
        options = []
        for q in daily_quests:
            if q["completed"] and not q["claimed"]:
                self.quest_period_map[q["id"]] = "daily"
                options.append(discord.SelectOption(label=f"[Ngày] {q['desc'][:90]}", value=q["id"]))
        for q in weekly_quests:
            if q["completed"] and not q["claimed"]:
                self.quest_period_map[q["id"]] = "weekly"
                options.append(discord.SelectOption(label=f"[Tuần] {q['desc'][:90]}", value=q["id"]))
        super().__init__(placeholder="Chọn nhiệm vụ để nhận thưởng...", options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        quest_id = self.values[0]
        period = self.quest_period_map.get(quest_id, "daily")
        result = store.claim_quest_reward(interaction.user.id, quest_id, period)

        if not result["ok"]:
            await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)
            return

        reward = result["reward"]
        reward_label = {
            "coins": f"{reward['amount']} xu",
            "elo": f"{reward['amount']} ELO",
            "xp": f"{reward['amount']} XP",
            "game_ticket": f"{reward['amount']} vé chơi game (có hạn 24h)",
        }.get(reward["type"], "")

        await interaction.response.send_message(f"🎉 Nhận thưởng: **{reward_label}**!", ephemeral=True)

class ShopBuyDropdown(discord.ui.Select):
    def __init__(self, items: dict):
        options = []
        for key, stock in items.items():
            item = config.SHOP_ITEMS.get(key)
            if not item or stock <= 0:
                continue
            currency_label = _SHOP_CURRENCY_LABELS.get(item["currency"], item["currency"])
            options.append(discord.SelectOption(
                label=f"{item['name']} — {item['price']} {currency_label}",
                value=key,
                description=item["desc"][:100],
            ))
        super().__init__(placeholder="Chọn vật phẩm muốn mua...", options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        item_key = self.values[0]
        result = store.buy_shop_item(interaction.user.id, item_key)

        if not result["ok"]:
            await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"✅ Đã mua {result['item_name']}!",
            description=result.get("effect_summary", ""),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Xử lý role riêng (cần context guild, không thể làm trong store.py)
        item = config.SHOP_ITEMS.get(item_key, {})
        role_id = item.get("effect", {}).get("role_id")
        if role_id and interaction.guild:
            role = interaction.guild.get_role(role_id)
            member = interaction.guild.get_member(interaction.user.id)
            if role and member and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Mua từ shop: {item.get('name')}")
                except discord.Forbidden:
                    pass

        # Cập nhật lại view shop (rotation có thể đã đổi tồn kho)
        rotation = store.get_current_shop_rotation()
        new_embed, new_view = _build_shop_embed_and_view(interaction.user.id, rotation)
        try:
            await interaction.message.edit(embed=new_embed, view=new_view)
        except discord.HTTPException:
            pass

class TitleEquipDropdown(discord.ui.Select):
    def __init__(self, owner_id: int, owned: List[str], equipped: List[str]):
        self.owner_id = owner_id
        options = [
            discord.SelectOption(
                label=config.TITLES[key]["name"][:100],
                value=key,
                description=config.TITLES[key]["desc"][:100],
                default=key in equipped,
            )
            for key in owned
            if key in config.TITLES
        ][:25]
        super().__init__(
            placeholder=f"Chọn tối đa {config.TITLE_MAX_EQUIPPED} danh hiệu để trang bị...",
            min_values=0,
            max_values=min(len(options), config.TITLE_MAX_EQUIPPED) or 1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Không phải của bạn.", ephemeral=True)
            return

        ok, msg = store.set_equipped_titles(self.owner_id, self.values)
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        names = [config.TITLES[k]["name"] for k in self.values if k in config.TITLES]
        await interaction.response.send_message(
            f"✅ Đã trang bị: {', '.join(names) if names else '_không có_'}", ephemeral=True
        )

class CompanyChooseView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.add_item(CompanyDropdown(user_id))

class CompanyDropdown(discord.ui.Select):
    def __init__(self, user_id: int):
        self.user_id = user_id
        options = []
        for cid, cfg in config.COMPANIES.items():
            fee = store.get_company_entry_fee(cid)
            desc = f"Phí vào: {fee} xu" if fee > 0 else None
            options.append(discord.SelectOption(label=cfg["name"], value=cid, description=desc))
        super().__init__(placeholder="Chọn công ty...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Không phải công việc của bạn.", ephemeral=True
            )
            return

        company_id = self.values[0]

        try:
            await interaction.response.edit_message(
                content="👔 Đang làm việc...", embed=None, view=None
            )
            await asyncio.sleep(1)

            result = store.do_work(self.user_id, company_id)

            if not result.get("ok"):
                msg = result["message"]
                if msg.startswith("cooldown:"):
                    sec = int(msg.split(":")[1])
                    await interaction.edit_original_response(
                        content=f"⏱️ Bạn đã làm việc hôm nay rồi, quay lại sau **{_fmt_td(sec)}** nữa (reset 0h giờ VN).",
                        embed=None, view=None,
                    )
                elif msg.startswith("company_penalty:"):
                    sec = int(msg.split(":")[1])
                    await interaction.edit_original_response(
                        content=f"🚫 Công ty này đang tạm ngừng nhận bạn, còn **{_fmt_td(sec)}** nữa.",
                        embed=None, view=None,
                    )
                elif msg.startswith("switch_cooldown:"):
                    sec = int(msg.split(":")[1])
                    await interaction.edit_original_response(
                        content=f"🔒 Bạn chỉ mới đổi công ty gần đây — cần chờ **{_fmt_td(sec)}** nữa mới đổi công ty tiếp được.",
                        embed=None, view=None,
                    )
                elif msg.startswith("resign_cooldown:"):
                    sec = int(msg.split(":")[1])
                    await interaction.edit_original_response(
                        content=f"📄 Bạn vừa từ chức gần đây — cần chờ **{_fmt_td(sec)}** nữa mới đi làm lại được.",
                        embed=None, view=None,
                    )
                elif msg.startswith("entry_fee:"):
                    await interaction.edit_original_response(
                        content=f"💰 {msg.split(':', 1)[1]}", embed=None, view=None,
                    )
                elif msg == "too_late":
                    await interaction.edit_original_response(
                        content=f"🌙 Đã quá trễ (sau {config.WORK_LATE_CUTOFF_HOUR}h trưa), hôm nay bạn không thể đi làm nữa.",
                        embed=None, view=None,
                    )
                else:
                    await interaction.edit_original_response(
                        content=f"❌ {result.get('message', 'Có lỗi xảy ra.')}"
                    )
                return

            if result["event"]:
                embed = discord.Embed(
                    title=f"⚠️ Sự cố tại {result['company_name']}",
                    description=result["event"]["text"],
                    color=discord.Color.dark_red(),
                )
                embed.add_field(
                    name="Hậu quả",
                    value=f"Không nhận được lương, tạm ngừng làm việc tại công ty này {result['event']['penalty_hours']} giờ.",
                    inline=False,
                )
                await interaction.edit_original_response(content=None, embed=embed)
                return

            idx = min(result["position_level"], len(config.POSITION_NAMES) - 1)
            position_name = config.POSITION_NAMES[idx]

            good_event = result.get("good_event")
            embed_title = f"✨ May mắn tại {result['company_name']}!" if good_event else f"✅ Hoàn thành công việc tại {result['company_name']}"
            embed = discord.Embed(
                title=embed_title,
                color=discord.Color.gold() if good_event else discord.Color.green(),
            )
            if good_event:
                embed.description = good_event["text"]
            embed.add_field(name="Lương nhận được", value=f"{result['pay']} xu", inline=True)
            embed.add_field(name="Chức vụ", value=position_name, inline=True)
            embed.add_field(
                name="Streak",
                value=f"{result['streak_weeks']} tuần (+{result['streak_weeks'] * config.STREAK_BONUS_PER_WEEK * 100:.0f}% lương)",
                inline=True,
            )

            minutes_late = result.get("minutes_late", 0)
            late_penalty = result.get("late_penalty", 0)
            if minutes_late > 0:
                embed.add_field(
                    name="⏰ Đi trễ",
                    value=f"{minutes_late} phút (-{late_penalty*100:.0f}% lương)",
                    inline=True,
                )

            await interaction.edit_original_response(content=None, embed=embed)

            store.track_quest_progress(self.user_id, "do_work", 1)
            store.track_quest_progress(self.user_id, "earn_coins", result["pay"])

            if result.get("became_president"):
                member = interaction.guild.get_member(self.user_id) if interaction.guild else None
                if member:
                    try:
                        new_nick = config.WORK_PRESIDENT_NICKNAME_PREFIX + member.display_name
                        if len(new_nick) <= 32:
                            await member.edit(nick=new_nick, reason="Thăng chức Chủ tịch")
                    except discord.Forbidden:
                        pass
                await interaction.followup.send(
                    f"🎉 {member.mention if member else ''} vừa trở thành **Chủ tịch**! Chúc mừng!"
                )

        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.edit_original_response(
                content=f"❌ Đã xảy ra lỗi không mong muốn.", embed=None, view=None
            )

class LixiCloseView(discord.ui.View):
    def __init__(self, envelope_id: str, jump_url: str):
        super().__init__(timeout=config.LIXI_DURATION_MIN * 60 + 5)
        self.envelope_id = envelope_id
        self.add_item(discord.ui.Button(label="Xem lì xì", style=discord.ButtonStyle.link, url=jump_url))

    @discord.ui.button(label="🔒 Đóng lì xì sớm", style=discord.ButtonStyle.danger)
    async def close_early(self, interaction: discord.Interaction, button: discord.ui.Button):
        envelope = store.get_lixi(self.envelope_id)
        if envelope is None or envelope.get("closed"):
            await interaction.response.send_message("Lì xì này đã đóng rồi.", ephemeral=True)
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                    item.disabled = True
            return

        refund = store.refund_expired_lixi(self.envelope_id)
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                item.disabled = True

        text = f"🔒 Đã đóng lì xì sớm." + (f" Hoàn lại **{refund} xu** chưa ai nhận." if refund > 0 else " Toàn bộ đã được nhận hết.")
        await interaction.response.edit_message(content=text, view=self)

        envelope_after = store.get_lixi(self.envelope_id) or envelope
        channel_id = envelope_after.get("channel_id")
        message_id = envelope_after.get("message_id")
        if channel_id and message_id:
            channel = interaction.client.get_channel(channel_id)
            if channel:
                try:
                    original_message = await channel.fetch_message(message_id)
                    closed_embed = discord.Embed(
                        title="🧧 Lì xì đã đóng",
                        description="Người tạo đã đóng lì xì này.",
                        color=discord.Color.dark_grey(),
                    )
                    await original_message.edit(embed=closed_embed, view=None)
                except discord.HTTPException:
                    pass

class LixiClaimView(discord.ui.View):
    def __init__(self, guild_id: int, envelope_id: str, creator_id: int):
        super().__init__(timeout=config.LIXI_DURATION_MIN * 60 + 5)
        self.guild_id = guild_id
        self.envelope_id = envelope_id
        self.creator_id = creator_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.creator_id:
            await interaction.response.send_message(
                "Bạn không thể tự nhận lì xì của chính mình.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="🧧 Nhận lì xì", style=discord.ButtonStyle.danger)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok, msg, amount = store.claim_lixi(self.envelope_id, interaction.user.id)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        envelope = store.get_lixi(self.envelope_id)
        await interaction.response.send_message(
            f"🎉 Bạn đã nhận được **{amount} xu** từ lì xì!",
            ephemeral=True
        )

        updated_embed = _build_lixi_embed(self.envelope_id)
        if updated_embed:
            try:
                await interaction.message.edit(embed=updated_embed)
            except discord.HTTPException:
                pass

def _build_lixi_embed(envelope_id: str) -> Optional[discord.Embed]:
    envelope = store.get_lixi(envelope_id)
    if envelope is None:
        return None

    creator_mention = f"<@{envelope['creator_id']}>"
    amount = envelope["total_amount"]
    expires_unix = int(store.parse_iso(envelope["expires_at"]).timestamp())

    lines_status = (
        f"{creator_mention} vừa lì xì **{amount} xu**!\n"
        f"Bấm nút bên dưới để nhận — mỗi người chỉ nhận được 1 lần.\n"
        f"Lì xì tự động đóng lúc <t:{expires_unix}:t> (<t:{expires_unix}:R>)."
    )

    embed = discord.Embed(
        title="🧧 Lì xì!",
        description=lines_status,
        color=discord.Color.red()
    )

    claimed_order = envelope.get("claimed_order", [])
    claimed_by = envelope.get("claimed_by", {})
    
    if claimed_order:
        lines = [
            f"<@{uid}> — **{claimed_by.get(uid, 0)} xu**"
            for uid in claimed_order
        ]
        embed.add_field(name="🎁 Người đã nhận", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="🎁 Người đã nhận", value="_Chưa có ai nhận._", inline=False)
    
    return embed

class HelpView(discord.ui.View):
    def __init__(self, pages: List[discord.Embed]):
        super().__init__(timeout=300)
        self.pages = pages
        self.index = 0
        self._sync_buttons()

    def _sync_buttons(self):
        self.prev_button.disabled = self.index == 0
        self.next_button.disabled = self.index == len(self.pages) - 1

    @discord.ui.button(label="◀ Trước", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = max(0, self.index - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Sau ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = min(len(self.pages) - 1, self.index + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

def _build_help_pages(bot: commands.Bot, requester_id: int) -> List[discord.Embed]:
    is_owner = store.is_owner(requester_id)
    all_commands = bot.tree.get_commands()
    locked_commands = store.get_locked_commands() if not is_owner else {}

    grouped: Dict[str, List] = {}
    for cmd in all_commands:
        if not is_owner and locked_commands.get(cmd.name, False):
            continue
        cog_name = getattr(cmd.binding, "__class__", None)
        cog_name = cog_name.__name__ if cog_name else "Khác"
        grouped.setdefault(cog_name, []).append(cmd)

    # Sort commands within each group
    for cog_name in grouped:
        grouped[cog_name] = sorted(grouped[cog_name], key=lambda c: c.name)

    # Define display names and order
    COG_DISPLAY_NAMES = {
        "GamesCog": "💵 Kinh tế & Tiện ích",
        "WikiCog": "📖 Tra cứu",
    }
    COG_ORDER = ["GamesCog", "WikiCog"]

    # Order groups
    ordered_cog_names = [
        c for c in COG_ORDER if c in grouped
    ] + [
        c for c in grouped if c not in COG_ORDER
    ]

    pages = []
    for cog_name in ordered_cog_names:
        commands_in_cog = grouped[cog_name]
        display_name = COG_DISPLAY_NAMES.get(cog_name, cog_name)
        lines = [f"`/{cmd.name}` — {cmd.description}" for cmd in commands_in_cog]
        embed = discord.Embed(
            title=f"📖 Danh sách lệnh — {display_name}",
            description="\n".join(lines),
            color=discord.Color.teal(),
        )
        pages.append(embed)

    for i, embed in enumerate(pages):
        embed.set_footer(text=f"Trang {i + 1}/{len(pages)}")

    return pages

class WordleView(discord.ui.View):
    def __init__(self, finished: bool = False):
        super().__init__(timeout=None)
        self.guess_button.custom_id = "wordle:guess"
        self.end_button.custom_id = "wordle:end"
        if finished:
            for item in self.children:
                item.disabled = True

    @discord.ui.button(label="🔤 Đoán từ", style=discord.ButtonStyle.primary, custom_id="wordle:guess:template")
    async def guess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_owner = bool(interaction.message and interaction.message.interaction_metadata and interaction.message.interaction_metadata.user.id == interaction.user.id)

        game = store.get_active_wordle_game(interaction.user.id)
        if game is None:
            remaining = store.get_wordle_plays_remaining(interaction.user.id)
            if remaining <= 0 or not store.consume_wordle_play(interaction.user.id):
                await interaction.response.send_message(
                    f"Bạn đã dùng hết lượt `/wordle` hôm nay, hãy quay lại vào ngày mai.", ephemeral=True
                )
                return
            store.create_wordle_game(interaction.user.id)

        await interaction.response.send_modal(WordleGuessModal(is_owner))

    @discord.ui.button(label="🛑 Kết thúc", style=discord.ButtonStyle.danger, custom_id="wordle:end:template")
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_owner = bool(interaction.message and interaction.message.interaction_metadata and interaction.message.interaction_metadata.user.id == interaction.user.id)

        game = store.get_active_wordle_game(interaction.user.id)
        word_text = f"\n\nTừ bí mật là **`{game['word']}`**." if game else ""
        store.delete_wordle_game(interaction.user.id)

        embed = discord.Embed(
            title="🛑 Đã kết thúc ván đoán từ",
            description=("Tin nhắn này sẽ tự xoá sau 15 giây." if is_owner else "Ván của bạn đã kết thúc.") + word_text,
            color=discord.Color.dark_grey(),
        )

        if is_owner:
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)

            async def _auto_delete():
                await asyncio.sleep(15)
                try:
                    await interaction.delete_original_response()
                except discord.HTTPException:
                    pass
            asyncio.create_task(_auto_delete())
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

def _build_wordle_embed(
    user: discord.User,
    guesses: List[Dict[str, Any]],
    guesses_left: int,
    finished_text: Optional[str] = None
) -> discord.Embed:
    lines = []
    emoji_map = {"correct": "🟩", "present": "🟨", "absent": "⬜"}
    
    for g in guesses:
        row = "".join(emoji_map[r] for r in g["result"])
        lines.append(f"`{g['word']}`  {row}")

    description = "\n".join(lines) if lines else "_Chưa có lượt đoán nào._"
    description += f"\n\nCòn lại: **{guesses_left}** lượt đoán."
    
    if finished_text:
        description += f"\n\n{finished_text}"

    embed = discord.Embed(
        title=f"🔤 Ván đoán từ của {user.display_name}",
        description=description,
        color=discord.Color.blurple() if not finished_text else discord.Color.dark_grey(),
    )
    return embed

class WordleGuessModal(discord.ui.Modal, title="Đoán từ Wordle"):
    guess_input = discord.ui.TextInput(
        label="Từ 5 chữ cái",
        placeholder="Ví dụ: APPLE",
        min_length=5,
        max_length=5,
    )

    def __init__(self, is_owner_of_message: bool):
        super().__init__()
        self.is_owner_of_message = is_owner_of_message

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guess = self.guess_input.value.strip()
        edit = self.is_owner_of_message

        if not guess.isalpha() or not guess.isascii():
            await interaction.response.send_message(
                "Chỉ được nhập chữ cái tiếng Anh (A-Z), thử lại.", ephemeral=True
            )
            return

        result = store.submit_wordle_guess(user_id, guess)

        if result["status"] == "no_game":
            await interaction.response.send_message(
                "Ván này đã kết thúc rồi.", ephemeral=True
            )
            return

        user = interaction.user
        game = store.get_active_wordle_game(user_id) or {"guesses": []}

        async def _send(embed, view=None):
            if edit:
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view or discord.utils.MISSING)

        if result["status"] == "win":
            stats_result = store.update_wordle_stats(user_id, True)
            reward = store.apply_coins_mult(user_id, config.WORDLE_WIN_REWARD, command="wordle")
            store.transaction_coins(user_id, reward)
            level_result = store.add_minigame_win_xp(user_id)
            store.track_quest_progress(user_id, "win_minigame", 1)
            store.track_quest_progress(user_id, "win_wordle", 1)

            finished_text = f"🎉 **Chính xác!** Bạn nhận **{reward} xu**!"
            if level_result["leveled_up"]:
                finished_text += f"\n🎊 **Lên cấp {level_result['new_level']}**!"

            if stats_result.get("achievement"):
                role_mappings = store.get_wordle_achievement_roles()
                role_key = stats_result["achievement"]
                role_id = role_mappings.get(role_key)

                if role_id and interaction.guild:
                    role = interaction.guild.get_role(role_id)
                    if role and role not in user.roles:
                        try:
                            await user.add_roles(role)
                            finished_text += f"\n🏆 Đạt thành tích mới! Nhận role <@&{role_id}>"
                        except discord.Forbidden:
                            pass

            store.delete_wordle_game(user_id)

            guesses_list = game.get("guesses", []) if isinstance(game, dict) else []
            embed = _build_wordle_embed(user, guesses_list, 0, finished_text)
            view = WordleView(finished=True)
            await _send(embed, view)

        elif result["status"] == "lose":
            finished_text = f"💀 Hết lượt! Từ bí mật là **`{result['word']}`**."
            store.delete_wordle_game(user_id)

            guesses_list = game.get("guesses", []) if isinstance(game, dict) else []
            embed = _build_wordle_embed(user, guesses_list, 0, finished_text)
            view = WordleView(finished=True)
            await _send(embed, view)

        else:
            guesses_list = game.get("guesses", []) if isinstance(game, dict) else []
            embed = _build_wordle_embed(user, guesses_list, result["guesses_left"])
            await _send(embed)

# Flag
def _build_flag_embed(user, game: dict, extra_text: str | None = None) -> discord.Embed:
    idx = game["current_index"]
    question = game["questions"][idx]
    mode = game["mode"]
    attempts_used = game["current_attempts"]
    attempts_left = config.FLAG_ATTEMPTS_PER_QUESTION - attempts_used

    deadline = store.parse_iso(game["current_deadline"])
    now = datetime.datetime.utcnow()
    total_seconds = config.FLAG_SECONDS_PER_QUESTION
    seconds_left = max(0, (deadline - now).total_seconds()) if deadline else total_seconds
    progress = seconds_left / total_seconds if total_seconds else 0
    bar_len = 10
    filled = round(progress * bar_len)
    time_bar = "█" * filled + "░" * (bar_len - filled)

    embed = discord.Embed(
        title=f"🚩 Đoán cờ — {user.display_name}",
        description=(
            f"**Câu {idx + 1}/{config.FLAG_QUESTIONS_PER_GAME}** — Độ khó: **{config.FLAG_MODE_NAMES[mode]}**\n"
            f"Đây là cờ của quốc gia nào?\n\n"
            f"⏱️ `{time_bar}` {int(seconds_left)}s\n"
            f"Lượt thử còn lại: **{attempts_left}/{config.FLAG_ATTEMPTS_PER_QUESTION}**\n"
            f"Đúng đến hiện tại: **{game['correct_count']}/{config.FLAG_QUESTIONS_PER_GAME}**"
        ),
        color=discord.Color.blue(),
    )
    embed.set_image(url=f"https://flagcdn.com/w320/{question['iso_code']}.png")
    if extra_text:
        embed.add_field(name="Kết quả", value=extra_text, inline=False)
    embed.set_footer(text=f"Mỗi câu đúng: {config.FLAG_MODE_REWARD_PER_QUESTION[mode]} xu")
    return embed

def _build_flag_finished_embed(user, mode: str, correct_count: int, streak_achieved: bool) -> discord.Embed:
    total_reward = correct_count * config.FLAG_MODE_REWARD_PER_QUESTION[mode]
    embed = discord.Embed(
        title=f"🏁 Kết thúc ván đoán cờ — {user.display_name}",
        description=(
            f"Độ khó: **{config.FLAG_MODE_NAMES[mode]}**\n"
            f"Kết quả: **{correct_count}/{config.FLAG_QUESTIONS_PER_GAME}** câu đúng\n"
            f"Tổng nhận: **{total_reward} xu**"
        ),
        color=discord.Color.green() if correct_count >= 3 else discord.Color.dark_grey(),
    )
    if streak_achieved:
        embed.add_field(
            name="🏆 Thành tích mới!",
            value=f"Đạt {config.FLAG_STREAK_REQUIRED} câu đúng trong {config.FLAG_STREAK_WINDOW_GAMES} ván liên tiếp (chế độ trung bình trở lên)!\nNhận role <@&{config.FLAG_STREAK_ROLE_ID}>",
            inline=False,
        )
    return embed

class FlagModeDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=config.FLAG_MODE_NAMES[m], value=m,
                                  description=f"{config.FLAG_MODE_REWARD_PER_QUESTION[m]} xu/câu đúng")
            for m in config.FLAG_MODE_ORDER
        ]
        super().__init__(placeholder="Chọn độ khó...", options=options)

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        is_owner = bool(interaction.message and interaction.message.interaction_metadata and interaction.message.interaction_metadata.user.id == user_id)

        if store.get_active_flag_game(user_id):
            await interaction.response.send_message("Bạn đang có ván đoán cờ chưa kết thúc.", ephemeral=True)
            return

        if not store.consume_flag_play(user_id):
            await interaction.response.send_message(
                f"Bạn đã dùng hết {config.FLAG_DAILY_LIMIT} lượt `/flag` hôm nay, hãy quay lại vào ngày mai.",
                ephemeral=True,
            )
            return

        mode = self.values[0]
        game = store.create_flag_game(user_id, mode)
        embed = _build_flag_embed(interaction.user, game)
        view = FlagView()
        if is_owner:
            await interaction.response.edit_message(content=None, embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)

class FlagView(discord.ui.View):
    def __init__(self, finished: bool = False):
        super().__init__(timeout=None)
        self.guess_button.custom_id = "flag:guess"
        self.end_button.custom_id = "flag:end"
        if finished:
            for item in self.children:
                item.disabled = True

    @discord.ui.button(label="🚩 Đoán", style=discord.ButtonStyle.primary, custom_id="flag:guess:template")
    async def guess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        is_owner = bool(interaction.message and interaction.message.interaction_metadata and interaction.message.interaction_metadata.user.id == user_id)

        expired = store.check_and_expire_flag_question(user_id)
        if expired:
            await self._render_after_expire_or_answer(interaction, expired, is_owner)
            return

        game = store.get_active_flag_game(user_id)
        if game is None:
            await interaction.response.send_message(
                "Bạn chưa có ván đoán cờ nào — dùng lệnh `/flag` để bắt đầu.", ephemeral=True
            )
            return

        await interaction.response.send_modal(FlagGuessModal(is_owner))

    @discord.ui.button(label="🛑 Kết thúc", style=discord.ButtonStyle.danger, custom_id="flag:end:template")
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        is_owner = bool(interaction.message and interaction.message.interaction_metadata and interaction.message.interaction_metadata.user.id == user_id)

        store.delete_flag_game(user_id)
        embed = discord.Embed(
            title="🛑 Đã kết thúc ván đoán cờ",
            description="Tin nhắn này sẽ tự xoá sau 15 giây." if is_owner else "Ván của bạn đã kết thúc.",
            color=discord.Color.dark_grey(),
        )

        if is_owner:
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)

            async def _auto_delete():
                await asyncio.sleep(15)
                try:
                    await interaction.delete_original_response()
                except discord.HTTPException:
                    pass
            asyncio.create_task(_auto_delete())
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _render_after_expire_or_answer(self, interaction: discord.Interaction, result: dict, is_owner: bool):
        user = interaction.user
        if result["is_last_question"]:
            embed = _build_flag_finished_embed(user, result["mode"], result["correct_count"], False)
            view = FlagView(finished=True)
            if is_owner:
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view)
        else:
            game = store.get_active_flag_game(interaction.user.id)
            embed = _build_flag_embed(user, game, extra_text=f"⏱️ Hết giờ! Đáp án là **{result['country']}**.")
            if is_owner:
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.send_message(embed=embed, view=FlagView())

class FlagGuessModal(discord.ui.Modal, title="Đoán tên quốc gia"):
    guess_input = discord.ui.TextInput(
        label="Tên quốc gia",
        placeholder="Ví dụ: Việt Nam",
        max_length=50,
    )

    def __init__(self, is_owner_of_message: bool):
        super().__init__()
        self.is_owner_of_message = is_owner_of_message

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        edit = self.is_owner_of_message
        guess = self.guess_input.value.strip()
        result = store.submit_flag_guess(user_id, guess)

        if result["status"] == "no_game":
            await interaction.response.send_message("Ván này đã kết thúc rồi.", ephemeral=True)
            return

        user = interaction.user

        async def _send(embed, view=None):
            if edit:
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view or discord.utils.MISSING)

        if result["status"] == "correct":
            store.transaction_coins(user_id, result["reward"])
            await _grant_win_xp_and_announce(interaction.channel, user)

        if result["status"] in ("correct", "wrong_final") and result["is_last_question"]:
            game_check = store.get_active_flag_game(user_id)
            if game_check is None:  # ván đã hết
                embed = _build_flag_finished_embed(user, result["mode"], result["correct_count"], result["streak_achieved"])
                view = FlagView(finished=True)

                if result["streak_achieved"] and interaction.guild:
                    role = interaction.guild.get_role(config.FLAG_STREAK_ROLE_ID)
                    if role and role not in user.roles:
                        try:
                            await user.add_roles(role)
                        except discord.Forbidden:
                            pass

                await _send(embed, view)
                return

        game = store.get_active_flag_game(user_id)
        if result["status"] == "correct":
            extra = f"✅ Chính xác! **{result['country']}** — nhận **{result['reward']} xu**."
        elif result["status"] == "wrong_retry":
            extra = f"❌ Sai rồi, còn **{result['attempts_left']}** lượt thử."
        else:  # wrong_final
            extra = f"❌ Hết lượt! Đáp án là **{result['country']}**."

        embed = _build_flag_embed(user, game, extra_text=extra)
        await _send(embed, FlagView())

async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))