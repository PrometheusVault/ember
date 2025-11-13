# Ember Roadmap

## Current Sprint

1. **Agent registry** – Normalize agent metadata/interfaces so `core.agent` can query capabilities.
   - `/agents` slash command to list metadata + latest run state (interactive view).
   - Registry tests + docs (AGENTS.md, architecture) ✅
   - Hook additional agents as they land (network, toolchain, etc.) so they register once implemented.

## Backlog (highest priority first)

1. **Configuration loader** – Formalize the design so the CLI can validate configs without manual exports.
2. **Offline provisioning bundles** – Ensure all dependencies/models/scripts can be staged locally for Raspberry Pi installs with zero network access.
3. **Testing surface** – Stand up `test.agent` scaffolding; add coverage for the CLI + agents.
4. **IPC/message bus** – Define JSON schema for agent-to-agent communication, starting with localhost transport.
5. **Plugin loader** – Watch `/plugins` and `/usr/local/ember/plugins` for extensions and register them dynamically.
6. **Metrics/telemetry** – Implement `metrics.agent` to collect system stats and expose them locally.
7. **Secure updates** – Flesh out `update.agent` with checksum validation and staged rollout support (USB/offline friendly).
8. **Runtime agent toggles** – Allow enabling/disabling agents without restarting (e.g., `/agent enable provision.agent`).
9. **Editable /config** – Allow operators to modify config values (e.g., logging level) from within the REPL and persist them back to the vault.
10. **Command-local help** – Support `/<command> --help` shortcuts that display the corresponding manpage inline.
11. **Shell passthrough mode** – Explore a shell-first experience (command passthrough, planner hotkey, tmux integration).
12. **REPL + llama.cpp** – Swap the placeholder planner with real llama.cpp inference on Raspberry Pi images.
13. **llama.cpp curl dependency** – Investigate building without libcurl to support fully offline systems.
14. **Model download TLS** – Restore strict SSL handling once we control mirrors or can pin certificates.
15. **UI dashboard** – Build optional `ui.agent` for local web monitoring tied to the same command API.
