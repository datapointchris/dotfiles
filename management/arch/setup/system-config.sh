#!/usr/bin/env bash
set -euo pipefail

# NOTE: Use exported DOTFILES_DIR from install.sh for consistency.
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Runtime systemctl commands (start, is-active) require a running systemd.
# Enable/disable/is-enabled only manage symlinks and work without one.
SYSTEMD_RUNNING=false
if [[ -d /run/systemd/system ]]; then
  SYSTEMD_RUNNING=true
fi

# ── Docker ──────────────────────────────────────────────────────

print_section "Configuring Docker"

CURRENT_USER="$(whoami)"

if ! getent group docker &>/dev/null; then
  log_info "Creating docker group..."
  sudo groupadd docker
fi

if id -nG "$CURRENT_USER" | grep -qw docker; then
  log_info "User $CURRENT_USER already in docker group"
else
  log_info "Adding $CURRENT_USER to docker group..."
  sudo usermod -aG docker "$CURRENT_USER"
  log_success "Added $CURRENT_USER to docker group (re-login to take effect)"
fi

if systemctl is-enabled docker.socket &>/dev/null; then
  log_info "docker.socket already enabled"
else
  log_info "Enabling docker.socket (socket activation)..."
  sudo systemctl enable docker.socket
  log_success "docker.socket enabled"
fi

if [[ "$SYSTEMD_RUNNING" == "true" ]]; then
  if systemctl is-active docker.socket &>/dev/null; then
    log_info "docker.socket already active"
  else
    log_info "Starting docker.socket..."
    sudo systemctl start docker.socket
    log_success "docker.socket started"
  fi
else
  log_info "Skipping docker.socket start (no running systemd)"
fi

# ── GDM ─────────────────────────────────────────────────────────

print_section "Configuring display manager"

if systemctl is-enabled gdm &>/dev/null; then
  log_info "Disabling GDM (using TTY auto-login for Hyprland)..."
  sudo systemctl disable gdm
  log_success "GDM disabled"
else
  log_info "GDM not enabled, nothing to do"
fi

# ── TTY Auto-login ──────────────────────────────────────────────

print_section "Configuring TTY auto-login"

AUTOLOGIN_DIR="/etc/systemd/system/getty@tty1.service.d"
AUTOLOGIN_CONF="$AUTOLOGIN_DIR/autologin.conf"

if [[ -f "$AUTOLOGIN_CONF" ]] && grep -q "autologin $CURRENT_USER" "$AUTOLOGIN_CONF"; then
  log_info "TTY1 auto-login already configured for $CURRENT_USER"
else
  log_info "Configuring auto-login on TTY1 for $CURRENT_USER..."
  sudo mkdir -p "$AUTOLOGIN_DIR"
  sudo tee "$AUTOLOGIN_CONF" >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty -o '-p -f -- \\u' --noclear --autologin $CURRENT_USER %I \$TERM
EOF
  log_success "TTY1 auto-login configured for $CURRENT_USER"
fi

log_success "Arch system configuration complete"
