#!/usr/bin/env bash
set -uo pipefail

# Health check shared by `dotfiles doctor` and `task doctor`.

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$OPS_DIR/../.." && pwd)"
export DOTFILES_DIR
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

cd "$DOTFILES_DIR" || exit 1

print_section "Checking symlinks" "cyan"
uv run symlinks check
symlinks_status=$?

print_section "Verifying package manifest" "cyan"
packages verify
packages_status=$?

[[ $symlinks_status -eq 0 && $packages_status -eq 0 ]]
