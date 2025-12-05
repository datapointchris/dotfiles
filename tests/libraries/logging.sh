#!/usr/bin/env bash
# ================================================================
# Test platforms/common/.local/shell/logging.sh
# ================================================================
# Tests for the logging library functions:
# - log_info, log_success, log_warning, log_error, log_fatal
# - log_section
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source the library under test
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

# ================================================================
# Test Helpers
# ================================================================

pass() {
  echo -e "\033[0;32m✓\033[0m $1"
  ((PASSED++))
}

fail() {
  echo -e "\033[0;31m✗\033[0m $1"
  ((FAILED++))
}

# ================================================================
# Tests
# ================================================================

PASSED=0
FAILED=0

echo "========================================"
echo "Logging Library Tests"
echo "========================================"
echo ""

# TODO: Add tests for logging functions
# - Test log_info outputs with [INFO] prefix
# - Test log_success outputs with [SUCCESS] prefix
# - Test log_warning outputs with [WARNING] prefix
# - Test log_error outputs with [ERROR] prefix
# - Test log_fatal exits with code 1
# - Test log_section outputs section header

echo "Tests not yet implemented - placeholder"

echo ""
echo "========================================"
echo "Test Results"
echo "========================================"
echo "Tests run: 0"
echo -e "\033[0;32mPassed: $PASSED\033[0m"
echo -e "\033[0;31mFailed: $FAILED\033[0m"

[[ $FAILED -eq 0 ]]
