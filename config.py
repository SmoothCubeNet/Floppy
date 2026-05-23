import json
import os

CONFIG_FILE = "config.json"

DEFAULTS = {
    "welcome_channel": None,
    "welcome_message": "Welcome {mention} to {server}! 🎉",
    "goodbye_channel": None,
    "goodbye_message": "Goodbye {mention}, we'll miss you! 👋",
    "join_role": None,
    "audit_log_channel": None,
}

def load():
    if not os.path.exists(CONFIG_FILE):
        save(DEFAULTS.copy())
        return DEFAULTS.copy()
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    # fill in any missing keys
    for k, v in DEFAULTS.items():
        if k not in data:
            data[k] = v
    return data

def save(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
