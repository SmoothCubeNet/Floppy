import discord
from discord import app_commands
from datetime import timedelta
import config
import levelling


def is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator


def get_commands_channel_id(cfg: dict) -> int | None:
    raw = cfg.get("commands_channel")
    return int(raw) if raw else None


async def enforce_commands_channel(interaction: discord.Interaction) -> bool:
    cfg = config.load()
    ch_id = get_commands_channel_id(cfg)
    if not ch_id:
        return True
    if is_admin(interaction.user):
        return True
    if interaction.channel_id == ch_id:
        return True
    channel = interaction.guild.get_channel(ch_id)
    mention = channel.mention if channel else f"<#{ch_id}>"
    await interaction.response.send_message(
        f"❌ Please use commands in {mention}.", ephemeral=True
    )
    return False


def register(tree: app_commands.CommandTree, guild: discord.Object):
    """Register all commands onto an existing tree for a specific guild."""

    @tree.command(name="ping", description="Check the bot's latency", guild=guild)
    async def ping(interaction: discord.Interaction):
        if not await enforce_commands_channel(interaction):
            return
        latency = round(interaction.client.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! Latency is **{latency}ms**")

    @tree.command(name="purge", description="Delete messages from a given message ID up to now", guild=guild)
    @app_commands.describe(message_id="The ID of the oldest message to delete")
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
        to_delete = [anchor]
        async for msg in interaction.channel.history(limit=None, after=anchor, oldest_first=True):
            to_delete.append(msg)
        if not to_delete:
            await interaction.followup.send("Nothing to delete.", ephemeral=True)
            return
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

    @tree.command(name="level", description="Check your (or another member's) XP and level", guild=guild)
    @app_commands.describe(member="The member to check (defaults to you)")
    async def level(interaction: discord.Interaction, member: discord.Member = None):
        if not await enforce_commands_channel(interaction):
            return
        target = member or interaction.user
        total_xp = levelling.get_user_xp(target.id)
        lv, xp_into, xp_needed = levelling.xp_progress(total_xp)
        bar_filled = int((xp_into / xp_needed) * 10) if xp_needed else 10
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        embed = discord.Embed(title=f"📊 {target.display_name}'s Level", color=0x5865f2)
        embed.add_field(name="Level", value=str(lv), inline=True)
        embed.add_field(name="Total XP", value=str(total_xp), inline=True)
        embed.add_field(name="Progress", value=f"`{bar}` {xp_into}/{xp_needed} XP", inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @tree.command(name="levelboard", description="Show the server's top members by XP", guild=guild)
    @app_commands.describe(page="Page number (10 entries per page, default: 1)")
    async def levelboard(interaction: discord.Interaction, page: int = 1):
        if not await enforce_commands_channel(interaction):
            return

        import storage
        data = storage.get_cached(levelling.TABLE)

        if not data:
            await interaction.response.send_message(
                "📭 No XP data yet — start chatting to earn some!", ephemeral=True
            )
            return

        # Sort all users by XP descending
        sorted_users = sorted(data.items(), key=lambda x: x[1], reverse=True)
        total_users = len(sorted_users)
        per_page = 10
        total_pages = max(1, (total_users + per_page - 1) // per_page)

        if page < 1 or page > total_pages:
            await interaction.response.send_message(
                f"❌ Invalid page. There are **{total_pages}** page(s) of results.", ephemeral=True
            )
            return

        start = (page - 1) * per_page
        page_entries = sorted_users[start:start + per_page]

        # Find the calling user's rank
        caller_rank = next(
            (i + 1 for i, (uid, _) in enumerate(sorted_users) if uid == str(interaction.user.id)),
            None,
        )

        # Medal emojis for the podium
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}

        lines = []
        for i, (user_id, xp) in enumerate(page_entries):
            rank = start + i + 1
            medal = medals.get(rank, f"`#{rank}`")

            # Try to resolve the member; fall back to a plain mention if not cached
            member = interaction.guild.get_member(int(user_id))
            name = member.display_name if member else f"<@{user_id}>"

            lv, _, _ = levelling.xp_progress(xp)
            lines.append(f"{medal} **{name}** — Lvl {lv} · {xp:,} XP")

        description = "\n".join(lines)

        embed = discord.Embed(
            title="🏆 Level Leaderboard",
            description=description,
            color=0x5865f2,
        )
        embed.set_footer(
            text=(
                f"Page {page}/{total_pages} · {total_users} members ranked"
                + (f" · You are #{caller_rank}" if caller_rank else "")
            )
        )

        await interaction.response.send_message(embed=embed)
