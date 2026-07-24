import os
import threading

from flask import Flask
import discord
from discord.ext import commands

from firebase_init import init_firebase
from gif_tracker import add_gif

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

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    is_gif = (
        any(a.filename.lower().endswith(".gif") for a in message.attachments)
        or ".gif" in message.content.lower()
        or any(e.type == "gifv" for e in message.embeds)
    )

    if is_gif:
        await add_gif(message.author)

    await bot.process_commands(message)

bot.run(os.environ["TOKEN"])