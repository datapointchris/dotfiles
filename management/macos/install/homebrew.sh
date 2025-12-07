#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Check if Homebrew is already installed
if command -v brew >/dev/null 2>&1; then
  log_success "Homebrew already installed"
  exit 0
fi

print_section "Installing Homebrew" "cyan"

if /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; then
  log_success "Homebrew installed"
else
  log_error "Failed to install Homebrew"
  exit 1
fi
