import discord
from discord import app_commands

def setup(client: discord.Client):
    tree = app_commands.CommandTree(client)

    @tree.command(name="ping", description="Check the bot's latency")
    async def ping(interaction: discord.Interaction):
        latency = round(client.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! Latency is **{latency}ms**")

    return tree
