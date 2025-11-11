# Ember Runtime

Ember is the Prometheus Vault runtime that boots, supervises, and extends
lightweight edge nodes. A dedicated tmux “HUD” keeps the REPL visible on
headless consoles while agents (see `AGENTS.md`) provision networks, load
plugins, and execute commands suggested by the LLM planner.

## Quick start (macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m ember
```

Need an attachable HUD? Run `./ember/ember_dev_run.sh` to keep a tmux session
named `ember` alive and drop into the REPL on every login.

## Key capabilities

- Planner/responder loop powered by `llama.cpp` (local GGUF models)
- Declarative config (`config/*.yml`) and dynamically loaded agents/plugins
- tmux-based HUD so operators can monitor and control nodes without a GUI
- Turnkey provisioning script for fresh Alpine images (creates the `ember`
  user, installs dependencies, builds llama, downloads a model, and configures
  autologin)

## Documentation

- Operations, provisioning, tmux behavior, and troubleshooting:
  `docs/operations.md`
- Agent responsibilities and relationships: `AGENTS.md`
- Roadmap and long-term planning: `docs/ROADMAP.md`
- Configuration keys, env vars, and offline editing tips: `docs/configuration.md`

The rest of the repository follows the conventions in `AGENTS.md`—`/agents`
contains agent shims, `/config` holds YAML configs, `/plugins` is the extension
drop zone, and `/tests` covers the current Python stub. See `docs/operations.md`
for detailed workflows (Docker, provisioning, upgrades, etc.).
