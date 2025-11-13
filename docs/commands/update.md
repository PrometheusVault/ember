# NAME

`/update` – Fetch the latest git changes and rerun provisioning.

# SYNOPSIS

```
/update
```

# DESCRIPTION

Runs three steps from the repo root:

1. `git fetch --prune`
2. `git pull --ff-only`
3. `scripts/provision.sh` (with `sudo -E` when available)

Outputs the exit code plus captured stdout/stderr for each stage.

# EXAMPLES

- `/update` – Sync to origin/main and reapply the provisioner.

# SEE ALSO

`/status`, `/config`, `/man update`
