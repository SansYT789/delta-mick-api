import time

import discord
from discord import app_commands
from discord.ext import commands

from firebase_admin import db

BOT_VERSION = "1.0.0"
BOT_DESCRIPTION = "Delta Mick Entertainment Bot đa năng: nông trại, kinh tế, mini-game và tiện ích."

class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------- /ping ----------------
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

    # ---------------- /about ----------------
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

    # ---------------- /avatar ----------------
    @app_commands.command(name="avatar", description="Xem ảnh đại diện của bạn hoặc người khác")
    @app_commands.describe(user="Người muốn xem (bỏ trống = xem của bạn)")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        avatar_asset = target.display_avatar

        embed = discord.Embed(title=f"🖼️ Avatar của {target.display_name}", color=discord.Color.random())
        embed.set_image(url=avatar_asset.url)

        view = discord.ui.View(timeout=120)
        for size in (128, 256, 512, 1024, 2048):
            view.add_item(
                discord.ui.Button(
                    label=f"{size}px",
                    style=discord.ButtonStyle.link,
                    url=avatar_asset.with_size(size).url,
                )
            )
        await interaction.response.send_message(embed=embed, view=view)

    # ---------------- /server ----------------
    @app_commands.command(name="server", description="Xem thông tin máy chủ hiện tại")
    async def server(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Lệnh này chỉ dùng được trong server.", ephemeral=True)
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

    # ---------------- /rank ----------------
    @app_commands.command(name="rank", description="Xem top 10 người dùng có nhiều mango nhất")
    async def rank(self, interaction: discord.Interaction):
        await interaction.response.defer()

        users_ref = db.reference("users")
        all_users = users_ref.get() or {}

        entries = []
        for uid_str, udata in all_users.items():
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

        medal = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, amount) in enumerate(top):
            user_obj = self.bot.get_user(uid)
            name = user_obj.display_name if user_obj else f"Người dùng {uid}"
            rank_icon = medal[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{rank_icon} **{name}** — {amount:,} 🥭")

        embed = discord.Embed(title="🏆 Bảng xếp hạng Mango (Toàn cục)", description="\n".join(lines), color=discord.Color.gold())
        embed.set_footer(text="Mango được tính chung cho toàn bộ máy chủ.")
        await interaction.followup.send(embed=embed)

    # ---------------- /invite ----------------
    @app_commands.command(name="invite", description="Tạo link mời của server này")
    async def invite(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Lệnh này chỉ dùng được trong server.", ephemeral=True)
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

    # ---------------- /help ----------------
    @app_commands.command(name="help", description="Xem danh sách lệnh của bot")
    async def help(self, interaction: discord.Interaction):
        pages = _build_help_pages()
        view = HelpView(pages)
        await interaction.response.send_message(embed=pages[0], view=view)

def _build_help_pages() -> list[discord.Embed]:
    sections = [
        ("🌾 Nông trại", [
            "`/farm` — Mở nông trại của bạn",
            "`/shop` — Cửa hàng nông trại",
            "`/inventory` — Kho nông sản, bán trái",
            "`/mango` — Xem số mango",
        ]),
        ("🛠️ Tiện ích", [
            "`/ping` — Độ trễ bot",
            "`/about` — Thông tin bot",
            "`/avatar` — Xem ảnh đại diện",
            "`/server` — Thông tin máy chủ",
            "`/rank` — Bảng xếp hạng mango",
            "`/invite` — Link mời bot",
        ]),
        ("⚙️ Quản trị", [
            "`/purge` — Xoá tin nhắn hàng loạt",
        ]),
    ]

    pages = []
    for title, lines in sections:
        embed = discord.Embed(title=f"📖 Danh sách lệnh — {title}", description="\n".join(lines), color=discord.Color.teal())
        embed.set_footer(text=f"Trang {len(pages) + 1}/{len(sections)}")
        pages.append(embed)
    return pages

class HelpView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=120)
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
    await bot.add_cog(UtilityCog(bot))