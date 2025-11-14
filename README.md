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
terminal, `/agents` to inspect registered agents, and `/model` to see or switch
the active llama.cpp model on the fly.

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

## Operator knowledge base

- Store reference material (field guides, almanacs, edible-plant lists, etc.)
  inside the **vault**: `$VAULT_DIR/library`, `$VAULT_DIR/reference`,
  `$VAULT_DIR/notes`, `$VAULT_DIR/almanac`, or any subdirectory you prefer.
  Ember ingests the first ~2 KB per file and feeds those excerpts into llama.cpp
  so responses stay grounded in what *you* know about the world.
- This repo ships sample entries under `vault/library/` and `vault/almanac/` to
  illustrate the format. Customize or replace them—everything under the vault is
  persistent storage and should become your personal knowledge base.
- Drop new files or edit existing ones at any time; restart Ember to reload the
  corpus. Subdirectories are supported, so organize by region/topic however you like.
- Technical docs (`README.md`, `AGENTS.md`, …) are intentionally excluded for now
  so the model stays focused on survival knowledge rather than repo internals.
- Toggle the REPL verbosity via `ui.verbose` (or `EMBER_UI_VERBOSE=0/1`) to
  switch between the rich development HUD and the terse production view.
