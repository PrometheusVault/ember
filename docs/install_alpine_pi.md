# Ember Install Guide – Alpine Linux on Raspberry Pi

These steps assume a freshly imaged Alpine Linux system running on Raspberry Pi
hardware with a working network connection. Commands prefixed with `#` require
root (use `sudo` if you are logged in as a non-root user).

---

## 1. Prepare the base system

```sh
# apk update && apk upgrade
apk update
apk upgrade

# Install git (needed to pull the repo) and basic tooling
apk add git curl
```

Make sure the system clock is roughly correct (TLS/SSL downloads will fail
otherwise):

```sh
date
```

Adjust with `hwclock` or `date -s` if necessary.

---

## 2. Pull the Ember repository

Clone the repo somewhere managed by root (so we can hand ownership to the
`ember` user later). `/opt/PrometheusVault/ember` keeps both the vendor and
project in the path, but any writable location works:

```sh
mkdir -p /opt/PrometheusVault
cd /opt/PrometheusVault
git clone https://github.com/PrometheusVault/ember.git
cd ember
```

---

## 3. Run the configure helper

`make configure` auto-detects Alpine and dispatches to
`scripts/provision.sh`, which:

- Installs Python, tmux, zsh, curl, build tools, etc.
- Creates (or updates) the `ember` user/home directory.
- Builds the virtualenv, installs Python deps, and renders tmux/zsh dotfiles.
- Configures tty1 autologin so the tmux HUD launches automatically.
- Clones/compiles `llama.cpp`, downloads a default GGUF model, and ensures the
  vault directory exists.

Run it with sudo/root privileges (from the repo root you just cloned):

```sh
sudo make configure
# or explicitly: sudo EMBER_CONFIGURE_TARGET=alpine ./scripts/configure_system.sh
```

Provisioning is idempotent; re-run the command after future `git pull` updates.

---

## 4. Reboot and verify

```sh
sudo reboot
```

After the Pi restarts:

1. It will autologin on tty1 as the `ember` user.
2. tmux starts automatically with the Ember HUD at the top of the screen.
3. The Ember REPL launches in the active pane. Use `/status` to confirm the
   vault path and provisioning diagnostics.

Detach from the HUD with `Ctrl-a d` (prefix default is `Ctrl-a`). Reattach via
`tmux attach -t ember` or run `./ember/ember_dev_run.sh`.

---

## 5. Optional settings

- Point Ember at a different vault directory:
  ```sh
  sudo sh -c 'export EMBER_VAULT_DIR=/data/vault && ./scripts/provision.sh'
  ```
- Skip the auto-launch HUD for one login by exporting `EMBER_SKIP_AUTO_TMUX=1`
  before logging in (useful for maintenance shells).
- Override the default GGUF model URL by setting `EMBER_MODEL_URL` before
  running the provisioner.

---

## 6. Troubleshooting

- If `make configure` fails because git is missing, re-run `apk add git` and try
  again.
- Permission errors writing to the vault usually mean the SD card/partition is
  read-only or not owned by `ember`. Fix with:
  ```sh
  sudo chown -R ember:ember /home/ember/vault
  ```
- `tmux` not starting? Ensure `/home/ember/.tmux.conf` exists (provisioner
  renders it) and rerun `sudo make configure`.

Once the base install is working, consult `docs/operations.md` for day-to-day
workflow details and `docs/configuration.md` for editing YAML overrides.
