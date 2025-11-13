# Ember Configuration Reference

Keep this document on every node so operators can edit configs even when the
system is completely offline. All examples assume `vim` is the preferred editor;
swap in another editor only if absolutely necessary.

---

## 1. How configuration is loaded

1. **Repo defaults** – every `*.yml`/`*.yaml` file under `config/` in the git
   repo is loaded first (see `config/system.yml`).
2. **Vault overrides** – Ember then loads the same pattern from
   `$VAULT_DIR/config/` (see `docs/vault.md`). These values override repo
   defaults key-by-key.
3. **Validation & diagnostics** – The merged result is wrapped in a
   `ConfigurationBundle`. Any errors (missing vault, malformed YAML, etc.) are
   surfaced immediately at startup and via the `/status` slash command inside
   the REPL (`ember/app.py:110-151`).

Quick edit loop with `vim`:

```bash
# 1) edit the repo default
vim config/system.yml

# 2) (optional) drop a machine-specific override in the vault
mkdir -p "$VAULT_DIR/config"
vim "$VAULT_DIR/config/10-local.yml"

# 3) restart Ember or run /status to verify the change
```

---

## 2. Schema summary (`config/system.yml`)

Ember now validates the merged configuration against a simple schema. Invalid
types or unknown keys surface as diagnostics (and `/status` will show
`status=invalid`). Supported keys:

| Key | Type / Default | Description |
| --- | --- | --- |
| `runtime.name` | `str` (default `"Ember"`) | Friendly display name used in prompts/logs. |
| `runtime.auto_restart` | `bool` (`true`) | Allows `core.agent` or service managers to auto-restart Ember after crashes. |
| `logging.level` | `str` (`"INFO"`) | Baseline log level; overridable via `EMBER_LOG_LEVEL`. |
| `agents.enabled` | `list[str]` (empty) | Explicit allow-list; when set, only these agents run. |
| `agents.disabled` | `list[str]` (empty) | Optional deny-list; handy when relying on defaults. |
| `provision.enabled` | `bool` (`true`) | Toggle the provisioning agent entirely. |
| `provision.skip_env` | `str` (`EMBER_SKIP_PROVISION`) | Environment variable that skips one run when set. |
| `provision.required_paths` | `list[str]` (see defaults in `ProvisionSettings`) | Directories that must exist under the vault. |
| `provision.state_file` | `str` (`state/provision.json`) | Where provisioning writes its latest summary. |

Unknown top-level keys trigger warnings so you can catch typos before the node
reboots.

Edit with `vim config/system.yml`, keeping YAML indentation (two spaces).

---

## 3. Provision agent settings

`provision.agent` now runs automatically during bootstrap (`docs/operations.md:25-45`).
Tune its behavior by adding a `provision` block to either the repo default or a
vault override:

```yaml
provision:
  enabled: true            # disable entirely by setting to false
  skip_env: EMBER_SKIP_PROVISION
  required_paths:
    - config
    - logs
    - logs/agents
    - plugins/custom
  state_file: state/provision.json
```

- `required_paths` are created relative to the vault and must be directories.
- `state_file` stores the most recent run summary; view it with `vim
  "$VAULT_DIR/state/provision.json"`.
- Set the environment variable defined in `skip_env` (defaults to
  `EMBER_SKIP_PROVISION`) to skip provisioning for one session, e.g.
  `EMBER_SKIP_PROVISION=1 python -m ember`.

`/status` lists each agent’s latest result so you can confirm provisioning
completed successfully (`ember/app.py:110-151`).

---

## 4. Logging configuration

- `logging.level` controls the baseline verbosity.
- Ember writes to `$VAULT_DIR/logs/agents/core.log` with rotation. If the vault
  is not writable it falls back to `./.ember_runtime/logs/agents/core.log` and
  emits a warning (`ember/logging_utils.py` tests cover this behavior).
- Use `/status` to view the active log path or edit the vault/log permissions
  with `sudo chown -R ember:ember "$VAULT_DIR/logs"`.

---

## 5. Agent enablement and overrides

The agent registry reads the `agents` block to decide which handlers run:

```yaml
agents:
  enabled:
    - provision.agent
    - network.agent
  disabled:
    - update.agent
```

- If `agents.enabled` is provided, only those names are executed (all others are
  skipped, regardless of their default).
- Otherwise each agent follows its `default_enabled` flag unless it appears in
  `agents.disabled`.
- Create overrides under the vault to customize individual machines:

  ```bash
  vim "$VAULT_DIR/config/20-agents.yml"
  ```

Future agent-specific settings (e.g., `metrics:`) will live under their own
top-level key so overrides remain declarative and straightforward to audit.

---

## 6. Environment variables cheat sheet

These are read during bootstrap or by helper scripts; set them in your shell,
systemd unit, or tmux profile as needed:

| Variable | Purpose | Default/Notes |
| --- | --- | --- |
| `VAULT_DIR` | Points Ember at the active vault. | Defaults to `/vault` (`ember/app.py:46`). |
| `EMBER_MODE` | Freeform label printed in the banner. | `DEV (Docker)` when unset. |
| `EMBER_LOG_LEVEL` | Overrides `logging.level` at runtime. | Upper-cased value; `WARNING` default. |
| `LLAMA_CPP_MODEL` (+ `LLAMA_CPP_MAX_TOKENS`, `LLAMA_CPP_THREADS`, `LLAMA_CPP_TEMPERATURE`, `LLAMA_CPP_TOP_P`, `LLAMA_CPP_TIMEOUT`) | Tuning knobs for the local llama.cpp binding (`README.md`). | Set per session or inject via `make dev ENV_VARS="..."`. |
| `EMBER_SKIP_PROVISION` | Skips the provisioning agent once. | Useful for read-only media. |
| `EMBER_SKIP_AUTO_TMUX` / `EMBER_SKIP_AUTO_REPL` | Bypass the auto-launch HUD or REPL when opening tmux panes (`docs/operations.md:118-123`). | Leave unset for normal behavior. |
| `EMBER_MODEL_URL`, `EMBER_MODEL_DIR`, `LLAMA_DIR`, `EMBER_VAULT_DIR`, `EMBER_USER` | Consumption knobs for `scripts/provision.sh` during first-boot installs. |
| `EMBER_TMUX_SESSION` | Name of the tmux HUD session when using the bundled dotfiles. |

Remember: `export VAR=value` before running `python -m ember` or edit the
systemd/rc files under `/etc` if you need persistent overrides on bare metal.

---

## 7. Troubleshooting & verification

1. Run `/status` in the REPL to inspect diagnostics, log paths, and agent
   results.
2. Use `/config` to dump the merged configuration tree plus the list of YAML
   files currently loaded (read-only view).
3. Review `$VAULT_DIR/logs/agents/core.log` with `vim` or `less` for detailed
   errors.
4. Ensure the vault overrides were actually picked up by checking
   `$VAULT_DIR/config/*.yml` timestamps and contents.
5. When in doubt, temporarily set `EMBER_LOG_LEVEL=DEBUG` and relaunch Ember.

Happy editing! All configuration artifacts are plain text, so `vim` remains the
fastest and most reliable way to manage them in disconnected environments.
