#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/dsvc"
DEFAULT_USER_BIN="$HOME/.local/bin"
CONFIG_DIR="$HOME/.dsv_client"

remove_launchers() {
  local -a candidates=("/usr/local/bin/dsvc" "${DEFAULT_USER_BIN}/dsvc")
  local candidate=""
  local removed_count=0

  for candidate in "${candidates[@]}"; do
    if [[ -e "$candidate" || -L "$candidate" ]]; then
      rm -f "$candidate" && {
        echo "Removed launcher: $candidate"
        removed_count=$((removed_count + 1))
      }
    fi
  done

  if (( removed_count == 0 )); then
    echo "Launcher not found in expected paths."
  fi
}

remove_config() {
  if [[ -d "$CONFIG_DIR" ]]; then
    rm -rf "$CONFIG_DIR"
    echo "Removed config directory: $CONFIG_DIR"
  else
    echo "Config directory not found: $CONFIG_DIR"
  fi
}

main() {
  remove_launchers

  if [[ -d "$RUNTIME_ROOT" ]]; then
    rm -rf "$RUNTIME_ROOT"
    echo "Removed runtime: $RUNTIME_ROOT"
  else
    echo "Runtime directory not found: $RUNTIME_ROOT"
  fi

  remove_config
}

main "$@"
