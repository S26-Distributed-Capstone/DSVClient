# Distributed Secrets Vault Client

This `DSVClient` repository is a standalone project that represents the
external client system in the architecture of the Distributed Secrets Vault
project. The client is written in Python and runs as a CLI/TUI application.

## What it does

- Connects to the gateway over HTTP.
- Sends create / get / update / delete requests to `/api/v1/secrets`.
- Supports retrieving the latest secret value, a specific version, or all versions.
- Uses per-command `authKey` values for secret operation authentication.
- Retries retryable failures (`503`, `429`) with a configurable delay.
- Stores the server URL in `~/.dsv_client/config.json` so
  you only need to configure once.
- Accepts a script file of commands for batch / automation use.

## Requirements

- Python 3.10 or later (no third-party packages required — uses stdlib only).
- The Distributed Secrets Vault server must already be running.

## Project structure

| File | Purpose |
|------|---------|
| `cli.py` | Runnable CLI entry point (interactive and script modes). |
| `client.py` | Reusable HTTP client with the full secrets API. |
| `config.py` | Config load/save helpers and interactive setup wizard. |

## Setup wizard (optional)

Pass `--setup` (or run `setup` inside interactive mode) to have the wizard ask for:

1. **Server URL** — the base address of the DSV gateway (e.g. `http://localhost:8080`).

If you skip setup, the client still runs using default values.

## Run CLI (interactive)

```bash
python cli.py
```

You will be dropped into an interactive prompt:

```
dsv-client> ping
dsv-client> create my-secret value authKey
dsv-client> get my-secret authKey
dsv-client> get my-secret authKey 2
dsv-client> get my-secret authKey all
dsv-client> update my-secret new-value authKey
dsv-client> delete my-secret authKey
dsv-client> help
dsv-client> exit
```

Additional commands available in interactive mode:

| Command | Description |
|---------|-------------|
| `setup` | Re-run the server-URL / token setup wizard. |

## Run CLI with a script file

Pass `--script <file>` to execute a batch of commands non-interactively.
Lines starting with `#` and blank lines are ignored.

```bash
python cli.py --script commands.txt
```

Example `commands.txt`:

```text
# health check
ping

# create a secret
create db-password hunter2 myAuthKey

# retrieve it
get db-password myAuthKey

# retrieve a specific version
get db-password myAuthKey 2

# retrieve all versions
get db-password myAuthKey all

# update it
update db-password new-value myAuthKey

# remove it
delete db-password myAuthKey
```

## Run setup wizard explicitly

```bash
python cli.py --setup
```

## Available commands

```
ping
create <secretName> <secretValue> <authKey>
get <secretName> <authKey> [version|all]
update <secretName> <updatedValue> <authKey>
delete <secretName> <authKey>
setup
help
exit
```

All API commands print the response message body returned by the server. For `get`, the optional final argument retrieves a specific version or all versions.

## Configuration file

`~/.dsv_client/config.json` stores the following keys:

| Key | Default | Description |
|-----|---------|-------------|
| `base_url` | *(prompted)* | Gateway base URL |
| `connect_timeout` | `3.0` | Connection timeout in seconds |
| `read_timeout` | `5.0` | Read timeout in seconds |
| `max_retries` | `2` | Max retry attempts on 503/429 |
| `retry_delay` | `0.2` | Seconds to wait between retries |
| `debug_http` | `false` | Print request/response debug lines |
