import discord
from discord import app_commands
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

    @tree.command(name="levelboard", description="Show the top 10 members by XP", guild=guild)
    async def levelboard(interaction: discord.Interaction):
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

        # Find the caller's rank across everyone
        caller_id = str(interaction.user.id)
        caller_rank = next(
            (i + 1 for i, (uid, _) in enumerate(sorted_users) if uid == caller_id),
            None,
        )

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}

        lines = []
        for i, (user_id, xp) in enumerate(sorted_users[:10]):
            rank = i + 1
            medal = medals.get(rank, f"`#{rank}`")
            member = interaction.guild.get_member(int(user_id))
            name = member.display_name if member else f"<@{user_id}>"
            lv, _, _ = levelling.xp_progress(xp)
            lines.append(f"{medal} **{name}** — Lvl {lv} · {xp:,} XP")

        # If the caller is outside the top 10, append their entry separated by a divider
        if caller_rank and caller_rank > 10:
            caller_xp = data.get(caller_id, 0)
            caller_lv, _, _ = levelling.xp_progress(caller_xp)
            caller_member = interaction.guild.get_member(interaction.user.id)
            caller_name = caller_member.display_name if caller_member else interaction.user.mention
            lines.append("┈" * 20)
            lines.append(f"`#{caller_rank}` **{caller_name}** — Lvl {caller_lv} · {caller_xp:,} XP")

        embed = discord.Embed(
            title="🏆 Level Leaderboard",
            description="\n".join(lines),
            color=0x5865f2,
        )
        embed.set_footer(text=f"{len(sorted_users)} members ranked")

        await interaction.response.send_message(embed=embed)

    @tree.command(name="staff", description="Open the staff control panel", guild=guild)
    async def staff(interaction: discord.Interaction):
        import staff_panel
        if not staff_panel.is_staff(interaction) and not is_admin(interaction.user):
            await interaction.response.send_message(
                "❌ Only staff can use this command.", ephemeral=True
            )
            return
        embed = staff_panel.panel_embed()
        await interaction.response.send_message(
            embed=embed, view=staff_panel.StaffPanelView(), ephemeral=True
        )
