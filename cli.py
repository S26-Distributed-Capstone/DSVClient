#!/usr/bin/env python3
"""Distributed Secrets Vault — Python CLI client.

Usage
-----
Interactive mode (prompts for commands one at a time)::

    python cli.py

Batch / script mode (reads commands from a file)::

    python cli.py --script commands.txt

Run the setup wizard explicitly::

    python cli.py --setup
"""

import argparse
import sys
from typing import Optional

from client import Client, ClientException
from config import is_configured, load_config, save_config, setup_wizard


# ---------------------------------------------------------------------------
# Command runners
# ---------------------------------------------------------------------------

def _run_ping(client: Client, args: list[str]) -> None:
    if len(args) != 1:
        _print_usage()
        return
    response = client.ping()
    print(response if response.strip() else "OK")


def _run_create(client: Client, args: list[str]) -> None:
    if len(args) != 4:
        _print_usage()
        return
    print(client.create_secret(args[1], args[2], args[3]))


def _run_get(client: Client, args: list[str]) -> None:
    if len(args) != 3:
        _print_usage()
        return
    print(client.get_secret(args[1], args[2]))


def _run_update(client: Client, args: list[str]) -> None:
    if len(args) != 4:
        _print_usage()
        return
    print(client.update_secret(args[1], args[2], args[3]))


def _run_delete(client: Client, args: list[str]) -> None:
    if len(args) != 3:
        _print_usage()
        return
    response = client.delete_secret(args[1], args[2])
    print(response if response.strip() else "Delete succeeded (no response body).")


def _run_command(client: Client, args: list[str]) -> None:
    if not args:
        return
    operation = args[0].lower()
    try:
        match operation:
            case "ping":
                _run_ping(client, args)
            case "create":
                _run_create(client, args)
            case "get":
                _run_get(client, args)
            case "update":
                _run_update(client, args)
            case "delete":
                _run_delete(client, args)
            case _:
                print(f"Unknown command: {args[0]}")
                _print_usage()
    except ClientException as exc:
        _print_request_failure(exc)


# ---------------------------------------------------------------------------
# Login helper
# ---------------------------------------------------------------------------

def _run_login(config: dict) -> tuple[dict, Client]:
    """Prompt for a bearer token, persist it, and return an updated client."""
    print("=== Login ===")
    token = input("Bearer token: ").strip()
    if token:
        config["bearer_token"] = token
        save_config(config)
        print("Token saved.")
    else:
        print("No token provided; login cancelled.")
    return config, Client(config)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _print_usage() -> None:
    print("Usage:")
    print("  ping")
    print("  create <secretName> <secretValue> <authKey>")
    print("  get <secretName> <authKey>")
    print("  update <secretName> <updatedValue> <authKey>")
    print("  delete <secretName> <authKey>")
    print("  login")
    print("  setup")
    print("  help")
    print("  exit")


def _print_welcome() -> None:
    print("Distributed Secrets Vault Client CLI")
    print("Type a command and press Enter. Use 'help' to print commands.")


def _print_request_failure(exc: ClientException) -> None:
    print(f"Request failed: {exc}", file=sys.stderr)
    if exc.status_code > 0:
        print(f"Status: {exc.status_code}", file=sys.stderr)
    if exc.response_body and exc.response_body.strip():
        print(f"Body: {exc.response_body}", file=sys.stderr)


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
# Execution modes
# ---------------------------------------------------------------------------

def _interactive(client: Client, config: dict) -> None:
    """Run the interactive REPL."""
    _print_welcome()
    _print_usage()

    while True:
        try:
            line = input("dsv-client> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not line:
            continue

        if line.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        if line.lower() == "help":
            _print_usage()
            continue

        if line.lower() == "setup":
            config = setup_wizard(config)
            client = Client(config)
            continue

        if line.lower() == "login":
            config, client = _run_login(config)
            continue

        _run_command(client, _parse_line(line))


def _run_script(client: Client, config: dict, script_file: str) -> None:
    """Execute commands from *script_file*, one per line."""
    try:
        with open(script_file, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        print(f"Error reading script file: {exc}", file=sys.stderr)
        sys.exit(1)

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.lower() in ("exit", "quit"):
            break

        if line.lower() == "help":
            _print_usage()
            continue

        if line.lower() in ("setup", "login"):
            print(
                f"'{line}' command is not supported in script mode.",
                file=sys.stderr,
            )
            continue

        print(f"dsv-client> {line}")
        _run_command(client, _parse_line(line))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Distributed Secrets Vault CLI Client"
    )
    parser.add_argument(
        "--script",
        metavar="FILE",
        help="path to a script file with commands to execute (one per line)",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="run the setup wizard before starting",
    )
    parsed = parser.parse_args()

    config = load_config()

    if parsed.setup or not is_configured(config):
        config = setup_wizard(config)

    client = Client(config)

    if parsed.script:
        _run_script(client, config, parsed.script)
    else:
        _interactive(client, config)


if __name__ == "__main__":
    main()
