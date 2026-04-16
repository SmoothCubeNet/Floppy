import os
import discord
from discord.ext import tasks
from itertools import cycle
from dotenv import load_dotenv

# Config
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
        print(f"✅ {self.user} is online")

if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        exit("Error: TOKEN missing from .env")
        
    intents = discord.Intents.default()
    intents.message_content = True
    
    Floppy(intents=intents).run(token)
