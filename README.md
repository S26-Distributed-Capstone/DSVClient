# Distributed Secrets Vault Client

`DSVClient` is the command-line client for interacting with the Distributed
Secrets Vault gateway.

## Requirements

- Python 3.10 or later
- A running Distributed Secrets Vault server
- `curl` (for install/uninstall scripts)

## Install

Install directly from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/S26-Distributed-Capstone/DSVClient/main/scripts/install.sh | bash
```

The installer:

- Downloads `cli.py`, `client.py`, and `config.py`
- Installs runtime files into `~/.local/share/dsvc`
- Installs `dsvc` into `/usr/local/bin` (if writable) or `~/.local/bin`
- Prompts for initial `base_url` and `username`
- Writes config to `~/.dsv_client/config.json`

If `~/.local/bin` is not on your `PATH`, add:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Usage

Run command help:

```bash
dsvc help
```

### Authentication commands

```bash
dsvc login <username>
dsvc logout
```

Notes:

- You must be logged in before running API commands.
- You must run `logout` before logging in as a different user.

### API commands

```bash
dsvc ping
dsvc create <secretName> <secretValue>
dsvc get <secretName>
dsvc update <secretName> <updatedValue>
dsvc delete <secretName>
```

Examples:

```bash
dsvc login alice
dsvc ping
dsvc create db-password hunter2
dsvc get db-password
dsvc update db-password new-value
dsvc delete db-password
dsvc logout
```

With no arguments, `dsvc` prints help and exits.

## Batch mode

Use `--script <file>` to run commands from a file:

```bash
dsvc --script commands.txt
```

Rules:

- One command per line
- Blank lines are ignored
- Lines starting with `#` are ignored

Example `commands.txt`:

```text
# start session
login alice

# health check
ping

# create a secret
create db-password hunter2

# retrieve it
get db-password

# update it
update db-password new-value

# remove it
delete db-password

# end session
logout
```

## Configuration

`~/.dsv_client/config.json` stores:

- `base_url`: gateway base URL
- `username`: current logged-in username

HTTP timeout, retry, and debug behavior are hardcoded in the client with
internal defaults.

## Run tests

From the repo root:

```bash
python3 -m unittest tests/test_cli.py
```

Or discover all tests under `tests/`:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/S26-Distributed-Capstone/DSVClient/main/scripts/uninstall.sh | bash
```

The uninstall script removes:

- `dsvc` launcher symlink
- Installed runtime directory
- Optional client config (prompted)
