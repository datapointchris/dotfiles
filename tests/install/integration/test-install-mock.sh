#!/usr/bin/env bash
# ================================================================
# Mock Install Script - Fast Integration Test
# ================================================================
# Tests the full run_installer + failures log flow with mock installers
# No real downloads - completes in seconds
# ================================================================

set -uo pipefail

# Initialize paths (same as real install.sh)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
export DOTFILES_DIR

# Source libraries
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

print_banner "Mock Installation Test"

# Initialize failures log (same as real install.sh)
FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"
export FAILURES_LOG
rm -f "$FAILURES_LOG"

log_info "DOTFILES_DIR=$DOTFILES_DIR"
log_info "FAILURES_LOG=$FAILURES_LOG"
echo ""

# ================================================================
# Copy run_installer from install.sh
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
# Create Mock Installers
# ================================================================

MOCK_DIR="/tmp/mock-installers-$$"
mkdir -p "$MOCK_DIR"

# Mock success installer
cat > "$MOCK_DIR/mock-success.sh" << 'ENDMOCK1'
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

log_info "Installing mock-success tool..."
sleep 0.1
log_success "mock-success installed"
exit 0
ENDMOCK1
chmod +x "$MOCK_DIR/mock-success.sh"

# Mock failure installer with structured output
cat > "$MOCK_DIR/mock-failure.sh" << 'ENDMOCK2'
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

TOOL_NAME="mock-failure"
DOWNLOAD_URL="https://github.com/mock/mock-failure/releases/download/v1.0.0/mock-failure.tar.gz"
VERSION="v1.0.0"

MANUAL_STEPS="1. Download from: $DOWNLOAD_URL
2. Extract: tar -xzf mock-failure.tar.gz
3. Install: mv mock-failure ~/.local/bin/
4. Verify: mock-failure --version"

log_error "Failed to download from $DOWNLOAD_URL"
output_failure_data "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "$MANUAL_STEPS" "Download failed - mock network error"
exit 1
ENDMOCK2
chmod +x "$MOCK_DIR/mock-failure.sh"

# ================================================================
# Run Mock Installation
# ================================================================

print_header "Mock Phase 1 - GitHub Releases" "cyan"
run_installer "$MOCK_DIR/mock-success.sh" "mock-fzf"
run_installer "$MOCK_DIR/mock-failure.sh" "mock-neovim"
run_installer "$MOCK_DIR/mock-success.sh" "mock-lazygit"
run_installer "$MOCK_DIR/mock-failure.sh" "mock-yazi"
echo ""

print_header "Mock Phase 2 - Cargo Tools" "cyan"
run_installer "$MOCK_DIR/mock-success.sh" "mock-cargo"
run_installer "$MOCK_DIR/mock-success.sh" "mock-bat"
echo ""

# Show summary
show_failures_summary

# Cleanup
rm -rf "$MOCK_DIR"

# Validation
echo ""
print_section "Test Validation" "cyan"

# Count actual failures
FAILURE_COUNT=$(grep -c "^---$" "$FAILURES_LOG" || echo 0)
EXPECTED_FAILURES=2

if [[ "$FAILURE_COUNT" == "$EXPECTED_FAILURES" ]]; then
  log_success "✓ Expected $EXPECTED_FAILURES failures, got $FAILURE_COUNT"
else
  log_error "✗ Expected $EXPECTED_FAILURES failures, got $FAILURE_COUNT"
  exit 1
fi

# Verify structured data captured
# Note: The mock installers use tool name "mock-failure" internally
if grep -q "mock-failure - Installation Failed" "$FAILURES_LOG"; then
  log_success "✓ mock-failure entries captured"
else
  log_error "✗ mock-failure entries not found"
  exit 1
fi

if grep -q "Download URL: https://github.com/mock/mock-failure" "$FAILURES_LOG"; then
  log_success "✓ Download URL captured"
else
  log_error "✗ Download URL not captured"
  exit 1
fi

echo ""
print_banner_success "Mock Installation Test Passed!"
log_info "The refactored install system is working correctly"
rm -f "$FAILURES_LOG"
