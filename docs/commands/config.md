# NAME

`/config` – Inspect merged Ember configuration and source files.

# SYNOPSIS

```
/config [--yaml]
```

# DESCRIPTION

Displays two Rich panels:

1. **Loaded Config Files** – Ordered list of YAML files that were merged.
2. **Merged Configuration (Tree)** – Hierarchical view of the combined config.

Passing `--yaml` adds a third panel that prints the merged configuration as
YAML, suitable for exporting or diffing.

# OPTIONS

- `--yaml`, `-y`, `yaml` – Render an additional YAML block.

# EXAMPLES

- `/config` – Show the file list and tree view.
- `/config --yaml` – Include the YAML export panel.

# SEE ALSO

`/status`, `/help`, `/man config`
