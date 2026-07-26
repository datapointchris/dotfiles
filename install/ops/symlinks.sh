#!/usr/bin/env bash
set -uo pipefail

# Shared implementation of the composite symlink operations.
# Called by both front doors: `dotfiles symlinks <verb>` and `task symlinks:*`.

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$OPS_DIR/../.." && pwd)"
export DOTFILES_DIR
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/install/platform-detection.sh"

# Format: verb|description
VERBS=(
  "link|Create symlinks for the common layer and this platform's overlay"
  "relink|Remove and recreate every symlink (idempotent; prunes dangling links)"
  "unlink|Remove all symlinks"
  "check|Find broken symlinks and remove them"
  "show|List every symlink this repo manages"
)

usage() {
  local entry verb description

  print_header "symlinks" "brightcyan"
  print_cyan "Usage: symlinks.sh <link|relink|unlink|check|show>"

  print_section "Verbs" "brightcyan"
  for entry in "${VERBS[@]}"; do
    IFS='|' read -r verb description <<<"$entry"
    print_help_row 9 "$verb" "$description"
  done
  echo ""
  exit "${1:-0}"
}

sync_windows_shell_on_wsl() {
  [[ "$PLATFORM" != "wsl" ]] && return 0
  bash "$DOTFILES_DIR/install/wsl/sync-windows-shell.sh"
}

main() {
  local verb="${1:-}"
  [[ -z "$verb" || "$verb" == "help" || "$verb" == "-h" || "$verb" == "--help" ]] && usage 0

  PLATFORM="$(detect_platform)"

  # `uv run` resolves the project from the working directory.
  cd "$DOTFILES_DIR" || exit 1

  case "$verb" in
  link)
    print_section "Creating symlinks" "brightcyan"
    uv run symlinks link common
    uv run symlinks link "$PLATFORM"
    sync_windows_shell_on_wsl
    ;;
  relink)
    print_section "Relinking symlinks" "brightcyan"
    uv run symlinks relink "$PLATFORM"
    sync_windows_shell_on_wsl
    ;;
  unlink)
    print_section "Removing symlinks" "brightcyan"
    # Platform is an overlay on top of common, so it comes off first.
    uv run symlinks unlink "$PLATFORM"
    uv run symlinks unlink common
    ;;
  check)
    uv run symlinks check
    ;;
  show)
    uv run symlinks show
    ;;
  *)
    log_error "Unknown verb: $verb"
    usage 1
    ;;
  esac
}

main "$@"
