#!/usr/bin/env bash
set -euo pipefail

DSVC_GITHUB_REPO="${DSVC_GITHUB_REPO:-S26-Distributed-Capstone/DSVClient}"
DSVC_REF="${DSVC_REF:-main}"
DSVC_RAW_BASE_URL="${DSVC_RAW_BASE_URL:-}"
DSVC_BASE_URL="${DSVC_BASE_URL:-}"
RUNTIME_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/dsvc"
SRC_DIR="$RUNTIME_ROOT/src"
RUNTIME_BIN_DIR="$RUNTIME_ROOT/bin"
if [[ -n "${DSVC_BIN_DIR:-}" ]]; then
  BIN_DIR="${DSVC_BIN_DIR}"
elif [[ -w /usr/local/bin ]]; then
  BIN_DIR="/usr/local/bin"
else
  BIN_DIR="$HOME/.local/bin"
fi
CONFIG_DIR="$HOME/.dsv_client"
CONFIG_FILE="$CONFIG_DIR/config.json"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command '$1' is not installed." >&2
    exit 1
  fi
}

raw_base_url() {
  if [[ -n "$DSVC_RAW_BASE_URL" ]]; then
    printf "%s" "${DSVC_RAW_BASE_URL%/}"
    return 0
  fi
  printf "https://raw.githubusercontent.com/%s/%s" "$DSVC_GITHUB_REPO" "$DSVC_REF"
}

download_python_sources() {
  local base_url
  base_url="$(raw_base_url)"
  local files=("cli.py" "client.py" "config.py")
  local file=""

  mkdir -p "$SRC_DIR"
  for file in "${files[@]}"; do
    curl -fsSL "${base_url}/${file}" -o "${SRC_DIR}/${file}"
  done
}

configure_client() {
  local default_base_url="http://localhost:8080"
  local entered_base_url=""

  if [[ -f "$CONFIG_FILE" ]]; then
    entered_base_url="$(python3 - <<'PY' "$CONFIG_FILE"
import json
import pathlib
import sys

config_file = pathlib.Path(sys.argv[1])
try:
    data = json.loads(config_file.read_text(encoding="utf-8"))
except Exception:
    data = {}
value = str(data.get("base_url", "")).strip()
print(value, end="")
PY
)"
  fi

  local placeholder="$default_base_url"
  if [[ -n "$entered_base_url" ]]; then
    placeholder="$entered_base_url"
  fi

  if [[ -n "$DSVC_BASE_URL" ]]; then
    entered_base_url="$DSVC_BASE_URL"
  elif [[ -t 0 ]]; then
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

  mkdir -p "$CONFIG_DIR"
  python3 - <<'PY' "$CONFIG_FILE" "$entered_base_url"
import json
import pathlib
import sys

config_file = pathlib.Path(sys.argv[1])
base_url = sys.argv[2].strip() or "http://localhost:8080"
config = {
    "base_url": base_url.rstrip("/"),
    "connect_timeout": 3.0,
    "read_timeout": 5.0,
    "max_retries": 2,
    "retry_delay": 0.2,
    "debug_http": False,
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
    echo "Check DSVC_GITHUB_REPO/DSVC_REF (or provide DSVC_RAW_BASE_URL)." >&2
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
