# Ember System Architecture

This document stitches together the Ember runtime so operators can see how the
REPL, planner, agents, and vault collaborate—especially important when you are
working on a fully offline Raspberry Pi.

## 1. High-level flow

1. **Bootstrap**
   - `python -m ember` prints the banner, loads configuration from the repo
     (`config/*.yml`) plus `$VAULT_DIR/config`, validates the merged result
     against the built-in schema, and primes logging.
   - Enabled agents are registered via `ember/agents/registry.py`. On the
     `bootstrap` trigger the registry executes each agent in order (currently
     just `provision.agent`), storing results in `config_bundle.agent_state` so
     `/status` can surface them.
2. **REPL loop**
   - The banner is the only startup output; once you see the prompt (`>`), Ember
     is ready for input. `/help` lists commands; `/man <cmd>` opens the stored
     Markdown manpage for detailed syntax.
   - Natural-language prompts go through two llama.cpp templates: a planner
     that may request commands, and a responder that crafts the final reply.
3. **Command routing and planner safety**
   - Slash commands are registered with metadata (`allow_in_planner`,
     `requires_ready`). Only commands flagged for planner use appear in the
     planner prompt; interactive-only commands (`/help`, `/man`, `/update`,
     etc.) are blocked from planner execution.
   - The router enforces configuration readiness per command so long-running
     agents (e.g., future `metrics.agent`) can opt out until the system is
     healthy.
4. **Output and telemetry**
   - Command results and planner conversations are logged to
     `$VAULT_DIR/logs/agents/core.log`. `/status` renders the merged config,
     diagnostics, and agent results for quick inspection.

## 2. Agents in context

- **Registry-driven lifecycle** – Agents declare their triggers and are
  enabled/disabled entirely via YAML.
- **Provisioning** – `provision.agent` ensures the vault layout exists and
  writes a state file under `state/`. The output is visible via `/status`.
- **Future slots** – The registry is ready for `network.agent`,
  `metrics.agent`, `plugin.agent`, etc. The backlog tracks when each agent will
  be implemented.

## 3. Configuration touchpoints

- `docs/configuration.md` covers how repo defaults + vault overrides merge.
- `docs/operations.md` explains TMUX usage, provisioning workflows, and the
  planner/responder loop.
- Agents look up their own knobs (e.g., `provision.required_paths`) under their
  section in the merged config so the registry can pass the bundle directly.

## 4. Future enhancements

- Runtime toggles for agents (allowing `/agent disable foo` without restarting)
  sit in the backlog.
- IPC/message bus and plugin loader work will integrate with the same registry
  so discovery and scheduling stay consistent.

Keep this mental model handy when debugging or adding features; when in doubt,
trace a prompt through the banner → config load → agent registry → REPL →
planner → slash command router → logging.
