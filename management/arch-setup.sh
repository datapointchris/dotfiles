#!/usr/bin/env bash
# ================================================================
# Arch Linux Bootstrap Script
# ================================================================
# Minimal script to install Taskfile and delegate to taskfiles
# Bootstrap should ONLY install what's needed to run Task
# All package installation is handled by management/taskfiles/arch.yml
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
echo -e "${BLUE} Arch Linux Dotfiles Bootstrap${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Detect if running on Arch Linux
if [[ ! -f /etc/arch-release ]]; then
    echo -e "${YELLOW}⚠️  Warning: This script is designed for Arch Linux${NC}"
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
    echo "  Installing Taskfile via pacman..."

    # Install go-task from official repos
    sudo pacman -S --needed --noconfirm go-task

    echo -e "  ${GREEN}✓${NC} Taskfile installed"
else
    echo -e "  ${GREEN}✓${NC} Taskfile already installed: $(task --version)"
fi

echo ""
echo -e "${CYAN}[2/2] Running main installation${NC}"
echo ""

# Change to dotfiles directory (assumes script is in dotfiles/scripts/install/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOTFILES_DIR="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$DOTFILES_DIR"

# Run installation
task install-arch

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN} ✅ Arch Linux Bootstrap Complete${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Restart your terminal (or run: source ~/.zshrc)"
echo "  2. Run 'task --list' to see available commands"
echo "  3. Run 'tools list' to see installed tools"
echo "  4. Run 'theme-sync current' to see current theme"
echo ""
echo -e "${CYAN}Optional:${NC}"
echo "  • Install AUR packages: task arch:install-aur-packages"
echo "  • View Arch-specific notes: task arch:notes"
echo ""
