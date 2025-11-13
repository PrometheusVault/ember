# Ember Operations Guide

This guide covers day-to-day workflows for running Ember on headless Alpine
nodes, including runtime expectations, Docker development, provisioning, and
tmux ergonomics. For agent responsibilities see `AGENTS.md`; for the roadmap
see `docs/ROADMAP.md`.

## Runtime lifecycle

1. The device boots and `python -m ember` is launched (via tmux or a service
   manager such as systemd/OpenRC).
2. Ember mounts the vault (see `docs/vault.md` for structure), loads local
   documentation (README, AGENTS, roadmap), and primes `llama.cpp`
   (via `llama-cpp-python`) with that context.
3. The operator lands in the Ember REPL inside a dedicated tmux session. The
   HUD in the status line shows the active session, vault path, and basic
   health so you retain situational awareness while opening panes/windows.
4. Natural-language prompts flow through `llama.cpp`. Ember first executes a
   planner prompt. Only commands that are explicitly marked as planner-safe are
   exposed to that prompt (e.g., `/status`, `/config`). Suggested commands run
   in-process, their output is captured, and a responder prompt produces the
   final answer using the latest data. Commands flagged as “interactive-only”
   (such as `/help`, `/man`, `/update`) can still be issued manually at the
   REPL but are never triggered automatically.

If bindings or models cannot be found, the REPL emits actionable errors instead
of crashing so you can correct the configuration and retry.

### Provision agent on bootstrap

[See `docs/agents/provision.md`](agents/provision.md) for the full developer and
operator guide. Field notes below summarize the day-to-day workflow.

- During startup the `core.agent` automatically invokes `provision.agent`. The
  agent ensures the vault directory contains the expected layout (logs/,
  logs/agents/, plugins/, models/, state/, etc.) and writes a summary to
  `$VAULT_DIR/state/provision.json`.
- Set `EMBER_SKIP_PROVISION=1` before launching Ember to bypass the provisioning
  pass (handy for read-only demos or CI sandboxes). Any diagnostic failures are
  surfaced via `/status`.
- Override the required paths or the state-file location by adding a `provision`
  block to either `config/system.yml` or a vault override:

  ```yaml
  provision:
    required_paths:
      - config
      - logs
      - models/custom
    state_file: state/provision.json
  ```
  Set `skip_env` in the same block if you need a different environment toggle.

### Network agent quick checks

- `network.agent` runs in the same bootstrap pass and never requires the
  configuration bundle to be `ready`, so you always get a live network report
  even on half-configured devices.
- Use `/agents` (or `/status`) to inspect the `primary_interface`, address
  inventory, DNS sources, and optional connectivity probes. The summary looks
  like `2 up / 3 total interfaces; primary=eth0; connectivity 1/2 targets`.
- Set `network.preferred_interfaces` in the repo/vault config so the UI
  highlights the NIC you care about (e.g., `eth0` on wired racks, `wlan0` on
  Pi deployments).
- Leave `network.connectivity_checks` empty on air-gapped hardware so the agent
  immediately reports `status=degraded` instead of waiting for sockets to time
  out. Populate it with host[:port] pairs (e.g., `1.1.1.1:53`) when you want a
  sanity check before attempting model downloads or updates.
- DNS entries come straight from `network.dns_paths`, defaulting to
  `/etc/resolv.conf`. Add `/run/systemd/resolve/resolv.conf` if you’re on
  systemd-resolved to mirror what `dig` or `resolvectl` would show.

### Toolchain agent readiness

- `toolchain.agent` parses `.toolchain.yml` and reports whether Docker, make,
  git, Python deps, and key files are present. Review `docs/agents/toolchain.md`
  for the manifest schema.
- `/agents` shows per-command details (path + version output when configured),
  so after running `make configure` you can confirm `docker`, `make`, and
  `git` are ready before invoking `make build`.
- Update the manifest whenever provisioning scripts learn a new dependency so
  headless deployments advertise the correct requirements immediately.

### Test agent runs

- `test.agent` is disabled by default (running the suite on boot can be slow),
  but CI nodes or nightly QA boxes can enable it via `test.enabled: true` or the
  global `agents.enabled` list.
- `/agents` shows the latest result plus the report path. Inspect
  `$VAULT_DIR/state/test-agent.json` for full stdout/stderr when failures occur.
- Configure the command/timeout via the `test` block. See
  `docs/agents/test.md` for details on workdir overrides and env vars.

### Plugin agent discovery

- Drop plugins under `$VAULT_DIR/plugins/<plugin>/plugin.yml` (or in the repo
  `/plugins/` directory) and `plugin.agent` will report them automatically.
- The manifest requires at least `name`; include `description`, `version`, and
  `entrypoint` for richer `/agents` output. See `docs/agents/plugin.md` for the
  schema.
- To disable plugin scanning (e.g., hardened environments) set `plugin.enabled:
  false` or remove the agent from the enabled list. Diagnostics warn when a
  manifest is malformed so you can correct it before enabling the plugin.

### Configure command (Alpine + Raspberry Pi)

- Run `sudo make configure` (or `sudo ./scripts/configure_system.sh`) on any
  newly imaged device. The script detects the host OS and dispatches to the
  right bootstrap path:
  - **Alpine** ⇒ `scripts/provision.sh` (OpenRC autologin, llama.cpp build,
    etc.).
  - **Raspberry Pi OS / Debian** ⇒ `scripts/pi_bootstrap.sh` (systemd service +
    apt workflow).
- Override detection with `EMBER_CONFIGURE_TARGET=alpine` or
  `EMBER_CONFIGURE_TARGET=pi` if you’re running inside chroots or derivatives.
- The script must be run as root; use `sudo make configure`.

### Raspberry Pi 5 bootstrap

`scripts/pi_bootstrap.sh` prepares Pi OS (Debian-based) images:

1. Installs system packages (Python 3, tmux, zsh, git, build essentials).
2. Creates/updates the `ember` user, vault directory, and virtualenv.
3. Installs the tmux/zsh HUD dotfiles plus the executable helpers
   (`ember/ember_dev_run.sh`, `scripts/tmux_pane.sh`).
4. Renders `templates/ember.service` into `/etc/systemd/system/ember.service`.
   The service:
   - Runs as the `ember` user
   - Enforces `APP_DIR`, `VENV_DIR`, `VAULT_DIR`, and `EMBER_MODE`
   - Binds to `/dev/tty1` so the tmux HUD appears on the primary console
   - Restarts automatically on failure
5. Enables autologin on `tty1` by overriding `getty@tty1.service`.

Useful commands after running the bootstrap:

```bash
sudo systemctl status ember.service
sudo journalctl -u ember.service -f
```

Update variables such as `EMBER_VAULT_DIR` or `EMBER_SERVICE_NAME` before
running the installer to customize the deployment.

## Logging

Every Ember session writes a rotating log to `$VAULT_DIR/logs/agents/core.log`
(see `docs/vault.md`). Slash commands, planner activity, and general runtime
events appear there, giving you an audit trail even when the REPL scrollback is
cleared. Rotate or ship the log by managing the files under the vault’s
`logs/agents` directory. If the vault path is not writable (e.g., the default
`/vault` inside Docker without a bind mount), Ember falls back to
`./.ember_runtime/logs/agents/core.log` and surfaces a warning at startup.

Need to see exactly what llama.cpp is doing? Set `logging.level: DEBUG` (or run
`EMBER_LOG_LEVEL=DEBUG python -m ember`) to stream planner prompts, raw model
output, and responder prompts directly in the REPL. Drop back to `INFO` for a
quieter day-to-day experience.

## Inspecting agents

- Run `/agents` to see every registered agent, whether it is currently enabled
  (per the `agents.enabled`/`agents.disabled` lists), and the latest run status
  captured by the registry.
- Agent output is also visible via `/status`, but `/agents` focuses
  specifically on the registry metadata.

## Slash commands, help, and manpages

- Type `/help` in the REPL to see the currently registered commands.
- Run `/man <command>` to open the Markdown manpage (stored in
  `docs/commands/<command>.md`) inside an ANSI-aware pager. Scroll with the
  arrow keys/space, press `q` to exit.
- Append `--help` to future commands once command-local help lands (see
  `docs/ROADMAP.md`). For now, `/man` is the authoritative reference.
- Planner-exposed commands are intentionally constrained. If you need a command
  to be callable by the planner, mark it with `allow_in_planner=True` when it
  is registered. Interactive-only commands should leave the default (`False`)
  so the planner cannot run them automatically.

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
- Inside Ember, run `/model` to see the active model and local candidates, or
  `/model set <path-or-name>` to switch without restarting.

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

- The HUD status bar now lives at the top of the screen and refreshes every two
  seconds. It shows the session name, host, current path, the active pane
  command, the vault directory, battery/AC state (via
  `scripts/tmux_battery.sh`), plus the date/time. On Pi boards without a
  battery the indicator falls back to `AC Powered`.
- Customize the status line by editing `templates/tmux.conf` (for new installs)
  or adjusting `~/.tmux.conf` on an existing node; reload tmux with `prefix +
  :source-file ~/.tmux.conf`.

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
- Downloads a default GGUF model into `models/` (override with `EMBER_MODEL_URL`; wget currently runs with `--no-check-certificate` – override `EMBER_WGET_OPTS` once you have trusted mirrors)

For minimal installs, prune packages after provisioning:

```bash
APK_PRUNE="nano openssh-server" sudo ./scripts/provision.sh
```

Customize directories by exporting `LLAMA_DIR`, `EMBER_MODEL_DIR`, or
`EMBER_VAULT_DIR` before running the script (see `docs/vault.md` for more on
vault layout). Set `EMBER_SKIP_AUTO_TMUX=1` before logging in if you need a
plain shell for repairs.

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
- Shortcut: run `/update` inside the Ember REPL to perform the fetch/pull +
  provision steps automatically (you may be prompted for the sudo password).

## Troubleshooting

- `IndentationError` (or similar) running `python -m ember`: ensure
  `ember/app.py` matches the latest fixes.
- `ModuleNotFoundError`: confirm the virtualenv is active and `pip install -r`
  `requirements.txt` completed without errors.
- Need the legacy Docker flow? `make build && make dev` uses the `Dockerfile`,
  mounts the repo at `/srv/ember`, mounts a persistent Docker volume at `/vault`
  (default name `ember-dev-vault`), and keeps the container alive (`sleep
  infinity`) so you can attach with `docker exec -it ember-dev bash`. Override
  the vault volume with `VAULT_VOLUME=my-node-vault make dev` if you want
  multiple isolated dev vaults.
