#!/usr/bin/env bash
# ================================================================
# Test run_installer() wrapper function
# ================================================================
# Tests the new simplified wrapper that:
# - Captures script output
# - Checks exit codes
# - Parses structured failure data
# - Logs failures to single file
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source libraries
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
  echo -e "${GREEN}✓${NC} $1"
  ((TESTS_PASSED++)) || true
}

fail() {
  echo -e "${RED}✗${NC} $1"
  ((TESTS_FAILED++)) || true
}

# Setup test environment
FAILURES_LOG="/tmp/test-run-installer-$$.log"
export FAILURES_LOG
rm -f "$FAILURES_LOG"

# Define run_installer function (extracted from install.sh)
# This is the new simplified wrapper we're testing
run_installer() {
  local script="$1"
  local tool_name="$2"

  # Capture both stdout and stderr
  local output
  local exit_code

  output=$(bash "$script" 2>&1)
  exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    log_success "$tool_name installed"
    return 0
  else
    log_warning "$tool_name installation failed (see $FAILURES_LOG)"

    # Parse structured failure data from output
    local failure_tool failure_url failure_version failure_reason failure_manual
    failure_tool=$(echo "$output" | grep "^FAILURE_TOOL=" | cut -d"'" -f2 || echo "$tool_name")
    failure_url=$(echo "$output" | grep "^FAILURE_URL=" | cut -d"'" -f2 || echo "")
    failure_version=$(echo "$output" | grep "^FAILURE_VERSION=" | cut -d"'" -f2 || echo "")
    failure_reason=$(echo "$output" | grep "^FAILURE_REASON=" | cut -d"'" -f2 || echo "")

    # Extract multiline manual steps
    if echo "$output" | grep -q "^FAILURE_MANUAL<<"; then
      failure_manual=$(echo "$output" | sed -n '/^FAILURE_MANUAL<</,/^END_MANUAL/p' | sed '1d;$d')
    fi

    # Append to failures log
    cat >> "$FAILURES_LOG" << EOF
========================================
$failure_tool - Installation Failed
========================================
Script: $script
Exit Code: $exit_code
Timestamp: $(date -Iseconds)
${failure_url:+Download URL: $failure_url}
${failure_version:+Version: $failure_version}
${failure_reason:+Reason: $failure_reason}

${failure_manual:+Manual Installation Steps:
$failure_manual
}
---

EOF
    return 1
  fi
}

# ================================================================
# Tests
# ================================================================

print_banner "Testing run_installer() Wrapper"

# Test 1: Successful installation
echo "Test 1: Successful installation..."
((TESTS_RUN++)) || true

cat > /tmp/test-pass.sh << 'EOF'
#!/bin/bash
echo "Installing successfully..."
exit 0
EOF
chmod +x /tmp/test-pass.sh

if run_installer /tmp/test-pass.sh "test-tool" >/dev/null 2>&1; then
  pass "Successful script returns 0"
else
  fail "Successful script should return 0"
fi

if [[ ! -f "$FAILURES_LOG" ]] || [[ ! -s "$FAILURES_LOG" ]]; then
  pass "No failures logged for successful install"
else
  fail "Should not log failures for successful install"
fi

# Test 2: Failed installation without structured output
echo ""
echo "Test 2: Failed installation without structured output..."
((TESTS_RUN++)) || true

rm -f "$FAILURES_LOG"

cat > /tmp/test-fail.sh << 'EOF'
#!/bin/bash
echo "ERROR: Download failed"
exit 1
EOF
chmod +x /tmp/test-fail.sh

if run_installer /tmp/test-fail.sh "failing-tool" >/dev/null 2>&1; then
  fail "Failed script should return 1"
else
  pass "Failed script returns 1"
fi

if [[ -f "$FAILURES_LOG" ]] && grep -q "failing-tool" "$FAILURES_LOG"; then
  pass "Failure logged to FAILURES_LOG"
else
  fail "Should log failure to FAILURES_LOG"
fi

if grep -q "Exit Code: 1" "$FAILURES_LOG"; then
  pass "Log includes exit code"
else
  fail "Log should include exit code"
fi

# Test 3: Failed installation WITH structured output
echo ""
echo "Test 3: Failed installation with structured output..."
((TESTS_RUN++)) || true

rm -f "$FAILURES_LOG"

cat > /tmp/test-structured.sh << 'EOF'
#!/bin/bash
cat >&2 << 'FAILURE'
FAILURE_TOOL='structured-tool'
FAILURE_URL='https://example.com/download.tar.gz'
FAILURE_VERSION='v1.2.3'
FAILURE_REASON='Download failed - network timeout'
FAILURE_MANUAL<<'END_MANUAL'
1. Download from browser: https://example.com/download.tar.gz
2. Extract: tar -xzf download.tar.gz
3. Install: mv binary ~/.local/bin/
END_MANUAL
FAILURE
exit 1
EOF
chmod +x /tmp/test-structured.sh

if run_installer /tmp/test-structured.sh "structured-tool" >/dev/null 2>&1; then
  fail "Failed script should return 1"
else
  pass "Structured failure script returns 1"
fi

if [[ -f "$FAILURES_LOG" ]] && grep -q "structured-tool" "$FAILURES_LOG"; then
  pass "Structured failure logged"
else
  fail "Should log structured failure"
fi

if grep -q "Download URL: https://example.com/download.tar.gz" "$FAILURES_LOG"; then
  pass "Parsed FAILURE_URL correctly"
else
  fail "Should parse FAILURE_URL from output"
fi

if grep -q "Version: v1.2.3" "$FAILURES_LOG"; then
  pass "Parsed FAILURE_VERSION correctly"
else
  fail "Should parse FAILURE_VERSION from output"
fi

if grep -q "Reason: Download failed - network timeout" "$FAILURES_LOG"; then
  pass "Parsed FAILURE_REASON correctly"
else
  fail "Should parse FAILURE_REASON from output"
fi

if grep -q "Manual Installation Steps:" "$FAILURES_LOG" && \
   grep -q "Download from browser" "$FAILURES_LOG"; then
  pass "Parsed FAILURE_MANUAL steps correctly"
else
  fail "Should parse FAILURE_MANUAL from output"
fi

# Test 4: Multiple failures append to log
echo ""
echo "Test 4: Multiple failures append to log..."
((TESTS_RUN++)) || true

rm -f "$FAILURES_LOG"

run_installer /tmp/test-fail.sh "tool1" >/dev/null 2>&1 || true
run_installer /tmp/test-fail.sh "tool2" >/dev/null 2>&1 || true

failure_count=$(grep -c "^---$" "$FAILURES_LOG" || echo 0)
if [[ $failure_count -eq 2 ]]; then
  pass "Multiple failures appended to log"
else
  fail "Should append multiple failures (found $failure_count, expected 2)"
fi

# Cleanup
rm -f /tmp/test-*.sh "$FAILURES_LOG"

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
