import discord
from discord import app_commands
from discord.ext import commands

import views as tornado_views
import farm_shop
import farm_views
import farm_store
import farm_logic
import farm_config

MAX_CLEAR_AMOUNT = 2000  # trần an toàn — tránh treo bot / rate-limit gắt khi ai đó gõ số quá lớn


class ShopModeView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=60)
        self.add_item(ShopModeDropdown(guild_id, user_id))

class ShopModeDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int):
        self.guild_id = guild_id
        self.user_id = user_id
        options = [
            discord.SelectOption(label="🚗 Xe săn bão", value="tornado", description="Mua/xem xe săn bão"),
            discord.SelectOption(label="🌾 Nông trại", value="farm", description="Hạt giống, bình tưới, sprinkler, dụng cụ"),
        ]
        super().__init__(placeholder="Chọn loại shop...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return
        if self.values[0] == "tornado":
            embed, view = tornado_views.build_car_shop(self.guild_id, self.user_id)
        else:
            embed, view = farm_shop.build_farm_shop_embed_and_view(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="shop", description="Mở shop (xe săn bão hoặc nông trại)")
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛒 Shop",
            description="Chọn loại shop bạn muốn xem bên dưới.",
            color=discord.Color.gold(),
        )
        view = ShopModeView(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="farm", description="Mở nông trại của bạn")
    async def farm(self, interaction: discord.Interaction):
        embed, view = farm_views.build_farm_embed_and_view(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="mango", description="Xem số mango của bạn hoặc người khác")
    @app_commands.describe(user="Người muốn xem (bỏ trống = xem của bạn)")
    async def mango(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        amount = farm_store.get_mango(interaction.guild.id, target.id)
        embed = discord.Embed(
            title=f"🥭 Mango của {target.display_name}",
            description=f"**{amount}** mango",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="inventory", description="Xem kho nông sản và bán trái")
    async def inventory(self, interaction: discord.Interaction):
        embed, view = farm_shop.build_sell_view_and_embed(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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
        # bot cũng cần quyền manage_messages trong kênh, không chỉ người gọi lệnh
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
        await interaction.followup.send(
            f"✅ Đã xoá **{len(deleted)}** tin nhắn{target_text}.\n"
            f"-# Lưu ý: tin nhắn cũ hơn 14 ngày không thể xoá hàng loạt (giới hạn của Discord) — "
            f"nếu số lượng xoá được ít hơn `amount` bạn nhập, có thể là do gặp tin nhắn cũ.",
            ephemeral=True,
        )

    @clear.error
    async def clear_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "Bạn cần quyền **Manage Messages** để dùng lệnh này.", ephemeral=True
            )
        else:
            await interaction.response.send_message(f"Lỗi: {error}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))