#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv}"
PYTHON_BIN="$VENV_DIR/bin/python"

maybe_activate() {
  if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1090
    . "$VENV_DIR/bin/activate"
  fi
}

if [ -n "${EMBER_SKIP_AUTO_REPL:-}" ]; then
  exec /bin/zsh
fi

if [ ! -x "$PYTHON_BIN" ]; then
  printf '[tmux-pane] %s\n' "Python virtualenv missing at $VENV_DIR; opening shell instead." >&2
  exec /bin/zsh
fi

cd "$REPO_ROOT"
maybe_activate

printf '[tmux-pane] launching Ember REPL in %s\n' "$PWD"
if ! "$PYTHON_BIN" -m ember; then
  printf '[tmux-pane] ember exited with status %s\n' "$?" >&2
fi

exec /bin/zsh
