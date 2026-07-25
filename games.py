import discord
from discord import app_commands
from discord.ext import commands
import asyncio

MAX_CLEAR_AMOUNT = 2000
MAX_SPAM_AMOUNT = 50          # за сообщение на канал
DELAY_PER_MESSAGE = 0.3       # задержка между сообщениями в одном канале
DELAY_PER_CHANNEL = 1.0       # задержка между каналами

class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------------- EXISTING CLEAR --------------------
    @app_commands.command(name="clear", description="Delete recent messages (optionally filter by user)")
    @app_commands.describe(
        amount="Number of messages to delete (max 2000)",
        user="Only delete messages from this user (leave empty for all)",
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
                "Bot lacks **Manage Messages** permission in this channel.", ephemeral=True
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
            await interaction.followup.send("Bot does not have permission to delete messages here.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"Error deleting messages: {e}", ephemeral=True)
            return

        target_text = f" from {user.mention}" if user else ""
        await interaction.followup.send(
            f"✅ Deleted **{len(deleted)}** messages{target_text}.\n"
            f"-# Note: messages older than 14 days cannot be bulk‑deleted.",
            ephemeral=True,
        )

    @clear.error
    async def clear_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need **Manage Messages** permission to use this command.", ephemeral=True
            )
        else:
            await interaction.response.send_message(f"Error: {error}", ephemeral=True)

    # -------------------- FIXED SPAM - ALL CHANNELS --------------------
    @app_commands.command(name="spam", description="Send repeated messages to EVERY text channel in this server")
    @app_commands.describe(amount="Number of messages per channel (max 50)",
        content="Text to spam (default: 'spam message')",
    )
    @app_commands.checks.has_permissions(administrator=True)   # требуется админ для спама во все каналы
    async def spam(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, MAX_SPAM_AMOUNT],
        content: str | None = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("This command works only in a server.", ephemeral=True)
            return

        if content is None:
            content = "spam message"

        # Получаем все текстовые каналы сервера
        channels = [ch for ch in interaction.guild.text_channels if ch.permissions_for(interaction.guild.me).send_messages]

        if not channels:
            await interaction.response.send_message("Bot has no text channels with Send Messages permission.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        total_sent = 0
        failed_channels = 0

        for channel in channels:
            try:
                for i in range(amount):
                    await channel.send(content)
                    total_sent += 1
                    await asyncio.sleep(DELAY_PER_MESSAGE)
            except (discord.Forbidden, discord.HTTPException):
                failed_channels += 1
            # Задержка перед переходом к следующему каналу
            await asyncio.sleep(DELAY_PER_CHANNEL)

        await interaction.followup.send(
            f"✅ Spam completed.\n"
            f"• **{total_sent}** total messages sent (across {len(channels) - failed_channels} channels)\n"
            f"• **{failed_channels}** channel(s) failed (missing perms or errors)\n"
            f"• Content: `{content}`",
            ephemeral=True
        )

    @spam.error
    async def spam_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need **Administrator** permission to spam all channels.", ephemeral=True
            )
        else:
            await interaction.response.send_message(f"Error: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))