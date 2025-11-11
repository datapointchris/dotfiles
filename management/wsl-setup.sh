#!/usr/bin/env bash
# ================================================================
# WSL Ubuntu Bootstrap Script
# ================================================================
# Minimal script to install Taskfile and delegate to taskfiles
# Bootstrap should ONLY install what's needed to run Task
# All package installation is handled by management/taskfiles/wsl.yml
# ================================================================

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE} WSL Ubuntu Dotfiles Bootstrap${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Detect if running on WSL
if ! grep -q "Microsoft" /proc/version 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Warning: This script is designed for WSL Ubuntu${NC}"
    echo -e "${YELLOW}   Continuing anyway...${NC}"
    echo ""
fi

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo -e "${RED}✗ Error: Do not run this script as root${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}[1/2] Checking Taskfile${NC}"
echo ""

if ! command -v task &> /dev/null; then
    echo "  Installing Taskfile..."

    # Install via install script
    sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin

    # Add to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    echo -e "  ${GREEN}✓${NC} Taskfile installed to ~/.local/bin"
else
    echo -e "  ${GREEN}✓${NC} Taskfile already installed: $(task --version)"
fi

echo ""
echo -e "${CYAN}[2/2] Running main installation${NC}"
echo ""

cd "$HOME/dotfiles" || {
    echo -e "${RED}Error: Could not change to dotfiles directory${NC}"
    exit 1
}

# Run installation
task install-wsl

echo ""
echo -e "${CYAN}Configuring shell environment${NC}"
echo ""

# Set ZSHDOTDIR in system-wide zshenv if not already set
if ! grep -q "ZSHDOTDIR" /etc/zsh/zshenv 2>/dev/null; then
    # shellcheck disable=SC2016  # $HOME needs to expand when zsh reads the file, not now
    echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv >/dev/null
    echo -e "  ${GREEN}✓${NC} ZSHDOTDIR configured in /etc/zsh/zshenv"
else
    echo -e "  ${GREEN}✓${NC} ZSHDOTDIR already configured"
fi

# Change default shell to zsh
if [[ "$SHELL" != *"zsh"* ]]; then
    echo "  Changing default shell to zsh..."
    sudo chsh -s "$(which zsh)" "$(whoami)"
    echo -e "  ${GREEN}✓${NC} Default shell changed to zsh"
    echo -e "    ${YELLOW}(will take effect after logout/login)${NC}"
else
    echo -e "  ${GREEN}✓${NC} Default shell is already zsh"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN} ✅ WSL Ubuntu Bootstrap Complete${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Restart your terminal (or logout/login for shell change)"
echo "  2. Run 'task --list' to see available commands"
echo "  3. Run 'tools list' to see installed tools"
echo "  4. Run 'theme-sync current' to see current theme"
echo ""
