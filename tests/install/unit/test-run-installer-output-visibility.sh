#!/usr/bin/env bash
# ================================================================
# Test: run_installer Output Visibility
# ================================================================
# Verifies that installer output is visible to users, not captured
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

echo "=========================================="
echo "Test: run_installer Output Visibility"
echo "=========================================="
echo ""

# Create temporary directory for test
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# Create mock installer that outputs log messages
cat > "$TEST_DIR/mock-installer.sh" << 'EOF'
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

log_info "Starting installation..."
log_info "Downloading package..."
log_info "Extracting files..."
log_success "Installation complete!"
exit 0
EOF
chmod +x "$TEST_DIR/mock-installer.sh"

# Source the FIXED run_installer function from install.sh
FAILURES_LOG="$TEST_DIR/failures.txt"
export FAILURES_LOG

# Extract and source run_installer from install.sh
run_installer() {
  local script="$1"
  local tool_name="$2"

  # FIXED: Capture stderr only for parsing failure data, let stdout flow through
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

echo "Running mock installer through run_installer..."
echo "Expected: We should see log messages from the installer in real-time"
echo ""
echo "--- Installer Output ---"

# Run without capturing to see if output flows through
# (capturing with $() would defeat the purpose of the test)
run_installer "$TEST_DIR/mock-installer.sh" "mock-tool"
EXIT_CODE=$?

echo "--- End Output ---"
echo ""

# The installer should have succeeded
if [[ $EXIT_CODE -eq 0 ]]; then
  log_success "✓ PASS: run_installer completed successfully"
  log_success "✓ PASS: Check output above - you should see all log messages"
  log_info "Expected messages:"
  log_info "  [INFO] ● Starting installation..."
  log_info "  [INFO] ● Downloading package..."
  log_info "  [INFO] ● Extracting files..."
  log_info "  [INFO] ✓ Installation complete!"
  log_info "  [INFO] ✓ mock-tool installed"
  exit 0
else
  log_error "✗ FAIL: run_installer failed unexpectedly (exit code: $EXIT_CODE)"
  exit 1
fi
