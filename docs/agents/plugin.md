# Plugin Agent Guide

`plugin.agent` discovers extension manifests so Ember can expose available tools
without hardcoding them into the runtime. It scans the repo, vault, and
system-wide plugin directories for manifest files and reports each plugin’s
metadata via `/agents` and `/status`.

## 1. Configuration

```yaml
plugin:
  enabled: true
  manifest_name: plugin.yml
  directories:
    - plugins                # relative to repo root
    - /usr/local/ember/plugins
  include_vault: true        # scans $VAULT_DIR/plugins when true
```

- `manifest_name` defines the required file inside each plugin directory.
- `directories` accepts a mix of relative (repo-root) and absolute paths. Use
  a vault override to customize per-device without touching the repo.
- `include_vault` is enabled by default so field deployments can drop plugins
  straight into `$VAULT_DIR/plugins`.

## 2. Manifest schema (`plugin.yml`)

```yaml
name: my-plugin                     # required
version: 1.0.0
description: Adds a custom REPL command.
entrypoint: python3 plugins/my-plugin/main.py
hooks:
  status: plugins/my-plugin/status.py
```

- Only `name` is required; other keys are optional metadata surfaced in
  `/agents`.
- `entrypoint` is informational for now—future work may autoload or execute it.
- `hooks` can announce scripts for future automation; the agent currently just
  records them for inspection.

## 3. Operator workflow

1. Place each plugin inside its own directory (e.g.,
   `$VAULT_DIR/plugins/red-team/`).
2. Create `plugin.yml` following the schema above.
3. Restart Ember or run `/agents`; the plugin should appear with `status=ready`.
4. Fix any parsing issues flagged in `/status` (the agent records warnings when
   manifests are missing/invalid).

## 4. Developer workflow

- Keep manifests committed under `plugins/` when shipping built-in extensions.
- Use vault overrides or `/usr/local/ember/plugins` for site-specific plugins.
- Extend the manifest schema carefully—update this guide, the agent, and add
  tests under `tests/test_plugin_agent.py` so the CI suite enforces the behavior.

## 5. Troubleshooting

- **Missing plugin directories** – the agent silently skips non-existent paths;
  ensure the repo/vault path exists if you expect results.
- **Manifest parse errors** – YAML syntax errors or missing `name` fields mark
  the plugin as `status=invalid` and add a warning diagnostic. Fix the manifest
  and rerun `/agents`.
- **Permissions** – the Ember process must be able to read the directories. Set
  ownership to the `ember` user on production nodes.
