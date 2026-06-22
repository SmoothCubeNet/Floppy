"""
staff_panel.py — the single /staff control panel.

A panel of buttons (persistent view) that exposes staff actions:
  • ⚠️ Warn        — pick a member, then a modal for the reason
  • 📋 View Warns   — pick a member, see their warning history
  • 🏓 Ping         — quick latency check

Warnings are stored on Discord through warnings.py (table "warnings"), exactly
like levelling — keyed by the warned user's ID.

All views are persistent (timeout=None, fixed custom_ids) so the buttons keep
working after a bot restart. They're registered in main.py's setup_hook.
"""

import discord
import config
import warns

PANEL_COLOR = 0x5865f2
WARN_COLOR = 0xf1c40f


# ---------------------------------------------------------------------------
# Permission helper
# ---------------------------------------------------------------------------

def is_staff(interaction: discord.Interaction) -> bool:
    cfg = config.load()
    staff_role_ids = [str(x) for x in cfg.get("ticket_staff_roles", [])]
    member = interaction.user
    if getattr(member, "guild_permissions", None) and member.guild_permissions.administrator:
        return True
    return any(str(r.id) in staff_role_ids for r in getattr(member, "roles", []))


async def _guard(interaction: discord.Interaction) -> bool:
    """Block non-staff. Returns True if allowed."""
    if is_staff(interaction):
        return True
    await interaction.response.send_message(
        "❌ Only staff can use this.", ephemeral=True
    )
    return False


def panel_embed() -> discord.Embed:
    e = discord.Embed(
        title="🛠️ Staff Panel",
        description=(
            "Pick an action below.\n\n"
            "⚠️ **Warn** — warn a member (stored permanently)\n"
            "📋 **View Warnings** — see a member's warning history\n"
            "🏓 **Ping** — check the bot's latency"
        ),
        color=PANEL_COLOR,
    )
    e.set_footer(text="Staff only • actions are logged")
    return e


# ---------------------------------------------------------------------------
# The panel itself
# ---------------------------------------------------------------------------

class StaffPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Warn", style=discord.ButtonStyle.danger, emoji="⚠️",
        custom_id="staff:warn",
    )
    async def warn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _guard(interaction):
            return
        await interaction.response.send_message(
            "Select the member to warn:",
            view=WarnMemberSelectView(),
            ephemeral=True,
        )

    @discord.ui.button(
        label="View Warnings", style=discord.ButtonStyle.secondary, emoji="📋",
        custom_id="staff:viewwarns",
    )
    async def view_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _guard(interaction):
            return
        await interaction.response.send_message(
            "Select the member to look up:",
            view=ViewWarnsMemberSelectView(),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Ping", style=discord.ButtonStyle.secondary, emoji="🏓",
        custom_id="staff:ping",
    )
    async def ping_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _guard(interaction):
            return
        latency = round(interaction.client.latency * 1000)
        await interaction.response.send_message(
            f"🏓 Pong! Latency is **{latency}ms**", ephemeral=True
        )


# ---------------------------------------------------------------------------
# Warn flow: member select  →  reason modal  →  store
# ---------------------------------------------------------------------------

class WarnMemberSelectView(discord.ui.View):
    """Ephemeral, short-lived select shown after pressing Warn."""

    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Choose a member to warn…",
        min_values=1,
        max_values=1,
    )
    async def pick(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if not await _guard(interaction):
            return
        member = select.values[0]
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You can't warn yourself.", ephemeral=True
            )
            return
        if member.bot:
            await interaction.response.send_message(
                "❌ You can't warn a bot.", ephemeral=True
            )
            return
        await interaction.response.send_modal(WarnReasonModal(member))


class WarnReasonModal(discord.ui.Modal, title="Warn Member"):
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Why is this member being warned?",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_warnings = await warns.add_warning(
            interaction.guild,
            self.member.id,
            interaction.user.id,
            self.reason.value,
        )
        count = len(user_warnings)

        embed = discord.Embed(
            title="⚠️ Member Warned",
            description=f"{self.member.mention} has been warned.",
            color=WARN_COLOR,
        )
        embed.add_field(name="Reason", value=self.reason.value, inline=False)
        embed.add_field(name="Total Warnings", value=str(count), inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.set_thumbnail(url=self.member.display_avatar.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Best-effort DM to the warned member.
        try:
            dm = discord.Embed(
                title=f"⚠️ You were warned in {interaction.guild.name}",
                description=self.reason.value,
                color=WARN_COLOR,
            )
            dm.set_footer(text=f"You now have {count} warning(s).")
            await self.member.send(embed=dm)
        except (discord.Forbidden, discord.HTTPException):
            pass


# ---------------------------------------------------------------------------
# View-warnings flow: member select  →  list
# ---------------------------------------------------------------------------

class ViewWarnsMemberSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Choose a member to look up…",
        min_values=1,
        max_values=1,
    )
    async def pick(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if not await _guard(interaction):
            return
        member = select.values[0]
        user_warnings = warns.get_user_warnings(member.id)

        if not user_warnings:
            await interaction.response.send_message(
                f"✅ {member.mention} has no warnings.", ephemeral=True
            )
            return

        lines = []
        for i, w in enumerate(user_warnings, start=1):
            when = ""
            ts = w.get("timestamp", "")
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(ts)
                when = f" · <t:{int(dt.timestamp())}:R>"
            except (ValueError, TypeError):
                pass
            mod_id = w.get("moderator_id")
            mod = f"<@{mod_id}>" if mod_id else "Unknown"
            lines.append(f"`#{i}` {w.get('reason', 'No reason')} — by {mod}{when}")

        embed = discord.Embed(
            title=f"⚠️ Warnings for {member.display_name}",
            description="\n".join(lines),
            color=WARN_COLOR,
        )
        embed.set_footer(text=f"{len(user_warnings)} total")
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
