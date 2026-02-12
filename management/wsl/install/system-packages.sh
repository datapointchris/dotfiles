#!/usr/bin/env bash
set -euo pipefail

# NOTE: Use exported DOTFILES_DIR from install.sh for consistency.
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_section "Installing WSL Ubuntu packages"

log_info "Updating package lists..."
sudo apt update

# Bootstrap: Install python3-yaml first (needed for parse_packages.py)
log_info "Installing bootstrap packages..."
sudo apt install -y python3-yaml

# Install system packages from packages.yml
log_info "Installing system packages from packages.yml..."

# Exclude Docker packages - WSL uses Windows Docker Desktop, not native Docker
# The Docker apt repo is intentionally not configured on WSL (see docker-repo.sh)
PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=system --manager=apt | \
  grep -v -E '^(docker-ce|docker-ce-cli|containerd\.io|docker-buildx-plugin|docker-compose-plugin)$' | \
  tr '\n' ' ')

# shellcheck disable=SC2086
if sudo apt install -y $PACKAGES; then
  log_success "WSL packages installed"
else
  log_warning "Some packages may have failed to install"
fi
