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

Away from a shell? Use `/config <key>` to inspect a single value or
`/config <key> <value>` in the REPL to write machine-local overrides into
`$VAULT_DIR/config/99-cli-overrides.yml` without leaving Ember. The command
reloads the configuration immediately so follow-up commands see the new value.

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

Tips:

- Set `logging.level: DEBUG` (or export `EMBER_LOG_LEVEL=DEBUG`) to trace
  planner/responder prompts and llama.cpp interactions directly in the REPL.
- Leave it at `INFO` for normal usage so only high-level events are surfaced.
- Keep `agents.enabled` empty unless you truly need an allow-list—`core.agent`
  records the default policy and lets every default-enabled agent run otherwise.

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

Need the full agent flow? See `docs/agents/provision.md` for developer +
operator guidance.

---

## 4. Network agent settings

Use the `network` block to tune how `network.agent` inspects interfaces and
optionally performs connectivity probes:

```yaml
network:
  enabled: true              # disable entirely by setting to false
  preferred_interfaces:
    - eth0                   # prioritized when reporting `primary_interface`
    - wlan0
  include_loopback: false    # set true to show lo*/loopback adapters
  connectivity_checks:
    - 1.1.1.1:53             # optional TCP host[:port] probes
  connectivity_timeout: 1.0  # seconds per check (floats/ints allowed)
  dns_paths:
    - /etc/resolv.conf       # files to scan for `nameserver` entries
```

- When `connectivity_checks` is empty the agent simply reports interface/DNS
  state so air-gapped nodes never wait on outbound sockets.
- Populate `preferred_interfaces` on devices with multiple NICs so `/agents`
  consistently spotlights the interface you care about first.
- Override `dns_paths` if your distro stores resolver config elsewhere (e.g.,
  `/run/systemd/resolve/resolv.conf`). The agent reads every listed file in
  order and ignores files that are missing.

`network.agent` runs even when the configuration bundle is still marked
`missing`/`invalid`, meaning it can surface degraded/offline status before the
rest of the runtime is ready.

## 5. Toolchain agent settings

`toolchain.agent` reads `.toolchain.yml` (repo root by default) to confirm
Docker, Make, git, Python dependencies, and environment variables are ready for
dev workflows.

```yaml
toolchain:
  enabled: true
  manifest: .toolchain.yml   # relative to repo root; absolute paths supported
```

- Keep `.toolchain.yml` under version control so contributors see which binaries
  are required for `make build`, `make shell`, and local provisioning.
- Override the manifest per-host (e.g., drop-in YAML inside `$VAULT_DIR/config`)
  when staging experimental toolchains.
- `/agents` shows which requirements are missing and includes version strings
  when `version_command` is specified in the manifest.
- See `docs/agents/toolchain.md` for the manifest schema and workflow tips.

## 6. Plugin agent settings

`plugin.agent` scans plugin directories for `plugin.yml` manifests so Ember can
surface available extensions.

```yaml
plugin:
  enabled: true
  manifest_name: plugin.yml
  directories:
    - plugins
    - /usr/local/ember/plugins
  include_vault: true
```

- Relative directories resolve against the repo root. Add absolute paths for
  system-wide plugin drops.
- When `include_vault` is true the agent scans `$VAULT_DIR/plugins` so field
  teams can ship plugins without rebuilding the repo.
- Each plugin directory must contain `plugin.yml` with at least a `name`. See
  `docs/agents/plugin.md` for the manifest schema.
- `/agents` reports any parsing errors as `status=invalid` and logs a diagnostic
  so operators can fix malformed manifests quickly.

## 7. Update agent settings

`update.agent` summarizes git status so operators can decide when to run future
update workflows.

```yaml
update:
  enabled: false
  allowed_branches:
    - main
  fetch: false
```

- Set `enabled: true` on monitoring/CI nodes or when testing update flows.
- `allowed_branches` marks which branches are safe for auto-update. Being on a
  different branch sets `status=degraded`.
- `fetch: true` runs `git fetch --dry-run` so the agent can report whether new
  commits exist without modifying the working tree.
- Full guidance lives in `docs/agents/update.md`.

## 8. Logging configuration

- `logging.level` controls the baseline verbosity.
- Ember writes to `$VAULT_DIR/logs/agents/core.log` with rotation. If the vault
  is not writable it falls back to `./.ember_runtime/logs/agents/core.log` and
  emits a warning (`ember/logging_utils.py` tests cover this behavior).
- Use `/status` to view the active log path or edit the vault/log permissions
  with `sudo chown -R ember:ember "$VAULT_DIR/logs"`.

---

## 9. Agent enablement and overrides

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

## 10. Operator UI settings

`ui.verbose` governs how chatty the REPL is. Leaving it `true` shows the banner,
planner panels, and tool summaries suited for development. Setting it to `false`
simulates the headless production HUD: no ASCII art banner, no planner panel,
and final responses are rendered as plain text with a terse `[tools]` summary.

```yaml
ui:
  verbose: false
```

The `EMBER_UI_VERBOSE` environment variable overrides the YAML (accepts
`1/true/on` or `0/false/off`). Use it when you need a quick quiet session
without editing config files.

---

## 11. Knowledge base ingestion

Ember keeps llama.cpp grounded with whatever survival manuals you stash on disk.
Treat the **vault** (`$VAULT_DIR`) as the authoritative library: folders named
`library/`, `reference/`, `docs/`, `notes/`, `knowledge/`, or `almanac/`
automatically feed into the prompt cache. Files ending in `.md`, `.markdown`, or
`.txt` are eligible, and Ember reads the first ~2 KB from up to 10 files per
directory. Drop your own almanacs, checklists, and regional guides inside those
folders (or create symlinks) and relaunch Ember to refresh the prompt cache.

For convenience the repo still scans optional directories (`reference/`,
`library/`, `docs/reference/`, `docs/library/`) when they exist, but the vault
is the only location that survives upgrades. Developer/operator docs such as
`README.md` and `AGENTS.md` are intentionally excluded for now so responses stay
focused on world knowledge rather than repo internals.

---

## 12. Environment variables cheat sheet

These are read during bootstrap or by helper scripts; set them in your shell,
systemd unit, or tmux profile as needed:

| Variable | Purpose | Default/Notes |
| --- | --- | --- |
| `VAULT_DIR` | Points Ember at the active vault. | Defaults to `/vault` (`ember/app.py:46`). |
| `EMBER_MODE` | Freeform label printed in the banner. | `DEV (Docker)` when unset. |
| `EMBER_LOG_LEVEL` | Overrides `logging.level` at runtime. | Upper-cased value; `WARNING` default. |
| `EMBER_UI_VERBOSE` | Forces HUD verbosity (`1/true/on` vs `0/false/off`). | Overrides `ui.verbose`; defaults to verbose. |
| `LLAMA_CPP_MODEL` (+ `LLAMA_CPP_MAX_TOKENS`, `LLAMA_CPP_THREADS`, `LLAMA_CPP_TEMPERATURE`, `LLAMA_CPP_TOP_P`, `LLAMA_CPP_TIMEOUT`) | Tuning knobs for the local llama.cpp binding (`README.md`). | Set per session or inject via `make dev ENV_VARS="..."`. |
| `EMBER_SKIP_PROVISION` | Skips the provisioning agent once. | Useful for read-only media. |
| `EMBER_SKIP_AUTO_TMUX` / `EMBER_SKIP_AUTO_REPL` | Bypass the auto-launch HUD or REPL when opening tmux panes (`docs/operations.md:118-123`). | Leave unset for normal behavior. |
| `EMBER_MODEL_URL`, `EMBER_MODEL_DIR`, `LLAMA_DIR`, `EMBER_VAULT_DIR`, `EMBER_USER` | Consumption knobs for `scripts/provision.sh` during first-boot installs. |
| `EMBER_TMUX_SESSION` | Name of the tmux HUD session when using the bundled dotfiles. |

Remember: `export VAR=value` before running `python -m ember` or edit the
systemd/rc files under `/etc` if you need persistent overrides on bare metal.

---

## 13. Troubleshooting & verification

1. Run `/status` in the REPL to inspect diagnostics, log paths, and agent
   results.
2. Use `/config` to dump the merged configuration tree plus the list of YAML
   files currently loaded (read-only view). Run `/config validate` when you need
   a fresh diagnostics summary without restarting Ember.
3. Review `$VAULT_DIR/logs/agents/core.log` with `vim` or `less` for detailed
   errors.
4. Ensure the vault overrides were actually picked up by checking
   `$VAULT_DIR/config/*.yml` timestamps and contents.
5. When in doubt, temporarily set `EMBER_LOG_LEVEL=DEBUG` and relaunch Ember.

Happy editing! All configuration artifacts are plain text, so `vim` remains the
fastest and most reliable way to manage them in disconnected environments.
