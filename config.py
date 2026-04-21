"""Configuration management for the DSV Client.

Settings are persisted in ~/.dsv_client/config.json so that the user is
prompted once for the server URL instead of
needing to export environment variables every session.
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".dsv_client"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: dict = {
    "base_url": "",
    "connect_timeout": 3.0,
    "read_timeout": 5.0,
    "max_retries": 2,
    "retry_delay": 0.2,
    "debug_http": False,
}


def _parse_bool_env(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _apply_environment_overrides(config: dict) -> dict:
    """Apply Java-compatible env var overrides to *config*.

    Supported variables match the Java client:
    - DSV_API_BASE_URL
    - DSV_CLIENT_CONNECT_TIMEOUT_MS
    - DSV_CLIENT_READ_TIMEOUT_MS
    - DSV_CLIENT_MAX_RETRIES
    - DSV_CLIENT_RETRY_DELAY_MS
    - DSV_CLIENT_DEBUG_HTTP
    """
    merged = dict(config)

    base_url = os.getenv("DSV_API_BASE_URL")
    if base_url and base_url.strip():
        merged["base_url"] = base_url.strip().rstrip("/")

    connect_timeout_ms = os.getenv("DSV_CLIENT_CONNECT_TIMEOUT_MS")
    if connect_timeout_ms and connect_timeout_ms.strip():
        try:
            merged["connect_timeout"] = float(connect_timeout_ms) / 1000.0
        except ValueError:
            pass

    read_timeout_ms = os.getenv("DSV_CLIENT_READ_TIMEOUT_MS")
    if read_timeout_ms and read_timeout_ms.strip():
        try:
            merged["read_timeout"] = float(read_timeout_ms) / 1000.0
        except ValueError:
            pass

    max_retries = os.getenv("DSV_CLIENT_MAX_RETRIES")
    if max_retries and max_retries.strip():
        try:
            merged["max_retries"] = int(max_retries)
        except ValueError:
            pass

    retry_delay_ms = os.getenv("DSV_CLIENT_RETRY_DELAY_MS")
    if retry_delay_ms and retry_delay_ms.strip():
        try:
            merged["retry_delay"] = float(retry_delay_ms) / 1000.0
        except ValueError:
            pass

    debug_http = _parse_bool_env("DSV_CLIENT_DEBUG_HTTP")
    if debug_http is not None:
        merged["debug_http"] = debug_http

    return merged


def load_config() -> dict:
    """Return the stored configuration, falling back to defaults."""
    if not CONFIG_FILE.exists():
        return _apply_environment_overrides(dict(DEFAULT_CONFIG))
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        config = dict(DEFAULT_CONFIG)
        config.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
        return _apply_environment_overrides(config)
    except (json.JSONDecodeError, OSError):
        return _apply_environment_overrides(dict(DEFAULT_CONFIG))


def save_config(config: dict) -> None:
    """Persist *config* to the config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)


def is_configured(config: dict) -> bool:
    """Return True when a non-blank server URL has been set."""
    return bool(config.get("base_url", "").strip())


def setup_wizard(config: dict) -> dict:
    """Interactively prompt the user for configuration values and save them.

    Returns the updated config dict.
    """
    print("=== DSV Client Setup ===")

    current_url = config.get("base_url", "")
    placeholder = current_url or "http://localhost:8080"
    raw = input(f"Server URL [{placeholder}]: ").strip()
    config["base_url"] = (raw or placeholder).rstrip("/")

    save_config(config)
    print(f"Configuration saved to {CONFIG_FILE}")
    return config
