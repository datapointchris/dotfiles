#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

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
      manual_steps="Clone manually with git:
   git clone $repo $PLUGIN_DIR

Or install manually:
   cd ~/.config/zsh/plugins
   git clone $repo"

      output_failure_data "$name" "$repo" "latest" "$manual_steps" "Failed to git clone plugin"
      log_warning "Failed to install $name (see summary)"
    fi
  fi
done <<< "$PLUGINS"

log_success "Shell plugins installed to $PLUGINS_DIR"
