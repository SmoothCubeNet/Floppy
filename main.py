import os
import discord
from discord.ext import tasks
from itertools import cycle
from dotenv import load_dotenv
import state
import config

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
        state.bot = self
        print(f"✅ {self.user} is online")

    async def on_disconnect(self):
        state.bot_ready = False

    async def log(self, message: str):
        cfg = config.load()
        channel_id = cfg.get("audit_log_channel")
        if not channel_id:
            return
        channel = self.get_channel(int(channel_id))
        if channel:
            await channel.send(message)

    # --- Welcome / Goodbye / Join Role ---

    async def on_member_join(self, member: discord.Member):
        cfg = config.load()

        # Assign join role
        role_id = cfg.get("join_role")
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                await member.add_roles(role, reason="Auto join role")

        # Welcome message
        channel_id = cfg.get("welcome_channel")
        if channel_id:
            channel = self.get_channel(int(channel_id))
            if channel:
                msg = cfg.get("welcome_message", DEFAULTS["welcome_message"])
                await channel.send(msg.format(
                    mention=member.mention,
                    name=str(member),
                    server=member.guild.name
                ))

        await self.log(f"📥 **{member}** joined the server.")

    async def on_member_remove(self, member: discord.Member):
        cfg = config.load()

        channel_id = cfg.get("goodbye_channel")
        if channel_id:
            channel = self.get_channel(int(channel_id))
            if channel:
                msg = cfg.get("goodbye_message", DEFAULTS["goodbye_message"])
                await channel.send(msg.format(
                    mention=member.mention,
                    name=str(member),
                    server=member.guild.name
                ))

        await self.log(f"📤 **{member}** left the server.")

    # --- Audit Log Events ---

    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        await self.log(
            f"🗑️ Message by **{message.author}** deleted in {message.channel.mention}:\n> {message.content}"
        )

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content:
            return
        await self.log(
            f"✏️ Message by **{before.author}** edited in {before.channel.mention}:\n"
            f"> **Before:** {before.content}\n"
            f"> **After:** {after.content}"
        )

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles:
            added = [r for r in after.roles if r not in before.roles]
            removed = [r for r in before.roles if r not in after.roles]
            if added:
                await self.log(f"🔖 **{after}** was given roles: {', '.join(r.name for r in added)}")
            if removed:
                await self.log(f"🔖 **{after}** had roles removed: {', '.join(r.name for r in removed)}")
        if before.nick != after.nick:
            await self.log(f"📝 **{after}** changed nickname: `{before.nick}` → `{after.nick}`")

    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        await self.log(f"🔨 **{user}** was banned from the server.")

    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        await self.log(f"✅ **{user}** was unbanned from the server.")

    async def on_guild_channel_create(self, channel):
        await self.log(f"📢 Channel **#{channel.name}** was created.")

    async def on_guild_channel_delete(self, channel):
        await self.log(f"🗑️ Channel **#{channel.name}** was deleted.")

    async def on_guild_channel_update(self, before, after):
        if before.name != after.name:
            await self.log(f"📢 Channel **#{before.name}** renamed to **#{after.name}**.")

    async def on_guild_role_create(self, role: discord.Role):
        await self.log(f"🔖 Role **{role.name}** was created.")

    async def on_guild_role_delete(self, role: discord.Role):
        await self.log(f"🔖 Role **{role.name}** was deleted.")

    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if before.name != after.name:
            await self.log(f"🔖 Role **{before.name}** renamed to **{after.name}**.")

DEFAULTS = {
    "welcome_message": "Welcome {mention} to {server}!",
    "goodbye_message": "Goodbye {name}, we'll miss you!",
}

def get_bot():
    token = os.getenv("TOKEN")
    if not token:
        exit("Error: TOKEN missing from .env")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.moderation = True
    return Floppy(intents=intents), token
