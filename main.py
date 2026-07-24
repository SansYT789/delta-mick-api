import os
import threading

from flask import Flask
import discord

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is online!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_web, daemon=True).start()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

client.run(os.environ["TOKEN"])