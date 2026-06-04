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
        status_msg = await interaction.original_response()

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

        # Disable all buttons on the panel
        for child in self.children:
            child.disabled = True
            if hasattr(child, 'custom_id') and child.custom_id == "ticket:close":
                child.label = "Closed"
        await interaction.message.edit(view=self)

        # Move to closed category instead of deleting
        closed_cat_id = cfg.get("ticket_closed_category")
        if closed_cat_id:
            closed_category = interaction.guild.get_channel(int(closed_cat_id))
            if closed_category:
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
                await status_msg.delete()
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
        self.claim_ticket.disabled = True
        self.claim_ticket.label = f"Claimed by {interaction.user.display_name}"
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Ticket Actions", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="ticket:actions")
    async def ticket_actions(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = config.load()
        staff_role_ids = cfg.get("ticket_staff_roles", [])
        is_staff = any(str(r.id) in [str(x) for x in staff_role_ids] for r in interaction.user.roles)
        if not is_staff:
            await interaction.response.send_message("Only staff can use ticket actions.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚙️ Ticket Actions",
                description="Choose an action below.",
                color=0x5865f2,
            ),
            view=TicketActionsView(),
            ephemeral=True,
        )


# ── Ticket Actions select + modals ────────────────────────────────────────────

class TicketActionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.select(
        placeholder="Select an action...",
        custom_id="ticket:actions_select",
        options=[
            discord.SelectOption(label="Add User(s)", value="add", emoji="➕", description="Grant one or more users access to this ticket"),
            discord.SelectOption(label="Remove User(s)", value="remove", emoji="➖", description="Revoke one or more users' access to this ticket"),
        ],
    )
    async def select_action(self, interaction: discord.Interaction, select: discord.ui.Select):
        action = select.values[0]
        if action == "add":
            await interaction.response.send_modal(AddUsersModal())
        else:
            await interaction.response.send_modal(RemoveUsersModal())


class AddUsersModal(discord.ui.Modal, title="Add Users to Ticket"):
    user_ids = discord.ui.TextInput(
        label="User ID(s)",
        placeholder="Comma-separated IDs, e.g. 123456789, 987654321",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        guild = interaction.guild

        raw_ids = [s.strip() for s in self.user_ids.value.split(",") if s.strip()]
        added, already_in, not_found, errors = [], [], [], []

        for raw in raw_ids:
            try:
                uid = int(raw)
            except ValueError:
                errors.append(raw)
                continue
            member = guild.get_member(uid)
            if not member:
                try:
                    member = await guild.fetch_member(uid)
                except Exception:
                    not_found.append(raw)
                    continue

            existing = channel.overwrites_for(member)
            if existing.view_channel:
                already_in.append(member.mention)
                continue

            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                reason=f"Added to ticket by {interaction.user}",
            )
            added.append(member)

        # Rename channel to include newly added users
        if added:
            await _rename_ticket_channel(channel, guild)

        # Build response
        lines = []
        if added:
            lines.append(f"✅ Added: {', '.join(m.mention for m in added)}")
        if already_in:
            lines.append(f"ℹ️ Already in ticket: {', '.join(already_in)}")
        if not_found:
            lines.append(f"❌ Not found: {', '.join(not_found)}")
        if errors:
            lines.append(f"⚠️ Invalid IDs: {', '.join(errors)}")

        await interaction.followup.send("\n".join(lines) or "Nothing changed.", ephemeral=True)

        if added:
            mentions_str = ", ".join(m.mention for m in added)
            e = discord.Embed(
                description=f"➕ {mentions_str} {'has' if len(added) == 1 else 'have'} been added to this ticket by {interaction.user.mention}.",
                color=0x43b581,
                timestamp=datetime.now(timezone.utc),
            )
            await channel.send(embed=e)


class RemoveUsersModal(discord.ui.Modal, title="Remove Users from Ticket"):
    user_ids = discord.ui.TextInput(
        label="User ID(s)",
        placeholder="Comma-separated IDs, e.g. 123456789, 987654321",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        guild = interaction.guild

        # Protect the opener from being removed
        opener_id = None
        if channel.topic:
            try:
                opener_id = int(channel.topic.split("opener:")[1].split(" |")[0].strip())
            except Exception:
                pass

        raw_ids = [s.strip() for s in self.user_ids.value.split(",") if s.strip()]
        removed, protected, not_found, errors = [], [], [], []

        for raw in raw_ids:
            try:
                uid = int(raw)
            except ValueError:
                errors.append(raw)
                continue

            if uid == opener_id:
                protected.append(raw)
                continue

            member = guild.get_member(uid)
            if not member:
                try:
                    member = await guild.fetch_member(uid)
                except Exception:
                    not_found.append(raw)
                    continue

            await channel.set_permissions(member, overwrite=None, reason=f"Removed from ticket by {interaction.user}")
            removed.append(member)

        if removed:
            await _rename_ticket_channel(channel, guild)

        lines = []
        if removed:
            lines.append(f"✅ Removed: {', '.join(m.mention for m in removed)}")
        if protected:
            lines.append(f"🔒 Can't remove ticket opener: {', '.join(protected)}")
        if not_found:
            lines.append(f"❌ Not found: {', '.join(not_found)}")
        if errors:
            lines.append(f"⚠️ Invalid IDs: {', '.join(errors)}")

        await interaction.followup.send("\n".join(lines) or "Nothing changed.", ephemeral=True)

        if removed:
            mentions_str = ", ".join(m.mention for m in removed)
            e = discord.Embed(
                description=f"➖ {mentions_str} {'has' if len(removed) == 1 else 'have'} been removed from this ticket by {interaction.user.mention}.",
                color=0xf04747,
                timestamp=datetime.now(timezone.utc),
            )
            await channel.send(embed=e)


# ── Shared channel rename helper ──────────────────────────────────────────────

async def _rename_ticket_channel(channel: discord.TextChannel, guild: discord.Guild):
    """Rebuild the ticket channel name from opener + all explicitly added members."""
    opener_id = None
    opener_name = channel.name.removeprefix("ticket-")
    if channel.topic:
        try:
            opener_id = int(channel.topic.split("opener:")[1].split(" |")[0].strip())
            opener_member = guild.get_member(opener_id)
            if opener_member:
                opener_name = opener_member.name.lower()
        except Exception:
            pass

    added_names = []
    for target, overwrite in channel.overwrites.items():
        if not isinstance(target, discord.Member):
            continue
        if target == guild.me:
            continue
        if opener_id and target.id == opener_id:
            continue
        if overwrite.view_channel:
            added_names.append(target.name.lower())

    added_names.sort()
    parts = [opener_name] + added_names
    new_name = "ticket-" + "-".join(parts)[:90]

    if channel.name != new_name:
        try:
            await channel.edit(name=new_name, reason="Ticket users updated")
        except discord.HTTPException:
            pass



# ── Mention handler (called from on_message in main.py) ──────────────────────

async def handle_ticket_mention(message: discord.Message):
    """
    If a staff member pings one or more users inside a ticket channel,
    grant each mentioned user view access and rename the channel to
    include all their names (e.g. ticket-alice-bob).
    """
    channel = message.channel

    # Only act in ticket channels (name starts with ticket-)
    if not isinstance(channel, discord.TextChannel):
        return
    if not channel.name.startswith("ticket-"):
        return

    # Only act on messages from real users that actually mention someone
    if message.author.bot or not message.mentions:
        return

    cfg = config.load()
    staff_role_ids = [str(r) for r in cfg.get("ticket_staff_roles", [])]
    author_role_ids = [str(r.id) for r in message.author.roles]
    is_staff = any(rid in staff_role_ids for rid in author_role_ids)
    if not is_staff:
        return

    guild = channel.guild
    newly_added = []

    for user in message.mentions:
        if user.bot:
            continue
        # Skip if they already have explicit access
        existing = channel.overwrites_for(user)
        if existing.view_channel:
            continue

        await channel.set_permissions(
            user,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            reason=f"Added to ticket by {message.author}",
        )
        newly_added.append(user)

    if not newly_added:
        return

    await _rename_ticket_channel(channel, guild)

    # Notify in channel
    mentions_str = ", ".join(u.mention for u in newly_added)
    e = discord.Embed(
        description=f"👥 {mentions_str} {'has' if len(newly_added) == 1 else 'have'} been added to this ticket by {message.author.mention}.",
        color=0x5865f2,
        timestamp=datetime.now(timezone.utc),
    )
    await channel.send(embed=e)


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
