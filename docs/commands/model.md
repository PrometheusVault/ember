# NAME

`/model` – Show or change the active llama.cpp model.

# SYNOPSIS

```
/model
/model set <path-or-name>
```

# DESCRIPTION

`/model` without arguments prints the currently loaded model path plus any
models discovered under the standard search directories (`./models`,
`/srv/ember/models`, `/opt/ember-app/models`, `/opt/llama.cpp/models`).

Use `set` with either an absolute/relative path or the basename of a discovered
model to switch. The new path is validated before the backing llama session is
reloaded; models are reloaded lazily when the next prompt runs.

# EXAMPLES

- `/model` – Inspect the current model and local candidates.
- `/model set models/llama-3b.gguf` – Switch to a specific file.
- `/model set llama-3b.gguf` – Switch using the basename from the discovered list.

# SEE ALSO

`docs/operations.md`, `docs/configuration.md`
