#!/usr/bin/env bash
set -euo pipefail

# System packages for a generic Debian/Ubuntu Linux host (the linux platform:
# headless LXCs and small boxes). Installs the tier passed by install.sh via
# SYSTEM_PACKAGE_TIER — typically "core", which parse_packages.py filters down
# to the lean base set (no docker/media/GUI). apt-based, like the WSL script.

# Use exported DOTFILES_DIR from install.sh for consistency.
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
TIER="${SYSTEM_PACKAGE_TIER:-core}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

print_section "Installing Linux system packages (tier: $TIER)"

log_info "Updating package lists..."
sudo apt update

# Bootstrap: python3-yaml is required for parse_packages.py to read packages.yml.
log_info "Installing bootstrap packages..."
sudo apt install -y python3-yaml

log_info "Installing system packages from packages.yml..."
PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=system --manager=apt --tier="$TIER" | tr '\n' ' ')

# shellcheck disable=SC2086
if sudo apt install -y $PACKAGES; then
  log_success "Linux packages installed"
else
  log_warning "Some packages may have failed to install"
fi
