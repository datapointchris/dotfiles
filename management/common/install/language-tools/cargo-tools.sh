#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

source "$HOME/.cargo/env"

print_banner "Installing Rust CLI Tools"

log_info "Reading packages from packages.yml..."

FAILURE_COUNT=0
while read -r package; do
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
    FAILURE_COUNT=$((FAILURE_COUNT + 1))
  fi
done < <(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=cargo)

if [[ $FAILURE_COUNT -gt 0 ]]; then
  log_warning "$FAILURE_COUNT package(s) failed to install"
  exit 1
else
  log_success "All Rust CLI tools installed successfully"
  log_info "Installed to: ~/.cargo/bin (highest PATH priority)"
fi
