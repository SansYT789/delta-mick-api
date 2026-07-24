import discord
from discord import app_commands
from discord.ext import commands

import views


class TornadoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="tornado", description="Mở trung tâm săn bão")
    async def tornado(self, interaction: discord.Interaction):
        embed = views.build_main_menu_embed(interaction.guild.id, interaction.user.id)
        view = views.MainMenuView(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(TornadoCog(bot))
