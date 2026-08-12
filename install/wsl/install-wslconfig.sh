#!/usr/bin/env bash
# ================================================================
# Install .wslconfig to the Windows user profile
# ================================================================
# Usage: install-wslconfig.sh [--check]   (run from WSL)
#
# .wslconfig configures the VM that hosts every distro, so it lives on the
# Windows side and cannot be a symlink from this repo — the symlink manager
# deploys below $HOME, and $HOME here is inside the guest.
#
# An existing file is never silently replaced. It is a file a person edits by
# hand at the exact moment something is broken, and overwriting that during an
# unrelated install is how a fix disappears without anything saying so.
# ================================================================

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)}"
TEMPLATE="$DOTFILES_DIR/install/wsl/wslconfig.template"

is_wsl() {
  grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null
}

# Asked of Windows rather than built from $WINDOWS_USER: the profile directory is
# not always C:\Users\<name>, and Windows knows which one it is.
windows_userprofile() {
  local profile
  profile=$(powershell.exe -NoProfile -NonInteractive -Command "Write-Output \$env:USERPROFILE" </dev/null 2>/dev/null | tr -d '\r\n\0')
  [[ -n "$profile" ]] || return 1
  wslpath -u "$profile" 2>/dev/null
}

main() {
  local mode="${1:-install}"

  if ! is_wsl; then
    [[ "$mode" == "--check" ]] || echo "Not in WSL - skipping .wslconfig install"
    return 0
  fi

  local profile
  if ! profile=$(windows_userprofile); then
    [[ "$mode" == "--check" ]] || echo "Could not resolve %USERPROFILE% - skipping .wslconfig install"
    return 0
  fi

  local target="$profile/.wslconfig"

  # Drift on stdout and nothing else, so the caller reads an empty answer as
  # converged. Same contract as sync-windows-shell.sh --check.
  if [[ "$mode" == "--check" ]]; then
    if [[ ! -f "$target" ]]; then
      echo "missing: .wslconfig"
    elif ! cmp -s "$TEMPLATE" "$target"; then
      echo "differs: .wslconfig"
    fi
    return 0
  fi

  if [[ -f "$target" ]]; then
    if cmp -s "$TEMPLATE" "$target"; then
      echo ".wslconfig is already current: $target"
      return 0
    fi

    echo "An existing .wslconfig differs from the template:"
    diff -u "$target" "$TEMPLATE" || true
    echo ""

    local backup
    backup="$target.$(date +%Y%m%d%H%M%S).bak"
    cp "$target" "$backup"
    echo "Backed up to: $backup"
  fi

  cp "$TEMPLATE" "$target"
  echo "Wrote: $target"
  echo ""
  echo "Run 'wsl.exe --shutdown' from Windows, wait ~8 seconds, then reopen the terminal."
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
