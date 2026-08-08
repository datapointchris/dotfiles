#!/usr/bin/env bash
set -uo pipefail

# BATS suite runner, driven by `task test*`.

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export DOTFILES_DIR
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"

# The globs below resolve relative to the repo, so this must precede them —
# expanding them from an arbitrary caller's directory leaves the patterns literal.
cd "$DOTFILES_DIR" || exit 1

# nullglob, because a directory emptying as its suites port to pytest must make
# the tier smaller rather than making bats fail on a literal glob it cannot open.
shopt -s nullglob
LIBRARY_TESTS=(tests/libraries/*.bats)
UNIT_TESTS=(tests/install/unit/*.bats tests/apps/*.bats)
INTEGRATION_TESTS=(tests/install/integration/*.bats)
shopt -u nullglob

# Each test is its own process, so the suite is dominated by process startup and
# scales almost linearly across cores. bats needs GNU parallel for --jobs and
# fails outright without it, so a machine that lacks it runs serially instead.
BATS_ARGS=()
if command -v parallel >/dev/null 2>&1; then
  cores=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)
  BATS_ARGS=(--jobs "$cores")
fi

run_bats() {
  bats "${BATS_ARGS[@]}" "$@"
}

usage() {
  help_header "test"
  help_usage "test.sh [all|unit|integration|watch]"

  help_section "Suites"
  help_row "all" "" "Library, unit, and integration suites (default)"
  help_row "unit" "" "Library and unit suites (no Docker)"
  help_row "integration" "" "Integration suites (includes Docker tests if the image is built)"
  help_row "watch" "" "Re-run everything on file changes (requires entr)"

  help_end
  exit "${1:-0}"
}

# The work WSL image lacks the Docker and system access these suites assume.
skip_on_wsl() {
  if grep -qi microsoft /proc/version 2>/dev/null; then
    print_warning "Skipping bats $1 tests on WSL"
    exit 0
  fi
}

main() {
  local suite="${1:-all}"
  [[ "$suite" == "help" || "$suite" == "-h" || "$suite" == "--help" ]] && usage 0

  case "$suite" in
    all)
      run_bats "${LIBRARY_TESTS[@]}" "${UNIT_TESTS[@]}" "${INTEGRATION_TESTS[@]}"
      ;;
    unit)
      skip_on_wsl unit
      run_bats "${LIBRARY_TESTS[@]}" "${UNIT_TESTS[@]}"
      ;;
    integration)
      skip_on_wsl integration
      run_bats "${INTEGRATION_TESTS[@]}"
      ;;
    watch)
      if ! command -v entr >/dev/null 2>&1; then
        log_error "entr is not installed"
        print_info "Install with: brew install entr (macOS) or pacman -S entr (Arch)"
        exit 1
      fi
      find tests -name '*.bats' | entr -c bats "${BATS_ARGS[@]}" "${LIBRARY_TESTS[@]}" "${UNIT_TESTS[@]}" "${INTEGRATION_TESTS[@]}"
      ;;
    *)
      log_error "Unknown suite: $suite"
      usage 1
      ;;
  esac
}

main "$@"
