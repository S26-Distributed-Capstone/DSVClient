#!/usr/bin/env python3
"""Distributed Secrets Vault command-line client.

Examples::

    dsvc ping
    dsvc create my-secret value authKey
    dsvc --script commands.txt
"""

import argparse
import json
import sys
from typing import Optional

from client import Client, ClientException
from config import load_config


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
    if len(args) != 3:
        _print_invalid_parameters("get", "get <secretName> <authKey>")
        return
    response = client.get_secret(args[1], args[2])
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
    print("  dsvc ping")
    print("  dsvc create <secretName> <secretValue> <authKey>")
    print("  dsvc get <secretName> <authKey>")
    print("  dsvc update <secretName> <updatedValue> <authKey>")
    print("  dsvc delete <secretName> <authKey>")
    print("  dsvc --script <file>")


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
# Execution mode
# ---------------------------------------------------------------------------


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

        if line.lower() == "help":
            _print_usage()
            continue

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
        "command",
        nargs=argparse.REMAINDER,
        help="command to execute (ping, create, get, update, delete)",
    )
    parsed = parser.parse_args()

    if parsed.script and parsed.command:
        parser.error("command arguments cannot be used together with --script")

    client = Client(load_config())

    if parsed.script:
        _run_script(client, parsed.script)
        return

    if not parsed.command:
        parser.print_help()
        print()
        _print_usage()
        return

    operation = parsed.command[0].lower()
    if operation == "help":
        _print_usage()
        return

    _run_command(client, parsed.command)


if __name__ == "__main__":
    main()
