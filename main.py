import os
import discord
from discord.ext import tasks
from itertools import cycle
from datetime import datetime, timezone
from dotenv import load_dotenv
import state
import config
from tickets import OpenTicketView, TicketPanelView, post_ticket_panel
import commands

load_dotenv()

STATUSES = cycle([
    "🫧 floating around", "🐟 flopping about", "🗄️ peeking at the db",
    "🔌 poking the API", "🔍 searching messages", "📋 reading logs"
])

def make_embed(color, title, description=None, fields=None, footer=None):
    e = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
    if fields:
        for name, value, inline in fields:
            e.add_field(name=name, value=value, inline=inline)
    if footer:
        e.set_footer(text=footer)
    return e

GREEN  = 0x43b581
RED    = 0xf04747
YELLOW = 0xfaa61a
BLUE   = 0x5865f2

class Floppy(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.invite_cache = {}
        self.tree = commands.setup(self)

    async def setup_hook(self):
        self.add_view(OpenTicketView())
        self.add_view(TicketPanelView())
        self.cycle_status.start()

    @tasks.loop(seconds=600)
    async def cycle_status(self):
        await self.change_presence(activity=discord.CustomActivity(name=next(STATUSES)))

    @cycle_status.before_loop
    async def before_cycle(self):
        await self.wait_until_ready()

    async def on_ready(self):
        state.bot = self
        state.add_log(f"Bot online as {self.user}")
        await self.tree.sync()
        for guild in self.guilds:
            try:
                invites = await guild.fetch_invites()
                self.invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
            except Exception:
                pass
        await post_ticket_panel(self)
        state.add_log("Ticket panel posted")
        print(f"Online as {self.user}")

    async def on_disconnect(self):
        state.add_log("Bot disconnected")

    async def log(self, guild, emb):
        cfg = config.load()
        channel_id = cfg.get("audit_log_channel")
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id))
        if channel:
            try:
                await channel.send(embed=emb)
            except Exception:
                pass

    async def on_member_join(self, member):
        if member.bot:
            return
        cfg = config.load()
        used_invite = None
        try:
            new_invites = await member.guild.fetch_invites()
            new_map = {inv.code: inv.uses for inv in new_invites}
            old_map = self.invite_cache.get(member.guild.id, {})
            for code, uses in new_map.items():
                if uses > old_map.get(code, 0):
                    used_invite = next((i for i in new_invites if i.code == code), None)
                    break
            self.invite_cache[member.guild.id] = new_map
        except Exception:
            pass

        role_id = cfg.get("join_role")
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role, reason="Auto join role")
                except Exception:
                    pass

        channel_id = cfg.get("welcome_channel")
        if channel_id:
            channel = member.guild.get_channel(int(channel_id))
            if channel:
                msg = cfg.get("welcome_message", "Welcome {mention} to {server}!")
                text = msg.format(mention=member.mention, name=str(member), server=member.guild.name)
                await channel.send(text)

        state.add_log(f"Member joined: {member}")
        await self.log(member.guild, make_embed(GREEN, "Member Joined", fields=[
            ("Member", f"{member.mention} ({member})", True),
            ("Account Age", f"<t:{int(member.created_at.timestamp())}:R>", True),
            ("Member #", str(member.guild.member_count), True),
        ], footer=f"ID: {member.id}"))

    async def on_member_remove(self, member):
        if member.bot:
            return
        cfg = config.load()
        channel_id = cfg.get("goodbye_channel")
        if channel_id:
            channel = member.guild.get_channel(int(channel_id))
            if channel:
                msg = cfg.get("goodbye_message", "Goodbye {mention}, we'll miss you!")
                text = msg.format(mention=member.mention, name=str(member), server=member.guild.name)
                await channel.send(text)

        state.add_log(f"Member left: {member}")
        await self.log(member.guild, make_embed(RED, "Member Left", fields=[
            ("Member", f"{member} ({member.id})", False),
        ], footer=f"ID: {member.id}"))

    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
        fields = [("Author", f"{message.author.mention} ({message.author})", True), ("Channel", message.channel.mention, True)]
        if message.content:
            fields.append(("Content", message.content[:1024], False))
        if message.attachments:
            fields.append(("Attachments", "\n".join(a.filename for a in message.attachments), False))
        await self.log(message.guild, make_embed(RED, "Message Deleted", fields=fields, footer=f"Author ID: {message.author.id}"))

    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        await self.log(before.guild, make_embed(YELLOW, "Message Edited", fields=[
            ("Author", f"{before.author.mention} ({before.author})", True),
            ("Channel", before.channel.mention, True),
            ("Jump", f"[Go to message]({after.jump_url})", True),
            ("Before", before.content[:1024] or "*empty*", False),
            ("After", after.content[:1024] or "*empty*", False),
        ], footer=f"Author ID: {before.author.id}"))

    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            added = [r for r in after.roles if r not in before.roles]
            removed = [r for r in before.roles if r not in after.roles]
            fields = []
            if added:
                fields.append(("Roles Added", " ".join(r.mention for r in added), False))
            if removed:
                fields.append(("Roles Removed", " ".join(r.mention for r in removed), False))
            fields.append(("Member", f"{after.mention} ({after})", True))
            await self.log(after.guild, make_embed(BLUE, "Roles Updated", fields=fields, footer=f"ID: {after.id}"))
        if before.nick != after.nick:
            await self.log(after.guild, make_embed(YELLOW, "Nickname Changed", fields=[
                ("Member", f"{after.mention} ({after})", True),
                ("Before", before.nick or "*none*", True),
                ("After", after.nick or "*none*", True),
            ], footer=f"ID: {after.id}"))

    async def on_member_ban(self, guild, user):
        state.add_log(f"Member banned: {user}")
        await self.log(guild, make_embed(RED, "Member Banned", fields=[("User", f"{user.mention} ({user})", True)], footer=f"ID: {user.id}"))

    async def on_member_unban(self, guild, user):
        await self.log(guild, make_embed(GREEN, "Member Unbanned", fields=[("User", f"{user.mention} ({user})", True)], footer=f"ID: {user.id}"))

    async def on_guild_channel_create(self, channel):
        await self.log(channel.guild, make_embed(GREEN, "Channel Created", fields=[("Name", f"#{channel.name}", True), ("Type", str(channel.type), True)]))

    async def on_guild_channel_delete(self, channel):
        await self.log(channel.guild, make_embed(RED, "Channel Deleted", fields=[("Name", f"#{channel.name}", True), ("Type", str(channel.type), True)]))

    async def on_guild_channel_update(self, before, after):
        if before.name != after.name:
            await self.log(after.guild, make_embed(YELLOW, "Channel Renamed", fields=[("Before", f"#{before.name}", True), ("After", f"#{after.name}", True)]))

    async def on_guild_role_create(self, role):
        await self.log(role.guild, make_embed(GREEN, "Role Created", fields=[("Name", role.name, True)]))

    async def on_guild_role_delete(self, role):
        await self.log(role.guild, make_embed(RED, "Role Deleted", fields=[("Name", role.name, True)]))

    async def on_guild_role_update(self, before, after):
        if before.name != after.name:
            await self.log(after.guild, make_embed(YELLOW, "Role Renamed", fields=[("Before", before.name, True), ("After", after.name, True)]))

    async def on_invite_create(self, invite):
        if invite.guild:
            cache = self.invite_cache.get(invite.guild.id, {})
            cache[invite.code] = invite.uses or 0
            self.invite_cache[invite.guild.id] = cache
        await self.log(invite.guild, make_embed(GREEN, "Invite Created", fields=[
            ("Code", invite.code, True),
            ("Created By", str(invite.inviter), True),
            ("Max Uses", str(invite.max_uses) if invite.max_uses else "∞", True),
        ]))

    async def on_invite_delete(self, invite):
        if invite.guild:
            cache = self.invite_cache.get(invite.guild.id, {})
            cache.pop(invite.code, None)
            self.invite_cache[invite.guild.id] = cache
        await self.log(invite.guild, make_embed(RED, "Invite Deleted", fields=[("Code", invite.code, True)]))

    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        if before.channel is None and after.channel is not None:
            await self.log(member.guild, make_embed(GREEN, "Joined Voice", fields=[("Member", f"{member.mention} ({member})", True), ("Channel", after.channel.name, True)], footer=f"ID: {member.id}"))
        elif before.channel is not None and after.channel is None:
            await self.log(member.guild, make_embed(RED, "Left Voice", fields=[("Member", f"{member.mention} ({member})", True), ("Channel", before.channel.name, True)], footer=f"ID: {member.id}"))
        elif before.channel != after.channel:
            await self.log(member.guild, make_embed(YELLOW, "Switched Voice", fields=[("Member", f"{member.mention} ({member})", True), ("From", before.channel.name, True), ("To", after.channel.name, True)], footer=f"ID: {member.id}"))


def get_bot():
    token = os.getenv("TOKEN")
    if not token:
        exit("Error: TOKEN missing from .env")
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.moderation = True
    intents.invites = True
    intents.voice_states = True
    return Floppy(intents=intents), token
