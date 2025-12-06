#!/usr/bin/env bash
# ================================================================
# Integration test for language manager installers pattern
# ================================================================
# Tests that language manager installers:
# 1. Output structured failure data using output_failure_data()
# 2. Return proper exit codes (0 for success, 1 for failure)
# 3. Work with run_installer wrapper
# 4. Generate properly formatted failure logs
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source libraries
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

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
  TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
  echo -e "${RED}✗${NC} $1"
  TESTS_FAILED=$((TESTS_FAILED + 1))
}

print_banner "Testing Language Managers Pattern"

# Setup test environment
FAILURES_LOG="/tmp/test-language-managers-$$.log"
export FAILURES_LOG
rm -f "$FAILURES_LOG"

# Create mock language manager installer that uses new pattern
MOCK_INSTALLER="/tmp/mock-language-manager.sh"
cat > "$MOCK_INSTALLER" << 'EOF'
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

# Simulate language manager installer that fails
TOOL_NAME="mock-lang-manager"
DOWNLOAD_URL="https://example.com/install.sh"
VERSION="v1.0"
MANUAL_STEPS="1. Download from: $DOWNLOAD_URL
2. Run: bash install.sh
3. Verify: mock-lang-manager --version"

# Simulate download failure
log_error "Failed to download installer from $DOWNLOAD_URL"

# Output structured failure data (new pattern)
output_failure_data "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "$MANUAL_STEPS" "Download failed - network timeout"

# Return error code
exit 1
EOF
chmod +x "$MOCK_INSTALLER"

# Define run_installer wrapper (from install.sh)
run_installer() {
  local script="$1"
  local tool_name="$2"

  local output
  local exit_code

  output=$(bash "$script" 2>&1)
  exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    log_success "$tool_name installed"
    return 0
  else
    log_warning "$tool_name installation failed (see $FAILURES_LOG)"

    local failure_tool failure_url failure_version failure_reason failure_manual
    failure_tool=$(echo "$output" | grep "^FAILURE_TOOL=" | cut -d"'" -f2 || echo "$tool_name")
    failure_url=$(echo "$output" | grep "^FAILURE_URL=" | cut -d"'" -f2 || echo "")
    failure_version=$(echo "$output" | grep "^FAILURE_VERSION=" | cut -d"'" -f2 || echo "")
    failure_reason=$(echo "$output" | grep "^FAILURE_REASON=" | cut -d"'" -f2 || echo "")

    if echo "$output" | grep -q "^FAILURE_MANUAL<<"; then
      failure_manual=$(echo "$output" | sed -n '/^FAILURE_MANUAL<</,/^END_MANUAL/p' | sed '1d;$d')
    fi

    cat >> "$FAILURES_LOG" << EOF_LOG
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

EOF_LOG
    return 1
  fi
}

# ================================================================
# Tests
# ================================================================

# Test 1: Mock installer outputs structured failure data
echo "Test 1: Installer outputs structured failure data..."
TESTS_RUN=$((TESTS_RUN + 1))

OUTPUT=$(bash "$MOCK_INSTALLER" 2>&1 || true)

if echo "$OUTPUT" | grep -q "FAILURE_TOOL='mock-lang-manager'"; then
  pass "Outputs FAILURE_TOOL field"
else
  fail "Missing FAILURE_TOOL field"
fi

if echo "$OUTPUT" | grep -q "FAILURE_URL='https://example.com/install.sh'"; then
  pass "Outputs FAILURE_URL field"
else
  fail "Missing FAILURE_URL field"
fi

if echo "$OUTPUT" | grep -q "FAILURE_VERSION='v1.0'"; then
  pass "Outputs FAILURE_VERSION field"
else
  fail "Missing FAILURE_VERSION field"
fi

if echo "$OUTPUT" | grep -q "FAILURE_REASON='Download failed"; then
  pass "Outputs FAILURE_REASON field"
else
  fail "Missing FAILURE_REASON field"
fi

if echo "$OUTPUT" | grep -q "FAILURE_MANUAL"; then
  pass "Outputs FAILURE_MANUAL section"
else
  fail "Missing FAILURE_MANUAL section"
fi

# Test 2: run_installer captures and logs structured data
echo ""
echo "Test 2: Wrapper captures structured failure data..."
TESTS_RUN=$((TESTS_RUN + 1))

rm -f "$FAILURES_LOG"
run_installer "$MOCK_INSTALLER" "mock-lang-manager" >/dev/null 2>&1 || true

if [[ -f "$FAILURES_LOG" ]]; then
  pass "Failures log created"
else
  fail "No failures log created"
fi

if grep -q "mock-lang-manager - Installation Failed" "$FAILURES_LOG"; then
  pass "Log contains tool name"
else
  fail "Log missing tool name"
fi

if grep -q "Download URL: https://example.com/install.sh" "$FAILURES_LOG"; then
  pass "Log contains parsed URL"
else
  fail "Log missing parsed URL"
fi

if grep -q "Version: v1.0" "$FAILURES_LOG"; then
  pass "Log contains parsed version"
else
  fail "Log missing parsed version"
fi

if grep -q "Reason: Download failed" "$FAILURES_LOG"; then
  pass "Log contains parsed reason"
else
  fail "Log missing parsed reason"
fi

if grep -q "Manual Installation Steps:" "$FAILURES_LOG"; then
  pass "Log contains manual steps"
else
  fail "Log missing manual steps"
fi

# Test 3: Installer returns proper exit code
echo ""
echo "Test 3: Installer returns proper exit code..."
TESTS_RUN=$((TESTS_RUN + 1))

if bash "$MOCK_INSTALLER" >/dev/null 2>&1; then
  fail "Installer should return exit code 1"
else
  pass "Installer returns exit code 1 on failure"
fi

# Cleanup
rm -f "$MOCK_INSTALLER" "$FAILURES_LOG"

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
  print_banner_success "Language managers pattern test passed"
  exit 0
fi
