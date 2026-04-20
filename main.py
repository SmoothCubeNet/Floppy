import os
import discord
from discord.ext import tasks
from itertools import cycle
from dotenv import load_dotenv

#fuck comments B)

load_dotenv()
STATUSES = cycle([
    "🫧 floating around", "🐟 flopping about", "🗄️ peeking at the db",
    "🔌 poking the API", "🔍 searching messages", "📋 reading logs"
])

class Floppy(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sticky_channels = {} 

    async def setup_hook(self):
        for filename in os.listdir('.'):
            if filename.endswith('.txt') and filename[:-4].isdigit():
                try:
                    channel_id = int(filename[:-4])
                    with open(filename, 'r', encoding='utf-8') as f:
                        text = f.read()
                    self.sticky_channels[channel_id] = {
                        "text": text,
                        "message_id": None,
                        "needs_update": True
                    }
                except Exception:
                    pass

        self.cycle_status.start()
        self.sticky_loop.start()

    @tasks.loop(seconds=600)
    async def cycle_status(self):
        await self.change_presence(activity=discord.CustomActivity(name=next(STATUSES)))

    @cycle_status.before_loop
    async def before_cycle(self):
        await self.wait_until_ready()

    @tasks.loop(seconds=2.5)
    async def sticky_loop(self):
        for channel_id in list(self.sticky_channels.keys()):
            data = self.sticky_channels[channel_id]
            
            if not data["needs_update"]:
                continue

            channel = self.get_channel(channel_id)
            if not channel:
                continue

            try:
                if data["message_id"]:
                    old_msg = await channel.fetch_message(data["message_id"])
                    await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

            new_msg = await channel.send(data["text"])

            self.sticky_channels[channel_id]["message_id"] = new_msg.id
            self.sticky_channels[channel_id]["needs_update"] = False

    @sticky_loop.before_loop
    async def before_sticky(self):
        await self.wait_until_ready()

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.guild is None:
            return

        if message.channel.id in self.sticky_channels:
            self.sticky_channels[message.channel.id]["needs_update"] = True

        if message.content.startswith("?stick "):
            if not message.author.guild_permissions.manage_messages:
                return

            if message.channel.id in self.sticky_channels:
                await message.channel.send("Only 1 sticky message allowed per channel. Please `?unstick` first.", delete_after=5)
                await message.delete()
                return

            text = message.content[7:].strip()
            msg = await message.channel.send(text)
            
            self.sticky_channels[message.channel.id] = {
                "text": text,
                "message_id": msg.id,
                "needs_update": False 
            }
            
            with open(f"{message.channel.id}.txt", "w", encoding="utf-8") as f:
                f.write(text)
            
            await message.delete()

        elif message.content == "?unstick":
            if not message.author.guild_permissions.manage_messages:
                return

            if message.channel.id in self.sticky_channels:
                data = self.sticky_channels[message.channel.id]
                
                try:
                    if data["message_id"]:
                        old_msg = await message.channel.fetch_message(data["message_id"])
                        await old_msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
                    
                del self.sticky_channels[message.channel.id]
                
                if os.path.exists(f"{message.channel.id}.txt"):
                    os.remove(f"{message.channel.id}.txt")
                    
                await message.channel.send("Sticky message removed.", delete_after=3)
            else:
                await message.channel.send("There is no sticky message in this channel.", delete_after=3)
                
            await message.delete()

    async def on_ready(self):
        print(f"✅ {self.user} is online")

if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        exit("Error: TOKEN missing from .env")
        
    intents = discord.Intents.default()
    intents.message_content = True
    
    Floppy(intents=intents).run(token)
