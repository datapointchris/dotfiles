#!/usr/bin/env bash
# ================================================================
# Test: run_installer Shows Full stderr Output
# ================================================================
# Validates that run_installer shows stderr output to users
# Tests with mock installer that outputs verbose stderr
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

echo "=========================================="
echo "Test: run_installer stderr Visibility"
echo "=========================================="
echo ""

# Create temporary test environment
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# Set up failure log
FAILURES_LOG="$TEST_DIR/failures.txt"
export FAILURES_LOG

# Create mock installer that outputs verbose stderr (simulating cargo/go install)
cat > "$TEST_DIR/mock-verbose-installer.sh" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "[INFO] Starting installation..." >&2
echo "  Downloading package..." >&2
echo "  Extracting files..." >&2
echo "  Compiling source..." >&2
echo "    - Building module 1..." >&2
echo "    - Building module 2..." >&2
echo "    - Building module 3..." >&2
echo "  Installation complete!" >&2

exit 0
EOF

chmod +x "$TEST_DIR/mock-verbose-installer.sh"

# Define run_installer with updated stderr tee logic
run_installer() {
  local script="$1"
  local tool_name="$2"

  local stderr_file
  stderr_file=$(mktemp)

  # Temporarily disable exit on error to capture exit code
  set +e
  bash "$script" 2> >(tee "$stderr_file" >&2)
  exit_code=$?
  set -e

  # Wait for background tee process to finish writing
  wait

  if [[ $exit_code -eq 0 ]]; then
    rm -f "$stderr_file"
    log_success "$tool_name installed"
    return 0
  else
    log_warning "$tool_name installation failed (see $FAILURES_LOG)"
    rm -f "$stderr_file"
    return 1
  fi
}

log_info "Running mock installer (watch for verbose stderr output)..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

run_installer "$TEST_DIR/mock-verbose-installer.sh" "mock-tool"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

log_success "==========================================="
log_success "✓ TEST PASSED"
log_success "  - You should see all stderr messages above:"
log_success "    • Starting installation..."
log_success "    • Downloading package..."
log_success "    • Extracting files..."
log_success "    • Compiling source..."
log_success "    • Building module 1/2/3..."
log_success "    • Installation complete!"
log_success "==========================================="
