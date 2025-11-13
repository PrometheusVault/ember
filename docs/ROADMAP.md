# Ember Roadmap

## Current Sprint

1. **Command routing layer** – Replace the placeholder dispatcher in `ember/app.py` with a planner-driven router so future agents can hook in cleanly.

## Backlog (highest priority first)

1. **Agent registry** – Normalize agent metadata/interfaces so `core.agent` can query capabilities.
2. **Configuration loader** – Formalize the design so the CLI can validate configs without manual exports.
3. **Offline provisioning bundles** – Ensure all dependencies/models/scripts can be staged locally for Raspberry Pi installs with zero network access.
4. **Testing surface** – Stand up `test.agent` scaffolding; add coverage for the CLI + agents.
5. **IPC/message bus** – Define JSON schema for agent-to-agent communication, starting with localhost transport.
6. **Plugin loader** – Watch `/plugins` and `/usr/local/ember/plugins` for extensions and register them dynamically.
7. **Metrics/telemetry** – Implement `metrics.agent` to collect system stats and expose them locally.
8. **Secure updates** – Flesh out `update.agent` with checksum validation and staged rollout support (USB/offline friendly).
9. **Command-local help** – Support `/<command> --help` shortcuts that display the corresponding manpage inline.
10. **Shell passthrough mode** – Explore a shell-first experience (command passthrough, planner hotkey, tmux integration).
11. **REPL + llama.cpp** – Swap the placeholder planner with real llama.cpp inference on Raspberry Pi images.
12. **llama.cpp curl dependency** – Investigate building without libcurl to support fully offline systems.
13. **Model download TLS** – Restore strict SSL handling once we control mirrors or can pin certificates.
14. **UI dashboard** – Build optional `ui.agent` for local web monitoring tied to the same command API.
