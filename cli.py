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
import json
import sys
from typing import Optional

from client import Client, ClientException
from config import load_config, setup_wizard


# ---------------------------------------------------------------------------
# Command runners
# ---------------------------------------------------------------------------

def _run_ping(client: Client, args: list[str]) -> None:
    if len(args) != 1:
        _print_invalid_parameters("ping", "ping")
        return
    response = client.ping()
    _print_http_response(response)


def _run_create(client: Client, args: list[str]) -> None:
    if len(args) != 4:
        _print_invalid_parameters(
            "create", "create <secretName> <secretValue> <authKey>"
        )
        return
    response = client.create_secret(args[1], args[2], args[3])
    _print_http_response(response)


def _run_get(client: Client, args: list[str]) -> None:
    if len(args) not in (3, 4):
        _print_invalid_parameters("get", "get <secretName> <authKey> [version|all]")
        return
    if len(args) == 3:
        response = client.get_secret(args[1], args[2])
    elif args[3].lower() == "all":
        response = client.get_all_secret_versions(args[1], args[2])
    else:
        response = client.get_secret_version(args[1], args[3], args[2])
    _print_http_response(response)


def _run_update(client: Client, args: list[str]) -> None:
    if len(args) != 4:
        _print_invalid_parameters(
            "update", "update <secretName> <updatedValue> <authKey>"
        )
        return
    response = client.update_secret(args[1], args[2], args[3])
    _print_http_response(response)


def _run_delete(client: Client, args: list[str]) -> None:
    if len(args) != 3:
        _print_invalid_parameters("delete", "delete <secretName> <authKey>")
        return
    response = client.delete_secret(args[1], args[2])
    _print_http_response(response)


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
                print("Type 'help' to print commands.")
    except ClientException as exc:
        _print_request_failure(exc)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _print_usage() -> None:
    print("Usage:")
    print("  ping")
    print("  create <secretName> <secretValue> <authKey>")
    print("  get <secretName> <authKey> [version|all]")
    print("  update <secretName> <updatedValue> <authKey>")
    print("  delete <secretName> <authKey>")
    print("  setup")
    print("  help")
    print("  exit")


def _print_welcome() -> None:
    print("Distributed Secrets Vault Client CLI")
    print("Type a command and press Enter. Use 'help' to print commands.")


def _print_invalid_parameters(command: str, expected_usage: str) -> None:
    print(f"Invalid parameters for '{command}'.")
    print(f"Expected: {expected_usage}")


def _print_request_failure(exc: ClientException) -> None:
    if exc.response_body and exc.response_body.strip():
        _print_http_response(exc.response_body)
        return
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

        _run_command(client, _parse_line(line))


def _run_script(client: Client, script_file: str) -> None:
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

        if line.lower() == "setup":
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

    if parsed.setup:
        config = setup_wizard(config)

    client = Client(config)

    if parsed.script:
        _run_script(client, parsed.script)
    else:
        _interactive(client, config)


if __name__ == "__main__":
    main()
