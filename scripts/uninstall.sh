#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/dsvc"
RUNTIME_BIN_DIR="$RUNTIME_ROOT/bin"
DEFAULT_USER_BIN="$HOME/.local/bin"
CONFIG_FILE="$HOME/.dsv_client/config.json"

remove_launchers() {
  local -a candidates=()
  local candidate=""
  local target=""
  local removed_count=0
  local found_count=0

  if [[ -n "${DSVC_BIN_DIR:-}" ]]; then
    candidates+=("${DSVC_BIN_DIR}/dsvc")
  else
    candidates+=("/usr/local/bin/dsvc" "${DEFAULT_USER_BIN}/dsvc")
  fi

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

maybe_remove_config() {
  local remove_config=""

  if [[ ! -f "$CONFIG_FILE" ]]; then
    return 0
  fi

  case "${DSVC_REMOVE_CONFIG:-}" in
    true|TRUE|1|yes|YES|y|Y)
      rm -f "$CONFIG_FILE"
      echo "Removed config file."
      return 0
      ;;
    false|FALSE|0|no|NO|n|N)
      echo "Config file kept."
      return 0
      ;;
  esac

  if [[ -t 0 ]]; then
    if ! read -r -p "Remove config file at $CONFIG_FILE? [y/N]: " remove_config; then
      remove_config=""
    fi
  else
    echo "No interactive terminal detected. Keeping config file."
    return 0
  fi

  case "$remove_config" in
    y|Y|yes|YES)
      rm -f "$CONFIG_FILE"
      echo "Removed config file."
      ;;
    *)
      echo "Config file kept."
      ;;
  esac
}

main() {
  remove_launchers

  if [[ -d "$RUNTIME_ROOT" ]]; then
    rm -rf "$RUNTIME_ROOT"
    echo "Removed runtime: $RUNTIME_ROOT"
  else
    echo "Runtime directory not found: $RUNTIME_ROOT"
  fi

  maybe_remove_config
}

main "$@"
