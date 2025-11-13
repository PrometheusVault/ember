# NAME

`/status` – Show vault paths, configuration diagnostics, and agent results.

# SYNOPSIS

```
/status [section ...] [--all]
```

# DESCRIPTION

Renders a Rich summary of runtime state. Sections can be requested
individually:

- `info` – vault dir, configuration status, files loaded.
- `diagnostics` – warnings/errors gathered during configuration load.
- `agents` – most recent results from enabled agents.

Pass `--all` (or `-a`) to bypass pagination in diagnostics/agents tables.

# OPTIONS

- `info | diagnostics | agents` – Optional section names; multiple can be
  provided.
- `--all`, `-a`, `all` – Show every row instead of truncating to five.

# EXAMPLES

- `/status` – Render all sections with pagination.
- `/status diagnostics` – Only display diagnostics findings.
- `/status agents --all` – Show the full agent table without truncation.

# SEE ALSO

`/config`, `/update`, `/man status`
