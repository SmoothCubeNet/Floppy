"""
storage.py — Discord-backed persistent storage for Floppy.

Primary:  #floppystorage        — one live message per table (old deleted after new confirmed)
Backup:   #floppystoragebackup  — append-only log, NEVER deleted, each message has a
                                  "↩ Restore" button that reinstates that snapshot as live data.
"""

import io
import json
from datetime import datetime, timezone
import discord
import state

STORAGE_CHANNEL_NAME        = "floppystorage"
BACKUP_CHANNEL_NAME         = "floppystoragebackup"

# Tables that should always exist, even before any data is written.
KNOWN_TABLES = ["levelling"]

# In-memory cache: { "levelling": { "user_id": xp, ... }, ... }
_cache: dict[str, dict] = {}

# Cached channel objects.
_channel: discord.TextChannel | None = None
_backup_channel: discord.TextChannel | None = None

# Message ID of the current live storage message per table.
_msg_ids: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Backup restore button
# ---------------------------------------------------------------------------

class RestoreBackupButton(discord.ui.View):
    """
    Persistent button attached to every backup message.
    custom_id encodes the table name so it survives bot restarts.
    """

    def __init__(self, table: str):
        # timeout=None makes it persistent across restarts
        super().__init__(timeout=None)
        self.table = table

        button = discord.ui.Button(
            label="↩ Restore this backup",
            style=discord.ButtonStyle.danger,
            custom_id=f"floppy_restore:{table}",
        )
        button.callback = self.restore_callback
        self.add_item(button)

    async def restore_callback(self, interaction: discord.Interaction):
        # Only admins can restore
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only admins can restore backups.", ephemeral=True
            )
            return

        # Read the JSON from this message's attachment
        msg = interaction.message
        if not msg.attachments:
            await interaction.response.send_message(
                "❌ No attachment found on this message.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            raw = await msg.attachments[0].read()
            data = json.loads(raw.decode("utf-8"))
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to read backup: {e}", ephemeral=True)
            return

        # Write it as the new live data (this also posts a new backup snapshot)
        await write(interaction.guild, self.table, data)

        state.add_log(
            f"Storage: '{self.table}' restored from backup by {interaction.user} "
            f"(msg {msg.id})"
        )
        await interaction.followup.send(
            f"✅ `{self.table}` restored from backup ({len(data)} entries). "
            f"A new backup snapshot has been posted.",
            ephemeral=True,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_or_create_channel(
    guild: discord.Guild,
    name: str,
) -> discord.TextChannel | None:
    """Find a private bot channel by name, creating it if missing."""
    channel = discord.utils.get(guild.text_channels, name=name)
    if channel:
        return channel
    try:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
            ),
        }
        channel = await guild.create_text_channel(
            name=name,
            overwrites=overwrites,
            reason="Floppy auto-created storage channel",
        )
        state.add_log(f"Storage: created #{name} automatically")
        return channel
    except Exception as e:
        state.add_log(f"Storage: failed to create #{name} — {e}")
        return None


async def _get_or_create_storage_channel(guild: discord.Guild) -> discord.TextChannel | None:
    global _channel
    if _channel and _channel.guild.id == guild.id:
        return _channel
    _channel = await _get_or_create_channel(guild, STORAGE_CHANNEL_NAME)
    return _channel


async def _get_or_create_backup_channel(guild: discord.Guild) -> discord.TextChannel | None:
    global _backup_channel
    if _backup_channel and _backup_channel.guild.id == guild.id:
        return _backup_channel
    _backup_channel = await _get_or_create_channel(guild, BACKUP_CHANNEL_NAME)
    return _backup_channel


async def _find_table_message(channel: discord.TextChannel, table: str) -> discord.Message | None:
    """Scan the primary channel for the bot's live storage message for this table."""
    try:
        async for msg in channel.history(limit=100):
            if (
                msg.author == channel.guild.me
                and msg.attachments
                and msg.attachments[0].filename == f"{table}.json"
            ):
                return msg
    except Exception as e:
        state.add_log(f"Storage: error scanning channel for '{table}' — {e}")
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def read(guild: discord.Guild, table: str) -> dict:
    """Load a table from #floppystorage into memory and return it."""
    channel = await _get_or_create_storage_channel(guild)
    if not channel:
        return _cache.get(table, {})

    msg = await _find_table_message(channel, table)
    if not msg:
        state.add_log(f"Storage: no existing message for '{table}', starting fresh")
        return _cache.get(table, {})

    _msg_ids[table] = msg.id

    try:
        raw = await msg.attachments[0].read()
        data = json.loads(raw.decode("utf-8"))
        _cache[table] = data
        state.add_log(f"Storage: loaded '{table}' ({len(data)} entries)")
        return data
    except Exception as e:
        state.add_log(f"Storage: failed to read '{table}' — {e}")
        return _cache.get(table, {})


async def write(guild: discord.Guild, table: str, data: dict):
    """Persist a table to #floppystorage and append a snapshot to #floppystoragebackup.

    Order of operations (safe by design):
      1. Post new live message in #floppystorage
      2. Post backup snapshot in #floppystoragebackup (never deleted)
      3. Delete the old live message from #floppystorage
    """
    _cache[table] = data

    channel = await _get_or_create_storage_channel(guild)
    if not channel:
        return

    old_id = _msg_ids.get(table)

    # 1. Write new live message first
    try:
        raw = json.dumps(data, indent=2).encode("utf-8")
        file = discord.File(io.BytesIO(raw), filename=f"{table}.json")
        new_msg = await channel.send(
            content=f"`{table}` — {len(data)} entries",
            file=file,
        )
        _msg_ids[table] = new_msg.id
    except Exception as e:
        state.add_log(f"Storage: failed to write '{table}' — {e}")
        return  # Old message untouched.

    # 2. Post backup snapshot (append-only, never deleted)
    backup_channel = await _get_or_create_backup_channel(guild)
    if backup_channel:
        try:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            raw2 = json.dumps(data, indent=2).encode("utf-8")
            file2 = discord.File(io.BytesIO(raw2), filename=f"{table}.json")
            await backup_channel.send(
                content=f"📦 `{table}` backup — {len(data)} entries — {ts}",
                file=file2,
                view=RestoreBackupButton(table),
            )
        except Exception as e:
            state.add_log(f"Storage: failed to post backup for '{table}' — {e}")

    # 3. Delete old live message now that both new messages are safe
    if old_id:
        try:
            old_msg = await channel.fetch_message(old_id)
            await old_msg.delete()
        except Exception:
            pass


def get_cached(table: str) -> dict:
    """Fast in-memory read — use this during normal operation."""
    return _cache.get(table, {})


def set_cached(table: str, data: dict):
    """Update only the in-memory cache (no Discord write)."""
    _cache[table] = data


# ---------------------------------------------------------------------------
# Startup loader — call once in on_ready
# ---------------------------------------------------------------------------

async def load_all(guild: discord.Guild):
    """
    Ensure #floppystorage and #floppystoragebackup exist, then load all tables.
    """
    channel = await _get_or_create_storage_channel(guild)
    if not channel:
        state.add_log("Storage: startup aborted — could not get/create storage channel")
        return

    # Ensure backup channel exists at startup too
    await _get_or_create_backup_channel(guild)

    for table in KNOWN_TABLES:
        await read(guild, table)

    state.add_log(f"Storage: startup complete — {len(KNOWN_TABLES)} table(s) ready")
