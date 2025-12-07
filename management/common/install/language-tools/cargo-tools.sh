#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

source "$HOME/.cargo/env"

print_banner "Installing Rust CLI Tools"

log_info "Reading packages from packages.yml..."
/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=cargo | while read -r package; do
  log_info "Installing $package..."
  if cargo binstall -y "$package"; then
    log_success "$package installed"
  else
    manual_steps="Install manually with cargo:
   cargo install $package

Or try cargo-binstall directly:
   cargo binstall -y $package"

    output_failure_data "$package" "https://crates.io/crates/$package" "latest" "$manual_steps" "Failed to install via cargo-binstall"
    log_warning "$package installation failed (see summary)"
  fi
done

log_success "Rust CLI tools installation complete"
log_info "Installed to: ~/.cargo/bin (highest PATH priority)"
