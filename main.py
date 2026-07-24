import os
import threading

from flask import Flask
import discord
from discord.ext import commands

from firebase_init import init_firebase

# ---------- Web server (giữ Render service alive) ----------
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is online!"


def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


threading.Thread(target=run_web, daemon=True).start()

# ---------- Firebase ----------
init_firebase()

# ---------- Discord bot ----------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


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
        await bot.load_extension("tornado_cog")
        await bot.start(os.environ["TOKEN"])


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())