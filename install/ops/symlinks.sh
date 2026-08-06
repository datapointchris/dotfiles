#!/usr/bin/env bash
set -uo pipefail

# Shared implementation of the composite symlink operations.
# Called by both front doors: `dotfiles symlinks <verb>` and `task symlinks:*`.

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export DOTFILES_DIR
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/install/platform-detection.sh"

usage() {
  help_header "symlinks"
  help_usage "symlinks.sh <link|relink|unlink|check|show>"

  help_section "Verbs"
  help_row "link" "" "Create symlinks for the common layer and this platform's overlay"
  help_row "relink" "" "Remove and recreate every symlink (idempotent; prunes dangling links)"
  help_row "unlink" "" "Remove all symlinks"
  help_row "check" "" "Find broken symlinks and remove them"
  help_row "show" "" "List every symlink this repo manages"

  help_end
  exit "${1:-0}"
}

sync_windows_shell_on_wsl() {
  [[ "$PLATFORM" != "wsl" ]] && return 0
  bash "$DOTFILES_DIR/install/wsl/sync-windows-shell.sh"
}

# `git config --global` writes to ~/.config/git/config when ~/.gitconfig does not
# exist — and this repo owns the former through a symlink, so following git's own
# "Please tell me who you are" hint on a fresh machine would commit an identity
# into the repo. An empty file is enough to redirect the write; it deliberately
# carries no [user], so useConfigOnly still refuses to commit until one is set.
ensure_identity_file() {
  local identity="$HOME/.gitconfig"
  [[ -e "$identity" ]] && return 0

  cat >"$identity" <<'EOF'
# This machine's git identity. Not in the dotfiles repo: identity is per-machine,
# and the shared config sets user.useConfigOnly so a machine without one refuses
# to commit rather than guessing an author from the hostname.
#
# Read after ~/.config/git/config, so anything here wins.
EOF
  print_info "Created $identity — set an identity with: git config --global user.email <address>"
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
      ensure_identity_file
      sync_windows_shell_on_wsl
      ;;
    relink)
      print_section "Relinking symlinks" "brightcyan"
      uv run symlinks relink "$PLATFORM"
      ensure_identity_file
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
