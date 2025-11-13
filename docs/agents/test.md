# Test Agent Guide

`test.agent` runs the Ember test suite (or any custom command) so CI/CD runs and
field diagnostics can surface directly inside `/agents` and `/status`.

## 1. Configuration (`config/system.yml` or vault override)

```yaml
test:
  enabled: false              # opt-in: running tests on bootstrap can be slow
  command: "pytest -q"        # string or list (e.g., [python3, -m, pytest, -q])
  workdir: .                  # defaults to repo root
  report_path: state/test-agent.json
  timeout: 600                # seconds
  env:
    PYTEST_ADDOPTS: "-q"
```

- Set `enabled: true` locally when you want every bootstrap to run tests (e.g.,
  in CI). Operators can toggle this via `agents.enabled`/`agents.disabled`.
- `command` is parsed with `shlex.split` when a string. Provide a list to avoid
  shell quoting issues.
- `workdir` resolves relative to the repo root; point it at subpackages if you
  only want to exercise part of the tree.
- `report_path` lives inside the vault by default. Each run overwrites the JSON
  payload so offline nodes can review the latest log in `$VAULT_DIR/state/`.
- `env` lets you pass feature flags (e.g., `PYTEST_ADDOPTS`). Values are merged
  into the existing environment.

## 2. Runtime behaviour

- Triggered via the normal agent lifecycle. Because it is `default_enabled=False`
  it only runs when explicitly enabled or requested via future triggers.
- Captures stdout/stderr plus exit codes into the JSON report. `/agents` shows
  `passed`, `failed`, or `error/timeout` along with the configured command.
- Adds a diagnostic when the command fails or times out so `/status` flags the
  run.

## 3. Developer workflow

1. Keep the command consistent with local expectations (default `pytest -q`).
2. Update `.toolchain.yml` whenever new tooling is required (e.g., `pytest-xdist`).
3. Extend `tests/test_test_agent.py` when changing behaviour (e.g., new report
   fields) to avoid regressions.
4. Set `test.enabled` in CI-specific config (vault overlay or environment) to
   ensure the agent executes automatically.

## 4. Operator workflow

- Run `/agents` to see the latest test status. A failed suite surfaces as
  `status=failed` with the exit code/duration.
- Inspect the report file for full stdout/stderr:

  ```bash
  less "$VAULT_DIR/state/test-agent.json"
  ```

- Disable the agent (set `test.enabled=false` or add it to `agents.disabled`) on
  constrained hardware where running tests on boot is undesirable.

## 5. Troubleshooting

- **`Command 'pytest' not found`** – ensure the virtualenv is activated or
  change `command` to `python3 -m pytest`.
- **Timeouts** – increase `timeout` for slower hardware. The agent records a
  `timeout` status and leaves partial stdout/stderr in the report.
- **Large logs** – adjust the test command to write JUnit XML or condensed
  output if needed; the agent writes whatever stdout/stderr the command emits.
