#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

START_TIME=$(date +%s)

print_title "macOS Update All" "cyan"

print_banner "Step 1/7 - Homebrew" "cyan"
echo "  Updating Homebrew..."
brew update
echo "  Upgrading formulas and casks..."
brew upgrade
brew upgrade --cask --greedy
echo "  ✓ Homebrew packages updated"
echo ""

print_banner "Step 2/7 - Mac App Store" "blue"
if ! command -v mas >/dev/null 2>&1; then
  echo "  ⚠️  mas not found - install with: brew install mas"
else
  echo "  Updating Mac App Store apps..."
  if mas upgrade 2>&1; then
    echo "  ✓ Mac App Store apps updated"
  else
    echo "  ⚠️  Update failed (mas may be incompatible with your macOS version)"
    echo "  ℹ️  You can update apps manually via the App Store GUI"
  fi
fi
echo ""

print_banner "Step 3/7 - npm Global Packages" "green"
echo "  Updating npm global packages..."
NVM_DIR="$HOME/.config/nvm" bash "$DOTFILES_DIR/management/common/install/language-tools/npm-install-globals.sh"
echo "  ✓ npm global packages updated"
echo ""

print_banner "Step 4/7 - Python Tools" "yellow"
echo "  Updating Python tools..."
source "$HOME/.local/bin/env" 2>/dev/null || true
uv tool upgrade --all
echo "  ✓ Python tools updated"
echo ""

print_banner "Step 5/7 - Rust Packages" "magenta"
echo "  Updating Rust packages..."
source "$HOME/.cargo/env"
cargo install-update -a
echo "  ✓ Rust packages updated"
echo ""

print_banner "Step 6/7 - Shell Plugins" "orange"
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

print_banner "Step 7/7 - Tmux Plugins" "brightcyan"
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

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

print_title_success "Update Complete"
echo "Total time: ${TOTAL_DURATION}s"
echo ""
