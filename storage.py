"""
storage.py — Discord-backed persistent storage for Floppy.

Data is stored directly in #floppystorage as pinned messages with JSON
attachments — one message per table, named by the table (e.g. "levelling").
No threads are used.
"""

import io
import json
import discord
import state

STORAGE_CHANNEL_NAME = "floppystorage"

# Tables that should always exist, even before any data is written.
KNOWN_TABLES = ["levelling"]

# In-memory cache: { "levelling": { "user_id": xp, ... }, ... }
_cache: dict[str, dict] = {}

# Cached channel object.
_channel: discord.TextChannel | None = None

# Message ID for each table's storage message: { "levelling": message_id }
_msg_ids: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_or_create_storage_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Find #floppystorage, or create it as a private bot-only channel if missing."""
    global _channel
    if _channel and _channel.guild.id == guild.id:
        return _channel

    channel = discord.utils.get(guild.text_channels, name=STORAGE_CHANNEL_NAME)
    if not channel:
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
                name=STORAGE_CHANNEL_NAME,
                overwrites=overwrites,
                reason="Floppy auto-created storage channel",
            )
            state.add_log(f"Storage: created #{STORAGE_CHANNEL_NAME} automatically")
        except Exception as e:
            state.add_log(f"Storage: failed to create #{STORAGE_CHANNEL_NAME} — {e}")
            return None

    _channel = channel
    return channel


async def _find_table_message(channel: discord.TextChannel, table: str) -> discord.Message | None:
    """Scan the channel for the bot's storage message for this table."""
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
        # No data yet — that's fine, start empty.
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
    """Persist a table to #floppystorage.

    Sends the new message FIRST, then deletes the old one — so a failed
    send never causes data loss.
    """
    _cache[table] = data

    channel = await _get_or_create_storage_channel(guild)
    if not channel:
        return

    # Remember the old message ID before we do anything.
    old_id = _msg_ids.get(table)

    # Write new message first.
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
        return  # Old message untouched; data is still safe.

    # New message confirmed — now delete the old one.
    if old_id:
        try:
            old_msg = await channel.fetch_message(old_id)
            await old_msg.delete()
        except Exception:
            pass  # Already gone or no permission — not a problem.


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
    Ensure #floppystorage exists, then load all known tables from it.
    """
    channel = await _get_or_create_storage_channel(guild)
    if not channel:
        state.add_log("Storage: startup aborted — could not get/create storage channel")
        return

    for table in KNOWN_TABLES:
        await read(guild, table)

    state.add_log(f"Storage: startup complete — {len(KNOWN_TABLES)} table(s) ready")
