# Provision Agent Guide

The provision agent (`provision.agent`) is Ember’s vault bootstrapper. It runs
on the `bootstrap` trigger to ensure every required directory exists before the
rest of the runtime spins up models, planners, and plugins.

## 1. Responsibilities & data flow

- Reads merged configuration from `ConfigurationBundle` (`ember/agents/provision.py`).
- Creates directories listed under `provision.required_paths` (relative to
  `$VAULT_DIR` unless absolute).
- Records results (created vs. verified paths, issues, last run timestamp) in
  the JSON file defined by `provision.state_file` (defaults to
  `$VAULT_DIR/state/provision.json`).
- Emits diagnostics into the bundle so `/status` surfaces permission or layout
  problems immediately.
- Writes structured output consumed by `/agents` so operators see whether
  provisioning completed, skipped, or partially succeeded.

## 2. Developer guide

Configuration schema (override via `config/system.yml` or a vault file):

```yaml
provision:
  enabled: true                 # set false to disable globally
  skip_env: EMBER_SKIP_PROVISION
  required_paths:
    - config
    - logs
    - logs/agents
    - models
    - plugins
    - state
  state_file: state/provision.json
```

- **Add new directories** whenever a feature requires persistent storage under
  the vault (e.g., `models/gguf`, `logs/metrics`, `plugins/custom`).
- **Skip a single run** by exporting the environment variable defined in
  `skip_env` (`EMBER_SKIP_PROVISION=1 python -m ember`). Handy for read-only
  builds or when you need to inspect an inconsistent vault without mutating it.
- **Extend tests** in `tests/test_provision_agent.py` whenever behavior changes.
  Use the helper `_bundle` to create disposable vault trees.
- **Manual execution**: within a REPL or script run

  ```python
  from ember.configuration import load_runtime_configuration
  from ember.agents.provision import run_provision_agent

  bundle = load_runtime_configuration()
  result = run_provision_agent(bundle)
  print(result.to_dict())
  ```

- **Logging**: the agent logs with the `ember.provision` logger. Set
  `logging.level: DEBUG` while developing to inspect path creation decisions.

## 3. Operator guide

1. Launch Ember (`python -m ember` or the systemd/tmux wrapper). The agent runs
   immediately after configuration loads.
2. Run `/agents` to confirm the entry reports `status=completed` plus counts for
   created/verified paths.
3. Use `/status` during bring-up to see provisioning diagnostics alongside other
   configuration warnings.
4. Inspect `$VAULT_DIR/state/provision.json` for timestamps and details when
   debugging field deployments. The file survives reboots so you can review the
   last run without rerunning the agent.
5. Set `EMBER_SKIP_PROVISION=1` before launching Ember if the vault is mounted
   read-only (e.g., forensic imaging) to avoid write attempts.

## 4. Interaction with Docker & provisioning scripts

- The Dev Docker image installs all Python dependencies via `requirements.txt`,
  so no additional system packages are needed for the agent today. If future
  tooling requires extra utilities (e.g., `rsync` or `parted`), update both the
  `Dockerfile` and the hardware bootstrap scripts below.
- Bare-metal/Raspberry Pi installs rely on `scripts/provision.sh` (Alpine) and
  `scripts/pi_bootstrap.sh` (Debian/Pi OS). These scripts set up `$VAULT_DIR`
  directories before Ember starts, but `provision.agent` is the safety net that
  keeps them in sync.

## 5. Troubleshooting checklist

- **`status=partial`**: review `bundle.diagnostics` via `/status`; the agent
  records permission failures or non-directory conflicts (e.g., a file where a
  folder is expected).
- **State file not updating**: ensure `$VAULT_DIR/state/` is writable. The agent
  appends a diagnostic when it cannot write to disk.
- **Skipped runs**: confirm whether `EMBER_SKIP_PROVISION` (or your override) is
  set in the environment. `/agents` shows `detail=environment variable ... is
  set` for these cases.
- **CI failures**: use the `skip_env` flag inside workflows that purposely run
  with read-only vaults, or mount a tmpfs as the vault path so the agent can
  create directories freely.

Keep this file synchronized with code changes so operators on offline systems
can rely on the bundled documentation.
