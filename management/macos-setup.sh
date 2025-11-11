#!/usr/bin/env bash
# ================================================================
# macOS Bootstrap Script
# ================================================================
# Minimal script to install prerequisites and run Taskfile
# for automated testing and fresh installations
# ================================================================

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
# shellcheck disable=SC2034
YELLOW='\033[1;33m'  # Reserved for future use
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE} macOS Dotfiles Bootstrap${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Detect if running on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}✗ Error: This script is for macOS only${NC}"
    exit 1
fi

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo -e "${RED}✗ Error: Do not run this script as root${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}[1/3] Checking Homebrew${NC}"
echo ""

if ! command -v brew &> /dev/null; then
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for this session
    eval "$(/usr/local/bin/brew shellenv)"

    echo -e "  ${GREEN}✓${NC} Homebrew installed"
else
    echo -e "  ${GREEN}✓${NC} Homebrew already installed: $(brew --version | head -n1)"
fi

echo ""
echo -e "${CYAN}[2/3] Checking Taskfile${NC}"
echo ""

if ! command -v task &> /dev/null; then
    echo "  Installing Taskfile..."
    brew install go-task
    echo -e "  ${GREEN}✓${NC} Taskfile installed"
else
    echo -e "  ${GREEN}✓${NC} Taskfile already installed: $(task --version)"
fi

echo ""
echo -e "${CYAN}[3/3] Running main installation${NC}"
echo ""

# Change to dotfiles directory (assumes script is in dotfiles/scripts/install/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOTFILES_DIR="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$DOTFILES_DIR"

# Run installation
task install-macos

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN} ✅ macOS Bootstrap Complete${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Restart your terminal (or run: source ~/.zshrc)"
echo "  2. Run 'task --list' to see available commands"
echo "  3. Run 'tools list' to see installed tools"
echo "  4. Run 'theme-sync current' to see current theme"
echo ""
