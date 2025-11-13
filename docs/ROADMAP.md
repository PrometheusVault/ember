# Ember Roadmap

Status legend:

- **Planned** – concept approved, design/outcome documented.
- **Placeholder** – stub code or interface exists; full logic pending.
- **In Progress** – actively being built.

## Phase 1 – Developer Runtime Parity

| Feature | Status | Notes |
| --- | --- | --- |
| Interactive CLI loop | Placeholder | `ember/app.py` mirrors the eventual planner/actuator loop and accepts commands for now. |
| Vault-aware configuration | Completed | Vault dir detection, YAML merging, diagnostics, and docs shipped. |
| Basic logging pipeline | Completed | CLI + planner events now stream to `/logs/agents/core.log` with rotation. |
| Provisioning hooks | Completed | `core.agent` now triggers `provision.agent` during bootstrap and records the run to `state/provision.json`. |
| Raspberry Pi 5 bootstrap | Completed | `scripts/pi_bootstrap.sh` + `templates/ember.service` install a tmux HUD service on tty1 with systemd autologin. |
| llama.cpp wiring | Completed | Runtime now uses `llama-cpp-python`, supports env overrides, logging, and unit tests without external CLI tooling. |
| tmux HUD | Planned | Standardize the tmux status line so users always see session/vault/health info even while multitasking. |
| Rich renderer sizing | Planned | Make `render_rich` respect the active terminal width/height so recorded panels match small screens. |
| Status command layout | Planned | Rework `/status` tables (diagnostics/agents) for folding columns, pagination, and narrow padding. |
| Config view readability | Planned | Replace the flat `repr` dump with a tree/YAML view that wraps nested values for handheld displays. |
| Planner response compaction | Planned | Restructure runtime overview + planner summaries into stacked, narrow-friendly layouts with truncation. |
| Responsive banner | Planned | Detect terminal width and fall back to a slim single-line banner when box art will overflow. |

## Phase 2 – Agent + Plugin Ecosystem

| Feature | Status | Notes |
| --- | --- | --- |
| Agent registry | Planned | Normalize agent metadata/interfaces so `core.agent` can query capabilities. |
| Plugin loader | Planned | Watch `/plugins` and `/usr/local/ember/plugins` for extensions and register them dynamically. |
| IPC/message bus | Planned | Define JSON schema for agent-to-agent communication, starting with localhost transport. |

## Phase 3 – Operational Experience

| Feature | Status | Notes |
| --- | --- | --- |
| Metrics/telemetry | Planned | Implement `metrics.agent` to collect system stats and expose them locally. |
| UI dashboard | Planned | Build optional `ui.agent` for local web monitoring tied to the same command API. |
| Secure updates | Planned | Flesh out `update.agent` with checksum validation and staged rollout support. |

## Locked Follow-ups

- **Command routing layer** – placeholder in `ember/app.py`; will evolve into planner-driven dispatcher.
- **Configuration loader** – design doc TBD; until then, CLI exports `VAULT_DIR` and validates at runtime.
- **Testing surface** – `test.agent` described in `AGENTS.md`; unit tests will target stubs as they are introduced.
- **REPL + llama.cpp** – REPL now differentiates between `:commands` and natural prompts; swap the placeholder planner with real llama.cpp inference on Raspberry Pi images.
- **llama.cpp curl dependency** – provisioning currently installs libcurl headers; investigate compiling without curl (and updating scripts) for fully offline systems.
- **Shell passthrough mode** – spike on treating Ember as a shell-first experience (command passthrough, planner hotkey, deeper zsh/tmux integration).
- **Model download TLS** – provisioning currently invokes curl with `-k` to bypass certificate checks; restore strict SSL handling once we have a signed mirror or pinned CA.

Document any newly agreed feature or constraint here so it can be surfaced in
future planning discussions and converted into implementation tickets.
