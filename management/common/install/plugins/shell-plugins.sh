#!/usr/bin/env bash
# ================================================================
# Install Shell Plugins
# ================================================================
# Installs ZSH plugins from packages.yml to ~/.config/zsh/plugins
# Universal script for all platforms
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

PLUGINS_DIR="$HOME/.config/zsh/plugins"

# Check if packages.yml exists
if [[ ! -f "$DOTFILES_DIR/management/packages.yml" ]]; then
  log_error "packages.yml not found at $DOTFILES_DIR/management/packages.yml"
  exit 1
fi

print_section "Installing shell plugins" "cyan"

# Create plugins directory if it doesn't exist
mkdir -p "$PLUGINS_DIR"

# Read plugins from management/packages.yml via Python parser
PLUGINS=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=shell-plugins --format=name_repo)

while IFS='|' read -r name repo; do
  PLUGIN_DIR="$PLUGINS_DIR/$name"

  if [[ -d "$PLUGIN_DIR" ]]; then
    log_info "$name already installed"
  else
    log_info "Installing $name..."
    if git clone "$repo" "$PLUGIN_DIR" --quiet; then
      log_success "$name installed"
    else
      log_warning "Failed to install $name"
    fi
  fi
done <<< "$PLUGINS"

log_success "Shell plugins installed to $PLUGINS_DIR"
