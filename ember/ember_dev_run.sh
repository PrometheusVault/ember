#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/ember-app"
SESSION="ember"

cd "$APP_DIR"

# Activate venv
source "$APP_DIR/venv/bin/activate"

# Start tmux session running Ember if it doesn't exist yet
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" "python -m ember"
fi

# Attach current TTY to Ember session
exec tmux attach-session -t "$SESSION"
