#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

log() {
  printf '[configure] %s\n' "$*"
}

fatal() {
  printf '[configure][error] %s\n' "$*" >&2
  exit 1
}

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    fatal "run this command with sudo/root privileges."
  fi
}

detect_os() {
  if [ ! -f /etc/os-release ]; then
    fatal "/etc/os-release not found; cannot detect host distribution."
  fi
  . /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_LIKE="${ID_LIKE:-}"
}

dispatch_configure() {
  target="${EMBER_CONFIGURE_TARGET:-auto}"
  case "$target" in
    alpine)
      log "Forcing Alpine provisioning."
      exec "$SCRIPT_DIR/provision.sh"
      ;;
    pi|pi5|debian)
      log "Forcing Raspberry Pi/Debian bootstrap."
      exec "$SCRIPT_DIR/pi_bootstrap.sh"
      ;;
    auto)
      if [ "$OS_ID" = "alpine" ]; then
        log "Detected Alpine Linux; running provision.sh"
        exec "$SCRIPT_DIR/provision.sh"
      fi
      if echo "$OS_ID $OS_LIKE" | grep -qiE '(debian|raspbian|ubuntu)'; then
        log "Detected Debian-like host; running pi_bootstrap.sh"
        exec "$SCRIPT_DIR/pi_bootstrap.sh"
      fi
      ;;
  esac
  fatal "unsupported distribution '$OS_ID' (set EMBER_CONFIGURE_TARGET=alpine or pi to override)."
}

main() {
  require_root
  detect_os
  dispatch_configure
}

main "$@"
