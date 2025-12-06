#!/usr/bin/env bash
# ================================================================
# Install Go Tools
# ================================================================
# Installs Go CLI tools from packages.yml via go install
# Universal script for all platforms
# ================================================================

set -euo pipefail

# Use DOTFILES_DIR if set (by install.sh), otherwise default to ~/dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

# Check if Go is installed
if ! command -v go &>/dev/null; then
  log_error "Go is not installed"
  echo "Install Go first: bash $DOTFILES_DIR/management/common/install/language-managers/install-go.sh"
  exit 1
fi

# Check if packages.yml exists
if [[ ! -f "$DOTFILES_DIR/management/packages.yml" ]]; then
  log_error "packages.yml not found at $DOTFILES_DIR/management/packages.yml"
  exit 1
fi

print_section "Installing Go tools" "cyan"

# Get Go tools from packages.yml via Python parser
GOBIN="$HOME/go/bin"
/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=go | while read -r tool; do
  print_section "  Installing $tool..." "yellow"
  if go install "$tool@latest"; then
    log_success "$tool installed"
  else
    manual_steps="Install manually with go:
   go install $tool@latest

Tool will be installed to:
   $GOBIN"

    output_failure_data "$tool" "https://pkg.go.dev/$tool" "latest" "$manual_steps" "Failed to install via go install"
    log_warning "Failed to install $tool (see summary)"
  fi
done

log_success "Go tools installed to $GOBIN"
