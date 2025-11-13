# NAME

`/config` – Inspect merged Ember configuration and source files.

# SYNOPSIS

```
/config [--yaml]
/config validate
/config <key.path>
/config <key.path> <value>
```

# DESCRIPTION

Displays two Rich panels:

1. **Loaded Config Files** – Ordered list of YAML files that were merged.
2. **Merged Configuration (Tree)** – Hierarchical view of the combined config.

Passing `--yaml` adds a third panel that prints the merged configuration as
YAML, suitable for exporting or diffing. Running `config validate` reloads the
configuration bundle and renders a diagnostics table so you can confirm whether
Ember considers the current YAML valid (handy on CI nodes or before committing
changes).

Providing a dotted key path switches `/config` into direct lookup/set mode:

- `/config <key.path>` – Print the current value (or a notice if it is unset).
- `/config <key.path> <value>` – Write a simple scalar (string/number/bool) into
  `$VAULT_DIR/config/99-cli-overrides.yml` and reload the configuration so the
  new value is available immediately. Array assignments are not supported yet.

# OPTIONS

- `--yaml`, `-y`, `yaml` – Render an additional YAML block.
- `validate`, `--validate`, `-v` – Reload the configuration and display a
  diagnostics summary/table.

# EXAMPLES

- `/config` – Show the file list and tree view.
- `/config --yaml` – Include the YAML export panel.
- `/config validate` – Reload the configuration and display validation status.
- `/config logging.level` – Print the current logging level.
- `/config logging.level DEBUG` – Raise the log level and persist it under
  `$VAULT_DIR/config/99-cli-overrides.yml`.

# SEE ALSO

`/status`, `/help`, `/man config`
