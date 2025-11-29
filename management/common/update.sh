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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

# Source platform detection to determine step numbering
source "$DOTFILES_DIR/management/utils/platform-detection.sh"
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
echo "  Updating npm global packages..."
NVM_DIR="$HOME/.config/nvm" bash "$lang_tools/npm-install-globals.sh"
echo "  ✓ npm global packages updated"
echo ""

# Python Tools
print_banner "Step $((START_STEP + 1)) - Python Tools" "yellow"
echo "  Updating Python tools..."
source "$HOME/.local/bin/env" 2>/dev/null || true
uv tool upgrade --all
echo "  ✓ Python tools updated"
echo ""

# Rust Packages
print_banner "Step $((START_STEP + 2)) - Rust Packages" "magenta"
echo "  Updating Rust packages..."
source "$HOME/.cargo/env"
cargo install-update -a
echo "  ✓ Rust packages updated"
echo ""

# Shell Plugins
print_banner "Step $((START_STEP + 3)) - Shell Plugins" "orange"
echo "  Updating shell plugins..."
PLUGINS_DIR="$HOME/.config/shell/plugins"
PLUGINS=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=shell-plugins --format=names)

for name in $PLUGINS; do
  PLUGIN_DIR="$PLUGINS_DIR/$name"
  if [[ -d "$PLUGIN_DIR" ]]; then
    echo "    Updating $name..."
    cd "$PLUGIN_DIR"
    DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
    if [[ -z "$DEFAULT_BRANCH" ]]; then
      DEFAULT_BRANCH=$(git remote show origin | grep 'HEAD branch' | cut -d' ' -f5)
    fi
    git pull origin "$DEFAULT_BRANCH" --quiet
  else
    echo "    $name not installed - skipping"
  fi
done
echo "  ✓ Shell plugins updated"
echo ""

# Tmux Plugins
print_banner "Step $((START_STEP + 4)) - Tmux Plugins" "brightcyan"
TPM_DIR="$HOME/.config/tmux/plugins/tpm"
if [[ ! -d "$TPM_DIR" ]]; then
  echo "  TPM not installed - skipping tmux plugin updates"
elif [[ ! -f "$TPM_DIR/bin/update_plugins" ]]; then
  echo "  TPM update script not found - skipping"
else
  echo "  Updating tmux plugins..."
  "$TPM_DIR/bin/update_plugins" all
  echo "  ✓ Tmux plugins updated"
fi
echo ""
