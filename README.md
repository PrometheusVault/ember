# Ember Runtime (dev stub)

Minimal Python CLI that emulates the future Ember runtime loop. The Docker
image in `Dockerfile` provides parity with production-like environments, but
you can just run the stub directly on macOS or Linux.

## Project Overview

- Ember is the Prometheus Vault runtime layer that boots, supervises, and
  extends lightweight edge nodes. It is agent-driven as described in
  `AGENTS.md`, with `core.agent` orchestrating supporting agents such as
  `network.agent`, `provision.agent`, and `toolchain.agent`.
- The current Python stub focuses on interactive development, mirroring the
  eventual CLI interface that will front a planner/actuator loop. The long-term
  hardware target is a Raspberry Pi 5 (8 GB) that auto-starts Ember on boot and
  immediately drops the operator into the REPL.
- Configuration is declarative (YAML under `config/`) and execution is
  modular, so that additional agents or plugins can be dropped in without
  rewriting the core runtime.

## Runtime Lifecycle

1. Raspberry Pi boots and systemd (or similar) invokes `python -m ember`.
2. Ember mounts the vault, loads local documentation (README, AGENTS, roadmap),
   and primes `llama.cpp` (via the `llama-cpp-python` bindings) with those
   excerpts for contextual grounding.
3. The user lands in the Ember REPL inside a dedicated `tmux` session. The HUD
   in the tmux status line shows the active session, vault path, and basic
   health so operators always have situational awareness even if they open new
   panes or windows.
4. Natural language prompts are sent to `llama.cpp` through the Python bindings,
   while commands prefixed
   with `/` (for example `/status`) call Ember's built-in handlers.
4. `llama.cpp` decides when to run commands (`status`, provisioning hooks, etc.).
   Ember executes each command, captures the output, and feeds that text back
   into the next prompt so the LLM maintains situational awareness.

If the bindings or model cannot be found, the REPL prints a helpful error
rather than crashing so you can correct the configuration and retry.

## Docker workflow

Everything needed to exercise the REPL + llama.cpp loop now lives inside the
dev container.

1. Build the image: `make build`
2. Download a `.gguf` model and place it somewhere within the repo (e.g.
   `models/ember.gguf`). When starting the container, tell Ember where to find
   it:\
   `ENV_VARS="-e LLAMA_CPP_MODEL=/srv/ember/models/ember.gguf" make dev`
3. Rebuild/start the dev container after any Dockerfile changes: `make rebuild`
   (one-time) followed by `make dev`
4. Drop straight into the REPL with llama.cpp available: `make repl`

`make repl` ensures the container is running, activates the virtualenv, and
executes `python -m ember` entirely inside Docker. Additional tuning knobs are
available through env vars such as `LLAMA_CPP_MAX_TOKENS`, `LLAMA_CPP_THREADS`,
`LLAMA_CPP_TEMPERATURE`, `LLAMA_CPP_TOP_P`, and `LLAMA_CPP_TIMEOUT`.

Model management tips:

- Ember automatically scans `./models` (and common container paths) for `.gguf`
  files, so dropping a model in that directory is usually enough.
- To pin a specific model for a single session, run `make repl MODEL=/srv/ember/models/foo.gguf`.
- For a persistent default inside the container, keep using `ENV_VARS="-e LLAMA_CPP_MODEL=..." make dev`.
- Prefer smaller, lower-quantized models (e.g., `llama-3.2-3b-instruct-q4_0.gguf`) for Raspberry Pis.
- You can cap generation time with `LLAMA_CPP_TIMEOUT` (default 120s). If llama
  exceeds this window the REPL reports a timeout instead of hanging.

### Prompt customization

- Ember renders planner prompts from `prompts/planner.prompt`. Adjust this file
  (or point `LLAMA_PROMPT_PATH` at your own) to change how we describe commands,
  required JSON formats, etc.
- The default template instructs the LLM to output JSON with `response` and
  `commands` keys, so we can decide whether to run slash commands or just reply.

## Testing

Use `make test` (or `pytest`) to run the growing unit-test suite. Tests avoid
loading actual GGUF models by injecting fakes, so they run quickly without
llama.cpp binaries present. GitHub Actions (`python-tests.yml`) runs `ruff`
lint plus the same pytest suite on every push/PR targeting `main`.

## Long-term Plan

High-level goals are tracked in `docs/ROADMAP.md`. The roadmap organizes work
into three standing themes:

1. **Runtime Reliability** – harden `core.agent`, integrate watchdogs, and let
   the CLI drive provisioning flows automatically on boot.
2. **Agent + Plugin Ecosystem** – load agents dynamically, standardize IPC, and
   expose a registry so new tools can be discovered without code changes.
3. **Operational Experience** – add telemetry (`metrics.agent`), optional UI,
   and secure update/auth flows for field deployments.

Each feature we lock in (like provisioning hooks, plugin lifecycle, or update
channels) receives a placeholder implementation or interface contract in the
codebase, plus a ticket-style entry in the roadmap so nothing is lost between
planning and execution.

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

Interaction tips:

- Prefix Ember runtime commands with `/` (e.g., `/status`, `/help`). These map
  directly to the CLI router and will eventually correspond to agent actions.
- Slash commands support TAB-completion (when readline is available), so typing
  `/sta[TAB]` will expand to `/status`.
- Any other input is forwarded to `llama.cpp`. If the model
  suggests a command (e.g., "status"), Ember runs it automatically and adds the
  resulting output to the conversational context.
- The llama bridge defaults to lightweight settings (128 token generations,
  conservative temperature) so it behaves on a Raspberry Pi. Override with
  `LLAMA_CPP_MAX_TOKENS`, `LLAMA_CPP_TEMPERATURE`, etc., when you have more
  headroom.
- `Ctrl-L` mirrors the usual shell behavior: the screen clears and the Ember
  banner is redrawn so you can refocus while staying in the same session.
- `tmux` shortcuts are your friend. `Ctrl-b c` opens additional Pi shells
  without leaving the REPL, while the status bar doubles as a “poor man's HUD”
  for Ember metadata. The dev runner script (`ember/ember_dev_run.sh`) mirrors
  the boot flow so you can practice locally.
- All REPL events are logged at INFO level. Run `make logs` (Docker) or inspect
  stdout when running locally to see prompts, llama invocations, and command
  executions.

## Auto-run on SSH/login

The helper script `ember/ember_dev_run.sh` keeps a `tmux` session named
`ember` alive and running `python -m ember`, then attaches your terminal.

```bash
# Once per machine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Each SSH/login (or add to your shell profile)
./ember/ember_dev_run.sh
```

Hints:

- Set `APP_DIR=/path/to/ember` or `VENV_DIR=/path/to/venv` before running the
  script if your layout differs. Otherwise it auto-discovers `.venv` in the
  repo, `venv` siblings, or `/opt/ember-app/venv` (Docker image default).
- To launch Ember automatically whenever you SSH in, add this to the end of
  your `~/.bash_profile` (guarded so it only triggers on new SSH sessions and
  doesn’t re-run inside an existing `tmux`):

  ```bash
  if [ -n "$SSH_CONNECTION" ] && [ -z "$TMUX" ]; then
    /Users/joshua/code/PrometheusVault/ember/ember/ember_dev_run.sh
    exit
  fi
  ```

  Replace the path with wherever the repo lives. Remove the `exit` if you want
  to drop back into your shell after detaching from Ember.

## Troubleshooting

- `IndentationError` or similar when running `python -m ember`: ensure
  `ember/app.py` matches the latest indentation fixes.
- `ModuleNotFoundError`: confirm your virtualenv is active and `pip install -r
  requirements.txt` completed without errors.
- Need the legacy Docker flow? `make build && make dev` uses the `Dockerfile`,
  mounts the repo at `/srv/ember`, and keeps the container alive (`sleep
  infinity`) so you can attach with `docker exec -it ember-dev bash`.
