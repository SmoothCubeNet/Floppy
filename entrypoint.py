import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve
from main import get_bot
from dash import app as dash_app
from messenger import messenger_app


async def main():
    bot, token = get_bot()

    dash_config = Config()
    dash_config.bind = ["0.0.0.0:8080"]

    messenger_config = Config()
    messenger_config.bind = ["0.0.0.0:8081"]

    await asyncio.gather(
        bot.start(token),
        serve(dash_app, dash_config),
        serve(messenger_app, messenger_config),
    )

if __name__ == "__main__":
    asyncio.run(main())
