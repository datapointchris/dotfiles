#!/usr/bin/env bash
# ================================================================
# WSL Ubuntu Bootstrap Script
# ================================================================
# Minimal script to install Taskfile and delegate to taskfiles
# Bootstrap should ONLY install what's needed to run Task
# All package installation is handled by management/taskfiles/wsl.yml
# ================================================================

set -euo pipefail

# Source formatting library from dotfiles repo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

print_header "WSL Ubuntu Dotfiles Bootstrap" "blue"

# Detect if running on WSL
if ! grep -q "Microsoft" /proc/version 2>/dev/null; then
    print_warning "Warning: This script is designed for WSL Ubuntu"
    print_warning "Continuing anyway..."
    echo ""
fi

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    die "Do not run this script as root"
fi

print_section "[1/2] Checking Taskfile" "cyan"

if ! command -v task &> /dev/null; then
    echo "  Installing Taskfile..."

    # Install via install script
    sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin

    # Add to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    print_success "Taskfile installed to ~/.local/bin"
else
    print_success "Taskfile already installed: $(task --version)"
fi

print_section "[2/2] Running main installation" "cyan"

cd "$HOME/dotfiles" || {
    die "Could not change to dotfiles directory"
}

# Run installation
task install-wsl

print_section "Configuring shell environment" "cyan"

# Set ZSHDOTDIR in system-wide zshenv if not already set
if ! grep -q "ZSHDOTDIR" /etc/zsh/zshenv 2>/dev/null; then
    # shellcheck disable=SC2016  # $HOME needs to expand when zsh reads the file, not now
    echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv >/dev/null
    print_success "ZSHDOTDIR configured in /etc/zsh/zshenv"
else
    print_success "ZSHDOTDIR already configured"
fi

# Change default shell to zsh
if [[ "$SHELL" != *"zsh"* ]]; then
    echo "  Changing default shell to zsh..."
    sudo chsh -s "$(which zsh)" "$(whoami)"
    print_success "Default shell changed to zsh"
    print_warning "(will take effect after logout/login)"
else
    print_success "Default shell is already zsh"
fi

print_header_success "WSL Ubuntu Bootstrap Complete"

echo ""
print_section "Next Steps" "cyan"
echo "  1. Restart your terminal (or logout/login for shell change)"
echo "  2. Run 'task --list' to see available commands"
echo "  3. Run 'tools list' to see installed tools"
echo "  4. Run 'theme-sync current' to see current theme"
echo ""
