import asyncio
import datetime

import discord
from discord import app_commands
from discord.ext import commands

import economy_store
import farm_store

def _fmt_td(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m}p"
    if m:
        return f"{m}p{s}s"
    return f"{s}s"

class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------- /work ----------------
    @app_commands.command(name="work", description="Đi làm tại 1 công ty để nhận mango")
    async def work(self, interaction: discord.Interaction):
        view = CompanyChooseView(interaction.guild.id, interaction.user.id)
        embed = discord.Embed(
            title="💼 Chọn công ty để làm việc",
            description="\n".join(
                f"• **{cfg['name']}**" for cfg in economy_store.COMPANIES.values()
            ),
            color=discord.Color.dark_blue(),
        )
        await interaction.response.send_message(embed=embed, view=view)

    # ---------------- /lixi ----------------
    @app_commands.command(name="lixi", description="Lì xì mango cho mọi người trong kênh")
    @app_commands.describe(amount="Tổng số mango muốn lì xì")
    async def lixi(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1]):
        ok, msg, envelope_id = economy_store.create_lixi(
            interaction.guild.id, interaction.channel.id, interaction.user.id, amount
        )
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed = discord.Embed(
            title="🧧 Lì xì mango!",
            description=(
                f"{interaction.user.mention} vừa lì xì **{amount} 🥭**!\n"
                f"Bấm nút bên dưới để nhận — mỗi người chỉ nhận được 1 lần.\n"
                f"Lì xì tự đóng sau **{economy_store.LIXI_DURATION_MIN} phút** hoặc khi hết."
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(text=f"ID lì xì: {envelope_id}")

        view = LixiClaimView(interaction.guild.id, envelope_id)
        await interaction.response.send_message(embed=embed, view=view)

        async def _auto_expire():
            await asyncio.sleep(economy_store.LIXI_DURATION_MIN * 60 + 2)
            refund = economy_store.refund_expired_lixi(interaction.guild.id, envelope_id)
            view.stop()
            try:
                for item in view.children:
                    item.disabled = True
                content_suffix = f"\n\n🔒 Lì xì đã đóng." + (f" Hoàn lại {refund} 🥭 cho người tạo." if refund > 0 else "")
                embed.description += content_suffix
                await interaction.edit_original_response(embed=embed, view=view)
            except discord.HTTPException:
                pass

        asyncio.create_task(_auto_expire())

    # ---------------- /quydoi ----------------
    @app_commands.command(name="quydoi", description="Quy đổi giữa mango và mango+")
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
        guild_id = interaction.guild.id
        user_id = interaction.user.id

        if direction.value == "to_plus":
            ok, msg, gained = economy_store.convert_mango_to_plus(guild_id, user_id, amount)
            if not ok:
                await interaction.response.send_message(msg, ephemeral=True)
                return
            await interaction.response.send_message(
                f"✅ Đã đổi **{amount} 🥭** thành **{gained} 🥭+** "
                f"(tỉ lệ 1 mango = {economy_store.MANGO_TO_PLUS_RATE} mango+)."
            )
        else:
            ok, msg, gained = economy_store.convert_plus_to_mango(guild_id, user_id, amount)
            if not ok:
                await interaction.response.send_message(msg, ephemeral=True)
                return
            await interaction.response.send_message(
                f"✅ Đã đổi **{amount} 🥭+** thành **{gained} 🥭** "
                f"(tỉ lệ 1 mango+ = {economy_store.PLUS_TO_MANGO_RATE} mango, đã trừ phí chuyển đổi)."
            )

    # ---------------- /bill ----------------
    @app_commands.command(name="bill", description="Xem danh sách vật phẩm có thể mua ở /shop")
    async def bill(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🧾 Bảng giá /shop", color=discord.Color.dark_gold())
        embed.add_field(
            name="🌾 Nông trại",
            value=(
                "Hạt giống, bình tưới, dụng cụ, sprinkler — xem chi tiết đầy đủ qua `/shop`."
            ),
            inline=False,
        )
        embed.add_field(
            name="♟️ Vật phẩm hỗ trợ cờ vua & game",
            value=(
                "• Quả óc chó — +30% IQ bot cờ vua — 130🥭\n"
                "• Trí tuệ nhân tạo — bot cờ vua lên 1500 elo — 500🥭\n"
                "• Mango mustard — +67 mango — 100🥭\n"
                "• Delta mick — +500 mango — 500 elo\n"
                "• Mua tài — +150 elo — 30🥭\n"
                "• Giá trị trí óc — +10 elo — 5🥭\n"
                "• Gợi ý cờ vua — +1 gợi ý nước đi — 200🥭\n"
                "• Tăng giới hạn game — +1 lượt /wordle, /flag — (giá xem `/shop`)\n"
                "• Túi tiền — +300 mango — 250 elo\n"
                "• Khiên Thời Gian — +5p thời gian đánh cờ — 800🥭\n"
                "• Thời Gian Vàng — x2 mango 1 ngày — 1200 elo"
            ),
            inline=False,
        )
        embed.set_footer(text="Giá có thể thay đổi theo cân bằng game. Dùng /shop để mua trực tiếp.")
        await interaction.response.send_message(embed=embed)

# ==================== /work UI ====================
class CompanyChooseView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        self.add_item(CompanyDropdown(guild_id, user_id))

class CompanyDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int):
        self.guild_id = guild_id
        self.user_id = user_id
        options = [
            discord.SelectOption(label=cfg["name"], value=cid)
            for cid, cfg in economy_store.COMPANIES.items()
        ]
        super().__init__(placeholder="Chọn công ty...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        company_id = self.values[0]

        cooldown = economy_store.get_work_cooldown_remaining_sec(self.user_id)
        if cooldown > 0:
            await interaction.response.edit_message(
                content=f"⏱️ Bạn cần chờ **{_fmt_td(cooldown)}** nữa mới đi làm tiếp được.",
                embed=None, view=None,
            )
            return

        penalty = economy_store.get_company_penalty_remaining_sec(self.user_id, company_id)
        if penalty > 0:
            await interaction.response.edit_message(
                content=f"🚫 Công ty này đang tạm ngừng nhận bạn, còn **{_fmt_td(penalty)}** nữa.",
                embed=None, view=None,
            )
            return

        await interaction.response.edit_message(content="👔 Đang làm việc...", embed=None, view=None)
        await asyncio.sleep(3)

        result = economy_store.do_work(self.guild_id, self.user_id, company_id)

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
                value=f"Không nhận được lương, tạm ngừng làm tại công ty này {result['event']['penalty_hours']}h.",
                inline=False,
            )
            await interaction.edit_original_response(content=None, embed=embed)
            return

        position_name = economy_store.POSITION_NAMES[result["position_level"]]
        embed = discord.Embed(
            title=f"✅ Hoàn thành công việc tại {result['company_name']}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Lương nhận được", value=f"{result['pay']} 🥭", inline=True)
        embed.add_field(name="Chức vụ", value=position_name, inline=True)
        embed.add_field(
            name="Streak",
            value=f"{result['streak_weeks']} tuần (+{result['streak_weeks'] * economy_store.STREAK_BONUS_PER_WEEK * 100:.0f}% lương)",
            inline=True,
        )
        await interaction.edit_original_response(content=None, embed=embed)

# ==================== /lixi UI ====================
class LixiClaimView(discord.ui.View):
    def __init__(self, guild_id: int, envelope_id: str):
        super().__init__(timeout=economy_store.LIXI_DURATION_MIN * 60 + 5)
        self.guild_id = guild_id
        self.envelope_id = envelope_id

    @discord.ui.button(label="🧧 Nhận lì xì", style=discord.ButtonStyle.danger)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok, msg, amount = economy_store.claim_lixi(self.guild_id, self.envelope_id, interaction.user.id)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        await interaction.response.send_message(f"🎉 Bạn đã nhận được **{amount} 🥭** từ lì xì!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))