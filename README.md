# Distributed Secrets Vault Client

This `DSVClient` repository is a standalone project that represents the
external client system in the architecture of the Distributed Secrets Vault
project. The client is written in Python and runs as a command-line tool.

## What it does

- Connects to the gateway over HTTP.
- Sends create / get / update / delete requests to `/api/v1/secrets`.
- Uses per-command `authKey` values for secret operation authentication.
- Retries retryable failures (`503`, `429`) with a configurable delay.
- Stores the server URL in `~/.dsv_client/config.json` so
  you only need to configure once.
- Accepts a script file of commands for batch / automation use.

## Requirements

- Python 3.10 or later (no third-party packages required — uses stdlib only).
- The Distributed Secrets Vault server must already be running.
- `curl` and `tar` for install script usage.

## Project structure

| File | Purpose |
|------|---------|
| `cli.py` | Runnable CLI entry point for direct command execution. |
| `client.py` | Reusable HTTP client with the full secrets API. |
| `config.py` | Config load/save helpers and interactive setup wizard. |
| `scripts/install.sh` | Curl-able installer that pulls from GitHub and installs `dsvc`. |
| `scripts/uninstall.sh` | Removes the installed runtime and launcher symlink. |

## Install (recommended)

Install directly from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/S26-Distributed-Capstone/DSVClient/main/scripts/install.sh | bash
```

Optional installer overrides:
- `DSVC_REF=<branch-or-tag>` to install from a different GitHub ref.
- `DSVC_TARBALL_URL=<url>` to install from an explicit tarball URL.

The installer:
- Downloads this repo from GitHub.
- Installs the source files into `~/.local/share/dsvc/src` (no pip install step).
- Creates `~/.local/bin/dsvc` so you can run `dsvc` from anywhere.
- Prompts for initial setup and writes `~/.dsv_client/config.json`.

If `~/.local/bin` is not on your `PATH`, add it in your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Run commands

Use one-shot command style:

```bash
dsvc ping
dsvc create my-secret value authKey
dsvc get my-secret authKey
dsvc update my-secret new-value authKey
dsvc delete my-secret authKey
```

With no arguments, `dsvc` shows help and exits.

## Batch mode

Pass `--script <file>` to execute a batch of commands non-interactively.
Lines starting with `#` and blank lines are ignored.

```bash
dsvc --script commands.txt
```

Example `commands.txt`:

```text
# health check
ping

# create a secret
create db-password hunter2 myAuthKey

# retrieve it
get db-password myAuthKey

# update it
update db-password new-value myAuthKey

# remove it
delete db-password myAuthKey
```

## Available commands

```
ping
create <secretName> <secretValue> <authKey>
get <secretName> <authKey>
update <secretName> <updatedValue> <authKey>
delete <secretName> <authKey>
```

All API commands print the response message body returned by the server.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/S26-Distributed-Capstone/DSVClient/main/scripts/uninstall.sh | bash
```

The uninstall script removes:
- `~/.local/bin/dsvc` (if it is a symlink)
- `~/.local/share/dsvc` runtime install directory
- optionally `~/.dsv_client/config.json` (prompted)

## Migration notes (`python cli.py` -> `dsvc`)

- Old usage: `python cli.py --script commands.txt`
- New usage: `dsvc --script commands.txt`
- Old usage: `python cli.py` interactive by default
- New usage: run one-shot commands directly, e.g. `dsvc ping`
- New install flow handles setup during installation.

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
