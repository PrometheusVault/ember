#!/bin/sh
set -eu

EMBER_USER="${EMBER_USER:-ember}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_DIR="$REPO_ROOT/templates"
VAULT_DIR="${EMBER_VAULT_DIR:-$REPO_ROOT/vault}"
VENV_DIR="$REPO_ROOT/.venv"
EMBER_HOME="/home/$EMBER_USER"
INITTAB_PATH="/etc/inittab"
LLAMA_DIR="${LLAMA_DIR:-/opt/llama.cpp}"
LLAMA_REPO="${LLAMA_REPO:-https://github.com/ggerganov/llama.cpp.git}"
MODEL_URL="${EMBER_MODEL_URL:-https://huggingface.co/QuantFactory/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf}"
MODEL_DIR="${EMBER_MODEL_DIR:-$REPO_ROOT/models}"
MODEL_FILENAME="$(basename "$MODEL_URL")"
[ "$MODEL_FILENAME" != "" ] || MODEL_FILENAME="default-model.gguf"
MODEL_PATH="$MODEL_DIR/$MODEL_FILENAME"
APK_PRUNE="${APK_PRUNE:-}"

log() {
  printf '[ember-install] %s\n' "$*"
}

fatal() {
  printf '[ember-install][error] %s\n' "$*" >&2
  exit 1
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    fatal "run this script as root (needed for apk, adduser, and /etc updates)"
  fi
}

ensure_alpine() {
  if [ ! -f /etc/os-release ]; then
    fatal "/etc/os-release not found; this script expects Alpine Linux"
  fi
  if ! grep -q '^ID=alpine' /etc/os-release; then
    fatal "non-Alpine distribution detected; aborting to avoid misconfiguration"
  fi
}

apk_bootstrap() {
  log "updating apk indexes"
  apk update >/dev/null
  log "installing system packages"
  apk add --no-cache python3 py3-pip py3-virtualenv tmux zsh shadow sudo git curl build-base cmake bash >/dev/null
}

ensure_user() {
  if id "$EMBER_USER" >/dev/null 2>&1; then
    log "user '$EMBER_USER' already exists"
    return
  fi

  log "creating user '$EMBER_USER'"
  adduser -D -s /bin/zsh "$EMBER_USER"
}

ensure_home_permissions() {
  if [ ! -d "$EMBER_HOME" ]; then
    fatal "expected home directory $EMBER_HOME to exist for $EMBER_USER"
  fi
  log "ensuring $EMBER_HOME belongs to $EMBER_USER"
  chown -R "$EMBER_USER:$EMBER_USER" "$EMBER_HOME"
}

ensure_repo_permissions() {
  log "ensuring repository at $REPO_ROOT is owned by $EMBER_USER"
  chown -R "$EMBER_USER:$EMBER_USER" "$REPO_ROOT"
}

ensure_vault_dir() {
  if [ ! -d "$VAULT_DIR" ]; then
    log "creating vault directory at $VAULT_DIR"
    mkdir -p "$VAULT_DIR"
  fi
  chown -R "$EMBER_USER:$EMBER_USER" "$VAULT_DIR"
}

setup_python_env() {
  if [ ! -d "$VENV_DIR" ]; then
    log "creating python virtualenv in $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  else
    log "virtualenv already exists at $VENV_DIR"
  fi

  log "installing python dependencies"
  "$VENV_DIR/bin/pip" install --upgrade pip >/dev/null
  "$VENV_DIR/bin/pip" install --no-cache-dir -r "$REPO_ROOT/requirements.txt" >/dev/null
  chown -R "$EMBER_USER:$EMBER_USER" "$VENV_DIR"
}

escape_sed_value() {
  printf '%s' "$1" | sed -e 's/[\\/&]/\\&/g'
}

render_template() {
  src="$1"
  dest="$2"
  mode="$3"
  owner="$4"

  tmp_file="$(mktemp)"
  cp "$src" "$tmp_file"

  repo_escaped="$(escape_sed_value "$REPO_ROOT")"
  vault_escaped="$(escape_sed_value "$VAULT_DIR")"
  model_escaped="$(escape_sed_value "$MODEL_PATH")"
  llama_dir_escaped="$(escape_sed_value "$LLAMA_DIR")"

  sed -i "s/{{REPO_DIR}}/$repo_escaped/g" "$tmp_file"
  sed -i "s/{{VAULT_DIR}}/$vault_escaped/g" "$tmp_file"
  sed -i "s/{{MODEL_PATH}}/$model_escaped/g" "$tmp_file"
  sed -i "s/{{LLAMA_DIR}}/$llama_dir_escaped/g" "$tmp_file"

  dest_dir="$(dirname "$dest")"
  mkdir -p "$dest_dir"
  install -m "$mode" "$tmp_file" "$dest"
  chown "$owner:$owner" "$dest"
  rm -f "$tmp_file"
}

install_user_templates() {
  log "installing template dotfiles"
  render_template "$TEMPLATE_DIR/tmux.conf" "$EMBER_HOME/.tmux.conf" 0644 "$EMBER_USER"
  render_template "$TEMPLATE_DIR/zshrc" "$EMBER_HOME/.zshrc" 0644 "$EMBER_USER"
  render_template "$TEMPLATE_DIR/zprofile" "$EMBER_HOME/.zprofile" 0644 "$EMBER_USER"
}

configure_autologin() {
  if [ ! -f "$INITTAB_PATH" ]; then
    fatal "$INITTAB_PATH not found; cannot configure autologin"
  fi

  if grep -q "agetty --autologin $EMBER_USER" "$INITTAB_PATH"; then
    log "agetty autologin already configured"
    return
  fi

  log "configuring tty1 autologin for $EMBER_USER"
  cp "$INITTAB_PATH" "$INITTAB_PATH.ember.bak"
  if grep -q '^tty1::' "$INITTAB_PATH"; then
    sed -i "s|^tty1::.*|tty1::respawn:/sbin/agetty --autologin $EMBER_USER --noclear 38400 tty1 linux|" "$INITTAB_PATH"
  else
    cat >>"$INITTAB_PATH" <<EOF
tty1::respawn:/sbin/agetty --autologin $EMBER_USER --noclear 38400 tty1 linux
EOF
  fi
}

ensure_tmux_script_exec() {
  chmod +x "$REPO_ROOT/ember/ember_dev_run.sh"
  chmod +x "$REPO_ROOT/scripts/tmux_pane.sh"
  chmod +x "$REPO_ROOT/scripts/tmux_battery.sh"
}

cpu_count() {
  if command -v nproc >/dev/null 2>&1; then
    nproc
  else
    getconf _NPROCESSORS_ONLN 2>/dev/null || printf '1'
  fi
}

sync_llama_cpp() {
  parent_dir="$(dirname "$LLAMA_DIR")"
  mkdir -p "$parent_dir"
  if [ -d "$LLAMA_DIR/.git" ]; then
    log "updating llama.cpp in $LLAMA_DIR"
    git -C "$LLAMA_DIR" fetch --depth 1 origin master >/dev/null
    git -C "$LLAMA_DIR" reset --hard origin/master >/dev/null
  else
    log "cloning llama.cpp into $LLAMA_DIR"
    rm -rf "$LLAMA_DIR"
    git clone --depth 1 "$LLAMA_REPO" "$LLAMA_DIR" >/dev/null
  fi
}

build_llama_cpp() {
  log "building llama.cpp (this can take a few minutes)"
  cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF >/dev/null
  cmake --build "$LLAMA_DIR/build" -j "$(cpu_count)" >/dev/null
  if [ -x "$LLAMA_DIR/build/bin/llama-cli" ]; then
    install -m 0755 "$LLAMA_DIR/build/bin/llama-cli" /usr/local/bin/llama-cli
  fi
  if [ -x "$LLAMA_DIR/build/bin/llama-quantize" ]; then
    install -m 0755 "$LLAMA_DIR/build/bin/llama-quantize" /usr/local/bin/llama-quantize
  fi
  chown -R "$EMBER_USER:$EMBER_USER" "$LLAMA_DIR"
}

install_llama_cpp() {
  sync_llama_cpp
  build_llama_cpp
}

download_llama_model() {
  if [ -z "$MODEL_URL" ]; then
    log "MODEL_URL not provided; skipping model download"
    return
  fi
  mkdir -p "$MODEL_DIR"
  if [ -f "$MODEL_PATH" ]; then
    log "model already present at $MODEL_PATH"
    chown "$EMBER_USER:$EMBER_USER" "$MODEL_PATH"
    return
  fi

  tmp_file="$MODEL_PATH.part"
  log "downloading LLM from $MODEL_URL (this may take a while)"
  if ! curl -L --fail --progress-bar "$MODEL_URL" -o "$tmp_file"; then
    rm -f "$tmp_file"
    fatal "failed to download model from $MODEL_URL"
  fi
  mv "$tmp_file" "$MODEL_PATH"
  chown "$EMBER_USER:$EMBER_USER" "$MODEL_PATH"
}

prune_packages() {
  if [ -z "$APK_PRUNE" ]; then
    return
  fi
  log "removing optional packages: $APK_PRUNE"
  apk del $APK_PRUNE >/dev/null || log "warning: apk del returned non-zero status"
}

main() {
  require_root
  ensure_alpine
  apk_bootstrap
  ensure_user
  ensure_home_permissions
  ensure_repo_permissions
  ensure_vault_dir
  setup_python_env
  install_user_templates
  configure_autologin
  ensure_tmux_script_exec
  install_llama_cpp
  download_llama_model
  prune_packages

  log "installation complete."
  log "Reboot or restart tty1 (kill -HUP \$(pgrep -f tty1)) for autologin changes to take effect."
  log "Set EMBER_SKIP_AUTO_TMUX=1 before logging in to bypass the HUD."
  log "llama.cpp binaries live in $LLAMA_DIR and the default model is $MODEL_PATH"
}

main "$@"
