"""Configuration management for the DSV Client."""

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
    """Interactively configure the DSV client settings."""
    print("\n=== DSV Client Setup Wizard ===")

    # Get base URL
    current_url = config.get("base_url", "")
    url_prompt = f"Base URL [{current_url}]: " if current_url else "Base URL: "
    base_url = input(url_prompt).strip()
    if not base_url:
        base_url = current_url

    # Get username
    current_user = config.get("username", "")
    user_prompt = f"Username [{current_user}]: " if current_user else "Username: "
    username = input(user_prompt).strip()
    if not username:
        username = current_user

    # Update config
    config["base_url"] = base_url
    config["username"] = username

    # Save configuration
    save_config(config)
    print("Configuration saved.\n")

    return config
