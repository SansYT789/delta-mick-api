import discord
from discord import app_commands
from discord.ext import commands

import image_config
import image_store
import image_views

class ImageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not image_store.is_collect_enabled(message.guild.id):
            return
        if not message.attachments:
            return

        for att in message.attachments:
            filename_lower = (att.filename or "").lower()
            is_image = (
                (att.content_type or "").startswith("image/")
                or filename_lower.endswith(image_config.IMAGE_EXTENSIONS)
            )
            if not is_image:
                continue

            image_id = str(att.id)  # attachment ID cố định — chống thu thập trùng
            image_store.add_image(
                guild_id=message.guild.id,
                image_id=image_id,
                url=att.url,
                submitted_by=message.author.id,
                channel_id=message.channel.id,
                message_id=message.id,
            )

    # ---------------- /enable-collect-image ----------------

    @app_commands.command(name="enable-collect-image", description="Bật/tắt thu thập ảnh tự động trong toàn server")
    @app_commands.describe(enabled="Bật (true) hoặc tắt (false)")
    @app_commands.checks.has_permissions(administrator=True)
    async def enable_collect_image(self, interaction: discord.Interaction, enabled: bool):
        image_store.set_collect_enabled(interaction.guild.id, enabled)
        status = "bật" if enabled else "tắt"
        await interaction.response.send_message(f"✅ Đã **{status}** thu thập ảnh tự động cho server này.", ephemeral=True)

    @enable_collect_image.error
    async def enable_collect_image_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Cần quyền **Administrator** để dùng lệnh này.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Lỗi: {error}", ephemeral=True)

    # ---------------- /review ----------------

    @app_commands.command(name="review", description="Duyệt các ảnh đang chờ trong hàng chờ (admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def review(self, interaction: discord.Interaction):
        embed, view = image_views.build_review_embed_and_view(interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @review.error
    async def review_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Cần quyền **Administrator** để dùng lệnh này.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Lỗi: {error}", ephemeral=True)

    # ---------------- /randomimage ----------------

    @app_commands.command(name="randomimage", description="Nhận 1 ảnh ngẫu nhiên đã được duyệt (nhận mango)")
    async def randomimage(self, interaction: discord.Interaction):
        result = image_views.use_randomimage(interaction.guild.id, interaction.user.id)
        embed = image_views.build_randomimage_embed(result)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ImageCog(bot))