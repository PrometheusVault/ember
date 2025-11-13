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
named `ember` alive and drop into the REPL on every login. Use `/help` for a
short command list, `/man <command>` to read the full Markdown manpage in the
terminal, and `/agents` to inspect which agents are registered/enabled.

## Key capabilities

- Planner/responder loop powered by `llama.cpp` (local GGUF models)
- Declarative config (`config/*.yml`) and dynamically loaded agents/plugins
- Agent registry that controls which agents run (and when) purely via config
- tmux-based HUD so operators can monitor and control nodes without a GUI
- Turnkey provisioning script for fresh Alpine images (creates the `ember`
  user, installs dependencies, builds llama, downloads a model, and configures
  autologin)

## Documentation

- Operations, provisioning, tmux behavior, and troubleshooting:
  `docs/operations.md`
- Agent responsibilities and relationships: `AGENTS.md`
- System architecture overview (planner, agents, registry): `docs/architecture.md`
- Roadmap and long-term planning: `docs/ROADMAP.md`
- Configuration keys, env vars, and offline editing tips: `docs/configuration.md`
- Fresh Alpine-on-Raspberry Pi install walkthrough: `docs/install_alpine_pi.md`

The rest of the repository follows the conventions in `AGENTS.md`—`/agents`
contains agent shims, `/config` holds YAML configs, `/plugins` is the extension
drop zone, and `/tests` covers the current Python stub. See `docs/operations.md`
for detailed workflows (Docker, provisioning, upgrades, etc.).
