import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve
from main import get_bot
from dash import app

async def main():
    bot, token = get_bot()

    hypercorn_config = Config()
    hypercorn_config.bind = ["0.0.0.0:8080"]

    await asyncio.gather(
        bot.start(token),
        serve(app, hypercorn_config),
    )

if __name__ == "__main__":
    asyncio.run(main())
