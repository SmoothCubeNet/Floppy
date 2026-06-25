import io
from quart import Blueprint, jsonify, request, send_from_directory
import os
import state

messenger_app = Blueprint('messenger', __name__)

# ---------------------------------------------------------------------------
# HTML PAGE
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@messenger_app.route("/")
async def index():
    here = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(here, "messenger.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    from quart import Response
    return Response(html, mimetype="text/html")


@messenger_app.route("/api/guild")
async def guild():
    import discord as _discord
    bot = state.bot
    if not bot or not bot.guilds:
        return jsonify({"channels": [], "categories": [], "members": [],
                        "guild_name": "", "guild_icon": None, "bot_name": "Floppy"})
    g = bot.guilds[0]

    # Channel type mapping
    TYPE_MAP = {
        _discord.ChannelType.text: "text",
        _discord.ChannelType.voice: "voice",
        _discord.ChannelType.news: "announcement",
        _discord.ChannelType.stage_voice: "stage",
        _discord.ChannelType.forum: "forum",
    }

    # All non-category channels sorted by position
    all_chans = sorted(
        [c for c in g.channels if not isinstance(c, _discord.CategoryChannel)],
        key=lambda c: (c.position if hasattr(c, "position") else 0)
    )

    channels = []
    for c in all_chans:
        ch_type = TYPE_MAP.get(c.type, str(c.type).replace("ChannelType.", ""))
        topic = getattr(c, "topic", None) or ""
        channels.append({
            "id": str(c.id),
            "name": c.name,
            "type": ch_type,
            "category_id": str(c.category_id) if getattr(c, "category_id", None) else None,
            "position": getattr(c, "position", 0),
            "topic": topic,
        })

    categories = [
        {"id": str(c.id), "name": c.name, "position": c.position}
        for c in sorted(g.categories, key=lambda c: c.position)
    ]

    guild_icon = str(g.icon.url) if g.icon else None
    bot_name = bot.user.display_name if bot.user else "Floppy"

    return jsonify({
        "channels": channels,
        "categories": categories,
        "members": [],
        "guild_name": g.name,
        "guild_icon": guild_icon,
        "bot_name": bot_name,
    })


@messenger_app.route("/api/members")
async def get_members():
    bot = state.bot
    if not bot or not bot.guilds:
        return jsonify({"members": []})
    g = bot.guilds[0]
    members = [
        {
            "id": str(m.id),
            "username": m.name,
            "display_name": m.display_name,
        }
        async for m in g.fetch_members(limit=1000)
        if not m.bot
    ]
    members.sort(key=lambda m: m["display_name"].lower())
    return jsonify({"members": members})


@messenger_app.route("/api/dms")
async def get_dms():
    bot = state.bot
    if not bot:
        return jsonify({"dms": []})
    dms = []
    for channel in bot.private_channels:
        if hasattr(channel, "recipient") and channel.recipient:
            u = channel.recipient
            dms.append({
                "user_id": str(u.id),
                "username": u.name,
                "display_name": u.display_name,
            })
    return jsonify({"dms": dms})


@messenger_app.route("/api/dm-messages/<int:user_id>")
async def get_dm_messages(user_id):
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503
    try:
        g = bot.guilds[0]
        member = g.get_member(user_id) or await g.fetch_member(user_id)
        dm = await member.create_dm()
        messages = []
        async for msg in dm.history(limit=60):
            if not msg.author:
                continue
            attachments = []
            for a in msg.attachments:
                is_image = a.content_type and a.content_type.startswith("image/")
                attachments.append({"name": a.filename, "url": a.url, "type": "image" if is_image else "file"})
            messages.append({
                "id": str(msg.id),
                "author": msg.author.display_name,
                "author_id": str(msg.author.id),
                "bot": msg.author.bot,
                "content": msg.content or "",
                "time": msg.created_at.strftime("%H:%M"),
                "timestamp": msg.created_at.timestamp(),
                "reply": None,
                "attachments": attachments,
                "reactions": [],
            })
        messages.reverse()
        return jsonify({"ok": True, "messages": messages})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@messenger_app.route("/api/dm-send", methods=["POST"])
async def dm_send():
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503

    form = await request.form
    files = await request.files
    user_id = form.get("user_id")
    content = form.get("content", "").strip()

    if not user_id:
        return jsonify({"ok": False, "error": "Missing user_id"}), 400
    if not content and not files.getlist("files"):
        return jsonify({"ok": False, "error": "Nothing to send"}), 400

    import discord as _discord
    try:
        g = bot.guilds[0]
        try:
            member = g.get_member(int(user_id)) or await g.fetch_member(int(user_id))
            dm = await member.create_dm()
        except (_discord.NotFound, _discord.HTTPException):
            # Fallback: fetch_member failed (e.g. Members Intent off), try fetch_user
            user = await bot.fetch_user(int(user_id))
            dm = await user.create_dm()
        discord_files = []
        for f in files.getlist("files"):
            discord_files.append(_discord.File(io.BytesIO(f.read()), filename=f.filename))
        await dm.send(
            content or None,
            files=discord_files if discord_files else _discord.utils.MISSING,
        )
        state.add_log(f"Messenger DM sent to user {user_id}")
        return jsonify({"ok": True})
    except _discord.Forbidden as e:
        return jsonify({"ok": False, "error": f"Forbidden — user may have DMs disabled ({e.text})"}), 403
    except _discord.NotFound:
        return jsonify({"ok": False, "error": "User not found"}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@messenger_app.route("/api/messages/<int:channel_id>")
async def get_messages(channel_id):
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503
    channel = bot.get_channel(channel_id)
    if not channel:
        return jsonify({"ok": False, "error": "Channel not found or no access"}), 404
    try:
        messages = []
        async for msg in channel.history(limit=60):
            if not msg.author:
                continue
            reply = None
            if msg.reference and msg.reference.resolved:
                ref = msg.reference.resolved
                if hasattr(ref, "content"):
                    reply = {
                        "id": str(ref.id),
                        "author": ref.author.display_name if hasattr(ref, "author") and ref.author else "Unknown",
                        "content": ref.content or "",
                    }
            attachments = []
            for a in msg.attachments:
                is_image = a.content_type and a.content_type.startswith("image/")
                attachments.append({
                    "name": a.filename,
                    "url": a.url,
                    "type": "image" if is_image else "file",
                })
            reactions = []
            for r in msg.reactions:
                reactions.append({
                    "emoji": str(r.emoji),
                    "count": r.count,
                })
            messages.append({
                "id": str(msg.id),
                "author": msg.author.display_name,
                "author_id": str(msg.author.id),
                "bot": msg.author.bot,
                "content": msg.content or "",
                "time": msg.created_at.strftime("%H:%M"),
                "timestamp": msg.created_at.timestamp(),
                "reply": reply,
                "attachments": attachments,
                "reactions": reactions,
            })
        messages.reverse()
        return jsonify({"ok": True, "messages": messages})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@messenger_app.route("/api/send", methods=["POST"])
async def send_message():
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503

    form = await request.form
    files = await request.files

    channel_id = form.get("channel_id")
    content = form.get("content", "").strip()
    reply_to = form.get("reply_to")

    if not channel_id:
        return jsonify({"ok": False, "error": "Missing channel_id"}), 400
    if not content and not files.getlist("files"):
        return jsonify({"ok": False, "error": "Nothing to send"}), 400
    if content and len(content) > 2000:
        return jsonify({"ok": False, "error": "Message exceeds 2000 chars"}), 400

    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({"ok": False, "error": "Channel not found"}), 404

    import discord as _discord

    try:
        reference = None
        if reply_to:
            try:
                ref_msg = await channel.fetch_message(int(reply_to))
                reference = ref_msg.to_reference()
            except Exception:
                pass

        # Build file objects
        discord_files = []
        for f in files.getlist("files"):
            data = f.read()
            discord_files.append(_discord.File(io.BytesIO(data), filename=f.filename))

        await channel.send(
            content or None,
            reference=reference,
            files=discord_files if discord_files else _discord.utils.MISSING,
        )
        state.add_log(f"Messenger sent to #{channel.name}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@messenger_app.route("/api/delete", methods=["POST"])
async def delete_message():
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503

    import discord as _discord

    payload = await request.get_json()
    message_id = payload.get("message_id")
    channel_id = payload.get("channel_id")   # server channel
    user_id    = payload.get("user_id")       # DM recipient

    if not message_id:
        return jsonify({"ok": False, "error": "Missing message_id"}), 400

    try:
        if user_id:
            # ── DM delete — bot can only delete its own messages ──
            g = bot.guilds[0]
            try:
                member = g.get_member(int(user_id)) or await g.fetch_member(int(user_id))
                dm = await member.create_dm()
            except (_discord.NotFound, _discord.HTTPException):
                user = await bot.fetch_user(int(user_id))
                dm = await user.create_dm()

            msg = await dm.fetch_message(int(message_id))
            if msg.author.id != bot.user.id:
                return jsonify({"ok": False, "error": "Can only delete the bot's own DM messages"}), 403
            await msg.delete()
            state.add_log(f"Messenger deleted DM message {message_id}")
            return jsonify({"ok": True})

        elif channel_id:
            # ── Server channel delete — needs Manage Messages ──
            channel = bot.get_channel(int(channel_id))
            if not channel:
                return jsonify({"ok": False, "error": "Channel not found"}), 404

            me = channel.guild.me
            perms = channel.permissions_for(me)
            if not perms.manage_messages and not perms.administrator:
                return jsonify({"ok": False, "error": "Bot lacks Manage Messages permission in this channel"}), 403

            msg = await channel.fetch_message(int(message_id))
            await msg.delete()
            state.add_log(f"Messenger deleted message {message_id} in #{channel.name}")
            return jsonify({"ok": True})

        else:
            return jsonify({"ok": False, "error": "Missing channel_id or user_id"}), 400

    except _discord.NotFound:
        return jsonify({"ok": False, "error": "Message not found (already deleted?)"}), 404
    except _discord.Forbidden as e:
        return jsonify({"ok": False, "error": f"Forbidden: {e.text}"}), 403
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@messenger_app.route("/api/voice-status")
async def voice_status():
    bot = state.bot
    if not bot:
        return jsonify({"connected": False})
    vc = bot.voice_clients[0] if bot.voice_clients else None
    if vc and vc.is_connected():
        return jsonify({
            "connected": True,
            "channel_id": str(vc.channel.id),
            "channel_name": vc.channel.name,
        })
    return jsonify({"connected": False})


@messenger_app.route("/api/voice-join", methods=["POST"])
async def voice_join():
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503

    import discord as _discord

    data = await request.get_json()
    channel_id = data.get("channel_id")
    if not channel_id:
        return jsonify({"ok": False, "error": "Missing channel_id"}), 400

    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({"ok": False, "error": "Channel not found"}), 404
    if not isinstance(channel, (_discord.VoiceChannel, _discord.StageChannel)):
        return jsonify({"ok": False, "error": "Not a voice channel"}), 400

    me = channel.guild.me
    perms = channel.permissions_for(me)
    if not perms.connect:
        return jsonify({"ok": False, "error": "Bot lacks Connect permission in this channel"}), 403

    try:
        existing = channel.guild.voice_client
        if existing and existing.is_connected():
            if existing.channel.id == channel.id:
                return jsonify({"ok": True, "channel_id": str(channel.id), "channel_name": channel.name})
            await existing.move_to(channel)
        else:
            await channel.connect()
        state.add_log(f"Messenger joined voice {channel.name}")
        return jsonify({"ok": True, "channel_id": str(channel.id), "channel_name": channel.name})
    except _discord.ClientException as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@messenger_app.route("/api/voice-leave", methods=["POST"])
async def voice_leave():
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503
    try:
        vc = bot.voice_clients[0] if bot.voice_clients else None
        if not vc or not vc.is_connected():
            return jsonify({"ok": True, "left": False})
        name = vc.channel.name
        await vc.disconnect(force=True)
        state.add_log(f"Messenger left voice {name}")
        return jsonify({"ok": True, "left": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@messenger_app.route("/api/react", methods=["POST"])
async def react():
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503

    data = await request.get_json()
    channel_id = data.get("channel_id")
    message_id = data.get("message_id")
    emoji = data.get("emoji")

    if not all([channel_id, message_id, emoji]):
        return jsonify({"ok": False, "error": "Missing fields"}), 400

    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({"ok": False, "error": "Channel not found"}), 404

    try:
        msg = await channel.fetch_message(int(message_id))
        await msg.add_reaction(emoji)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
