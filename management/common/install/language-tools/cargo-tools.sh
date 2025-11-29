#!/usr/bin/env bash
# ================================================================
# Install Cargo Tools via cargo-binstall
# ================================================================
# Reads packages.yml and installs all cargo packages via cargo-binstall
# Universal script for all platforms
# ================================================================

set -euo pipefail

# Source formatting library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Ensure cargo is available
source "$HOME/.cargo/env"

print_banner "Installing Rust CLI Tools"

# Get dotfiles directory
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

# Get cargo packages from packages.yml via Python parser
log_info "Reading packages from packages.yml..."
/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=cargo | while read -r package; do
  log_info "Installing $package..."
  cargo binstall -y "$package"
done

log_success "Rust CLI tools installation complete"
log_info "Installed to: ~/.cargo/bin (highest PATH priority)"
