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
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}WSL Ubuntu Dotfiles Bootstrap${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Detect if running on WSL
if ! grep -q "Microsoft" /proc/version 2>/dev/null; then
    echo -e "${YELLOW}Warning: This script is designed for WSL Ubuntu${NC}"
    echo -e "${YELLOW}Continuing anyway...${NC}"
    echo ""
fi

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo -e "${RED}Error: Do not run this script as root${NC}"
    exit 1
fi

# ================================================================
# INSTALL TASKFILE (go-task)
# ================================================================

echo -e "${BLUE}[1/2] Checking Taskfile...${NC}"

if ! command -v task &> /dev/null; then
    echo -e "${YELLOW}Taskfile not found. Installing...${NC}"

    # Install via install script
    sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin

    # Add to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    echo -e "${GREEN}Taskfile installed to ~/.local/bin${NC}"
else
    echo -e "${GREEN}Taskfile already installed${NC}"
    task --version
fi

echo ""

# ================================================================
# RUN MAIN INSTALLATION
# ================================================================

echo -e "${BLUE}[2/2] Running main installation...${NC}"
echo ""

# Change to dotfiles directory (assumes script is in dotfiles/scripts/install/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOTFILES_DIR="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$DOTFILES_DIR"

# Run installation
task install-wsl

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}WSL Ubuntu Bootstrap Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. If /etc/zsh/zshenv doesn't set ZSHDOTDIR, add:"
echo "     echo 'export ZSHDOTDIR=\"\$HOME/.config/zsh\"' | sudo tee -a /etc/zsh/zshenv"
echo "  2. If /etc/wsl.conf was modified, restart WSL:"
echo "     wsl.exe --shutdown"
echo "  3. Restart your terminal"
echo "  4. Run 'task --list' to see available commands"
echo "  5. Run 'tools list' to see installed tools (31 tools)"
echo "  6. Run 'theme-sync current' to see current theme"
echo ""
echo -e "${GREEN}Happy coding!${NC}"
