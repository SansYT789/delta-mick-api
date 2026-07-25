import discord
from discord import app_commands
from discord.ext import commands

MAX_CLEAR_AMOUNT = 2000  # trần an toàn — tránh treo bot / rate-limit gắt khi ai đó gõ số quá lớn

class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Xoá tin nhắn gần nhất trong kênh (tuỳ chọn lọc theo user)")
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
