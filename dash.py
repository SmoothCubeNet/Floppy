from quart import Quart
import state

app = Quart(__name__)

@app.route("/")
async def index():
    if state.bot_ready:
        return "<h1>🟢 Floppy is online</h1>", 200
    else:
        return "<h1>🔴 Floppy is offline</h1>", 503
