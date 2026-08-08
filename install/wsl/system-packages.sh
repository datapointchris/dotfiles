#!/usr/bin/env bash
set -euo pipefail

# NOTE: Use exported DOTFILES_DIR from install.sh for consistency.
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/python.sh"

print_section "Installing WSL Ubuntu packages"

log_info "Updating package lists..."
sudo apt update

log_info "Installing system packages from packages.yml..."

# Exclude Docker packages - WSL uses Windows Docker Desktop, not native Docker
# The Docker apt repo is intentionally not configured on WSL (see docker-repo.sh)
PACKAGES=$(dotfiles_python -m dotfiles.parse_packages --type=system --manager=apt --tier="${SYSTEM_PACKAGE_TIER:-workstation}" \
  | grep -v -E '^(docker-ce|docker-ce-cli|containerd\.io|docker-buildx-plugin|docker-compose-plugin)$' \
  | tr '\n' ' ')

# shellcheck disable=SC2086
if sudo apt install -y $PACKAGES; then
  log_success "WSL packages installed"
else
  log_warning "Some packages may have failed to install"
fi
