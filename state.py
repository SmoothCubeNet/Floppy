from collections import deque

bot_ready: bool = False
bot: object = None
logs: deque = deque(maxlen=25)

def add_log(message: str):
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    logs.appendleft(f"[{ts}] {message}")
