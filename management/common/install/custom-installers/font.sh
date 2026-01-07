#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

FONT_INSTALL_URL="https://raw.githubusercontent.com/datapointchris/font/main/install.sh"

# Support --print-url for offline bundle creator
if [[ "${1:-}" == "--print-url" ]]; then
  echo "font|latest|$FONT_INSTALL_URL"
  exit 0
fi

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

INSTALL_DIR="$HOME/.local/share/font"

if [[ -d "$INSTALL_DIR/.git" ]] && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
  log_success "font already installed at $INSTALL_DIR"
  exit 0
fi

log_info "Installing font via official installer..."

# Offline cache
OFFLINE_CACHE_DIR="${HOME}/installers/scripts"
CACHED_SCRIPT="$OFFLINE_CACHE_DIR/font-install.sh"

run_font_install() {
  local tmp_script="/tmp/font-install.sh"

  # Check offline cache first
  if [[ -f "$CACHED_SCRIPT" ]]; then
    log_info "Using cached install script: $CACHED_SCRIPT"
    chmod +x "$CACHED_SCRIPT"
    bash "$CACHED_SCRIPT"
    return $?
  fi

  # Try to download
  log_info "Downloading font install script..."
  if curl -fsSL "$FONT_INSTALL_URL" -o "$tmp_script"; then
    chmod +x "$tmp_script"
    bash "$tmp_script"
    return $?
  fi

  return 1
}

if run_font_install; then
  log_success "font installed: $(command -v font 2>/dev/null || echo "$HOME/.local/bin/font")"
else
  manual_steps="1. Download font install script in your browser:
   $FONT_INSTALL_URL

2. Save to: $CACHED_SCRIPT

3. Re-run this installer:
   bash $DOTFILES_DIR/management/common/install/custom-installers/font.sh"

  output_failure_data "font" "$FONT_INSTALL_URL" "latest" "$manual_steps" "Failed to download install script"
  log_error "font installation failed"
  exit 1
fi
