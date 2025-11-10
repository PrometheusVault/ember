# Ember Configuration Defaults

Files in this directory ship with the Ember repository and act as the baseline
configuration that every runtime inherits before applying vault-specific
overrides. Each file should contain a single YAML document describing a logical
feature set (for example `system.yml` for core runtime options). Operators can
copy these files into `$VAULT_DIR/config/` and customize them per device;
anything defined in the vault takes precedence over the repo defaults.

Loading order:

1. Repository defaults under `config/`
2. Vault overrides under `$VAULT_DIR/config/`

All files are merged in lexicographic order, so prefix names (e.g. `10-system`,
`20-network`) when you need predictable layering.
