# shellcheck shell=bash
# shellcheck disable=SC3043,SC3010,SC3046,SC3051
# ShellSpec runs with bash despite shell=sh directive

# ShellSpec Helper for Dotfiles Installation Failure Handling Tests
#
# This file is loaded before all test specs and provides:
# - Common test setup and teardown
# - Shared helper functions
# - Mock utilities
# - Fixture management

# Defining variables and functions here will affect all specfiles.
set -eu

# This callback function will be invoked only once before loading specfiles.
spec_helper_precheck() {
  : minimum_version "0.28.1"
}

# This callback function will be invoked after a specfile has been loaded.
spec_helper_loaded() {
  :
}

# This callback function will be invoked after core modules has been loaded.
spec_helper_configure() {
  # Set up test environment
  export DOTFILES_DIR="${DOTFILES_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
  export TERM="${TERM:-xterm}"

  # Ensure test isolation - use temporary directories for test runs
  export TEST_TEMP_DIR="${SHELLSPEC_TMPBASE:-/tmp}/dotfiles-test-$$"
}

# ================================================================
# Shared Test Helpers
# ================================================================

# Create a mock failure registry for testing
create_mock_failure_registry() {
  export DOTFILES_FAILURE_REGISTRY="${TEST_TEMP_DIR}/failures-$$"
  mkdir -p "$DOTFILES_FAILURE_REGISTRY"
}

# Clean up mock failure registry
cleanup_mock_failure_registry() {
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]] && [[ -d "$DOTFILES_FAILURE_REGISTRY" ]]; then
    rm -rf "$DOTFILES_FAILURE_REGISTRY"
  fi
  unset DOTFILES_FAILURE_REGISTRY
}

# Create a sample failure file for testing
create_sample_failure() {
  local tool_name="$1"
  local url="${2:-https://github.com/example/repo/releases/download/v1.0/tool.tar.gz}"
  local version="${3:-v1.0}"
  local reason="${4:-Download failed}"

  cat > "$DOTFILES_FAILURE_REGISTRY/$(date +%s)-${tool_name}.txt" <<EOF
TOOL=$tool_name
URL=$url
VERSION=$version
REASON=$reason
MANUAL_STEPS<<STEPS_END
1. Download in your browser:
   $url

2. After downloading:
   tar -xzf ~/Downloads/${tool_name}.tar.gz
   mv ${tool_name} ~/.local/bin/
   chmod +x ~/.local/bin/${tool_name}

3. Verify:
   ${tool_name} --version
STEPS_END
EOF
}

# Source the library under test
source_program_helpers() {
  # Source logging and formatting libraries first
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

  # Source the program helpers library
  source "$DOTFILES_DIR/management/common/lib/program-helpers.sh"
}
