#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_section "Installing WSL Ubuntu packages" "cyan"

log_info "Updating package lists..."
sudo apt update

# Bootstrap: Install python3-yaml first (needed for parse-packages.py)
log_info "Installing bootstrap packages..."
sudo apt install -y python3-yaml

# Install system packages from packages.yml
log_info "Installing system packages from packages.yml..."

# Skip Docker packages if running in Docker test environment
if [[ "${DOTFILES_DOCKER_TEST:-}" == "true" ]]; then
  log_info "Docker test mode - excluding Docker packages"
  PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=system --manager=apt | \
    grep -v -E '^(docker-ce|docker-ce-cli|containerd\.io|docker-buildx-plugin|docker-compose-plugin)$' | \
    tr '\n' ' ')
else
  PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=system --manager=apt | tr '\n' ' ')
fi

# shellcheck disable=SC2086
if sudo apt install -y $PACKAGES; then
  log_success "WSL packages installed"
else
  log_warning "Some packages may have failed to install"
fi
