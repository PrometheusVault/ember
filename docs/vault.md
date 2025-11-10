# Prometheus Vault – Ember Vault Guide

The **vault** is the persistent workspace Ember mounts at runtime. It holds
operator data, configuration overrides, logs, and plugins that should survive
code deployments. By default Ember looks for the vault path in the `VAULT_DIR`
environment variable (falling back to `/vault`). Provisioning scripts set
`VAULT_DIR` automatically, but you can override it per-node or per-session.

## Directory layout

While the vault can contain anything your agents need, the following layout is
recommended:

```
$VAULT_DIR/
├── config/          # YAML overrides loaded after repo defaults
├── logs/            # Runtime + agent logs (core.log, network.log, …)
├── plugins/         # Optional extensions discovered by plugin.agent
├── models/          # GGUF models or other large assets
└── state/           # Agent-managed state (locks, registries, etc.)
```

Only the `config/` directory is required for the new vault-aware configuration
flow, but keeping logs and plugins here ensures the vault remains self-contained.
Ember automatically writes `logs/agents/core.log`, so the directory is created
on first launch if it does not already exist. When the vault path is not
writable Ember falls back to `./.ember_runtime/logs/agents/core.log` (inside the
repo) and emits a warning so you can correct permissions or bind mounts.

## Configuration overrides

1. Ember loads every `*.yml`/`*.yaml` file under the repo `config/` directory.
2. It then loads the same pattern from `$VAULT_DIR/config/`, merging values on
   top of the defaults (lexicographic order, so prefix filenames if layering
   matters).
3. Any merge or validation issues are surfaced at startup and via the `/status`
   command inside the REPL.

Use this mechanism to store machine-specific secrets, network preferences, or
agent toggles without forking the repository.

## Validating the vault

When Ember starts it validates that:

- `VAULT_DIR` resolves to a directory
- the directory exists and is accessible
- the optional `config/` structure can be read

Problems are reported as diagnostics, enabling operators to fix misconfigurations
before proceeding.

## Selecting a vault path

- **Docker/dev containers**: The `Dockerfile` sets `VAULT_DIR=/vault`. Use
  `ENV_VARS="-e VAULT_DIR=/srv/ember/vault"` with `make dev` to override.
- **Bare metal**: `scripts/provision.sh` configures `/home/ember/vault` by
  default. Override with `EMBER_VAULT_DIR` before running the script.
- **Ad hoc sessions**: Export `VAULT_DIR=/path/to/vault && python -m ember`.

Point multiple devices at unique vault paths to keep their state isolated.
