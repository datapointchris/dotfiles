#!/usr/bin/env bash
# ================================================================
# Install Cargo Tools via cargo-binstall
# ================================================================
# Reads packages.yml and installs all cargo packages via cargo-binstall
# Universal script for all platforms
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/management/common/lib/structured-logging.sh"

# Ensure cargo is available
source "$HOME/.cargo/env"

print_banner "Installing Rust CLI Tools"

# Get dotfiles directory
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

# Get cargo packages from packages.yml via Python parser
print_info "Reading packages from packages.yml..."
/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=cargo | while read -r package; do
  print_info "Installing $package..."
  cargo binstall -y "$package"
done

print_success "Rust CLI tools installation complete"
print_info "Installed to: ~/.cargo/bin (highest PATH priority)"
