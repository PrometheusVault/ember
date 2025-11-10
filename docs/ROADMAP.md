# Ember Roadmap

Status legend:

- **Planned** – concept approved, design/outcome documented.
- **Placeholder** – stub code or interface exists; full logic pending.
- **In Progress** – actively being built.

## Phase 1 – Developer Runtime Parity

| Feature | Status | Notes |
| --- | --- | --- |
| Interactive CLI loop | Placeholder | `ember/app.py` mirrors the eventual planner/actuator loop and accepts commands for now. |
| Vault-aware configuration | Planned | Detect and validate `VAULT_DIR`, load YAML under `config/`. |
| Basic logging pipeline | Planned | Forward CLI events to `/logs/agents/core.log`; align with auditing goals. |
| Provisioning hooks | Planned | `core.agent` should trigger `provision.agent` as part of bootstrap workflow. |
| Raspberry Pi 5 bootstrap | Planned | Ship a systemd service that launches `python -m ember` at boot and attaches the REPL to the primary TTY. |
| llama.cpp wiring | Completed | Runtime now uses `llama-cpp-python`, supports env overrides, logging, and unit tests without external CLI tooling. |
| tmux HUD | Planned | Standardize the tmux status line so users always see session/vault/health info even while multitasking. |

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

Document any newly agreed feature or constraint here so it can be surfaced in
future planning discussions and converted into implementation tickets.
