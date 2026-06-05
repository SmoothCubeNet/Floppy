import random
import discord
import storage
import state
import config

# ---------------------------------------------------------------------------
# XP formula: 5n² + 50n + 100
# ---------------------------------------------------------------------------

XP_PER_MESSAGE_MIN = 15
XP_PER_MESSAGE_MAX = 25
XP_COOLDOWN_SECONDS = 60  # one XP grant per user per minute

TABLE = "levelling"

# In-memory cooldown tracker: {user_id: last_granted_monotonic_time}
_cooldowns: dict[int, float] = {}


# ---------------------------------------------------------------------------
# Level math
# ---------------------------------------------------------------------------

def xp_for_level(level: int) -> int:
    """Total XP required to reach this level from 0."""
    return 5 * level * level + 50 * level + 100


def level_for_xp(total_xp: int) -> int:
    level = 0
    while total_xp >= xp_for_level(level + 1):
        level += 1
    return level


def xp_progress(total_xp: int) -> tuple[int, int, int]:
    """Returns (current_level, xp_into_level, xp_needed_for_next_level)."""
    level = level_for_xp(total_xp)
    xp_start = xp_for_level(level) if level > 0 else 0
    xp_end = xp_for_level(level + 1)
    return level, total_xp - xp_start, xp_end - xp_start


# ---------------------------------------------------------------------------
# XP read/write (cache for reads, Discord write on change)
# ---------------------------------------------------------------------------

def get_user_xp(user_id: int) -> int:
    return storage.get_cached(TABLE).get(str(user_id), 0)


async def _set_user_xp(guild: discord.Guild, user_id: int, xp: int):
    data = dict(storage.get_cached(TABLE))  # copy
    data[str(user_id)] = xp
    storage.set_cached(TABLE, data)
    await storage.write(guild, TABLE, data)


async def wipe_user(guild: discord.Guild, user_id: int):
    """Remove a user's XP entry entirely — called on member leave."""
    data = dict(storage.get_cached(TABLE))
    if str(user_id) not in data:
        return
    del data[str(user_id)]
    storage.set_cached(TABLE, data)
    await storage.write(guild, TABLE, data)
    state.add_log(f"Levelling: wiped XP for user {user_id} (left server)")


# ---------------------------------------------------------------------------
# Core grant — called from on_message
# ---------------------------------------------------------------------------

async def handle_message(message: discord.Message):
    import time

    cfg = config.load()
    level_channel_id = cfg.get("level_channel")

    user_id = message.author.id
    now = time.monotonic()

    if now - _cooldowns.get(user_id, 0) < XP_COOLDOWN_SECONDS:
        return
    _cooldowns[user_id] = now

    gained = random.randint(XP_PER_MESSAGE_MIN, XP_PER_MESSAGE_MAX)
    old_xp = get_user_xp(user_id)
    new_xp = old_xp + gained

    old_level = level_for_xp(old_xp)
    new_level = level_for_xp(new_xp)

    await _set_user_xp(message.guild, user_id, new_xp)

    if new_level > old_level:
        state.add_log(f"Levelling: {message.author} reached level {new_level}")
        await _announce_level_up(message, new_level, new_xp, level_channel_id)


async def _announce_level_up(message: discord.Message, new_level: int, total_xp: int, level_channel_id):
    _, xp_into, xp_needed = xp_progress(total_xp)

    embed = discord.Embed(
        title="⬆️ Level Up!",
        description=f"{message.author.mention} just reached **Level {new_level}**! 🎉",
        color=0x5865f2,
    )
    embed.add_field(name="Progress", value=f"{xp_into} / {xp_needed} XP to next level", inline=False)
    embed.set_thumbnail(url=message.author.display_avatar.url)

    channel = None
    if level_channel_id:
        channel = message.guild.get_channel(int(level_channel_id))
    if channel is None:
        channel = message.channel

    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        state.add_log("Levelling: no permission to post in level channel")
