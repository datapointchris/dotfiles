#!/usr/bin/env bash
# ================================================================
# Quick Component Tests for Failure Registry System
# ================================================================
# Tests each component individually to avoid long integration tests
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Test helper functions
pass() {
  echo -e "${GREEN}✓ PASS${NC}: $1"
  TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
  echo -e "${RED}✗ FAIL${NC}: $1"
  TESTS_FAILED=$((TESTS_FAILED + 1))
}

info() {
  echo -e "${YELLOW}→${NC} $1"
}

echo "Testing Failure Registry Components"
echo "===================================="
echo ""

# Source the library
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

# ================================================================
# Test 1: init_failure_registry creates directory
# ================================================================
echo "Test 1: init_failure_registry creates directory and exports variable"
unset DOTFILES_FAILURE_REGISTRY 2>/dev/null || true
init_failure_registry

if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
  pass "DOTFILES_FAILURE_REGISTRY variable is set: $DOTFILES_FAILURE_REGISTRY"
else
  fail "DOTFILES_FAILURE_REGISTRY variable is NOT set"
fi

if [[ -d "$DOTFILES_FAILURE_REGISTRY" ]]; then
  pass "Registry directory exists: $DOTFILES_FAILURE_REGISTRY"
else
  fail "Registry directory does NOT exist"
fi
echo ""

# ================================================================
# Test 2: report_failure creates file in registry
# ================================================================
echo "Test 2: report_failure writes to registry"
report_failure "test-tool" "https://example.com/test.tar.gz" "v1.0" "Manual steps here" "Test failure"

if ls "$DOTFILES_FAILURE_REGISTRY"/*-test-tool.txt >/dev/null 2>&1; then
  pass "Failure file created in registry"
  FAILURE_FILE=$(find "$DOTFILES_FAILURE_REGISTRY" -name "*-test-tool.txt" -print -quit)
  info "File: $FAILURE_FILE"

  # Check file contents
  if grep -q "TOOL='test-tool'" "$FAILURE_FILE"; then
    pass "Failure file contains correct tool name"
  else
    fail "Failure file missing tool name"
  fi

  if grep -q "REASON='Test failure'" "$FAILURE_FILE"; then
    pass "Failure file contains reason"
  else
    fail "Failure file missing reason"
  fi
else
  fail "No failure file created"
fi
echo ""

# ================================================================
# Test 3: display_failure_summary creates permanent log
# ================================================================
echo "Test 3: display_failure_summary creates permanent log file"

# Clean up old test logs
rm -f /tmp/dotfiles-installation-failures-*.txt

display_failure_summary > /tmp/test-summary-output.txt 2>&1

# Check if permanent log was created
# shellcheck disable=SC2012,SC2086
if ls /tmp/dotfiles-installation-failures-*.txt >/dev/null 2>&1; then
  # shellcheck disable=SC2012
  PERMANENT_LOG=$(ls -t /tmp/dotfiles-installation-failures-*.txt 2>/dev/null | head -1)
  pass "Permanent failure log created: $PERMANENT_LOG"

  # Check log contents
  if grep -q "test-tool" "$PERMANENT_LOG"; then
    pass "Permanent log contains test-tool failure"
  else
    fail "Permanent log missing test-tool failure"
  fi
else
  fail "No permanent failure log created"
  cat /tmp/test-summary-output.txt
fi
echo ""

# ================================================================
# Test 4: report_failure standalone mode (no registry)
# ================================================================
echo "Test 4: report_failure prints immediately when no registry"
unset DOTFILES_FAILURE_REGISTRY

OUTPUT=$(report_failure "standalone-tool" "https://example.com/tool.tar.gz" "v2.0" "Install manually" "Download failed" 2>&1)

if echo "$OUTPUT" | grep -q "Manual Installation Required"; then
  pass "Standalone mode prints manual installation message"
else
  fail "Standalone mode did not print expected message"
  echo "Output was:"
  echo "$OUTPUT"
fi

if echo "$OUTPUT" | grep -q "standalone-tool"; then
  pass "Standalone mode includes tool name"
else
  fail "Standalone mode missing tool name"
fi
echo ""

# ================================================================
# Test 5: Environment variable inheritance
# ================================================================
echo "Test 5: DOTFILES_FAILURE_REGISTRY inherited by child processes"
init_failure_registry
export DOTFILES_FAILURE_REGISTRY

CHILD_OUTPUT=$(bash -c 'echo "Child sees: ${DOTFILES_FAILURE_REGISTRY:-NOT_SET}"')

if echo "$CHILD_OUTPUT" | grep -q "NOT_SET"; then
  fail "Environment variable NOT inherited by child process"
else
  pass "Environment variable inherited by child process"
  info "$CHILD_OUTPUT"
fi
echo ""

# ================================================================
# Summary
# ================================================================
echo "===================================="
echo "Test Results Summary"
echo "===================================="
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

# Cleanup
rm -f /tmp/test-summary-output.txt

if [[ $TESTS_FAILED -gt 0 ]]; then
  echo -e "${RED}Some tests failed!${NC}"
  exit 1
else
  echo -e "${GREEN}All tests passed!${NC}"
  exit 0
fi
