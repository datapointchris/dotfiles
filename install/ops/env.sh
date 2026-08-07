#!/usr/bin/env bash
set -uo pipefail

# Shared implementation of the ~/.env operations.
# Called by both front doors: `dotfiles env <verb>` and `task env:*`.

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export DOTFILES_DIR
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"

# MACHINE lives in the very file being managed, which is the bootstrap this
# whole design has to live with: ~/.env names the manifest, and the manifest
# generates ~/.env. A fresh machine passes --machine instead.
if [[ -f "$HOME/.env" ]]; then
  source "$HOME/.env"
fi

usage() {
  help_header "env"
  help_usage "env.sh <show|sync|check> [--machine NAME]"

  help_section "Verbs"
  help_row "show" "" "Print the generated section without writing anything"
  help_row "sync" "" "Write ~/.env from the manifest, preserving hand-edited overrides"
  help_row "check" "" "Report drift between the declared flags and this machine"

  help_end
  exit "${1:-0}"
}

main() {
  local verb="${1:-}"
  [[ -z "$verb" || "$verb" == "help" || "$verb" == "-h" || "$verb" == "--help" ]] && usage 0
  shift

  local machine="${MACHINE:-}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --machine)
        machine="${2:-}"
        shift 2
        ;;
      *)
        log_error "Unknown option: $1"
        usage 1
        ;;
    esac
  done

  if [[ -z "$machine" ]]; then
    log_error "No machine known: MACHINE is unset in ~/.env and --machine was not given"
    print_info "Available manifests:"
    local manifest
    for manifest in "$DOTFILES_DIR"/install/manifests/*.yml; do
      print_info "  $(basename "$manifest" .yml)"
    done
    exit 1
  fi

  cd "$DOTFILES_DIR" || exit 1

  case "$verb" in
    show)
      uv run install/render_env.py --machine "$machine"
      ;;
    sync)
      print_section "Syncing ~/.env" "brightcyan"
      uv run install/render_env.py --machine "$machine" --sync
      ;;
    check)
      print_section "Checking ~/.env" "brightcyan"
      uv run install/render_env.py --machine "$machine" --check
      ;;
    *)
      log_error "Unknown verb: $verb"
      usage 1
      ;;
  esac
}

main "$@"
