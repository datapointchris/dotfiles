#!/usr/bin/env bash
# Installs the fleet's default Node version through fnm and links it as the
# `default` alias.
#
# The alias is what .zshenv puts on PATH, so this is what bare `node` resolves
# to in every non-interactive shell — pre-commit hooks, scripts, agents. A repo
# pinning something else in .nvmrc gets it from --use-on-cd in .zshrc, or from
# `fnm exec` when the caller is not an interactive shell.
#
# fnm itself comes from cargo_packages; this script only manages versions.
set -uo pipefail

UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

# The version most of the portfolio pins and every CI workflow uses. Kept here
# rather than read from any one repo's .nvmrc: this is the floor for everything
# with no pin at all, and a repo that wants another version says so itself.
NODE_DEFAULT_VERSION="24"

if ! command -v fnm >/dev/null 2>&1; then
  output_failure_data "node" "fnm" "$NODE_DEFAULT_VERSION" "fnm not installed (cargo_packages)"
  log_error "fnm not found — install cargo_packages first"
  exit 1
fi

export FNM_DIR="${FNM_DIR:-$HOME/.local/share/fnm}"

current=""
if [[ -x "$FNM_DIR/aliases/default/bin/node" ]]; then
  current="$("$FNM_DIR/aliases/default/bin/node" --version 2>/dev/null)"
fi

if [[ "$UPDATE_MODE" == "false" && "$current" == v${NODE_DEFAULT_VERSION}.* ]]; then
  log_success "Node default already $current"
  exit 0
fi

log_info "Installing Node $NODE_DEFAULT_VERSION via fnm..."
if ! fnm install "$NODE_DEFAULT_VERSION"; then
  output_failure_data "node" "fnm install" "$NODE_DEFAULT_VERSION" "fnm install failed"
  log_error "fnm install $NODE_DEFAULT_VERSION failed"
  exit 1
fi

if ! fnm default "$NODE_DEFAULT_VERSION"; then
  output_failure_data "node" "fnm default" "$NODE_DEFAULT_VERSION" "fnm default failed"
  log_error "fnm default $NODE_DEFAULT_VERSION failed"
  exit 1
fi

log_success "Node default set to $("$FNM_DIR/aliases/default/bin/node" --version)"
