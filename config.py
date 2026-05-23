import json
import os

CONFIG_FILE = "config.json"

DEFAULTS = {
    "welcome_channel": None,
    "welcome_message": "Welcome {mention} to {server}!",
    "goodbye_channel": None,
    "goodbye_message": "Goodbye {name}, we'll miss you!",
    "join_role": None,
    "audit_log_channel": None,
}

def load():
    if not os.path.exists(CONFIG_FILE):
        save(DEFAULTS.copy())
        return DEFAULTS.copy()
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
