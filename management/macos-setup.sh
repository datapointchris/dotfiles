#!/usr/bin/env bash
# ================================================================
# macOS Bootstrap Script
# ================================================================
# Minimal script to install prerequisites and run Taskfile
# for automated testing and fresh installations
# ================================================================

set -euo pipefail

# Source formatting library from dotfiles repo
# Change to dotfiles directory (assumes script is in dotfiles/management/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOTFILES_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

print_header "macOS Dotfiles Bootstrap" "blue"

# Detect if running on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    die "This script is for macOS only"
fi

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    die "Do not run this script as root"
fi

print_section "[1/3] Checking Homebrew" "cyan"

if ! command -v brew &> /dev/null; then
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for this session
    eval "$(/usr/local/bin/brew shellenv)"

    print_success "Homebrew installed"
else
    print_success "Homebrew already installed: $(brew --version | head -n1)"
fi

print_section "[2/3] Checking Taskfile" "cyan"

if ! command -v task &> /dev/null; then
    echo "  Installing Taskfile..."
    brew install go-task
    print_success "Taskfile installed"
else
    print_success "Taskfile already installed: $(task --version)"
fi

print_section "[3/3] Running main installation" "cyan"

cd "$DOTFILES_DIR"

# Run installation
task install-macos

print_header_success "macOS Bootstrap Complete"

echo ""
print_section "Next Steps" "cyan"
echo "  1. Restart your terminal (or run: source ~/.zshrc)"
echo "  2. Run 'task --list' to see available commands"
echo "  3. Run 'tools list' to see installed tools"
echo "  4. Run 'theme-sync current' to see current theme"
echo ""
