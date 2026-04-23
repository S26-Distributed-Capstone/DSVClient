#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/dsvc"
BIN_DIR="${DSVC_BIN_DIR:-$HOME/.local/bin}"
LAUNCHER_PATH="$BIN_DIR/dsvc"
CONFIG_FILE="$HOME/.dsv_client/config.json"

main() {
  if [[ -L "$LAUNCHER_PATH" ]]; then
    rm -f "$LAUNCHER_PATH"
    echo "Removed launcher: $LAUNCHER_PATH"
  elif [[ -e "$LAUNCHER_PATH" ]]; then
    echo "Skipped $LAUNCHER_PATH because it is not a symlink."
  else
    echo "Launcher not found: $LAUNCHER_PATH"
  fi

  if [[ -d "$RUNTIME_ROOT" ]]; then
    rm -rf "$RUNTIME_ROOT"
    echo "Removed runtime: $RUNTIME_ROOT"
  else
    echo "Runtime directory not found: $RUNTIME_ROOT"
  fi

  if [[ -f "$CONFIG_FILE" ]]; then
    read -r -p "Remove config file at $CONFIG_FILE? [y/N]: " remove_config
    case "$remove_config" in
      y|Y|yes|YES)
        rm -f "$CONFIG_FILE"
        echo "Removed config file."
        ;;
      *)
        echo "Config file kept."
        ;;
    esac
  fi
}

main "$@"
