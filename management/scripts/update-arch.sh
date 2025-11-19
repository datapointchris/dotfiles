#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

START_TIME=$(date +%s)

print_title "Arch Linux Update All" "cyan"

print_banner "Step 1/7 - System Packages" "cyan"
task arch:pacman:update
echo ""

print_banner "Step 2/7 - AUR Packages" "blue"
task arch:yay:update
echo ""

print_banner "Step 3/7 - npm Global Packages" "green"
task arch:npm-global:update
echo ""

print_banner "Step 4/7 - Python Tools" "yellow"
task arch:uv-tools:update
echo ""

print_banner "Step 5/7 - Rust Packages" "magenta"
task arch:cargo:update
echo ""

print_banner "Step 6/7 - Shell Plugins" "orange"
task arch:shell-plugins:update
echo ""

print_banner "Step 7/7 - Tmux Plugins" "brightcyan"
task arch:tmux:update
echo ""

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

print_title_success "Update Complete"
echo "Total time: ${TOTAL_DURATION}s"
echo ""
