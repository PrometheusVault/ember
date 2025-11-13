# NAME

`/agents` – List registered agents, enablement, and last known results.

# SYNOPSIS

```
/agents
```

# DESCRIPTION

Displays a table summarizing every agent currently registered with Ember. For
each agent you see:

- **Name** – Registry identifier (matches `agents.enabled` config values).
- **Enabled** – Whether the agent is currently scheduled to run.
- **Status** – Latest recorded status from the registry (if the agent has run
  before).
- **Detail** – Notes from the last run (success, partial, error, etc.).

Information is pulled from the registry and the runtime configuration bundle, so
it reflects the live enable/disable state plus whatever the agent reported via
`config_bundle.agent_state`.

# EXAMPLES

- `/agents` – Inspect every agent’s enablement and recent results.

# SEE ALSO

`/status`, `/config`, `docs/architecture.md`
