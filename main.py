import discord
import os
import asyncio
import itertools
from dotenv import load_dotenv

load_dotenv()

STATUSES = [
    "🫧 floating around",
    "🐟 flopping about",
    "🗄️ peeking at the database",
    "🔌 poking the API",
    "🔍 searching for new messages",
    "📋 reading server logs",
]

STATUS_INTERVAL = 600


class Floppy(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._status_cycle = itertools.cycle(STATUSES)
        self._status_task: asyncio.Task | None = None

    async def setup_hook(self):
        self._status_task = asyncio.create_task(self._cycle_status())

    async def close(self):
        if self._status_task and not self._status_task.done():
            self._status_task.cancel()
            try:
                await self._status_task
            except asyncio.CancelledError:
                pass
        await super().close()

    async def _cycle_status(self):
        await self.wait_until_ready()

        while True:
            try:
                if not self.is_closed():
                    await self.change_presence(
                        activity=discord.CustomActivity(
                            name=next(self._status_cycle)
                        )
                    )
                await asyncio.sleep(STATUS_INTERVAL)

            except asyncio.CancelledError:
                break

            except Exception as e:
                print(f"⚠️ Status task error: {e}")
                await asyncio.sleep(10)  # prevent tight crash loop

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

    async def on_disconnect(self):
        print("⚠️ Disconnected from Discord...")

    async def on_resumed(self):
        print("🔄 Connection resumed!")

    async def on_connect(self):
        print("🌐 Connected to Discord gateway")


def main():
    token = os.getenv("TOKEN")
    if not token:
        raise ValueError("TOKEN environment variable is not set")

    intents = discord.Intents.default()
    intents.message_content = True

    floppy = Floppy(intents=intents)

    # reconnect=True is default, but being explicit is nice
    floppy.run(token, reconnect=True)


if __name__ == "__main__":
    main()
