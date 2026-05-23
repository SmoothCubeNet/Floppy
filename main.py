import os
import discord
from discord.ext import tasks
from itertools import cycle
from dotenv import load_dotenv
import state

load_dotenv()

STATUSES = cycle([
    "🫧 floating around", "🐟 flopping about", "🗄️ peeking at the db",
    "🔌 poking the API", "🔍 searching messages", "📋 reading logs"
])

class Floppy(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        self.cycle_status.start()

    @tasks.loop(seconds=600)
    async def cycle_status(self):
        await self.change_presence(activity=discord.CustomActivity(name=next(STATUSES)))

    @cycle_status.before_loop
    async def before_cycle(self):
        await self.wait_until_ready()

    async def on_ready(self):
        state.bot_ready = True
        print(f"✅ {self.user} is online")

    async def on_disconnect(self):
        state.bot_ready = False

def get_bot():
    token = os.getenv("TOKEN")
    if not token:
        exit("Error: TOKEN missing from .env")

    intents = discord.Intents.default()
    intents.message_content = True
    return Floppy(intents=intents), token
