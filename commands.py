import discord
from discord import app_commands
import config

def setup(client: discord.Client):
    tree = app_commands.CommandTree(client)

    @tree.command(name="ping", description="Check the bot's latency")
    async def ping(interaction: discord.Interaction):
        latency = round(client.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! Latency is **{latency}ms**")

    @tree.command(name="purge", description="Delete messages in this channel from a given message ID up to now")
    @app_commands.describe(message_id="The ID of the oldest message to delete (right-click a message → Copy Message ID)")
    async def purge(interaction: discord.Interaction, message_id: str):
        cfg = config.load()
        staff_role_ids = cfg.get("ticket_staff_roles", [])
        is_staff = any(str(r.id) in [str(x) for x in staff_role_ids] for r in interaction.user.roles)
        if not is_staff:
            await interaction.response.send_message("❌ Only staff can use this command.", ephemeral=True)
            return

        try:
            after_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ That doesn't look like a valid message ID.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Fetch the anchor message so we can include it in the purge
        try:
            anchor = await interaction.channel.fetch_message(after_id)
        except discord.NotFound:
            await interaction.followup.send("❌ Couldn't find that message in this channel.", ephemeral=True)
            return

        # Collect messages from the anchor onwards (inclusive)
        to_delete = []
        async for msg in interaction.channel.history(limit=None, after=anchor, oldest_first=True):
            to_delete.append(msg)
        to_delete.insert(0, anchor)  # include the anchor itself

        if not to_delete:
            await interaction.followup.send("Nothing to delete.", ephemeral=True)
            return

        # bulk_delete only works for messages under 14 days; delete older ones individually
        from datetime import datetime, timezone, timedelta
        cutoff = discord.utils.utcnow() - timedelta(days=14)
        bulk = [m for m in to_delete if m.created_at > cutoff]
        slow = [m for m in to_delete if m.created_at <= cutoff]

        deleted = 0
        # Bulk delete in chunks of 100
        for i in range(0, len(bulk), 100):
            chunk = bulk[i:i + 100]
            if len(chunk) == 1:
                await chunk[0].delete()
            else:
                await interaction.channel.delete_messages(chunk)
            deleted += len(chunk)

        for msg in slow:
            try:
                await msg.delete()
                deleted += 1
            except discord.NotFound:
                pass

        await interaction.followup.send(f"🗑️ Deleted **{deleted}** message(s).", ephemeral=True)

    return tree
