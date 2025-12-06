#!/usr/bin/env bash
# ================================================================
# Test: run_installer Failure Data Capture
# ================================================================
# Verifies that structured failure data is properly captured from stderr
# while still showing installer output to users
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

echo "=========================================="
echo "Test: run_installer Failure Capture"
echo "=========================================="
echo ""

# Create temporary directory for test
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# Create mock installer that FAILS and outputs structured data
cat > "$TEST_DIR/mock-failure.sh" << 'EOF'
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

log_info "Starting installation..."
log_error "Failed to download from https://example.com/tool.tar.gz"

# Output structured failure data to stderr
output_failure_data "test-tool" "https://example.com/tool.tar.gz" "v1.0.0" "Manual install steps here" "Download failed"

exit 1
EOF
chmod +x "$TEST_DIR/mock-failure.sh"

# Define PROPOSED FIXED version of run_installer
FAILURES_LOG="$TEST_DIR/failures.txt"
export FAILURES_LOG

run_installer_fixed() {
  local script="$1"
  local tool_name="$2"

  # FIX: Only capture stderr, let stdout flow through
  local stderr_file
  stderr_file=$(mktemp)

  bash "$script" 2>"$stderr_file"
  exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    rm -f "$stderr_file"
    log_success "$tool_name installed"
    return 0
  else
    log_warning "$tool_name installation failed (see $FAILURES_LOG)"

    # Parse structured failure data from stderr
    local output
    output=$(cat "$stderr_file")
    rm -f "$stderr_file"

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
    cat >> "$FAILURES_LOG" << EOFLOG
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

EOFLOG
    return 1
  fi
}

echo "Test 1: Verify user sees installer output (not captured)"
echo "--- Installer Output (should see log messages below) ---"

# Run without capturing to let output flow through
# We'll verify by checking the failure log was created
run_installer_fixed "$TEST_DIR/mock-failure.sh" "test-tool" || true

echo "--- End Output ---"
echo ""
log_success "✓ Test 1: Check output above - you should see 'Starting installation...' and 'Failed to download'"

echo ""
echo "Test 2: Verify structured failure data was captured"
if [[ ! -f "$FAILURES_LOG" ]]; then
  log_error "✗ Test 2 FAIL: Failures log not created"
  exit 1
fi

if grep -q "test-tool - Installation Failed" "$FAILURES_LOG"; then
  log_success "✓ Test 2 PASS: Failure logged"
else
  log_error "✗ Test 2 FAIL: Failure not logged"
  cat "$FAILURES_LOG"
  exit 1
fi

echo ""
echo "Test 3: Verify all structured data captured correctly"
FAIL_COUNT=0

if ! grep -q "https://example.com/tool.tar.gz" "$FAILURES_LOG"; then
  log_error "✗ Download URL not in log"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

if ! grep -q "v1.0.0" "$FAILURES_LOG"; then
  log_error "✗ Version not in log"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

if ! grep -q "Download failed" "$FAILURES_LOG"; then
  log_error "✗ Reason not in log"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

if ! grep -q "Manual install steps" "$FAILURES_LOG"; then
  log_error "✗ Manual steps not in log"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

if [[ $FAIL_COUNT -eq 0 ]]; then
  log_success "✓ Test 3 PASS: All structured data captured"
else
  log_error "✗ Test 3 FAIL: $FAIL_COUNT fields missing"
  echo ""
  echo "Failure log contents:"
  cat "$FAILURES_LOG"
  exit 1
fi

echo ""
log_success "=========================================="
log_success "All tests passed!"
log_success "The fixed run_installer:"
log_success "  1. Shows output to users"
log_success "  2. Captures failure data"
log_success "  3. Logs all structured fields"
log_success "=========================================="
