#!/usr/bin/env bash
# ================================================================
# Install UV Tools
# ================================================================
# Installs Python tools from packages.yml via uv tool install
# Universal script for all platforms
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Check if uv is installed
if ! command -v uv &>/dev/null; then
  print_error "uv is not installed"
  echo "Install uv first:"
  echo "  macOS: brew install uv"
  echo "  Linux: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

# Check if packages.yml exists
if [[ ! -f "$DOTFILES_DIR/management/packages.yml" ]]; then
  print_error "packages.yml not found at $DOTFILES_DIR/management/packages.yml"
  exit 1
fi

print_section "Installing Python tools via uv" "cyan"

# Get uv tools from packages.yml via Python parser
/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=uv | while read -r tool; do
  echo "  Installing $tool..."
  if uv tool install "$tool"; then
    echo "    ✓ $tool installed"
  else
    print_warning "Failed to install $tool"
  fi
done

print_success "Python tools installed"
