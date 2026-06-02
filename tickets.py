import discord
import io
import config
from datetime import datetime, timezone

PANEL_MESSAGE_KEY = "ticket_panel_message_id"

def format_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

# ── Views ────────────────────────────────────────────────────────────────────

class OpenTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open a Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="ticket:open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())


class TicketModal(discord.ui.Modal, title="Open a Ticket"):
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Briefly describe your issue...",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cfg = config.load()

        guild = interaction.guild
        member = interaction.user

        # Check if user already has an open ticket
        existing = discord.utils.get(guild.text_channels, name=f"ticket-{member.name.lower()}")
        if existing:
            await interaction.followup.send(f"You already have an open ticket: {existing.mention}", ephemeral=True)
            return

        # Category
        category = None
        cat_id = cfg.get("ticket_category")
        if cat_id:
            category = guild.get_channel(int(cat_id))

        # Permissions — staff roles + member
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        staff_role_ids = cfg.get("ticket_staff_roles", [])
        for role_id in staff_role_ids:
            role = guild.get_role(int(role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)

        channel = await guild.create_text_channel(
            name=f"ticket-{member.name.lower()}",
            category=category,
            overwrites=overwrites,
            topic=f"Ticket by {member} | opener:{member.id} | Reason: {self.reason.value}",
        )

        # Panel embed at top
        e = discord.Embed(
            title="🎫 Support Ticket",
            description=f"Thanks for reaching out, {member.mention}!\n\n**Reason:**\n{self.reason.value}",
            color=0x5865f2,
            timestamp=datetime.now(timezone.utc),
        )
        e.set_footer(text=f"Opened by {member} | {format_timestamp()}")
        e.set_thumbnail(url=member.display_avatar.url)

        await channel.send(
            content=f"{member.mention} — staff will be with you shortly.",
            embed=e,
            view=TicketPanelView(member.id),
        )

        await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self, opener_id: int = None):
        super().__init__(timeout=None)
        self.opener_id = opener_id

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = config.load()
        staff_role_ids = cfg.get("ticket_staff_roles", [])
        is_staff = any(str(r.id) in [str(x) for x in staff_role_ids] for r in interaction.user.roles)
        channel = interaction.channel

        # Get opener id from channel topic
        opener_id = None
        if channel.topic:
            try:
                opener_id = int(channel.topic.split("opener:")[1].split(" |")[0].strip())
            except Exception:
                pass

        is_opener = interaction.user.id == opener_id

        if not is_staff and not is_opener:
            await interaction.response.send_message("Only staff or the ticket opener can close this.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Closing ticket and sending transcript...", ephemeral=False)

        # Build transcript (excluding bot messages)
        lines = []
        async for msg in channel.history(limit=500, oldest_first=True):
            if msg.author.bot:
                continue
            ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"[{ts}] {msg.author} ({msg.author.id}): {msg.content}")
            for a in msg.attachments:
                lines.append(f"[{ts}] {msg.author} (attachment): {a.url}")

        transcript = "\n".join(lines)

        # DM opener
        if opener_id:
            opener = interaction.guild.get_member(opener_id)
            if opener:
                try:
                    dm_embed = discord.Embed(
                        title="🎫 Your ticket has been closed",
                        description=f"Here's the transcript from your ticket in **{interaction.guild.name}**.",
                        color=0x5865f2,
                        timestamp=datetime.now(timezone.utc),
                    )
                    file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{channel.name}.txt")
                    await opener.send(embed=dm_embed, file=file)
                except discord.Forbidden:
                    pass

        # Move to closed category instead of deleting
        closed_cat_id = cfg.get("ticket_closed_category")
        if closed_cat_id:
            closed_category = interaction.guild.get_channel(int(closed_cat_id))
            if closed_category:
                # Lock the channel for the opener, keep staff access
                overwrites = channel.overwrites
                opener = interaction.guild.get_member(opener_id) if opener_id else None
                if opener and opener in overwrites:
                    overwrites[opener] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
                await channel.edit(
                    name=f"closed-{channel.name.removeprefix('ticket-')}",
                    category=closed_category,
                    overwrites=overwrites,
                    reason="Ticket closed",
                )
                return

        # Fallback: delete if no closed category is configured
        await channel.delete(reason="Ticket closed")

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, emoji="👤", custom_id="ticket:claim")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = config.load()
        staff_role_ids = cfg.get("ticket_staff_roles", [])
        is_staff = any(str(r.id) in [str(x) for x in staff_role_ids] for r in interaction.user.roles)
        if not is_staff:
            await interaction.response.send_message("Only staff can claim tickets.", ephemeral=True)
            return

        e = discord.Embed(
            description=f"👤 This ticket has been claimed by {interaction.user.mention}.",
            color=0x43b581,
            timestamp=datetime.now(timezone.utc),
        )
        await interaction.response.send_message(embed=e)
        # Disable claim button
        self.claim_ticket.disabled = True
        self.claim_ticket.label = f"Claimed by {interaction.user.display_name}"
        await interaction.message.edit(view=self)



# ── Panel posting ─────────────────────────────────────────────────────────────

async def post_ticket_panel(bot: discord.Client):
    """Post (or re-post) the ticket panel. Only called explicitly — never on boot."""
    cfg = config.load()
    channel_id = cfg.get("ticket_channel")
    if not channel_id:
        return

    guild = bot.guilds[0] if bot.guilds else None
    if not guild:
        return

    channel = guild.get_channel(int(channel_id))
    if not channel:
        return

    # Delete old panel message if it still exists
    old_msg_id = cfg.get(PANEL_MESSAGE_KEY)
    if old_msg_id:
        try:
            old_msg = await channel.fetch_message(int(old_msg_id))
            await old_msg.delete()
        except Exception:
            pass

    e = discord.Embed(
        title="🎫 Support Tickets",
        description="Need help? Click the button below to open a ticket.\nA staff member will be with you shortly.",
        color=0x5865f2,
    )
    e.set_footer(text="One ticket per user • Be descriptive about your issue")

    msg = await channel.send(embed=e, view=OpenTicketView())

    cfg[PANEL_MESSAGE_KEY] = str(msg.id)
    config.save(cfg)
