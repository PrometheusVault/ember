# Ember Operations Guide

This guide covers day-to-day workflows for running Ember on headless Alpine
nodes, including runtime expectations, Docker development, provisioning, and
tmux ergonomics. For agent responsibilities see `AGENTS.md`; for the roadmap
see `docs/ROADMAP.md`.

## Runtime lifecycle

1. The device boots and `python -m ember` is launched (via tmux or a service
   manager such as systemd/OpenRC).
2. Ember mounts the vault, loads local documentation (README, AGENTS, roadmap),
   and primes `llama.cpp` (via `llama-cpp-python`) with that context.
3. The operator lands in the Ember REPL inside a dedicated tmux session. The
   HUD in the status line shows the active session, vault path, and basic
   health so you retain situational awareness while opening panes/windows.
4. Natural-language prompts flow through `llama.cpp`. Ember first executes a
   planner prompt (deciding whether to run slash commands). Suggested commands
   run in-process, their output is captured, and a responder prompt produces
   the final answer using the latest data.

If bindings or models cannot be found, the REPL emits actionable errors instead
of crashing so you can correct the configuration and retry.

## Docker workflow

Use Docker when you want parity with production-like environments:

1. `make build`
2. Drop a `.gguf` model anywhere in the repo (e.g. `models/ember.gguf`), then
   start the container with `ENV_VARS="-e LLAMA_CPP_MODEL=/srv/ember/models/ember.gguf" make dev`
3. After Dockerfile changes, run `make rebuild` once, then `make dev`
4. Start the REPL inside the container: `make repl`

`make repl` guarantees the container is running, activates the virtualenv, and
executes `python -m ember` entirely inside Docker. Tuning knobs are available
via env vars such as `LLAMA_CPP_MAX_TOKENS`, `LLAMA_CPP_THREADS`,
`LLAMA_CPP_TEMPERATURE`, `LLAMA_CPP_TOP_P`, and `LLAMA_CPP_TIMEOUT`.

### Model management tips

- Ember scans `./models` (and common container paths) for `.gguf` files, so
  dropping a model there is usually enough.
- Pin a specific model for one session: `make repl MODEL=/srv/ember/models/foo.gguf`
- For a persistent default in Docker, keep using `ENV_VARS="-e LLAMA_CPP_MODEL=..." make dev`
- Prefer smaller, lower-quantized models (e.g., `llama-3.2-3b-instruct-q4_0.gguf`) for Raspberry Pis
- Cap generation time with `LLAMA_CPP_TIMEOUT` (defaults to 120s) so the REPL
  reports timeouts instead of hanging.

## Login automation

`ember/ember_dev_run.sh` keeps a tmux session named `ember` alive and running
`python -m ember`, then attaches your terminal.

```bash
# Once per machine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Each SSH/login (or add to your shell profile)
./ember/ember_dev_run.sh
```

Hints:

- Set `APP_DIR=/path/to/ember` or `VENV_DIR=/path/to/venv` before running if
  your layout differs. Otherwise it auto-discovers `.venv` in the repo, `venv`
  siblings, or `/opt/ember-app/venv` (Docker default).
- To launch Ember automatically whenever you SSH in, append the following to
  your `~/.bash_profile` (guarded so it only triggers on new SSH sessions and
  doesn’t re-run inside tmux):

  ```bash
  if [ -n "$SSH_CONNECTION" ] && [ -z "$TMUX" ]; then
    /path/to/ember/ember/ember_dev_run.sh
    exit
  fi
  ```

  Remove the `exit` if you want to drop back into your shell after detaching.

## tmux panes & windows

The bundled tmux config (`templates/tmux.conf`) sets `default-shell` to zsh and
`default-command` to `scripts/tmux_pane.sh`, so every new pane/window starts
inside the Ember REPL automatically. Exit the REPL and the pane gracefully
falls back to a normal shell. Need a plain shell immediately? Prefix your tmux
command with `EMBER_SKIP_AUTO_REPL=1`, e.g., `EMBER_SKIP_AUTO_REPL=1 tmux new-window`.

## Alpine provisioning & upgrades

Provisioning or refreshing a node happens entirely from the console:

```bash
apk add git
git clone https://github.com/PrometheusVault/ember.git
cd ember
sudo ./scripts/provision.sh
```

The provisioner is idempotent—run it on day-0 images or again after a `git
pull` to pick up new dependencies. It:

- Installs Python 3, pip, tmux, zsh, curl, and build tooling via `apk`
- Creates (or updates) the `ember` operator account plus templated tmux/zsh dotfiles
- Builds `.venv`, installs `requirements.txt`, and wires login shells to launch the HUD
- Configures tty1 autologin so reboots land directly in the tmux session
- Clones & compiles `llama.cpp` into `/opt/llama.cpp`, copying `llama-cli` onto `$PATH`
- Downloads a default GGUF model into `models/` (override with `EMBER_MODEL_URL`)

For minimal installs, prune packages after provisioning:

```bash
APK_PRUNE="nano openssh-server" sudo ./scripts/provision.sh
```

Customize directories by exporting `LLAMA_DIR`, `EMBER_MODEL_DIR`, or
`EMBER_VAULT_DIR` before running the script. Set `EMBER_SKIP_AUTO_TMUX=1`
before logging in if you need a plain shell for repairs.

### Upgrading Ember

1. Log in (console or SSH), detach from tmux (`Ctrl-b d`), and update the repo:
   ```bash
   cd /home/ember/ember
   git pull --ff-only
   ```
2. Re-run the provisioner to rebuild the virtualenv, re-render templates, and
   update `llama.cpp`/models:
   ```bash
   sudo ./scripts/provision.sh
   ```
3. Reattach with `hud` or `ember/ember_dev_run.sh`. The script is safe to run
   repeatedly; it only rebuilds components that changed.

## Troubleshooting

- `IndentationError` (or similar) running `python -m ember`: ensure
  `ember/app.py` matches the latest fixes.
- `ModuleNotFoundError`: confirm the virtualenv is active and `pip install -r`
  `requirements.txt` completed without errors.
- Need the legacy Docker flow? `make build && make dev` uses the `Dockerfile`,
  mounts the repo at `/srv/ember`, and keeps the container alive (`sleep
  infinity`) so you can attach with `docker exec -it ember-dev bash`.
