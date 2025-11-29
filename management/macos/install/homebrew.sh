#!/usr/bin/env bash
# ================================================================
# Install Homebrew
# ================================================================
# Installs Homebrew package manager if not already present
# macOS-specific
# ================================================================

set -euo pipefail

# Use DOTFILES_DIR if set (by install.sh), otherwise default to ~/dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/management/common/lib/structured-logging.sh"

# Check if Homebrew is already installed
if command -v brew >/dev/null 2>&1; then
  print_success "Homebrew already installed"
  exit 0
fi

print_section "Installing Homebrew" "cyan"

if /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; then
  print_success "Homebrew installed"
else
  print_error "Failed to install Homebrew"
  exit 1
fi
