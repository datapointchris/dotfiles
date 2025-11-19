#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

START_TIME=$(date +%s)

print_title "WSL Ubuntu Update All" "cyan"

print_banner "Step 1/6 - System Packages" "cyan"
task wsl:apt:update
echo ""

print_banner "Step 2/6 - npm Global Packages" "blue"
task wsl:npm-global:update
echo ""

print_banner "Step 3/6 - Python Tools" "green"
task wsl:uv-tools:update
echo ""

print_banner "Step 4/6 - Rust Packages" "yellow"
task wsl:cargo:update
echo ""

print_banner "Step 5/6 - Shell Plugins" "magenta"
task wsl:shell-plugins:update
echo ""

print_banner "Step 6/6 - Tmux Plugins" "orange"
task wsl:tmux:update
echo ""

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

print_title_success "Update Complete"
echo "Total time: ${TOTAL_DURATION}s"
echo ""
