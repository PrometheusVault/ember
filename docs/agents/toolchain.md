# Toolchain Agent Guide

`toolchain.agent` keeps the development workflow honest: it inspects the
toolchain manifest (`.toolchain.yml`) and reports whether required binaries,
Python modules, files, and environment variables are ready for `make build`,
`make dev`, and related commands.

## 1. Manifest structure (`.toolchain.yml`)

```yaml
commands:
  - name: docker
    description: Required for container workflows
  - name: make
  - name: git
  - name: tmux        # optional example
    optional: true
python:
  - module: click
  - module: llama_cpp
files:
  - path: Makefile
env:
  - name: VAULT_DIR
    optional: true
```

- **commands** – each item checks `shutil.which(name)`; if `version_command` is
  supplied (e.g., `"docker --version"`) the output is captured for diagnostics.
- **python** – resolves import availability via `importlib.util.find_spec`.
- **files** – ensures critical files (Makefile, scripts) exist.
- **env** – verifies environment variables like `VAULT_DIR` are set when needed.

Override the manifest path per node via `config/system.yml`:

```yaml
toolchain:
  enabled: true
  manifest: .toolchain.yml
```

## 2. How the agent runs

- Triggered during Ember bootstrap so `/agents` and `/status` list readiness
  before the REPL prompt.
- Returns `status=ok` when every required entry is available, `degraded` when at
  least one required item is missing, and `error` when the manifest cannot be
  loaded.
- Optional entries never cause `degraded`, but are still reported so teams can
  see when “nice-to-have” utilities (like tmux) are missing.

## 3. Developer workflow

1. Update `.toolchain.yml` whenever Makefile targets or provisioning scripts
   learn a new dependency (Docker CLI, git-lfs, etc.).
2. Run `pytest tests/test_toolchain_agent.py` to validate schema/logic changes.
3. If the manifest references a binary that is not installed in the dev Docker
   image or provisioning scripts, update:
   - `Dockerfile` (apt install block)
   - `scripts/provision.sh` (Alpine `apk add` list)
   - `scripts/pi_bootstrap.sh` (Debian `apt-get install` list)
4. Surface any new environment knobs in `docs/configuration.md` and the agent
   manifest so downstream users immediately see what changed.

## 4. Operator workflow

- After running `make configure` (or the platform-specific bootstrap script),
  execute `/agents` in the REPL. The Toolchain row lists per-command results and
  the manifest path.
- Use the structured output to remediate missing binaries (`sudo apk add docker`
  on Alpine, `sudo apt install docker.io` on Debian, etc.).
- Optional entries act as recommendations. Required entries correspond to
  regressions (e.g., missing Docker CLI breaks `make build`).

## 5. Troubleshooting

- **Manifest not found** – ensure `.toolchain.yml` exists and is readable by the
  Ember user. The agent reports `status=error` with a diagnostic when missing.
- **False negatives** – if the host keeps tools outside `$PATH`, add wrapper
  scripts or adjust the manifest to point at the correct binary name.
- **Python module mismatch** – the agent only checks importability. If a module
  exists but is outdated, specify a `version_command` that shells into the
  interpreter (e.g., `"python3 -c 'import foo; print(foo.__version__)'"`).

Keep this guide close to the code: update it alongside `.toolchain.yml`, the
Dockerfile, and provisioning scripts whenever the toolchain requirements change.
