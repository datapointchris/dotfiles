#!/usr/bin/env bash
# Simple bash test for failure registry functions
# This verifies the core functionality works before we polish ShellSpec integration

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export DOTFILES_DIR
export TERM=xterm

# Source the libraries
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

# Test counter
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test helper functions
pass() {
  echo -e "${GREEN}✓${NC} $1"
  ((TESTS_PASSED++)) || true
}

fail() {
  echo -e "${RED}✗${NC} $1"
  ((TESTS_FAILED++)) || true
}

test_init_failure_registry() {
  echo "Testing init_failure_registry()..."
  ((TESTS_RUN++)) || true

  init_failure_registry

  if [[ -n "$DOTFILES_FAILURE_REGISTRY" ]] && [[ -d "$DOTFILES_FAILURE_REGISTRY" ]]; then
    pass "Creates registry directory"
  else
    fail "Failed to create registry directory"
  fi

  # Cleanup
  rm -rf "$DOTFILES_FAILURE_REGISTRY" 2>/dev/null || true
}

test_report_failure() {
  echo "Testing report_failure()..."
  ((TESTS_RUN++)) || true

  # Set up test registry
  export DOTFILES_FAILURE_REGISTRY="/tmp/test-failures-$$"
  mkdir -p "$DOTFILES_FAILURE_REGISTRY"

  # Report a failure
  report_failure "test-tool" "https://example.com/test.tar.gz" "v1.0" "Manual steps here" "Download failed"

  # Check if failure file was created
  if compgen -G "$DOTFILES_FAILURE_REGISTRY/*-test-tool.txt" > /dev/null; then
    pass "Creates failure file"

    # Check file contents
    failure_file=$(find "$DOTFILES_FAILURE_REGISTRY" -name "*-test-tool.txt" -type f | head -1)
    if grep -q "TOOL=test-tool" "$failure_file" && \
       grep -q "URL=https://example.com/test.tar.gz" "$failure_file" && \
       grep -q "VERSION=v1.0" "$failure_file" && \
       grep -q "REASON=Download failed" "$failure_file"; then
      pass "Includes all required fields"
    else
      fail "Missing required fields in failure file"
    fi
  else
    fail "Failed to create failure file"
  fi

  # Cleanup
  rm -rf "$DOTFILES_FAILURE_REGISTRY" 2>/dev/null || true
}

test_report_failure_without_registry() {
  echo "Testing report_failure() without registry..."
  ((TESTS_RUN++)) || true

  # Unset registry
  unset DOTFILES_FAILURE_REGISTRY

  # This should not fail
  if report_failure "test" "url" "v1" "steps" "error"; then
    pass "Gracefully handles missing registry"
  else
    fail "Failed when registry not set"
  fi
}

test_display_failure_summary() {
  echo "Testing display_failure_summary()..."
  ((TESTS_RUN++)) || true

  # Set up test registry with sample failure
  export DOTFILES_FAILURE_REGISTRY="/tmp/test-failures-$$"
  mkdir -p "$DOTFILES_FAILURE_REGISTRY"

  cat > "$DOTFILES_FAILURE_REGISTRY/123-yazi.txt" <<EOF
TOOL=yazi
URL=https://example.com/yazi.zip
VERSION=v1.0
REASON=Download failed
MANUAL_STEPS<<STEPS_END
1. Download manually
2. Extract archive
3. Install binary
STEPS_END
EOF

  # Capture output
  output=$(display_failure_summary 2>&1)

  if echo "$output" | grep -q "Installation Summary" && \
     echo "$output" | grep -q "yazi - Manual Installation Required"; then
    pass "Displays failure summary correctly"
  else
    fail "Summary output incorrect"
  fi

  # Check if report file was created
  if ls /tmp/dotfiles-installation-failures-*.txt 1> /dev/null 2>&1; then
    pass "Saves report to /tmp directory"
    # Clean up report files
    rm -f /tmp/dotfiles-installation-failures-*.txt
  else
    fail "Did not save report file"
  fi

  # Cleanup
  rm -rf "$DOTFILES_FAILURE_REGISTRY" 2>/dev/null || true
}

test_output_failure_data() {
  echo "Testing output_failure_data()..."
  ((TESTS_RUN++)) || true

  # Capture stderr output
  local stderr_output
  stderr_output=$(output_failure_data "test-tool" "https://example.com/tool.tar.gz" "v1.0" "Manual steps here" "Download failed" 2>&1 >/dev/null)

  # Check for required fields
  if echo "$stderr_output" | grep -q "FAILURE_TOOL='test-tool'"; then
    pass "Outputs FAILURE_TOOL field"
  else
    fail "Missing FAILURE_TOOL field"
  fi

  if echo "$stderr_output" | grep -q "FAILURE_URL='https://example.com/tool.tar.gz'"; then
    pass "Outputs FAILURE_URL field"
  else
    fail "Missing FAILURE_URL field"
  fi

  if echo "$stderr_output" | grep -q "FAILURE_VERSION='v1.0'"; then
    pass "Outputs FAILURE_VERSION field"
  else
    fail "Missing FAILURE_VERSION field"
  fi

  if echo "$stderr_output" | grep -q "FAILURE_REASON='Download failed'"; then
    pass "Outputs FAILURE_REASON field"
  else
    fail "Missing FAILURE_REASON field"
  fi

  if echo "$stderr_output" | grep -q "FAILURE_MANUAL"; then
    pass "Outputs FAILURE_MANUAL section"
  else
    fail "Missing FAILURE_MANUAL section"
  fi

  if echo "$stderr_output" | grep -q "Manual steps here"; then
    pass "Includes manual steps content"
  else
    fail "Missing manual steps content"
  fi

  # Test multiline manual steps
  ((TESTS_RUN++)) || true
  local multiline="Step 1
Step 2
Step 3"
  stderr_output=$(output_failure_data "test" "http://url" "v1" "$multiline" "reason" 2>&1 >/dev/null)

  if echo "$stderr_output" | grep -q "Step 1" && echo "$stderr_output" | grep -q "Step 2" && echo "$stderr_output" | grep -q "Step 3"; then
    pass "Handles multiline manual steps"
  else
    fail "Failed to handle multiline manual steps"
  fi
}

# Run all tests
echo "========================================"
echo "Failure Registry Function Tests"
echo "========================================"
echo ""

test_init_failure_registry
echo ""
test_report_failure
echo ""
test_report_failure_without_registry
echo ""
test_display_failure_summary
echo ""
test_output_failure_data

# Summary
echo ""
echo "========================================"
echo "Test Results"
echo "========================================"
echo "Tests run: $TESTS_RUN"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
if [[ $TESTS_FAILED -gt 0 ]]; then
  echo -e "${RED}Failed: $TESTS_FAILED${NC}"
  exit 1
else
  echo "All tests passed!"
  exit 0
fi
