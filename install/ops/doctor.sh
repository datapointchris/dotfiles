#!/usr/bin/env bash
set -uo pipefail

# Health check shared by `dotfiles doctor` and `task doctor`.

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$OPS_DIR/../.." && pwd)"
export DOTFILES_DIR
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

cd "$DOTFILES_DIR" || exit 1

print_header "doctor" "brightcyan"

print_section "Checking symlinks" "brightcyan"
uv run symlinks check
symlinks_status=$?

print_section "Verifying package manifest" "brightcyan"
packages verify
packages_status=$?

print_section "Summary" "brightcyan"
if [[ $symlinks_status -eq 0 ]]; then
  print_success "Symlinks are healthy"
else
  print_error "Symlink check reported problems"
fi
if [[ $packages_status -eq 0 ]]; then
  print_success "Package manifest matches what is installed"
else
  print_error "Package manifest has drifted"
fi
echo ""

[[ $symlinks_status -eq 0 && $packages_status -eq 0 ]]
