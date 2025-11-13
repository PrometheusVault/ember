# Update Agent Guide

`update.agent` provides a lightweight readiness check for future self-update
flows. It inspects the local git repository to ensure the working tree is clean,
on an allowed branch, and optionally performs a dry-run fetch so operators know
when new commits are available.

## 1. Configuration (`config/system.yml`)

```yaml
update:
  enabled: false               # disabled by default
  allowed_branches:
    - main
    - release
  fetch: false                 # set true to run `git fetch --dry-run`
```

- Enable the agent on CI or admin nodes that monitor repo state. Leave it
  disabled on constrained devices where git is unavailable.
- `allowed_branches` prevents accidental updates from feature branches. The
  agent reports `status=degraded` when the current HEAD is outside this list.
- `fetch: true` runs `git fetch --dry-run` (no network writes) to flag when new
  commits are available upstream. The output is stored in the agent detail.

## 2. Runtime behaviour

- Runs during the bootstrap trigger when enabled.
- Executes `git rev-parse` to capture the current branch/commit and
  `git status --porcelain` to detect dirty working trees.
- Adds a diagnostic if git is unavailable or the repo is malformed.

## 3. Operator workflow

1. Enable the agent (config override or `agents.enabled`) on the node.
2. Run `/agents` to see the branch, commit, dirty flag, and fetch summary.
3. Clean the working tree (`git status` should be empty) before invoking future
   `/update` commands or manual pulls.

## 4. Future integration

- The current implementation only reports readiness. Upcoming work will tie
  this data into scripted update flows that fetch/apply new releases or staged
  artifacts.
- When extending functionality (e.g., adding `channels`, `artifacts`, or
  `signed manifests`), update this guide plus `ember/agents/update_agent.py`
  tests to ensure the `/agents` output stays reliable.

## 5. Troubleshooting

- **Missing git** – ensure `git` is installed (see `.toolchain.yml`). The agent
  reports `status=error` when the binary is missing.
- **Dirty working tree** – commit or stash local changes. The agent keeps
  reporting `degraded` until `git status --porcelain` is empty.
- **Branch not allowed** – update `allowed_branches` or switch to an approved
  branch before running updates.
