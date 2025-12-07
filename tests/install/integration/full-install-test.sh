#!/usr/bin/env bash
# ================================================================
# Full Installation Integration Test
# ================================================================
# Tests install.sh with mixed successes and failures
# Validates run_installer wrapper and show_failures_summary
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

print_banner "Full Installation Integration Test"

# Set up test failures log
export FAILURES_LOG="/tmp/full-install-test-$$.log"
rm -f "$FAILURES_LOG"

# ================================================================
# Copy functions from install.sh
# (Avoids heredoc-in-eval conflicts)
# ================================================================

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
    cat >> "$FAILURES_LOG" << ENDLOG
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

ENDLOG
    return 1
  fi
}

show_failures_summary() {
  if [[ ! -f "$FAILURES_LOG" ]]; then
    return 0
  fi

  # Check if file has content
  if [[ ! -s "$FAILURES_LOG" ]]; then
    return 0
  fi

  # Count failures (each has a separator line)
  local failure_count
  failure_count=$(grep -c "^---$" "$FAILURES_LOG" || echo 0)

  if [[ $failure_count -eq 0 ]]; then
    return 0
  fi

  # Display header
  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "Installation Summary"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
  log_warning "$failure_count installation(s) failed"
  log_info "This is common in restricted network environments"
  echo ""

  # Display the log file contents (already formatted)
  cat "$FAILURES_LOG"

  echo "════════════════════════════════════════════════════════════════"
  echo "Full report saved to: $FAILURES_LOG"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
}

# ================================================================
# Test Setup - Create Mock Installers
# ================================================================

TEMP_DIR="/tmp/dotfiles-integration-test-$$"
mkdir -p "$TEMP_DIR"
MOCK_SUCCESS="$TEMP_DIR/mock-success.sh"
MOCK_FAILURE="$TEMP_DIR/mock-failure.sh"

# Mock installer that succeeds
cat > "$MOCK_SUCCESS" << 'ENDMOCK1'
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

log_info "Installing mock-success tool..."
sleep 0.1
log_success "mock-success installed successfully"
exit 0
ENDMOCK1
chmod +x "$MOCK_SUCCESS"

# Mock installer that fails with structured output
cat > "$MOCK_FAILURE" << 'ENDMOCK2'
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

TOOL_NAME="mock-failure"
DOWNLOAD_URL="https://example.com/mock-failure.tar.gz"
VERSION="v1.0.0"

# Build manual steps using simple variable (avoid heredoc-in-heredoc)
MANUAL_STEPS="1. Download from: https://example.com/mock-failure.tar.gz
2. Extract: tar -xzf mock-failure.tar.gz
3. Install: mv mock-failure ~/.local/bin/
4. Verify: mock-failure --version"

log_error "Failed to download from $DOWNLOAD_URL"
output_failure_data "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "$MANUAL_STEPS" "Download failed - simulated network error"
exit 1
ENDMOCK2
chmod +x "$MOCK_FAILURE"

# ================================================================
# Test 1: Successful Installation
# ================================================================

print_section "Test 1: Successful installer" "cyan"

if run_installer "$MOCK_SUCCESS" "mock-success"; then
  log_success "✓ Success installer handled correctly"
else
  log_error "✗ Success installer should return 0"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi

# Verify no failure log created for success
if [[ -f "$FAILURES_LOG" ]]; then
  log_error "✗ Failures log should not exist for successful install"
  cat "$FAILURES_LOG"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
else
  log_success "✓ No failure log created for success"
fi

# ================================================================
# Test 2: Failed Installation with Structured Output
# ================================================================

print_section "Test 2: Failed installer with structured output" "cyan"

if run_installer "$MOCK_FAILURE" "mock-failure"; then
  log_error "✗ Failing installer should return non-zero"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
else
  log_success "✓ Failure installer returned non-zero"
fi

# Verify failure log created
if [[ ! -f "$FAILURES_LOG" ]]; then
  log_error "✗ Failures log not created"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi
log_success "✓ Failures log created: $FAILURES_LOG"

# Verify log contains structured data
log_info "Validating log contents..."

if ! grep -q "mock-failure - Installation Failed" "$FAILURES_LOG"; then
  log_error "✗ Log missing failure header"
  cat "$FAILURES_LOG"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi
log_success "✓ Failure header present"

if ! grep -q "Download URL: https://example.com/mock-failure.tar.gz" "$FAILURES_LOG"; then
  log_error "✗ Log missing download URL"
  cat "$FAILURES_LOG"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi
log_success "✓ Download URL captured"

if ! grep -q "Version: v1.0.0" "$FAILURES_LOG"; then
  log_error "✗ Log missing version"
  cat "$FAILURES_LOG"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi
log_success "✓ Version captured"

if ! grep -q "Reason: Download failed - simulated network error" "$FAILURES_LOG"; then
  log_error "✗ Log missing reason"
  cat "$FAILURES_LOG"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi
log_success "✓ Reason captured"

if ! grep -q "Manual Installation Steps:" "$FAILURES_LOG"; then
  log_error "✗ Log missing manual steps"
  cat "$FAILURES_LOG"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi
log_success "✓ Manual steps captured"

# ================================================================
# Test 3: Failure Summary Display
# ================================================================

print_section "Test 3: Failure summary display" "cyan"

log_info "Testing show_failures_summary()..."
echo ""

# Capture summary output
SUMMARY_OUTPUT=$(show_failures_summary 2>&1)

if ! echo "$SUMMARY_OUTPUT" | grep -q "Installation Summary"; then
  log_error "✗ Summary missing header"
  echo "$SUMMARY_OUTPUT"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi
log_success "✓ Summary header present"

if ! echo "$SUMMARY_OUTPUT" | grep -q "1 installation(s) failed"; then
  log_error "✗ Summary missing failure count"
  echo "$SUMMARY_OUTPUT"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi
log_success "✓ Failure count correct"

if ! echo "$SUMMARY_OUTPUT" | grep -q "mock-failure - Installation Failed"; then
  log_error "✗ Summary missing failure details"
  echo "$SUMMARY_OUTPUT"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi
log_success "✓ Failure details displayed"

# ================================================================
# Test 4: Multiple Failures
# ================================================================

print_section "Test 4: Multiple failures accumulate" "cyan"

# Run another failure
if run_installer "$MOCK_FAILURE" "mock-failure-2"; then
  log_error "✗ Second failure should return non-zero"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi

# Count failures
FAILURE_COUNT=$(grep -c "^---$" "$FAILURES_LOG" || echo 0)
if [[ "$FAILURE_COUNT" != "2" ]]; then
  log_error "✗ Expected 2 failures, got $FAILURE_COUNT"
  cat "$FAILURES_LOG"
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
  exit 1
fi
log_success "✓ Multiple failures accumulated correctly"

# ================================================================
# Cleanup and Success
# ================================================================

rm -rf "$TEMP_DIR" "$FAILURES_LOG"

echo ""
print_banner_success "All Integration Tests Passed!"
echo ""
log_success "run_installer wrapper working correctly"
log_success "Structured failure data captured correctly"
log_success "show_failures_summary displays correctly"
log_success "Multiple failures accumulate correctly"
echo ""
