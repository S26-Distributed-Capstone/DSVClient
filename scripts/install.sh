#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/dsvc"
SRC_DIR="$RUNTIME_ROOT/src"
RUNTIME_BIN_DIR="$RUNTIME_ROOT/bin"
if [[ -w /usr/local/bin ]]; then
  BIN_DIR="/usr/local/bin"
else
  BIN_DIR="$HOME/.local/bin"
fi
CONFIG_DIR="$HOME/.dsv_client"
CONFIG_FILE="$CONFIG_DIR/config.json"
RAW_BASE_URL="https://raw.githubusercontent.com/S26-Distributed-Capstone/DSVClient/main"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command '$1' is not installed." >&2
    exit 1
  fi
}

download_python_sources() {
  local files=("cli.py" "client.py" "config.py")
  local file=""

  mkdir -p "$SRC_DIR"
  for file in "${files[@]}"; do
    curl -fsSL "${RAW_BASE_URL}/${file}" -o "${SRC_DIR}/${file}"
  done
}

configure_client() {
  local default_base_url="http://localhost:8080"
  local entered_base_url=""
  local entered_username=""

  if [[ -f "$CONFIG_FILE" ]]; then
    read -r entered_base_url entered_username < <(python3 - <<'PY' "$CONFIG_FILE"
import json
import pathlib
import sys

config_file = pathlib.Path(sys.argv[1])
try:
    data = json.loads(config_file.read_text(encoding="utf-8"))
except Exception:
    data = {}
base_url = str(data.get("base_url", "")).strip()
username = str(data.get("username", "")).strip()
print(base_url, username)
PY
)
  fi

  local placeholder="$default_base_url"
  if [[ -n "$entered_base_url" ]]; then
    placeholder="$entered_base_url"
  fi

  if [[ -t 0 ]]; then
    if ! read -r -p "Server URL [${placeholder}]: " entered_base_url; then
      entered_base_url="$placeholder"
    fi
  elif [[ -r /dev/tty ]]; then
    if ! read -r -p "Server URL [${placeholder}]: " entered_base_url < /dev/tty; then
      entered_base_url="$placeholder"
    fi
  else
    echo "No interactive terminal detected. Using default server URL: ${placeholder}"
    entered_base_url="$placeholder"
  fi

  entered_base_url="${entered_base_url:-$placeholder}"
  entered_base_url="${entered_base_url%/}"

  local username_placeholder="${entered_username:-your-username}"
  if [[ -t 0 ]]; then
    if ! read -r -p "Username [${username_placeholder}]: " entered_username; then
      entered_username="$username_placeholder"
    fi
  elif [[ -r /dev/tty ]]; then
    if ! read -r -p "Username [${username_placeholder}]: " entered_username < /dev/tty; then
      entered_username="$username_placeholder"
    fi
  else
    echo "No interactive terminal detected. Username will not be preconfigured."
    entered_username="${entered_username:-}"
  fi

  entered_username="${entered_username:-}"

  mkdir -p "$CONFIG_DIR"
  python3 - <<'PY' "$CONFIG_FILE" "$entered_base_url" "$entered_username"
import json
import pathlib
import sys

config_file = pathlib.Path(sys.argv[1])
base_url = sys.argv[2].strip() or "http://localhost:8080"
username = sys.argv[3].strip()
config = {
    "base_url": base_url.rstrip("/"),
    "username": username,
}
config_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
}

main() {
  require_cmd curl
  require_cmd python3

  mkdir -p "$RUNTIME_ROOT"
  rm -rf "$SRC_DIR"
  download_python_sources

  if [[ ! -f "$SRC_DIR/cli.py" || ! -f "$SRC_DIR/client.py" || ! -f "$SRC_DIR/config.py" ]]; then
    echo "Error: downloaded source does not contain expected Python client files." >&2
    echo "Unable to fetch expected sources from GitHub." >&2
    exit 1
  fi

  mkdir -p "$RUNTIME_BIN_DIR"
  cat > "$RUNTIME_BIN_DIR/dsvc" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec python3 "$SRC_DIR/cli.py" "\$@"
EOF
  chmod +x "$RUNTIME_BIN_DIR/dsvc"

  mkdir -p "$BIN_DIR"
  ln -sfn "$RUNTIME_BIN_DIR/dsvc" "$BIN_DIR/dsvc"

  echo "Configure DSV client:"
  configure_client

  echo
  echo "Installed dsvc to $BIN_DIR/dsvc"
  if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "Add $BIN_DIR to your PATH to run 'dsvc' globally."
  fi
  if [[ "$BIN_DIR" == "/usr/local/bin" ]]; then
    echo "Command is available system-wide as 'dsvc'."
  fi
  echo "Run: dsvc --help"
}

main "$@"
