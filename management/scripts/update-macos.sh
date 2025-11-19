#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

START_TIME=$(date +%s)

print_title "macOS Update All" "cyan"

print_banner "Step 1/7 - Homebrew" "cyan"
task macos:brew:update
echo ""

print_banner "Step 2/7 - Mac App Store" "blue"
task macos:mas:update
echo ""

print_banner "Step 3/7 - npm Global Packages" "green"
task macos:npm-global:update
echo ""

print_banner "Step 4/7 - Python Tools" "yellow"
task macos:uv-tools:update
echo ""

print_banner "Step 5/7 - Rust Packages" "magenta"
task macos:cargo:update
echo ""

print_banner "Step 6/7 - Shell Plugins" "orange"
task macos:shell-plugins:update
echo ""

print_banner "Step 7/7 - Tmux Plugins" "brightcyan"
task macos:tmux:update
echo ""

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

print_title_success "Update Complete"
echo "Total time: ${TOTAL_DURATION}s"
echo ""
