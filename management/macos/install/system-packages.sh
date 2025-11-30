#!/usr/bin/env bash
# ================================================================
# Install macOS System Packages
# ================================================================
# Installs system packages from packages.yml via Homebrew
# Includes PyYAML installation, system packages, and docker-compose setup
# macOS-specific
# ================================================================

set -euo pipefail

# Use DOTFILES_DIR if set (by install.sh), otherwise default to ~/dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_section "Installing macOS packages" "cyan"

# Step 1: Install PyYAML for system Python (bootstrap dependency)
if /usr/bin/python3 -c "import yaml" &>/dev/null; then
  log_info "PyYAML already installed for system Python"
else
  log_info "Installing PyYAML for system Python..."
  /usr/bin/python3 -m pip install --user PyYAML
  log_success "PyYAML installed"
fi

# Step 2: Install system packages from packages.yml
log_info "Installing system packages from packages.yml..."
PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=system --manager=brew | tr '\n' ' ')
# shellcheck disable=SC2086
if brew install $PACKAGES; then
  log_success "System packages installed"
else
  log_warning "Some packages may have failed to install"
fi

# Step 3: Setup docker-compose as Docker CLI plugin
if ! command -v docker-compose >/dev/null 2>&1; then
  log_warning "docker-compose not installed (run: brew install docker-compose)"
else
  log_info "Setting up docker-compose as Docker CLI plugin..."

  # Create plugin directory (DOCKER_CONFIG is set in zshrc to $XDG_CONFIG_HOME/docker)
  mkdir -p "${DOCKER_CONFIG:-$HOME/.config/docker}/cli-plugins"

  # Create symlink to enable 'docker compose' command
  ln -sfn "$(brew --prefix)/opt/docker-compose/bin/docker-compose" \
    "${DOCKER_CONFIG:-$HOME/.config/docker}/cli-plugins/docker-compose"

  log_success "docker-compose plugin configured"
  log_info "You can now use 'docker compose' (modern) instead of 'docker-compose' (legacy)"
fi

log_success "macOS packages installed"
