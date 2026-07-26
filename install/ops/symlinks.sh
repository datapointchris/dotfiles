#!/usr/bin/env bash
set -uo pipefail

# Shared implementation of the composite symlink operations.
# Called by both front doors: `dotfiles symlinks <verb>` and `task symlinks:*`.

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$OPS_DIR/../.." && pwd)"
export DOTFILES_DIR
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/platform-detection.sh"

usage() {
  echo "Usage: symlinks.sh <link|relink|unlink|check|show>"
  echo ""
  echo "  link     Create symlinks for the common layer and this platform's overlay"
  echo "  relink   Remove and recreate every symlink (idempotent; prunes dangling links)"
  echo "  unlink   Remove all symlinks"
  echo "  check    Find broken symlinks and remove them"
  echo "  show     List every symlink this repo manages"
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
    print_section "Creating symlinks" "cyan"
    uv run symlinks link common
    uv run symlinks link "$PLATFORM"
    sync_windows_shell_on_wsl
    ;;
  relink)
    print_section "Relinking symlinks" "cyan"
    uv run symlinks relink "$PLATFORM"
    sync_windows_shell_on_wsl
    ;;
  unlink)
    print_section "Removing symlinks" "cyan"
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
    echo "Unknown verb: $verb" >&2
    usage 1
    ;;
  esac
}

main "$@"
