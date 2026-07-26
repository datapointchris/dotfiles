#!/usr/bin/env bash
set -uo pipefail

# BATS suite runner shared by `dotfiles test` and `task test*`.

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$OPS_DIR/../.." && pwd)"
export DOTFILES_DIR

# The globs below resolve relative to the repo, so this must precede them —
# expanding them from an arbitrary caller's directory leaves the patterns literal.
cd "$DOTFILES_DIR" || exit 1

LIBRARY_TESTS=(tests/libraries/*.bats)
UNIT_TESTS=(tests/install/unit/*.bats tests/apps/*.bats)
INTEGRATION_TESTS=(tests/install/integration/*.bats)

usage() {
  echo "Usage: test.sh [all|unit|integration|watch]"
  echo ""
  echo "  all           Library, unit, and integration suites (default)"
  echo "  unit          Library and unit suites (no Docker)"
  echo "  integration   Integration suites (includes Docker tests if the image is built)"
  echo "  watch         Re-run everything on file changes (requires entr)"
  exit "${1:-0}"
}

# The work WSL image lacks the Docker and system access these suites assume.
skip_on_wsl() {
  if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "Skipping bats $1 tests on WSL"
    exit 0
  fi
}

main() {
  local suite="${1:-all}"
  [[ "$suite" == "help" || "$suite" == "-h" || "$suite" == "--help" ]] && usage 0

  case "$suite" in
  all)
    bats "${LIBRARY_TESTS[@]}" "${UNIT_TESTS[@]}" "${INTEGRATION_TESTS[@]}"
    ;;
  unit)
    skip_on_wsl unit
    bats "${LIBRARY_TESTS[@]}" "${UNIT_TESTS[@]}"
    ;;
  integration)
    skip_on_wsl integration
    bats "${INTEGRATION_TESTS[@]}"
    ;;
  watch)
    if ! command -v entr >/dev/null 2>&1; then
      echo "entr not installed. Install with: brew install entr (macOS) or pacman -S entr (Arch)"
      exit 1
    fi
    find tests -name '*.bats' | entr -c bats "${LIBRARY_TESTS[@]}" "${UNIT_TESTS[@]}" "${INTEGRATION_TESTS[@]}"
    ;;
  *)
    echo "Unknown suite: $suite" >&2
    usage 1
    ;;
  esac
}

main "$@"
