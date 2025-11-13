#!/usr/bin/env bash
set -euo pipefail

EMBER_USER="${EMBER_USER:-ember}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_DIR="$REPO_ROOT/templates"
VAULT_DIR="${EMBER_VAULT_DIR:-/home/$EMBER_USER/vault}"
VENV_DIR="${EMBER_VENV_DIR:-$REPO_ROOT/.venv}"
SERVICE_NAME="${EMBER_SERVICE_NAME:-ember.service}"
SYSTEMD_DIR="/etc/systemd/system"

log() {
  printf '[pi-bootstrap] %s\n' "$*"
}

fatal() {
  printf '[pi-bootstrap][error] %s\n' "$*" >&2
  exit 1
}

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    fatal "run this script with sudo/root privileges."
  fi
}

ensure_debian_like() {
  if [ ! -f /etc/os-release ]; then
    fatal "/etc/os-release not found; cannot detect host OS."
  fi
  . /etc/os-release
  if ! echo "${ID:-} ${ID_LIKE:-}" | grep -qiE '(debian|raspbian|ubuntu)'; then
    fatal "This bootstrap script targets Raspberry Pi OS/Debian. Detected ID='${ID:-unknown}'."
  fi
}

apt_bootstrap() {
  log "updating apt indexes"
  apt-get update -y >/dev/null
  log "installing system packages"
  apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    tmux \
    zsh \
    git \
    curl \
    libcurl4-openssl-dev \
    build-essential \
    pkg-config \
    cmake \
    linux-headers-$(uname -r | sed 's/-.*//') \
    libopenblas-dev \
    libffi-dev \
    sudo \
    util-linux \
    docker.io >/dev/null
}

ensure_user() {
  if id "$EMBER_USER" >/dev/null 2>&1; then
    log "user '$EMBER_USER' already exists"
    return
  fi
  log "creating user '$EMBER_USER'"
  adduser --disabled-password --gecos "" "$EMBER_USER"
  usermod -aG tty "$EMBER_USER"
}

ensure_repo_permissions() {
  log "ensuring repository ownership for $EMBER_USER"
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
    log "creating python virtualenv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
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
  venv_escaped="$(escape_sed_value "$VENV_DIR")"
  user_escaped="$(escape_sed_value "$EMBER_USER")"

  sed -i "s/{{REPO_DIR}}/$repo_escaped/g" "$tmp_file"
  sed -i "s/{{VAULT_DIR}}/$vault_escaped/g" "$tmp_file"
  sed -i "s/{{VENV_DIR}}/$venv_escaped/g" "$tmp_file"
  sed -i "s/{{EMBER_USER}}/$user_escaped/g" "$tmp_file"

  dest_dir="$(dirname "$dest")"
  mkdir -p "$dest_dir"
  install -m "$mode" "$tmp_file" "$dest"
  chown "$owner:$owner" "$dest"
  rm -f "$tmp_file"
}

install_user_templates() {
  log "installing tmux/zsh templates"
  render_template "$TEMPLATE_DIR/tmux.conf" "/home/$EMBER_USER/.tmux.conf" 0644 "$EMBER_USER"
  render_template "$TEMPLATE_DIR/zshrc" "/home/$EMBER_USER/.zshrc" 0644 "$EMBER_USER"
  render_template "$TEMPLATE_DIR/zprofile" "/home/$EMBER_USER/.zprofile" 0644 "$EMBER_USER"
}

ensure_exec_scripts() {
  chmod +x "$REPO_ROOT/ember/ember_dev_run.sh"
  chmod +x "$REPO_ROOT/scripts/tmux_pane.sh"
  chmod +x "$REPO_ROOT/scripts/tmux_battery.sh"
}

install_systemd_service() {
  unit_path="$SYSTEMD_DIR/$SERVICE_NAME"
  log "installing systemd unit to $unit_path"
  render_template "$TEMPLATE_DIR/ember.service" "$unit_path" 0644 root
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
}

maybe_enable_autologin() {
  # Create override to auto-login the ember user on tty1
  override_dir="/etc/systemd/system/getty@tty1.service.d"
  mkdir -p "$override_dir"
  cat >"$override_dir/autologin.conf" <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $EMBER_USER --noclear %I \$TERM
EOF
  systemctl daemon-reload
  systemctl restart "getty@tty1.service"
}

main() {
  require_root
  ensure_debian_like
  apt_bootstrap
  ensure_user
  ensure_repo_permissions
  ensure_vault_dir
  setup_python_env
  install_user_templates
  ensure_exec_scripts
  install_systemd_service
  maybe_enable_autologin
  log "Bootstrap complete. The tmux HUD should appear on tty1 after reboot."
}

main "$@"
