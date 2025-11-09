# Ember Runtime (dev stub)

Minimal Python CLI that emulates the future Ember runtime loop. The Docker
image in `Dockerfile` provides parity with production-like environments, but
you can just run the stub directly on macOS or Linux.

## No-Docker quick start

Prereqs: Python 3.11+ plus a working `pip`. Optional packages from the
Dockerfile (tmux, taskwarrior, etc.) are not required for this stub.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Optional: point Ember at a different vault path
export VAULT_DIR="$PWD/vault"

python -m ember
```

The CLI prints a banner, then waits for commands. Type `quit` or `exit` (or
press Ctrl-D/Ctrl-C) to leave.

## Troubleshooting

- `IndentationError` or similar when running `python -m ember`: ensure
  `ember/app.py` matches the latest indentation fixes.
- `ModuleNotFoundError`: confirm your virtualenv is active and `pip install -r
  requirements.txt` completed without errors.
- Need the legacy Docker flow? `make build && make dev` uses the `Dockerfile`,
  mounts the repo at `/srv/ember`, and keeps the container alive (`sleep
  infinity`) so you can attach with `docker exec -it ember-dev bash`.
