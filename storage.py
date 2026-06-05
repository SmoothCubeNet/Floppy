"""
storage.py — Discord-backed persistent storage for Floppy.

How it works:
  - There is one text channel called "floppystorage" (private, bot-only).
    If it doesn't exist, the bot creates it automatically on startup.
  - Each "table" gets its own private thread inside that channel.
  - The thread always contains exactly ONE message from the bot.
  - That message has a single file attachment: <table>.json
  - To read: download & parse the attachment.
  - To write: delete the old message, post a new one with the updated file.
  - On bot startup: call load_all() to pull everything into memory.

Adding a new table in the future:
  Just call `await storage.read("mytable")` / `await storage.write("mytable", data)`.
  The channel and thread are both created automatically if they don't exist.
"""

import io
import json
import discord
import state

STORAGE_CHANNEL_NAME = "floppystorage"

# In-memory cache so we're not hitting Discord on every XP grant.
# Structure: { "levelling": { "user_id": xp, ... }, ... }
_cache: dict[str, dict] = {}

# Thread objects keyed by table name so we don't re-fetch them.
_threads: dict[str, discord.Thread] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_or_create_storage_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Find #floppystorage, or create it as a private bot-only channel if missing."""
    channel = discord.utils.get(guild.text_channels, name=STORAGE_CHANNEL_NAME)
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
                create_private_threads=True,
                send_messages_in_threads=True,
                manage_threads=True,
            ),
        }
        channel = await guild.create_text_channel(
            name=STORAGE_CHANNEL_NAME,
            overwrites=overwrites,
            reason="Floppy auto-created storage channel",
        )
        state.add_log(f"Storage: created #{STORAGE_CHANNEL_NAME} automatically")
        return channel
    except Exception as e:
        state.add_log(f"Storage: failed to create #{STORAGE_CHANNEL_NAME} — {e}")
        return None


async def _get_or_create_thread(guild: discord.Guild, table: str) -> discord.Thread | None:
    """Return the private thread for this table, creating it if needed."""
    if table in _threads:
        return _threads[table]

    channel = await _get_or_create_storage_channel(guild)
    if not channel:
        return None

    # Look for an existing active thread with this name.
    for thread in channel.threads:
        if thread.name == table:
            _threads[table] = thread
            return thread

    # Also check archived threads.
    async for thread in channel.archived_threads(private=True):
        if thread.name == table:
            await thread.edit(archived=False)
            _threads[table] = thread
            return thread

    # Create a new private thread.
    try:
        thread = await channel.create_thread(
            name=table,
            type=discord.ChannelType.private_thread,
            reason=f"Floppy storage: {table} table",
        )
        _threads[table] = thread
        state.add_log(f"Storage: created thread '{table}'")
        return thread
    except Exception as e:
        state.add_log(f"Storage: failed to create thread '{table}' — {e}")
        return None


async def _find_storage_message(thread: discord.Thread) -> discord.Message | None:
    """Return the single bot-owned storage message in the thread, or None."""
    try:
        async for msg in thread.history(limit=20):
            if msg.author == thread.guild.me and msg.attachments:
                return msg
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def read(guild: discord.Guild, table: str) -> dict:
    """
    Load a table from Discord into memory and return it.
    Returns an empty dict if the table doesn't exist yet.
    """
    thread = await _get_or_create_thread(guild, table)
    if not thread:
        return {}

    msg = await _find_storage_message(thread)
    if not msg:
        _cache[table] = {}
        return {}

    try:
        attachment = msg.attachments[0]
        raw = await attachment.read()
        data = json.loads(raw.decode("utf-8"))
        _cache[table] = data
        state.add_log(f"Storage: loaded '{table}' ({len(data)} entries)")
        return data
    except Exception as e:
        state.add_log(f"Storage: failed to read '{table}' — {e}")
        _cache[table] = {}
        return {}


async def write(guild: discord.Guild, table: str, data: dict):
    """
    Persist data for a table to Discord.
    Deletes the old message and posts a fresh one with an updated .json attachment.
    Also updates the in-memory cache.
    """
    _cache[table] = data

    thread = await _get_or_create_thread(guild, table)
    if not thread:
        return

    # Delete old message if present.
    old_msg = await _find_storage_message(thread)
    if old_msg:
        try:
            await old_msg.delete()
        except Exception:
            pass

    # Upload fresh file.
    try:
        raw = json.dumps(data, indent=2).encode("utf-8")
        file = discord.File(io.BytesIO(raw), filename=f"{table}.json")
        await thread.send(
            content=f"`{table}` — {len(data)} entries",
            file=file,
        )
    except Exception as e:
        state.add_log(f"Storage: failed to write '{table}' — {e}")


def get_cached(table: str) -> dict:
    """
    Return the in-memory cache for a table without hitting Discord.
    Always use this for reads during normal operation (e.g. every message).
    Only call read() at startup.
    """
    return _cache.get(table, {})


def set_cached(table: str, data: dict):
    """Update only the in-memory cache (no Discord write). Used for partial updates."""
    _cache[table] = data


# ---------------------------------------------------------------------------
# Startup loader — call once in on_ready
# ---------------------------------------------------------------------------

async def load_all(guild: discord.Guild):
    """
    On startup: ensure #floppystorage exists, then load all table threads into cache.
    """
    channel = await _get_or_create_storage_channel(guild)
    if not channel:
        state.add_log("Storage: startup aborted — could not get/create storage channel")
        return

    threads_found = list(channel.threads)
    async for t in channel.archived_threads(private=True):
        threads_found.append(t)

    for thread in threads_found:
        _threads[thread.name] = thread
        await read(guild, thread.name)

    state.add_log(f"Storage: startup load complete ({len(threads_found)} tables)")
