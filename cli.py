#!/usr/bin/env python3
"""Distributed Secrets Vault command-line client.

Examples::

    dsvc ping
    dsvc login my-user
    dsvc create my-secret value
    dsvc --script commands.txt
"""

import argparse
import json
import sys
from typing import Optional

from client import Client, ClientException
from config import is_configured, is_logged_in, load_config, save_config

COMMAND_USAGE: dict[str, str] = {
    "help": "help",
    "ping": "ping",
    "login": "login <username>",
    "logout": "logout",
    "create": "create <secretName> <secretValue>",
    "get": "get <secretName>",
    "update": "update <secretName> <updatedValue>",
    "delete": "delete <secretName>",
}

COMMAND_ARGC: dict[str, int] = {
    "help": 1,
    "ping": 1,
    "login": 2,
    "logout": 1,
    "create": 3,
    "get": 2,
    "update": 3,
    "delete": 2,
}

COMMAND_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "ping": ("Check server connectivity.", "dsvc ping"),
    "login": ("Store the username and start a session.", "dsvc login my-user"),
    "logout": ("Clear the stored username and end the session.", "dsvc logout"),
    "create": ("Create a secret.", "dsvc create db-password hunter2"),
    "get": ("Retrieve a secret value.", "dsvc get db-password"),
    "update": ("Update an existing secret value.", "dsvc update db-password new-value"),
    "delete": ("Delete a secret.", "dsvc delete db-password"),
}

NO_LOGIN_REQUIRED = {"help", "login", "logout"}


# ---------------------------------------------------------------------------
# Command runners
# ---------------------------------------------------------------------------

def _run_ping(client: Client, args: list[str]) -> None:
    response = client.ping()
    _print_http_response(response)


def _run_create(client: Client, args: list[str], username: str) -> None:
    response = client.create_secret(args[1], args[2], username)
    _print_http_response(response)


def _run_get(client: Client, args: list[str], username: str) -> None:
    response = client.get_secret(args[1], username)
    _print_http_response(response)


def _run_update(client: Client, args: list[str], username: str) -> None:
    response = client.update_secret(args[1], args[2], username)
    _print_http_response(response)


def _run_delete(client: Client, args: list[str], username: str) -> None:
    try:
        client.delete_secret(args[1], username)
        print("Delete succeeded (HTTP 204 No Content).")
    except ClientException as exc:
        _print_delete_failure(exc)


def _run_login(config: dict, args: list[str]) -> dict:
    if is_logged_in(config):
        current_user = str(config.get("username", "")).strip()
        print(f"Already logged in as '{current_user}'.")
        print("Please run 'dsvc logout' before logging in again.")
        return config

    username = args[1].strip()
    if not username:
        print("Username cannot be empty.")
        return config

    config["username"] = username
    save_config(config)
    print(f"Logged in as '{username}'.")
    return config


def _run_logout(config: dict, args: list[str]) -> dict:
    if not str(config.get("username", "")).strip():
        print("You are already logged out.")
        return config

    config["username"] = ""
    save_config(config)
    print("Logged out.")
    return config


def _requires_login(operation: str) -> bool:
    return operation not in NO_LOGIN_REQUIRED


def _validate_command_arguments(args: list[str]) -> bool:
    if not args:
        return False
    command = args[0].lower()
    expected_count = COMMAND_ARGC.get(command)
    if expected_count is None:
        return True
    if len(args) == expected_count:
        return True
    _print_invalid_parameters(command, COMMAND_USAGE[command])
    return False


def _print_missing_server_configuration() -> None:
    print("Server URL is not configured.")
    print("Set 'base_url' in ~/.dsv_client/config.json or run the installer setup again.")


def _run_command(client: Optional[Client], config: dict, args: list[str]) -> dict:
    if not args:
        return config
    operation = args[0].lower()

    if operation == "help":
        if not _validate_command_arguments(args):
            return config
        _print_usage()
        return config

    if operation == "login":
        if not _validate_command_arguments(args):
            return config
        return _run_login(config, args)
    if operation == "logout":
        if not _validate_command_arguments(args):
            return config
        return _run_logout(config, args)

    if not _validate_command_arguments(args):
        return config

    if _requires_login(operation) and not is_logged_in(config):
        print("Please log in first: dsvc login <username>")
        return config

    username = str(config.get("username", "")).strip()

    if client is None:
        print("Internal error: client is required for this command.")
        return config

    try:
        match operation:
            case "ping":
                _run_ping(client, args)
            case "create":
                _run_create(client, args, username)
            case "get":
                _run_get(client, args, username)
            case "update":
                _run_update(client, args, username)
            case "delete":
                _run_delete(client, args, username)
            case _:
                print(f"Unknown command: {args[0]}")
                print("Type 'help' to print commands.")
    except ClientException as exc:
        _print_request_failure(exc)
    return config


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _print_usage() -> None:
    print("DSV Client usage")
    print()
    print("Run one command at a time:")
    print("  dsvc <command> [arguments]")
    print()
    print("Commands:")
    for command in ("ping", "login", "logout", "create", "get", "update", "delete"):
        description, example = COMMAND_DESCRIPTIONS[command]
        print(f"  {COMMAND_USAGE[command]}")
        print(f"      {description}")
        print(f"      Example: {example}")
        print()
    print("Batch mode:")
    print("  dsvc --script <file>")
    print("      Run commands from a file, one command per line.")
    print("      Lines starting with '#' and empty lines are ignored.")
    print()
    print("Authentication:")
    print("  - Run 'dsvc login <username>' before running API commands.")
    print("  - The username is stored in ~/.dsv_client/config.json.")


def _print_invalid_parameters(command: str, expected_usage: str) -> None:
    print(f"Invalid parameters for '{command}'.")
    print(f"Expected: {expected_usage}")


def _print_request_failure(exc: ClientException) -> None:
    if exc.response_body and exc.response_body.strip():
        _print_http_response(exc.response_body)
        return
    print(str(exc))


def _print_delete_failure(exc: ClientException) -> None:
    if exc.status_code > 0:
        reason = f" {exc.reason}" if exc.reason else ""
        print(f"Delete failed (HTTP {exc.status_code}{reason}).")
        if exc.response_body and exc.response_body.strip():
            _print_http_response(exc.response_body)
        return

    print("Delete failed (request error).")
    print(str(exc))


def _print_http_response(body: str) -> None:
    if body and body.strip():
        print(_extract_response_message(body))
    else:
        print("(no response body)")


def _extract_response_message(body: str) -> str:
    """Return a user-friendly message extracted from a response body."""
    text = body.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text

    if isinstance(payload, str):
        return payload

    if isinstance(payload, dict):
        if "message" in payload:
            value = payload.get("message")
            return str(value) if value is not None else ""

        if len(payload) == 1:
            value = next(iter(payload.values()))
            if isinstance(value, (str, int, float, bool)) or value is None:
                return "" if value is None else str(value)

    return text


# ---------------------------------------------------------------------------
# Line parser (handles quoted tokens)
# ---------------------------------------------------------------------------

def _parse_line(line: str) -> list[str]:
    """Split *line* into tokens, respecting single- and double-quoted strings."""
    tokens: list[str] = []
    current: list[str] = []
    in_quotes = False
    quote_char: Optional[str] = None

    for ch in line:
        if ch in ('"', "'") and not in_quotes:
            in_quotes = True
            quote_char = ch
        elif ch == quote_char and in_quotes:
            in_quotes = False
            quote_char = None
        elif ch.isspace() and not in_quotes:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)

    if current:
        tokens.append("".join(current))

    return tokens


# ---------------------------------------------------------------------------
# Execution mode
# ---------------------------------------------------------------------------


def _run_script(script_file: str) -> None:
    """Execute commands from *script_file*, one per line."""
    try:
        with open(script_file, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        print(f"Error reading script file: {exc}", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    client: Optional[Client] = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        args = _parse_line(line)
        if not args:
            continue

        operation = args[0].lower()
        active_client: Optional[Client] = None
        if _requires_login(operation):
            if not is_configured(config):
                _print_missing_server_configuration()
                continue
            if client is None:
                client = Client(config)
            active_client = client

        config = _run_command(active_client, config, args)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dsvc", description="Distributed Secrets Vault CLI Client"
    )
    parser.add_argument(
        "--script",
        metavar="FILE",
        help="path to a script file with commands to execute (one per line)",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="command to execute (help, login, logout, ping, create, get, update, delete)",
    )
    parsed = parser.parse_args()

    if parsed.script and parsed.command:
        parser.error("command arguments cannot be used together with --script")

    if parsed.script:
        _run_script(parsed.script)
        return

    if not parsed.command:
        parser.print_help()
        print()
        _print_usage()
        return

    config = load_config()
    client: Optional[Client] = None
    operation = parsed.command[0].lower()
    if _requires_login(operation):
        if not is_configured(config):
            _print_missing_server_configuration()
            return
        client = Client(config)
    _run_command(client, config, parsed.command)


if __name__ == "__main__":
    main()
