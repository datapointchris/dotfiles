#!/usr/bin/env bash
# ================================================================
# Install Mac App Store Apps
# ================================================================
# Installs Mac App Store apps from packages.yml using mas CLI
# macOS-specific
# ================================================================

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Installing Mac App Store Apps"

# Check if mas is installed
if ! command -v mas >/dev/null 2>&1; then
  log_warning "mas CLI not installed (install with: brew install mas)"
  log_info "Skipping Mac App Store installations"
  exit 0
fi

# Check if signed in (mas CLI has known issues on macOS 14.7+/15+)
if ! mas account >/dev/null 2>&1; then
  log_warning "Cannot detect Mac App Store account (known mas CLI bug on macOS 14.7+/15+)"
  log_info "Skipping Mac App Store installations"
  exit 0
fi

log_info "Mac App Store account detected"

INSTALLED=0
FAILED=0
SKIPPED=0

# Install each app
/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=mas | while read -r app_id; do
  # Check if already installed
  if mas list | grep -q "^$app_id "; then
    log_info "App $app_id already installed"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  log_info "Installing app $app_id..."
  if mas install "$app_id" 2>&1; then
    INSTALLED=$((INSTALLED + 1))
    log_success "Installed app $app_id"
  else
    FAILED=$((FAILED + 1))
    log_error "Failed to install app $app_id"
  fi
done

echo ""
if [ $INSTALLED -gt 0 ]; then
  log_success "Installed $INSTALLED app(s)"
fi
if [ $SKIPPED -gt 0 ]; then
  log_info "$SKIPPED app(s) already installed"
fi
if [ $FAILED -gt 0 ]; then
  log_warning "$FAILED app(s) failed to install"
fi

print_banner_success "Mac App Store Installation Complete"
