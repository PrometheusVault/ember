#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

APP_DIR="${APP_DIR:-$REPO_ROOT}"
SESSION="${SESSION:-ember}"
VENV_DIR_ENV="${VENV_DIR:-}"

cd "$APP_DIR"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required to run Ember in attachable mode. Please install tmux." >&2
  exit 1
fi

find_venv() {
  candidates=()
  if [ -n "$VENV_DIR_ENV" ]; then
    candidates+=("$VENV_DIR_ENV")
  fi
  candidates+=(
    "$APP_DIR/.venv"
    "$APP_DIR/venv"
    "/opt/ember-app/venv"
  )

  for candidate in "${candidates[@]}"; do
    if [ -n "$candidate" ] && [ -f "$candidate/bin/activate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

if ! VENV_PATH="$(find_venv)"; then
  echo "Could not locate a Python virtualenv. Set VENV_DIR or create $APP_DIR/.venv first." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"

start_cmd="cd \"$APP_DIR\" && . \"$VENV_PATH/bin/activate\" && python -m ember"

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" "$start_cmd"
fi

exec tmux attach-session -t "$SESSION"
