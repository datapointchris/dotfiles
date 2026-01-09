#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

THEME_INSTALL_URL="https://raw.githubusercontent.com/datapointchris/theme/main/install.sh"

# Support --print-url for offline bundle creator
if [[ "${1:-}" == "--print-url" ]]; then
  echo "theme|latest|$THEME_INSTALL_URL"
  exit 0
fi

# Support --update by delegating to theme's own upgrade command
if [[ "${1:-}" == "--update" ]]; then
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  if command -v theme >/dev/null 2>&1; then
    if upgrade_output=$(theme upgrade 2>&1); then
      if [[ "$upgrade_output" == *"already up to date"* ]]; then
        log_success "theme already at latest"
      else
        log_success "theme upgraded"
      fi
    else
      log_warning "theme upgrade failed"
    fi
  else
    log_info "theme not installed, skipping update"
  fi
  exit 0
fi

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

INSTALL_DIR="$HOME/.local/share/theme"

if [[ -d "$INSTALL_DIR/.git" ]] && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
  log_success "theme already installed at $INSTALL_DIR"
  exit 0
fi

log_info "Installing theme via official installer..."

# Offline cache
OFFLINE_CACHE_DIR="${HOME}/installers/scripts"
CACHED_SCRIPT="$OFFLINE_CACHE_DIR/theme-install.sh"

run_theme_install() {
  local tmp_script="/tmp/theme-install.sh"

  # Check offline cache first
  if [[ -f "$CACHED_SCRIPT" ]]; then
    log_info "Using cached install script: $CACHED_SCRIPT"
    chmod +x "$CACHED_SCRIPT"
    bash "$CACHED_SCRIPT"
    return $?
  fi

  # Try to download
  log_info "Downloading theme install script..."
  if curl -fsSL "$THEME_INSTALL_URL" -o "$tmp_script"; then
    chmod +x "$tmp_script"
    bash "$tmp_script"
    return $?
  fi

  return 1
}

if run_theme_install; then
  log_success "theme installed: $(command -v theme 2>/dev/null || echo "$HOME/.local/bin/theme")"
else
  manual_steps="1. Download theme install script in your browser:
   $THEME_INSTALL_URL

2. Save to: $CACHED_SCRIPT

3. Re-run this installer:
   bash $DOTFILES_DIR/management/common/install/custom-installers/theme.sh"

  output_failure_data "theme" "$THEME_INSTALL_URL" "latest" "$manual_steps" "Failed to download install script"
  log_error "theme installation failed"
  exit 1
fi
