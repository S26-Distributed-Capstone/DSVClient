"""Configuration management for the DSV Client.

Settings are persisted in ~/.dsv_client/config.json so that the user is
prompted once for the server URL instead of re-entering it every session.
"""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".dsv_client"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: dict = {
    "base_url": "",
    "username": "",
}

def load_config() -> dict:
    """Return the stored configuration, falling back to defaults."""
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        config = dict(DEFAULT_CONFIG)
        config.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
        return config
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    """Persist *config* to the config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)


def is_configured(config: dict) -> bool:
    """Return True when a non-blank server URL has been set."""
    return bool(config.get("base_url", "").strip())


def is_logged_in(config: dict) -> bool:
    """Return True when a non-blank username has been set."""
    return bool(str(config.get("username", "")).strip())


def setup_wizard(config: dict) -> dict:
    """Interactively prompt the user for configuration values and save them.

    Returns the updated config dict.
    """
    print("=== DSV Client Setup ===")

    current_url = config.get("base_url", "")
    placeholder = current_url or "http://localhost:8080"
    raw = input(f"Server URL [{placeholder}]: ").strip()
    config["base_url"] = (raw or placeholder).rstrip("/")

    current_user = str(config.get("username", "")).strip()
    user_placeholder = current_user or "your-username"
    user_raw = input(f"Username [{user_placeholder}]: ").strip()
    config["username"] = user_raw or current_user

    save_config(config)
    print(f"Configuration saved to {CONFIG_FILE}")
    return config
