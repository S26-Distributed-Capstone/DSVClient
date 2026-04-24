#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/dsvc"
RUNTIME_BIN_DIR="$RUNTIME_ROOT/bin"
DEFAULT_USER_BIN="$HOME/.local/bin"
CONFIG_DIR="$HOME/.dsv_client"
CONFIG_FILE="$CONFIG_DIR/config.json"

remove_launchers() {
  local -a candidates=("/usr/local/bin/dsvc" "${DEFAULT_USER_BIN}/dsvc")
  local candidate=""
  local target=""
  local removed_count=0
  local found_count=0

  for candidate in "${candidates[@]}"; do
    if [[ -L "$candidate" ]]; then
      target="$(readlink "$candidate" || true)"
      found_count=$((found_count + 1))
      if [[ "$target" == "$RUNTIME_BIN_DIR/dsvc" ]]; then
        rm -f "$candidate"
        echo "Removed launcher: $candidate"
        removed_count=$((removed_count + 1))
      else
        echo "Skipped $candidate because it does not point to $RUNTIME_BIN_DIR/dsvc."
      fi
    elif [[ -e "$candidate" ]]; then
      found_count=$((found_count + 1))
      echo "Skipped $candidate because it is not a symlink."
    fi
  done

  if (( found_count == 0 )); then
    echo "Launcher not found in expected paths."
  fi
  if (( removed_count == 0 && found_count > 0 )); then
    echo "No launcher symlinks were removed."
  fi
}

remove_config() {
  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Config file not found: $CONFIG_FILE"
    return
  fi
  rm -f "$CONFIG_FILE"
  echo "Removed config file: $CONFIG_FILE"
}

remove_config_dir_if_empty() {
  if [[ -d "$CONFIG_DIR" ]]; then
    rmdir "$CONFIG_DIR" 2>/dev/null || true
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
  remove_config_dir_if_empty
}

main "$@"
