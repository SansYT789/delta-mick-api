import os
import threading

from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

from firebase_init import init_firebase
import store

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is online!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_web, daemon=True).start()

init_firebase()

intents = discord.Intents.default()
intents.message_content = True

class LockAwareCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.command is None:
            return True
        if store.is_owner(interaction.user.id):
            return True
        command_name = interaction.command.name
        if store.is_locked(command_name):
            await interaction.response.send_message(f"🔧 Lệnh `/{command_name}` đang bảo trì, vui lòng quay lại sau.")
            return False
        return True

bot = commands.Bot(command_prefix="!", intents=intents, tree_cls=LockAwareCommandTree)

@bot.check
async def _global_prefix_lock_check(ctx: commands.Context) -> bool:
    if ctx.command is None:
        return True
    if store.is_owner(ctx.author.id):
        return True
    command_name = ctx.command.name
    if store.is_locked(command_name):
        await ctx.send(f"🔧 Lệnh `{command_name}` đang bảo trì, vui lòng quay lại sau.")
        return False
    return True

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Slash command sync failed: {e}")

async def main():
    async with bot:
        await bot.load_extension("games")
        await bot.load_extension("games1")
        await bot.load_extension("games2")
        await bot.start(os.environ["TOKEN"])

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())