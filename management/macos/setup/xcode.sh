#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_section "Setting up Xcode"

# Check if xcodebuild exists
if ! command -v xcodebuild &>/dev/null; then
  log_info "Xcode Command Line Tools not installed, skipping"
  exit 0
fi

# Check if full Xcode is installed (not just Command Line Tools)
xcode_path=$(xcode-select -p 2>/dev/null || echo "")
if [[ "$xcode_path" == "/Library/Developer/CommandLineTools" ]]; then
  log_info "Command Line Tools installed (full Xcode not required)"
  exit 0
fi

log_info "Full Xcode detected at $xcode_path"

# Accept license if needed
if sudo xcodebuild -license status &>/dev/null; then
  log_info "Xcode license already accepted"
else
  log_info "Accepting Xcode license..."
  sudo xcodebuild -license accept
  log_success "Xcode license accepted"
fi

# Run first launch setup
log_info "Running Xcode first launch setup..."
if xcodebuild -runFirstLaunch 2>/dev/null; then
  log_success "Xcode first launch complete"
else
  log_warning "First launch setup failed (may already be complete)"
fi
