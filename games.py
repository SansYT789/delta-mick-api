import time
import asyncio
import datetime

import discord
from discord import app_commands
from discord.ext import commands

import store

import farm_shop
import farm_views

MAX_CLEAR_AMOUNT = 2000  # trần an toàn
BOT_OWNER_ID = 985004175110848512  # chủ bot user id

BOT_VERSION = "1.1.0"
BOT_DESCRIPTION = "Delta Mick Entertainment đa năng các hoạt động lệnh giải trí: nông trại, kinh tế, mini-game và tiện ích."

def _fmt_td(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m}p"
    if m:
        return f"{m}p{s}s"
    return f"{s}s"

class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Farm
    @app_commands.command(name="shop", description="Mở cửa hàng Delta Mick")
    async def shop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed, view = farm_shop.build_farm_shop_embed_and_view(interaction.guild.id, interaction.user.id)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="farm", description="Mở nông trại của bạn")
    async def farm(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed, view, file = farm_views.build_farm_embed_and_view(interaction.guild.id, interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, file=file)

    @app_commands.command(name="inventory", description="Xem kho nông sản và bán trái")
    async def inventory(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed, view = farm_shop.build_sell_view_and_embed(interaction.guild.id, interaction.user.id)
        await interaction.followup.send(embed=embed, view=view)

    # Mod
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
        user: discord.Member | None = None,
    ):
        perms = interaction.channel.permissions_for(interaction.guild.me)
        if not perms.manage_messages:
            await interaction.response.send_message(
                "Bot thiếu quyền **Manage Messages** trong kênh này.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        def check(msg: discord.Message) -> bool:
            if user is not None:
                return msg.author.id == user.id
            return True

        try:
            deleted = await interaction.channel.purge(limit=amount, check=check)
        except discord.Forbidden:
            await interaction.followup.send("Bot không có quyền xoá tin nhắn ở đây.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"Lỗi khi xoá tin nhắn: {e}", ephemeral=True)
            return

        target_text = f" của {user.mention}" if user else ""
        await interaction.followup.send(f"✅ Đã xoá **{len(deleted)}** tin nhắn{target_text}.", delete_after=5)

    @clear.error
    async def clear_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "Bạn cần quyền **Manage Messages** để dùng lệnh này.", ephemeral=True
            )
        else:
            await interaction.response.send_message(f"Lỗi: {error}", ephemeral=True)

    # Chủ bot
    @app_commands.command(name="setmango", description="Chỉnh mango cho người dùng (chỉ chủ bot)")
    @app_commands.describe(
        amount="Số lượng mango cần chỉnh (số nguyên dương)",
        user="Chọn người dùng",
    )
    async def setmango(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 0],
        user: discord.Member | None = None,
    ):
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )
            return

        user = user or interaction.user
        store.set_mango(user.id, amount)

        await interaction.response.send_message(f"✅ Đã chỉnh Mango của {user.mention} thành **{amount}** 🥭", ephemeral=True)

    @app_commands.command(name="custom-status", description="Đổi trạng thái hiển thị của bot (chỉ chủ bot)")
    @app_commands.describe(
        status="Trạng thái online của bot",
        activity_type="Loại hoạt động hiển thị (bỏ trống nếu chỉ muốn đổi status)",
        text="Nội dung hiển thị sau loại hoạt động (ví dụ: 'nông trại' -> 'Đang chơi nông trại')",
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
        activity_type: app_commands.Choice[str] = None,
        text: str = None,
    ):
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("Bạn không có quyền dùng lệnh này.", ephemeral=True)
            return

        discord_status = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }[status.value]

        activity = None
        if activity_type and text:
            if activity_type.value == "playing":
                activity = discord.Game(name=text)
            elif activity_type.value == "watching":
                activity = discord.Activity(type=discord.ActivityType.watching, name=text)
            elif activity_type.value == "listening":
                activity = discord.Activity(type=discord.ActivityType.listening, name=text)
            elif activity_type.value == "streaming":
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
        await interaction.response.send_message(f"✅ Đã cập nhật trạng thái bot.\n{summary}", ephemeral=True)

    # Utility
    @app_commands.command(name="help", description="Xem danh sách lệnh của bot")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer()
        pages = _build_help_pages(self.bot, interaction.user.id)
        if not pages:
            await interaction.followup.send("Hiện chưa có lệnh nào khả dụng.")
            return
        view = HelpView(pages)
        await interaction.followup.send(embed=pages[0], view=view)

    @app_commands.command(name="mango", description="Xem số mango của bạn hoặc người khác")
    @app_commands.describe(user="Người muốn xem (bỏ trống = xem của bạn)")
    async def mango(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        amount = store.get_mango(target.id)
        embed = discord.Embed(
            title=f"🥭 Mango của {target.display_name}",
            description=f"**{amount}** mango",
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
        log = store.get_purchase_log(interaction.user.id, limit=20)

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
        summary = []
        if total_mango:
            summary.append(f"{total_mango} 🥭")
        if total_plus:
            summary.append(f"{total_plus} 🥭+")
        embed.set_footer(text=f"Tổng {len(log)} giao dịch gần nhất — đã chi: {' + '.join(summary) if summary else '0'}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="work", description="Đi làm tại 1 công ty để nhận tiền thưởng")
    async def work(self, interaction: discord.Interaction):
        view = CompanyChooseView(interaction.user.id)
        embed = discord.Embed(
            title="💼 Chọn công ty để làm việc",
            description="\n".join(
                f"• **{cfg['name']}**" for cfg in store.COMPANIES.values()
            ),
            color=discord.Color.dark_blue(),
        )
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="lixi", description="Lì xì mango hoặc mango+ cho mọi người trong kênh")
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
        currency: app_commands.Choice[str] = None,
    ):
        currency_value = currency.value if currency else "mango"
        currency_label = "🥭" if currency_value == "mango" else "🥭+"

        ok, msg, envelope_id = store.create_lixi(
            interaction.guild.id, interaction.channel.id, interaction.user.id, amount, currency_value
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
            refund = store.refund_expired_lixi(envelope_id)
            view.stop()
            try:
                for item in view.children:
                    item.disabled = True
                final_embed = _build_lixi_embed(envelope_id, closed=True, refund=refund, currency_label=currency_label)
                if final_embed:
                    await interaction.edit_original_response(embed=final_embed, view=view)
            except discord.HTTPException:
                pass

        asyncio.create_task(_auto_expire())

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
        embed = discord.Embed(title="🤖 Về bot này", description=BOT_DESCRIPTION, color=discord.Color.blue())
        embed.add_field(name="Phiên bản", value=BOT_VERSION, inline=True)
        embed.add_field(name="Server đang phục vụ", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(
            name="Người dùng",
            value=str(sum(g.member_count or 0 for g in self.bot.guilds)),
            inline=True,
        )
        embed.set_footer(text=f"Chạy trên discord.py {discord.__version__}")
        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Xem ảnh đại diện của bạn hoặc người khác")
    @app_commands.describe(user="Người muốn xem (bỏ trống = xem của bạn)")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member | None = None):
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

        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="server", description="Xem thông tin máy chủ hiện tại")
    async def server(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Lệnh này chỉ dùng được trong máy chủ.", ephemeral=True)
            return

        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        boosts = guild.premium_subscription_count or 0

        embed = discord.Embed(title=f"🏰 {guild.name}", color=discord.Color.green())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Chủ server", value=f"{guild.owner.mention}" if guild.owner else "Không rõ", inline=True)
        embed.add_field(name="Thành viên", value=str(guild.member_count), inline=True)
        embed.add_field(name="Ngày tạo", value=discord.utils.format_dt(guild.created_at, style="D"), inline=True)
        embed.add_field(name="Kênh chữ", value=str(text_channels), inline=True)
        embed.add_field(name="Kênh thoại", value=str(voice_channels), inline=True)
        embed.add_field(name="Vai trò", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Cấp boost", value=f"Level {guild.premium_tier} ({boosts} boost)", inline=True)
        embed.add_field(name="Emoji", value=str(len(guild.emojis)), inline=True)
        embed.set_footer(text=f"ID: {guild.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invite", description="Tạo link mời của máy chủ này")
    async def invite(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Lệnh này chỉ dùng được trong máy chủ.", ephemeral=True)
            return

        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
            await interaction.response.send_message("Không thể tạo lời mời tại kênh này.", ephemeral=True)
            return

        perms = channel.permissions_for(guild.me)
        if not perms.create_instant_invite:
            await interaction.response.send_message(
                "Bot thiếu quyền **Create Invite** trong kênh này.", ephemeral=True
            )
            return

        try:
            invite = await channel.create_invite(max_age=0, max_uses=0, unique=False, reason=f"Lời mời từ {interaction.user.display_name}")
        except discord.Forbidden:
            await interaction.response.send_message("Bot không có quyền tạo lời mời.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Lỗi khi tạo lời mời: {e}", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📨 Lời mời vào {guild.name}",
            description=f"{invite.url}\n\nLời mời này không giới hạn thời gian và số lượt dùng.",
            color=discord.Color.blurple(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rank", description="Xem top 10 người dùng có nhiều mango nhất")
    async def rank(self, interaction: discord.Interaction):
        await interaction.response.defer()

        users_ref_data = store.get_all_mango_data()

        entries = []
        for uid_str, udata in users_ref_data.items():
            if not isinstance(udata, dict):
                continue
            mango = udata.get("mango")
            if isinstance(mango, (int, float)) and mango > 0:
                entries.append((int(uid_str), int(mango)))

        entries.sort(key=lambda x: x[1], reverse=True)
        top = entries[:10]

        if not top:
            await interaction.followup.send("Chưa có ai sở hữu mango.")
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
        lines = []
        for i, (uid, amount) in enumerate(top):
            user = user_cache.get(uid)
            name = user.display_name if user else f"Người dùng {uid}"
            amount_str = f"{amount:,}".replace(",", ".")

            rank_icon = medal[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{rank_icon} **{name}** — {amount_str} 🥭")

        user_rank = None
        user_amount = None
        for rank, (uid, amount) in enumerate(entries, start=1):
            if uid == interaction.user.id:
                user_rank = rank
                user_amount = amount
                break

        embed = discord.Embed(
            title="🏆 Bảng xếp hạng Top 10 Mango", 
            description="\n".join(lines) if lines else "Không có dữ liệu",
            color=discord.Color.gold()
        )
        
        if user_rank is not None and user_amount is not None:
            amount_str = f"{user_amount:,}".replace(",", ".")
            embed.set_footer(text=f"📍 Hạng của bạn: #{user_rank} • {amount_str} 🥭")
        else:
            embed.set_footer(text="Mango được tính chung cho toàn bộ máy chủ.")

        await interaction.followup.send(embed=embed)

    # Lock
    @app_commands.command(name="lock", description="Khoá 1 lệnh (chỉ chủ bot)")
    @app_commands.describe(command_name="Tên lệnh cần khoá")
    async def lock(self, interaction: discord.Interaction, command_name: str):
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("Bạn không có quyền dùng lệnh này.", ephemeral=True)
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

    @app_commands.command(name="unlock", description="Mở khoá 1 lệnh đã khoá (chỉ chủ bot)")
    @app_commands.describe(command_name="Tên lệnh cần mở khoá")
    async def unlock(self, interaction: discord.Interaction, command_name: str):
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("Bạn không có quyền dùng lệnh này.", ephemeral=True)
            return

        command_name = command_name.lstrip("/").strip().lower()
        store.unlock_command(command_name)
        await interaction.response.send_message(f"🔓 Đã mở khoá lệnh `/{command_name}`.", ephemeral=True)

    @app_commands.command(name="locklist", description="Xem danh sách lệnh đang bị khoá (chỉ chủ bot)")
    async def locklist(self, interaction: discord.Interaction):
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("Bạn không có quyền dùng lệnh này.", ephemeral=True)
            return

        locked = store.get_locked_commands()
        active_locked = [name for name, is_locked in locked.items() if is_locked]
        if not active_locked:
            await interaction.response.send_message("Không có lệnh nào đang bị khoá.", ephemeral=True)
            return

        lines = "\n".join(f"🔒 `/{name}`" for name in active_locked)
        await interaction.response.send_message(f"**Lệnh đang bảo trì:**\n{lines}", ephemeral=True)

# Work UI
class CompanyChooseView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.add_item(CompanyDropdown(user_id))

class CompanyDropdown(discord.ui.Select):
    def __init__(self, user_id: int):
        self.user_id = user_id
        options = [
            discord.SelectOption(label=cfg["name"], value=cid)
            for cid, cfg in store.COMPANIES.items()
        ]
        super().__init__(placeholder="Chọn công ty...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        company_id = self.values[0]

        cooldown = store.get_work_cooldown_remaining_sec(self.user_id)
        if cooldown > 0:
            await interaction.response.edit_message(
                content=f"⏱️ Bạn cần chờ **{_fmt_td(cooldown)}** nữa mới đi làm tiếp được.",
                embed=None, view=None,
            )
            return

        penalty = store.get_company_penalty_remaining_sec(self.user_id, company_id)
        if penalty > 0:
            await interaction.response.edit_message(
                content=f"🚫 Công ty này đang tạm ngừng nhận bạn, còn **{_fmt_td(penalty)}** nữa.",
                embed=None, view=None,
            )
            return

        await interaction.response.edit_message(content="👔 Đang làm việc...", embed=None, view=None)
        await asyncio.sleep(3)

        result = store.do_work(self.user_id, company_id)

        if not result.get("ok"):
            await interaction.edit_original_response(content=f"❌ {result.get('message', 'Có lỗi xảy ra.')}")
            return

        if result["event"]:
            embed = discord.Embed(
                title=f"⚠️ Sự cố tại {result['company_name']}",
                description=result["event"]["text"],
                color=discord.Color.dark_red(),
            )
            embed.add_field(
                name="Hậu quả",
                value=f"Không nhận được lương, tạm ngừng làm việc tại công ty này {result['event']['penalty_hours']}h.",
                inline=False,
            )
            await interaction.edit_original_response(content=None, embed=embed)
            return

        position_name = store.POSITION_NAMES[result["position_level"]]
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

# Lixi
def _build_lixi_embed(envelope_id: str, closed: bool = False, refund: int = 0, currency_label: str = "🥭") -> discord.Embed | None:
    envelope = store.get_lixi(envelope_id)
    if envelope is None:
        return None

    creator_mention = f"<@{envelope['creator_id']}>"
    amount = envelope["total_amount"]
    expires_unix = int(store.parse_iso(envelope["expires_at"]).timestamp())

    lines_status = (
        f"{creator_mention} vừa lì xì **{amount} {currency_label}**!\n"
        f"Bấm nút bên dưới để nhận — mỗi người chỉ nhận được 1 lần.\n"
    )
    if closed:
        lines_status += "🔒 Lì xì đã đóng."
    else:
        lines_status += f"Lì xì tự động đóng lúc <t:{expires_unix}:t> (<t:{expires_unix}:R>)."

    embed = discord.Embed(title="🧧 Lì xì!", description=lines_status, color=discord.Color.red() if not closed else discord.Color.dark_grey())

    claimed_order = envelope.get("claimed_order", [])
    claimed_by = envelope.get("claimed_by", {})
    if claimed_order:
        lines = [f"<@{uid}> — **{claimed_by.get(uid, 0)} {currency_label}**" for uid in claimed_order]
        embed.add_field(name="🎁 Người đã nhận", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="🎁 Người đã nhận", value="_Chưa có ai nhận._", inline=False)
    return embed

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
        await interaction.response.send_message(f"🎉 Bạn đã nhận được **{amount} {currency_label}** từ lì xì!", ephemeral=True)

        updated_embed = _build_lixi_embed(self.envelope_id, currency_label=currency_label)
        if updated_embed:
            try:
                await interaction.message.edit(embed=updated_embed)
            except discord.HTTPException:
                pass


_COG_DISPLAY_NAMES = {
    "GamesCog": "🌾 Nông trại, Kinh tế & Tiện ích",
    "WikiCog": "📖 Tra cứu",
}
_COG_ORDER = ["GamesCog", "WikiCog"]

def _build_help_pages(bot: commands.Bot, requester_id: int) -> list[discord.Embed]:
    is_owner = store.is_owner(requester_id)
    all_commands = bot.tree.get_commands()
    locked_commands = store.get_locked_commands() if not is_owner else {}

    grouped: dict[str, list] = {}
    for cmd in all_commands:
        if not is_owner and locked_commands.get(cmd.name, False):
            continue
        cog_name = getattr(cmd.binding, "__class__", None)
        cog_name = cog_name.__name__ if cog_name else "Khác"
        grouped.setdefault(cog_name, []).append(cmd)

    ordered_cog_names = [c for c in _COG_ORDER if c in grouped] + [c for c in grouped if c not in _COG_ORDER]

    pages = []
    for cog_name in ordered_cog_names:
        commands_in_cog = sorted(grouped[cog_name], key=lambda c: c.name)
        display_name = _COG_DISPLAY_NAMES.get(cog_name, cog_name)
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

class HelpView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=200)
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


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))