import time
import asyncio
import datetime
import random
from typing import Optional, Dict, List, Any

import discord
from discord import app_commands
from discord.ext import commands

import store
import config

# Constants
MAX_CLEAR_AMOUNT = 2000
BOT_OWNER_ID = 985004175110848512
BOT_VERSION = "1.1.5"
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

def _is_owner(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID

class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._setup_owners()
    
    def _setup_owners(self):
        pass

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
                "Bot thiếu quyền **Manage Messages** trong kênh này.", ephemeral=True
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
                "Bạn cần quyền **Manage Messages** để dùng lệnh này.", ephemeral=True
            )
        else:
            await interaction.response.send_message(f"Lỗi: {error}", ephemeral=True)

    # ==================== OWNER COMMANDS ====================
    @app_commands.command(name="setmango", description="Chỉnh mango cho người dùng (chỉ chủ bot)")
    @app_commands.describe(
        amount="Số lượng mango cần chỉnh (số nguyên dương)",
        user="Chọn người dùng",
    )
    async def setmango(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 0],
        user: Optional[discord.Member] = None,
    ):
        if not _is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        user = user or interaction.user
        store.set_mango(user.id, amount)

        await interaction.response.send_message(
            f"✅ Đã chỉnh Mango của {user.mention} thành **{amount}** 🥭",
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
        if not _is_owner(interaction.user.id):
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
        if not _is_owner(interaction.user.id):
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
        if not _is_owner(interaction.user.id):
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
        if not _is_owner(interaction.user.id):
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
        if not _is_owner(interaction.user.id):
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
        if not _is_owner(interaction.user.id):
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
        elif aura <= 25:
            rank = "🥲 Farm hơi yếu."
            color = discord.Color.orange()
        elif aura <= 36:
            rank = "😋 36 thanh hoá ăn rau má"
            color = discord.Color.green()
        elif aura <= 45:
            rank = "🙂 Mới vào nghề."
            color = discord.Color.gold()
        elif aura <= 65:
            rank = "😎 Farm ổn áp."
            color = discord.Color.blue()
        elif aura <= 67:
            rank = "😱 Six seven"
            color = discord.Color.dark_grey()
        elif aura <= 69:
            rank = "😏 Nice"
            color = discord.Color.red()
        elif aura <= 85:
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
                f"Bạn đã dùng hết {store.WORDLE_DAILY_LIMIT} lượt `/wordle` hôm nay, hãy quay lại vào ngày mai.",
                ephemeral=True,
            )
            return

        if not store.consume_wordle_play(interaction.user.id):
            await interaction.response.send_message(
                f"Bạn đã dùng hết {store.WORDLE_DAILY_LIMIT} lượt `/wordle` hôm nay, hãy quay lại vào ngày mai.",
                ephemeral=True,
            )
            return

        store.create_wordle_game(interaction.user.id)

        embed = _build_wordle_embed(interaction.user, [], store.WORDLE_MAX_GUESSES)
        embed.set_footer(text=f"Bạn còn {remaining - 1} lượt tạo ván đoán từ hôm nay.")
        view = WordleView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

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
    @app_commands.command(name="mango", description="Xem số mango của bạn hoặc người khác")
    @app_commands.describe(user="Người muốn xem (bỏ trống = xem của bạn)")
    async def mango(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        mango = store.get_mango(target.id)
        mango_plus = store.get_mango_plus(target.id)
        embed = discord.Embed(
            title=f"🥭 Mango của {target.display_name}",
            description=f"**{mango}** 🥭 và **{mango_plus}** 🥭+",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quydoi", description="Quy đổi giữa các loại tiền tệ")
    @app_commands.describe(
        direction="Chiều quy đổi",
        amount="Số lượng muốn đổi",
    )
    @app_commands.choices(direction=[
        app_commands.Choice(name="Mango ➜ Mango+", value="to_plus"),
        app_commands.Choice(name="Mango+ ➜ Mango", value="to_mango"),
    ])
    async def quydoi(
        self,
        interaction: discord.Interaction,
        direction: app_commands.Choice[str],
        amount: app_commands.Range[int, 1],
    ):
        user_id = interaction.user.id

        if direction.value == "to_plus":
            ok, msg, gained = store.convert_mango_to_plus(user_id, amount)
            if not ok:
                await interaction.response.send_message(msg, ephemeral=True)
                return
            await interaction.response.send_message(
                f"✅ Đã đổi **{amount} 🥭** thành **{gained} 🥭+** "
                f"(tỉ lệ 1 mango = {store.MANGO_TO_PLUS_RATE} mango+)."
            )
        else:
            ok, msg, gained = store.convert_plus_to_mango(user_id, amount)
            if not ok:
                await interaction.response.send_message(msg, ephemeral=True)
                return
            await interaction.response.send_message(
                f"✅ Đã đổi **{amount} 🥭+** thành **{gained} 🥭** "
                f"(tỉ lệ 1 mango+ = {store.PLUS_TO_MANGO_RATE} mango)"
            )

    @app_commands.command(name="bill", description="Xem hoá đơn — lịch sử mua sắm gần đây của bạn")
    async def bill(self, interaction: discord.Interaction):
        max_log = store.MAX_LOG_ENTRIES or 10
        log = store.get_purchase_log(interaction.user.id, limit=max_log)

        if not log:
            await interaction.response.send_message(
                "Bạn chưa có giao dịch mua sắm nào. Dùng `/shop` để mua sắm vật phẩm.",
                ephemeral=True,
            )
            return

        lines = []
        total_mango = 0
        total_plus = 0
        
        for entry in log:
            currency_label = "🥭" if entry.get("currency") == "mango" else "🥭+"
            at = store.parse_iso(entry["at"])
            unix_ts = int(at.timestamp())
            lines.append(f"<t:{unix_ts}:R> — **{entry['label']}** — {entry['cost']} {currency_label}")
            
            if entry.get("currency") == "mango":
                total_mango += entry["cost"]
            else:
                total_plus += entry["cost"]

        embed = discord.Embed(
            title="🧾 Hoá đơn mua sắm",
            description="\n".join(lines),
            color=discord.Color.dark_gold(),
        )
        
        summary_parts = []
        if total_mango:
            summary_parts.append(f"{total_mango} 🥭")
        if total_plus:
            summary_parts.append(f"{total_plus} 🥭+")
        
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
            name="⏱️ Cooldown",
            value=f"Còn `{_fmt_td(cooldown)}`" if cooldown > 0 else "`Sẵn sàng`",
            inline=True
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lixi", description="Lì xì mango cho mọi người trong kênh")
    @app_commands.describe(
        amount="Tổng số lượng muốn lì xì",
        currency="Loại tiền tệ để lì xì",
    )
    @app_commands.choices(currency=[
        app_commands.Choice(name="Mango 🥭", value="mango"),
        app_commands.Choice(name="Mango+ 🥭+", value="mango_plus"),
    ])
    async def lixi(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1],
        currency: Optional[app_commands.Choice[str]] = None,
    ):
        currency_value = currency.value if currency else "mango"
        currency_label = "🥭" if currency_value == "mango" else "🥭+"

        ok, msg, envelope_id = store.create_lixi(
            interaction.guild.id, interaction.channel.id, 
            interaction.user.id, amount, currency_value
        )
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=store.LIXI_DURATION_MIN)
        expires_unix = int(expires_at.timestamp())

        embed = discord.Embed(
            title="🧧 Lì xì!",
            description=(
                f"{interaction.user.mention} vừa lì xì **{amount} {currency_label}**!\n"
                f"Bấm nút bên dưới để nhận — mỗi người chỉ nhận được 1 lần.\n"
                f"Lì xì tự đóng lúc <t:{expires_unix}:t> (<t:{expires_unix}:R>)."
            ),
            color=discord.Color.red(),
        )
        embed.add_field(name="🎁 Người đã nhận", value="_Chưa có ai nhận._", inline=False)

        view = LixiClaimView(interaction.guild.id, envelope_id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

        async def _auto_expire():
            await asyncio.sleep(store.LIXI_DURATION_MIN * 60 + 2)
            store.refund_expired_lixi(envelope_id)
            view.stop()
            try:
                await interaction.delete_original_response()
            except discord.HTTPException:
                pass

        asyncio.create_task(_auto_expire())

    @app_commands.command(name="rank", description="Xem top 10 người dùng có nhiều mango nhất")
    @app_commands.describe(type="Chọn loại mango muốn xem bảng xếp hạng")
    @app_commands.choices(type=[
        app_commands.Choice(name="Mango", value="mango"),
        app_commands.Choice(name="Mango+", value="mango_plus")
    ])
    async def rank(self, interaction: discord.Interaction, type: str = "mango"):
        await interaction.response.defer()

        users_ref_data = store.get_all_mango_data()

        entries = []
        for uid_str, udata in users_ref_data.items():
            if not isinstance(udata, dict):
                continue
            
            if type == "mango_plus":
                mango = udata.get("mango_plus")
            else:
                mango = udata.get("mango")
                
            if isinstance(mango, (int, float)) and mango > 0:
                entries.append((int(uid_str), int(mango)))

        entries.sort(key=lambda x: x[1], reverse=True)
        top = entries[:10]

        if not top:
            await interaction.followup.send("Chưa có ai sở hữu mango.")
            return

        # Cache user objects
        user_cache = {}
        for uid, _ in top:
            user = self.bot.get_user(uid)
            if user is None:
                try:
                    user = await self.bot.fetch_user(uid)
                except (discord.NotFound, discord.HTTPException):
                    user = None
            user_cache[uid] = user

        currency_txt = "🥭+" if type == "mango_plus" else "🥭"
        medal = ["🥇", "🥈", "🥉"]
        
        lines = []
        for i, (uid, amount) in enumerate(top):
            user = user_cache.get(uid)
            name = user.display_name if user else f"Người dùng {uid}"
            amount_str = f"{amount:,}".replace(",", ".")
            rank_icon = medal[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{rank_icon} **{name}** — {amount_str} {currency_txt}")

        # Find user's rank
        user_rank = None
        user_amount = None
        for rank, (uid, amount) in enumerate(entries, start=1):
            if uid == interaction.user.id:
                user_rank = rank
                user_amount = amount
                break

        title = "🏆 Bảng xếp hạng Mango+" if type == "mango_plus" else "🏆 Bảng xếp hạng Mango"

        embed = discord.Embed(
            title=title,
            description="\n".join(lines) if lines else "Không có dữ liệu",
            color=discord.Color.gold()
        )

        if user_rank is not None and user_amount is not None:
            amount_str = f"{user_amount:,}".replace(",", ".")
            embed.set_footer(text=f"📍 Hạng của bạn: #{user_rank} • {amount_str} {currency_txt}")
        else:
            embed.set_footer(text="Mango được tính chung toàn bộ máy chủ.")

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

    @app_commands.command(name="mango-mustard-day", description="Kiểm tra thông tin sự kiện Mango Mustard Day")
    async def mango_mustard_day(self, interaction: discord.Interaction):
        await interaction.response.defer()

        event_date = datetime.datetime.strptime(
            config.MANGO_MUSTARD_DAY["date"], "%Y-%m-%d"
        ).replace(tzinfo=datetime.timezone.utc)

        embed = discord.Embed(
            title="🌭 Mango Mustard Day 2026 🥭",
            description="Sự kiện đặc biệt của server!",
            color=discord.Color.gold()
        )

        # Check if event has started
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        if now >= event_date:
            embed.add_field(
                name="📅 Trạng thái",
                value="🟢 Sự kiện **đang diễn ra**!",
                inline=False
            )
            embed.add_field(
                name="🎯 Cách tham gia",
                value=f"Gõ `{config.MANGO_MUSTARD_DAY['trigger_phrase']}` trong bất kỳ kênh nào để nhận thưởng!",
                inline=False
            )
        else:
            embed.add_field(
                name="📅 Trạng thái",
                value=f"⏳ Sự kiện sẽ diễn ra vào <t:{int(event_date.timestamp())}:R>",
                inline=False
            )

        embed.add_field(
            name="🎁 Phần thưởng",
            value=f"**{config.MANGO_MUSTARD_DAY['reward_mango']} 🥭** + **{config.MANGO_MUSTARD_DAY['reward_plus']} 🥭+**",
            inline=True
        )
        embed.add_field(
            name="👤 Yêu cầu",
            value="Mỗi người chỉ được nhận **1 lần duy nhất**",
            inline=True
        )

        # Check if user has claimed
        if store.has_claimed_mango_mustard_day(interaction.user.id):
            embed.add_field(
                name="✅ Trạng thái của bạn",
                value="Bạn đã nhận thưởng thành công! 🎉",
                inline=False
            )
        else:
            embed.add_field(
                name="⏳ Trạng thái của bạn",
                value="Bạn chưa nhận thưởng! Hãy tham gia ngay!",
                inline=False
            )

        embed.set_footer(text=f"ID sự kiện: {int(event_date.timestamp())}")
        await interaction.followup.send(embed=embed)

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
                "Bot thiếu quyền **Create Invite** trong kênh này.", ephemeral=True
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

        # Mango Mustard Day
        if store.is_mango_mustard_day():
            await self._handle_mango_mustard_day(message)

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
                        title="🎉 **Thành tích Meme Master!**",
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
                        content=f"🎊 Chúc mừng {user.mention}! <@&{role_id}>",
                        embed=embed
                    )
                except discord.Forbidden:
                    print(f"Bot thiếu quyền thêm role {role_id} cho user {user.id}")
                except discord.HTTPException as e:
                    print(f"Lỗi khi thêm role: {e}")

    async def _handle_mango_mustard_day(self, message: discord.Message):
        if message.author.bot:
            return

        trigger = config.MANGO_MUSTARD_DAY["trigger_phrase"]
        user_input = " ".join(message.content.lower().split())
        trigger_lower = " ".join(trigger.lower().split())

        if user_input != trigger_lower:
            return

        if not store.is_mango_mustard_day():
            event_date = datetime.datetime.strptime(
                config.MANGO_MUSTARD_DAY["date"], "%Y-%m-%d"
            ).replace(tzinfo=datetime.timezone.utc)
        
            await message.reply(
                f"🌭 Sự kiện Ngày Mù Tạt sẽ diễn ra vào <t:{int(event_date.timestamp())}:R>! "
                f"Hãy quay lại vào ngày đó!",
                delete_after=15
            )
            return
    
        user = message.author

        if store.has_claimed_mango_mustard_day(user.id):
            await message.reply(
                "🌭 Bạn đã nhận thưởng Ngày Mù Tạt rồi! Hãy chờ năm sau 🥭",
                delete_after=10,
            )
            return

        success = store.claim_mango_mustard_day(user.id)
        if success:
            reward_mango = config.MANGO_MUSTARD_DAY["reward_mango"]
            reward_plus = config.MANGO_MUSTARD_DAY["reward_plus"]
            event_date = datetime.datetime.strptime(
                config.MANGO_MUSTARD_DAY["date"], "%Y-%m-%d"
            ).replace(tzinfo=datetime.timezone.utc)

            embed = discord.Embed(
                title="🌭 **NGÀY MÙ TẠT** 🥭",
                description=f"🎉 {user.mention} đã tham gia Ngày Mù Tạt thành công!",
                color=discord.Color.gold(),
            )
            embed.add_field(
                name="Phần thưởng nhận được",
                value=f"**{reward_mango} 🥭** và **{reward_plus} 🥭+**",
                inline=True
            )
            embed.add_field(
                name="Ngày sự kiện",
                value=f"<t:{int(event_date.timestamp())}:R>",
                inline=True
            )
            embed.set_footer(text="🎊 Chúc mừng bạn đã nhận được phần thưởng đặc biệt!")

            role_id = config.MANGO_MUSTARD_DAY["event_role_id"]
            role = message.guild.get_role(role_id)
            if role and role not in user.roles:
                try:
                    await user.add_roles(role, reason="Mango Mustard Day 2026 Participant")
                except discord.Forbidden:
                    print(f"Không thể thêm role {role_id} cho user {user.id}")

            await message.reply(
                content=f"<@&{role_id}> 🎊 Chúc mừng {user.mention}!",
                embed=embed
            )
        else:
            await message.reply(
                "❌ Có lỗi xảy ra khi nhận thưởng, vui lòng thử lại hoặc liên hệ admin.",
                delete_after=10,
            )

# ==================== UI COMPONENTS ====================
class CompanyChooseView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.add_item(CompanyDropdown(user_id))

class CompanyDropdown(discord.ui.Select):
    def __init__(self, user_id: int):
        self.user_id = user_id
        options = [
            discord.SelectOption(label=cfg["name"], value=cid)
            for cid, cfg in config.COMPANIES.items()
        ]
        super().__init__(placeholder="Chọn công ty...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Không phải phiên của bạn.", ephemeral=True
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
                        content=f"⏱️ Bạn cần chờ **{_fmt_td(sec)}** nữa mới đi làm tiếp được.",
                        embed=None, view=None,
                    )
                elif msg.startswith("company_penalty:"):
                    sec = int(msg.split(":")[1])
                    await interaction.edit_original_response(
                        content=f"🚫 Công ty này đang tạm ngừng nhận bạn, còn **{_fmt_td(sec)}** nữa.",
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

            embed = discord.Embed(
                title=f"✅ Hoàn thành công việc tại {result['company_name']}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Lương nhận được", value=f"{result['pay']} 🥭", inline=True)
            embed.add_field(name="Chức vụ", value=position_name, inline=True)
            embed.add_field(
                name="Streak",
                value=f"{result['streak_weeks']} tuần (+{result['streak_weeks'] * store.STREAK_BONUS_PER_WEEK * 100:.0f}% lương)",
                inline=True,
            )
            await interaction.edit_original_response(content=None, embed=embed)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.edit_original_response(
                content=f"❌ Đã xảy ra lỗi không mong muốn.", embed=None, view=None
            )

class LixiClaimView(discord.ui.View):
    def __init__(self, guild_id: int, envelope_id: str, creator_id: int):
        super().__init__(timeout=store.LIXI_DURATION_MIN * 60 + 5)
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
        currency_label = "🥭" if (envelope and envelope.get("currency") == "mango") else "🥭+"
        await interaction.response.send_message(
            f"🎉 Bạn đã nhận được **{amount} {currency_label}** từ lì xì!",
            ephemeral=True
        )

        updated_embed = _build_lixi_embed(self.envelope_id, currency_label=currency_label)
        if updated_embed:
            try:
                await interaction.message.edit(embed=updated_embed)
            except discord.HTTPException:
                pass

def _build_lixi_embed(envelope_id: str, currency_label: str = "🥭") -> Optional[discord.Embed]:
    envelope = store.get_lixi(envelope_id)
    if envelope is None:
        return None

    creator_mention = f"<@{envelope['creator_id']}>"
    amount = envelope["total_amount"]
    expires_unix = int(store.parse_iso(envelope["expires_at"]).timestamp())

    lines_status = (
        f"{creator_mention} vừa lì xì **{amount} {currency_label}**!\n"
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
            f"<@{uid}> — **{claimed_by.get(uid, 0)} {currency_label}**"
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
    is_owner = _is_owner(requester_id)
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
    def __init__(self, owner_id: int):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.guess_button.custom_id = f"wordle:guess:{owner_id}"
        self.end_button.custom_id = f"wordle:end:{owner_id}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Đây không phải ván đoán từ của bạn.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="🔤 Đoán từ", style=discord.ButtonStyle.primary, custom_id="wordle:guess:template")
    async def guess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = store.get_active_wordle_game(self.owner_id)
        if game is None:
            await interaction.response.send_message(
                "Ván này đã kết thúc rồi.", ephemeral=True
            )
            return
        await interaction.response.send_modal(WordleGuessModal(self.owner_id))

    @discord.ui.button(label="🛑 Kết thúc", style=discord.ButtonStyle.danger, custom_id="wordle:end:template")
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = store.get_active_wordle_game(self.owner_id)
        word_text = f"\n\nTừ bí mật là **`{game['word']}`**." if game else ""
        store.delete_wordle_game(self.owner_id)

        for item in self.children:
            item.disabled = True
            
        embed = discord.Embed(
            title="🛑 Đã kết thúc ván đoán từ",
            description=f"Tin nhắn này sẽ tự xoá sau 15 giây.{word_text}",
            color=discord.Color.dark_grey(),
        )
        await interaction.response.edit_message(embed=embed, view=self)

        async def _auto_delete():
            await asyncio.sleep(15)
            try:
                await interaction.delete_original_response()
            except discord.HTTPException:
                pass
        asyncio.create_task(_auto_delete())

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

    def __init__(self, owner_id: int):
        super().__init__()
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction):
        guess = self.guess_input.value.strip()
        
        if not guess.isalpha() or not guess.isascii():
            await interaction.response.send_message(
                "Chỉ được nhập chữ cái tiếng Anh (A-Z), thử lại.", ephemeral=True
            )
            return

        result = store.submit_wordle_guess(self.owner_id, guess)
        
        if result["status"] == "no_game":
            await interaction.response.send_message(
                "Ván này đã kết thúc rồi.", ephemeral=True
            )
            return

        user = interaction.user
        game = store.get_active_wordle_game(self.owner_id) or {"guesses": []}

        if result["status"] == "win":
            # Handle win
            stats_result = store.update_wordle_stats(self.owner_id, True)
            store.transaction_mango(self.owner_id, store.WORDLE_WIN_REWARD_MANGO)

            finished_text = f"🎉 **Chính xác!** Bạn nhận **{store.WORDLE_WIN_REWARD_MANGO} 🥭**!"

            # Check for achievement
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

            store.delete_wordle_game(self.owner_id)

            guesses_list = game.get("guesses", []) if isinstance(game, dict) else []
            embed = _build_wordle_embed(
                user,
                guesses_list,
                0,
                finished_text
            )

            view = WordleView(self.owner_id)
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(embed=embed, view=view)

        elif result["status"] == "lose":
            # Handle loss
            store.transaction_mango(
                self.owner_id,
                store.WORDLE_PARTICIPATE_REWARD_PLUS,
                use_plus=True
            )
            finished_text = (
                f"💀 Hết lượt! Từ bí mật là **`{result['word']}`**.\n"
                f"Bạn nhận **{store.WORDLE_PARTICIPATE_REWARD_PLUS} 🥭+**."
            )
            store.delete_wordle_game(self.owner_id)

            guesses_list = game.get("guesses", []) if isinstance(game, dict) else []
            embed = _build_wordle_embed(
                user,
                guesses_list,
                0,
                finished_text
            )
            
            view = WordleView(self.owner_id)
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(embed=embed, view=view)

        else:
            # Continue game
            guesses_list = game.get("guesses", []) if isinstance(game, dict) else []
            embed = _build_wordle_embed(
                user,
                guesses_list,
                result["guesses_left"]
            )
            await interaction.response.edit_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))