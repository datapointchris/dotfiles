#!/usr/bin/env bash
# ================================================================
# Common Update Script
# ================================================================
# Updates language tools and plugins common to all platforms:
# - npm global packages
# - Python tools (uv)
# - Rust packages (cargo)
# - Shell plugins (git repos)
# - Tmux plugins (TPM)
#
# Called by management/update.sh after platform-specific updates
# ================================================================

set -euo pipefail

# Use DOTFILES_DIR if set (by update.sh), otherwise default to ~/dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

# Source platform detection to determine step numbering
source "$DOTFILES_DIR/management/lib/platform-detection.sh"
PLATFORM=$(detect_platform)

# Determine starting step based on platform
case "$PLATFORM" in
    macos)
        START_STEP=3  # After Homebrew + Mac App Store
        ;;
    wsl)
        START_STEP=2  # After System Packages
        ;;
    arch)
        START_STEP=3  # After System Packages + AUR
        ;;
    *)
        START_STEP=1  # Unknown platform
        ;;
esac

lang_tools="$DOTFILES_DIR/management/common/install/language-tools"

# npm Global Packages
print_banner "Step $((START_STEP)) - npm Global Packages" "green"
log_info "Updating npm global packages..."
if NVM_DIR="$HOME/.config/nvm" bash "$lang_tools/npm-install-globals.sh"; then
    log_success "npm global packages updated"
else
    log_warning "Some npm packages failed to update (see details above)"
fi
echo ""

# Python Tools
print_banner "Step $((START_STEP + 1)) - Python Tools" "yellow"
log_info "Updating Python tools..."
source "$HOME/.local/bin/env" 2>/dev/null || true
if uv tool upgrade --all; then
    log_success "Python tools updated"
else
    log_warning "Some Python tools failed to update"
    log_info "Update manually with: uv tool upgrade --all"
fi
echo ""

# Rust Packages
print_banner "Step $((START_STEP + 2)) - Rust Packages" "magenta"
log_info "Updating Rust packages..."
source "$HOME/.cargo/env"
if cargo install-update -a; then
    log_success "Rust packages updated"
else
    log_warning "Some Rust packages failed to update"
    log_info "Update manually with: cargo install-update -a"
fi
echo ""

# Shell Plugins
print_banner "Step $((START_STEP + 3)) - Shell Plugins" "orange"
log_info "Updating shell plugins..."
PLUGINS_DIR="$HOME/.config/shell/plugins"
PLUGINS=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=shell-plugins --format=names)

PLUGIN_UPDATE_FAILURES=0
for name in $PLUGINS; do
  PLUGIN_DIR="$PLUGINS_DIR/$name"
  if [[ -d "$PLUGIN_DIR" ]]; then
    log_info "Updating $name..."
    cd "$PLUGIN_DIR"
    DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
    if [[ -z "$DEFAULT_BRANCH" ]]; then
      DEFAULT_BRANCH=$(git remote show origin | grep 'HEAD branch' | cut -d' ' -f5)
    fi
    if git pull origin "$DEFAULT_BRANCH" --quiet; then
      log_success "$name updated"
    else
      log_warning "$name update failed"
      log_info "Update manually: cd $PLUGIN_DIR && git pull origin $DEFAULT_BRANCH"
      PLUGIN_UPDATE_FAILURES=$((PLUGIN_UPDATE_FAILURES + 1))
    fi
  else
    log_info "$name not installed - skipping"
  fi
done

if [[ $PLUGIN_UPDATE_FAILURES -eq 0 ]]; then
  log_success "Shell plugins updated"
else
  log_warning "Some shell plugins failed to update (see summary)"
fi
echo ""

# Tmux Plugins
print_banner "Step $((START_STEP + 4)) - Tmux Plugins" "brightcyan"
TPM_DIR="$HOME/.config/tmux/plugins/tpm"
if [[ ! -d "$TPM_DIR" ]]; then
  log_info "TPM not installed - skipping tmux plugin updates"
elif [[ ! -f "$TPM_DIR/bin/update_plugins" ]]; then
  log_warning "TPM update script not found - skipping"
else
  log_info "Updating tmux plugins..."
  if "$TPM_DIR/bin/update_plugins" all; then
    log_success "Tmux plugins updated"
  else
    log_warning "Tmux plugins update failed"
    log_info "Update manually: $TPM_DIR/bin/update_plugins all"
    log_info "Or from within tmux: prefix + U"
  fi
fi
echo ""
