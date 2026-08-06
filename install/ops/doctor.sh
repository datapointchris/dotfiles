#!/usr/bin/env bash
set -uo pipefail

# Health check shared by `dotfiles doctor` and `task doctor`.

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
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

# Two separate questions, and only the first can fail a commit: `verify` compares
# packages.yml against the manifests and installer scripts, while `missing`
# compares this machine against what its manifest declares.
print_section "Checking installed packages" "brightcyan"
packages missing
missing_status=$?

# The third drift question, and the one nothing else asks: a flag added to the
# repo reaches no existing machine, so without this every machine silently keeps
# the old default forever.
print_section "Checking machine environment" "brightcyan"
bash "$DOTFILES_DIR/install/ops/env.sh" check
env_status=$?

print_section "Summary" "brightcyan"
if [[ $symlinks_status -eq 0 ]]; then
  print_success "Symlinks are healthy"
else
  print_error "Symlink check reported problems"
fi
if [[ $packages_status -eq 0 ]]; then
  print_success "packages.yml matches the manifests and installer scripts"
else
  print_error "Package manifest has drifted"
fi
if [[ $missing_status -eq 0 ]]; then
  print_success "Every package this machine declares is installed"
else
  print_error "Declared packages are missing — run 'dotfiles install'"
fi
if [[ $env_status -eq 0 ]]; then
  print_success "Machine environment matches the manifest and the declared flags"
else
  print_error "Machine environment has drifted — run 'dotfiles env sync'"
fi
echo ""

[[ $symlinks_status -eq 0 && $packages_status -eq 0 && $missing_status -eq 0 && $env_status -eq 0 ]]
