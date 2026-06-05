import discord
from discord import app_commands
import config
import levelling

# ---------------------------------------------------------------------------
# Helper — used by commands and main.py's on_message
# ---------------------------------------------------------------------------

def is_admin(member: discord.Member) -> bool:
    """True if the member has administrator permission."""
    return member.guild_permissions.administrator


def get_commands_channel_id(cfg: dict) -> int | None:
    raw = cfg.get("commands_channel")
    return int(raw) if raw else None


async def enforce_commands_channel(interaction: discord.Interaction) -> bool:
    """
    Call at the top of every user-facing command.
    Returns True if the command should proceed, False if it was blocked.
    If a commands channel is set and the interaction is elsewhere (and the
    user isn't an admin), send an ephemeral redirect and return False.
    """
    cfg = config.load()
    ch_id = get_commands_channel_id(cfg)
    if not ch_id:
        return True  # no restriction configured
    if is_admin(interaction.user):
        return True  # admins can use commands anywhere
    if interaction.channel_id == ch_id:
        return True  # correct channel

    channel = interaction.guild.get_channel(ch_id)
    mention = channel.mention if channel else f"<#{ch_id}>"
    await interaction.response.send_message(
        f"❌ Please use commands in {mention}.", ephemeral=True
    )
    return False


# ---------------------------------------------------------------------------
# Command tree
# ---------------------------------------------------------------------------

def setup(client: discord.Client):
    tree = app_commands.CommandTree(client)

    @tree.command(name="ping", description="Check the bot's latency")
    async def ping(interaction: discord.Interaction):
        if not await enforce_commands_channel(interaction):
            return
        latency = round(client.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! Latency is **{latency}ms**")

    @tree.command(name="purge", description="Delete messages in this channel from a given message ID up to now")
    @app_commands.describe(message_id="The ID of the oldest message to delete (right-click a message → Copy Message ID)")
    async def purge(interaction: discord.Interaction, message_id: str):
        cfg = config.load()
        staff_role_ids = cfg.get("ticket_staff_roles", [])
        is_staff = any(str(r.id) in [str(x) for x in staff_role_ids] for r in interaction.user.roles)
        if not is_staff:
            await interaction.response.send_message("❌ Only staff can use this command.", ephemeral=True)
            return

        try:
            after_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ That doesn't look like a valid message ID.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            anchor = await interaction.channel.fetch_message(after_id)
        except discord.NotFound:
            await interaction.followup.send("❌ Couldn't find that message in this channel.", ephemeral=True)
            return

        to_delete = []
        async for msg in interaction.channel.history(limit=None, after=anchor, oldest_first=True):
            to_delete.append(msg)
        to_delete.insert(0, anchor)

        if not to_delete:
            await interaction.followup.send("Nothing to delete.", ephemeral=True)
            return

        from datetime import timedelta
        cutoff = discord.utils.utcnow() - timedelta(days=14)
        bulk = [m for m in to_delete if m.created_at > cutoff]
        slow = [m for m in to_delete if m.created_at <= cutoff]

        deleted = 0
        for i in range(0, len(bulk), 100):
            chunk = bulk[i:i + 100]
            if len(chunk) == 1:
                await chunk[0].delete()
            else:
                await interaction.channel.delete_messages(chunk)
            deleted += len(chunk)

        for msg in slow:
            try:
                await msg.delete()
                deleted += 1
            except discord.NotFound:
                pass

        await interaction.followup.send(f"🗑️ Deleted **{deleted}** message(s).", ephemeral=True)

    @tree.command(name="level", description="Check your (or another member's) XP and level")
    @app_commands.describe(member="The member to check (defaults to you)")
    async def level(interaction: discord.Interaction, member: discord.Member = None):
        if not await enforce_commands_channel(interaction):
            return
        target = member or interaction.user
        total_xp = levelling.get_user_xp(target.id)
        lv, xp_into, xp_needed = levelling.xp_progress(total_xp)

        bar_filled = int((xp_into / xp_needed) * 10) if xp_needed else 10
        bar = "█" * bar_filled + "░" * (10 - bar_filled)

        embed = discord.Embed(
            title=f"📊 {target.display_name}'s Level",
            color=0x5865f2,
        )
        embed.add_field(name="Level", value=str(lv), inline=True)
        embed.add_field(name="Total XP", value=str(total_xp), inline=True)
        embed.add_field(name="Progress", value=f"`{bar}` {xp_into}/{xp_needed} XP", inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    return tree
