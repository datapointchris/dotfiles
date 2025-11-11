#!/usr/bin/env bash
# ================================================================
# Arch Linux Bootstrap Script
# ================================================================
# Minimal script to install Taskfile and delegate to taskfiles
# Bootstrap should ONLY install what's needed to run Task
# All package installation is handled by management/taskfiles/arch.yml
# ================================================================

set -euo pipefail

# Source formatting library from dotfiles repo
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOTFILES_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

print_header "Arch Linux Dotfiles Bootstrap" "blue"

# Detect if running on Arch Linux
if [[ ! -f /etc/arch-release ]]; then
    print_warning "Warning: This script is designed for Arch Linux"
    print_warning "Continuing anyway..."
    echo ""
fi

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    die "Do not run this script as root"
fi

print_section "[1/2] Checking Taskfile" "cyan"

if ! command -v task &> /dev/null; then
    echo "  Installing Taskfile via pacman..."

    # Install go-task from official repos
    sudo pacman -S --needed --noconfirm go-task

    print_success "Taskfile installed"
else
    print_success "Taskfile already installed: $(task --version)"
fi

print_section "[2/2] Running main installation" "cyan"

cd "$DOTFILES_DIR"

# Run installation
task install-arch

print_header_success "Arch Linux Bootstrap Complete"

echo ""
print_section "Next Steps" "cyan"
echo "  1. Restart your terminal (or run: source ~/.zshrc)"
echo "  2. Run 'task --list' to see available commands"
echo "  3. Run 'tools list' to see installed tools"
echo "  4. Run 'theme-sync current' to see current theme"
echo ""
print_section "Optional" "cyan"
echo "  • Install AUR packages: task arch:install-aur-packages"
echo "  • View Arch-specific notes: task arch:notes"
echo ""
