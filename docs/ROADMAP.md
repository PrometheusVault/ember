# Ember Roadmap

## Current Sprint

_(Complete – planning for next sprint in progress)_

## Backlog (highest priority first)

1. **Core agent alignment** – Implement (or retire) `core.agent`, update defaults/docs, and ensure the registry actually runs every required agent at bootstrap.
2. **Update workflow hardening** – Merge `update.agent` readiness into `/update`, block dirty/unapproved branches, and make provisioning reruns safe (rollback hooks, no blind `sudo`).
3. **Offline provisioning bundles** – Package llama.cpp sources, models, and dependencies so `scripts/provision.sh` works on air-gapped devices (USB/tarball ingestion flow + docs).
4. **Runtime agent toggles** – Add `/agent enable|disable` (and planner awareness) so operators can change behavior without restarting Ember.
5. **Metrics/telemetry** – Implement `metrics.agent` to report CPU/RAM/disk in `/status` and feed the planned UI/dashboard.
6. **Secure updates** – Extend `update.agent` with checksum validation, staged rollouts, and offline media support.
7. **IPC/message bus** – Define the JSON schema/transport for agent-to-agent communication, starting with localhost pipes.
8. **Editable /config expansion** – Allow `/config key value` to set lists/mappings, with validation and audit logs.
9. **Command-local help** – Support `/<command> --help` shortcuts that render the relevant manpage inline.
10. **Shell passthrough mode** – Explore a shell-first experience (command passthrough, planner hotkey, tmux integration).
11. **llama.cpp curl dependency** – Investigate building without libcurl to support fully offline systems.
12. **Model download TLS** – Restore strict SSL handling once we control mirrors or can pin certificates.
13. **UI dashboard** – Build optional `ui.agent` for local web monitoring tied to the same command API.
