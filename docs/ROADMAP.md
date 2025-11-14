# Ember Roadmap

## Current Sprint

_(Complete – planning for next sprint in progress)_

## Backlog (highest priority first)

1. **Operator knowledge packs** – Formalize how Markdown/plaintext files are staged under `docs/` and `$VAULT_DIR/docs`, add validation hooks, and ship a sync command so field teams can refresh survival manuals offline.
2. **Context-aware retrieval** – Chunk stored documents, score them per user prompt, and only stream the top excerpts into llama.cpp so answers stay grounded without blowing the context window.
3. **Conversation memory for llama.cpp** – Maintain a rolling conversational state (recent Q/A pairs plus clarifying questions) so the planner can ask follow-ups and better infer operator intent before drafting a response. Persist the transcript per session and expose toggles in `/config`.
4. **Full-text document index (Recoll)** – Integrate a lightweight indexer (Recoll or similar) so thousands of vault documents can be searched quickly. Expose CLI hooks to refresh the index, query it for planner context, and fall back gracefully when offline.
5. **Core agent lifecycle (next steps)** – Build on the new shim by:
   - gating downstream agents when configuration is `missing`/`invalid`, with retry hooks;
   - emitting per-agent telemetry so `/status` and the planner see orchestrated ordering/latency;
   - integrating runtime enable/disable requests so `core.agent` becomes the single source of truth for scheduling.
6. **Update workflow hardening** – Merge `update.agent` readiness into `/update`, block dirty/unapproved branches, and make provisioning reruns safe (rollback hooks, no blind `sudo`).
7. **Offline provisioning bundles** – Package llama.cpp sources, models, and dependencies so `scripts/provision.sh` works on air-gapped devices (USB/tarball ingestion flow + docs).
8. **Runtime agent toggles** – Add `/agent enable|disable` (and planner awareness) so operators can change behavior without restarting Ember.
9. **Metrics/telemetry** – Implement `metrics.agent` to report CPU/RAM/disk in `/status` and feed the planned UI/dashboard.
10. **Secure updates** – Extend `update.agent` with checksum validation, staged rollouts, and offline media support.
11. **IPC/message bus** – Define the JSON schema/transport for agent-to-agent communication, starting with localhost pipes.
12. **Editable /config expansion** – Allow `/config key value` to set lists/mappings; when operators set unknown keys (not present in the default repo config), warn loudly and refuse to write overrides. Add audit logs for successful writes.
13. **Command-local help** – Support `/<command> --help` shortcuts that render the relevant manpage inline.
14. **Shell passthrough mode** – Explore a shell-first experience (command passthrough, planner hotkey, tmux integration).
15. **llama.cpp curl dependency** – Investigate building without libcurl to support fully offline systems.
16. **Model download TLS** – Restore strict SSL handling once we control mirrors or can pin certificates.
17. **UI dashboard** – Build optional `ui.agent` for local web monitoring tied to the same command API.
