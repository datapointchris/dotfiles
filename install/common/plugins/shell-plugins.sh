#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

PLUGINS_DIR="$HOME/.config/zsh/plugins"

# Check if packages.yml exists
if [[ ! -f "$DOTFILES_DIR/install/packages.yml" ]]; then
  log_error "packages.yml not found at $DOTFILES_DIR/install/packages.yml"
  exit 1
fi

# Create plugins directory if it doesn't exist
mkdir -p "$PLUGINS_DIR"

# Read plugins from install/packages.yml via Python parser
PLUGINS=$(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=shell-plugins --format=name_repo)

while IFS='|' read -r name repo; do
  PLUGIN_DIR="$PLUGINS_DIR/$name"

  if [[ -d "$PLUGIN_DIR" ]]; then
    log_success "$name already installed: $PLUGIN_DIR"
  else
    log_info "Installing $name to: $PLUGIN_DIR"
    log_info "Repository: $repo"
    if clone_output=$(git clone "$repo" "$PLUGIN_DIR" --quiet 2>&1); then
      log_success "$name installed: $PLUGIN_DIR"
    else
      output_failure_data "$name" "$repo" "latest" "Failed to git clone plugin" "$clone_output"
      log_warning "Failed to install $name (see summary)"
    fi
  fi
done <<<"$PLUGINS"
