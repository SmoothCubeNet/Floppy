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

    if old_level < 10 <= new_level and isinstance(message.author, discord.Member):
        await apply_trust_role(message.author, cfg)


async def apply_trust_role(member: discord.Member, cfg: dict | None = None):
    """Remove the join role and add the level-10 role. Safe to call repeatedly."""
    if cfg is None:
        cfg = config.load()

    join_role_id = cfg.get("join_role")
    trust_role_id = cfg.get("trust_role")
    if not trust_role_id:
        return

    trust_role = member.guild.get_role(int(trust_role_id))
    if trust_role is None:
        return

    member_role_ids = {r.id for r in member.roles}

    try:
        if trust_role.id not in member_role_ids:
            await member.add_roles(trust_role, reason="Reached level 10")
        if join_role_id:
            join_role = member.guild.get_role(int(join_role_id))
            if join_role and join_role.id in member_role_ids:
                await member.remove_roles(join_role, reason="Reached level 10 — removing join role")
    except discord.Forbidden:
        state.add_log("Levelling: missing permissions to swap level-10 role")
    except discord.HTTPException:
        state.add_log(f"Levelling: failed to swap level-10 role for {member}")


async def revoke_trust_role(member: discord.Member, cfg: dict | None = None):
    """Inverse of apply_trust_role: remove the level-10 role when a member is
    set below level 10. Safe to call repeatedly. Does NOT re-add the join role,
    since that role is meant for brand-new arrivals, not demotions."""
    if cfg is None:
        cfg = config.load()

    trust_role_id = cfg.get("trust_role")
    if not trust_role_id:
        return

    trust_role = member.guild.get_role(int(trust_role_id))
    if trust_role is None:
        return

    if trust_role.id not in {r.id for r in member.roles}:
        return  # nothing to do

    try:
        await member.remove_roles(trust_role, reason="Set below level 10")
    except discord.Forbidden:
        state.add_log("Levelling: missing permissions to remove level-10 role")
    except discord.HTTPException:
        state.add_log(f"Levelling: failed to remove level-10 role for {member}")


async def backfill_trust_roles(guild: discord.Guild):
    """Reconcile the level-10 role for the whole guild on startup.

    Adds the role to anyone at level 10+ who lacks it, and removes it from
    anyone below level 10 who still has it (e.g. demoted while the bot was
    offline, or whose XP was manually lowered). Members with no XP entry count
    as level 0.
    """
    cfg = config.load()
    trust_role_id = cfg.get("trust_role")
    if not trust_role_id:
        return

    trust_role = guild.get_role(int(trust_role_id))
    if trust_role is None:
        state.add_log("Levelling: backfill skipped — trust role not found in guild")
        return

    xp_data = storage.get_cached(TABLE)

    added = 0
    removed = 0
    for member in guild.members:
        if member.bot:
            continue

        xp = xp_data.get(str(member.id), 0)
        qualifies = level_for_xp(xp) >= 10
        has_role = trust_role.id in {r.id for r in member.roles}

        if qualifies and not has_role:
            await apply_trust_role(member, cfg)
            added += 1
        elif not qualifies and has_role:
            await revoke_trust_role(member, cfg)
            removed += 1

    state.add_log(
        f"Levelling: backfill reconciled trust role — added {added}, removed {removed}"
    )


# ---------------------------------------------------------------------------
# Manual override — typed in #floppystorage
#   set <user_id> level <n>
#   set <user_id> xp <n>
# Admin-only. Returns True if the message was a (valid or invalid) set command,
# so the caller knows to stop further processing.
# ---------------------------------------------------------------------------

async def handle_storage_command(message: discord.Message) -> bool:
    content = message.content.strip()
    parts = content.split()

    # Must look like: set <id> <level|xp> <number>
    if len(parts) != 4 or parts[0].lower() != "set":
        return False

    # Admin gate
    author = message.author
    if not (isinstance(author, discord.Member) and author.guild_permissions.administrator):
        await message.channel.send("❌ Only admins can set XP/level.")
        return True

    _, raw_id, mode, raw_value = parts
    mode = mode.lower()

    # Parse user id (accept raw id or a <@123> / <@!123> mention)
    digits = "".join(ch for ch in raw_id if ch.isdigit())
    if not digits:
        await message.channel.send("❌ Invalid user ID.")
        return True
    user_id = int(digits)

    if mode not in ("level", "xp"):
        await message.channel.send("❌ Use `set <user_id> level <n>` or `set <user_id> xp <n>`.")
        return True

    try:
        value = int(raw_value)
    except ValueError:
        await message.channel.send(f"❌ `{raw_value}` is not a number.")
        return True

    if value < 0:
        await message.channel.send("❌ Value must be 0 or greater.")
        return True

    if mode == "level":
        new_xp = xp_for_level(value) if value > 0 else 0
    else:  # xp
        new_xp = value

    await _set_user_xp(message.guild, user_id, new_xp)

    final_level = level_for_xp(new_xp)
    state.add_log(f"Levelling: admin {author} set user {user_id} -> {new_xp} XP (level {final_level})")

    member = message.guild.get_member(user_id)
    who = member.mention if member else f"`{user_id}`"
    # Auto-delete the confirmation so #floppystorage stays clean and the
    # permanent JSON message doesn't get pushed out of the history scan window.
    await message.channel.send(
        f"✅ Set {who} to **{new_xp} XP** (level **{final_level}**).",
        delete_after=10,
    )

    # Clean up the command message now that it succeeded.
    try:
        await message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass

    # Keep the level-10 role in sync with the new value — both directions.
    if member and not member.bot:
        cfg = config.load()
        if final_level >= 10:
            await apply_trust_role(member, cfg)
        else:
            await revoke_trust_role(member, cfg)

    return True


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
