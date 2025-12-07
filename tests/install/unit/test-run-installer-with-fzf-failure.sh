#!/usr/bin/env bash
# ================================================================
# Test: run_installer Wrapper with fzf Failure
# ================================================================
# Tests the complete flow: run_installer + fzf installer + failure logging
# Validates: wrapper captures failure, creates log, shows output
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

echo "=========================================="
echo "Test: run_installer + fzf Failure"
echo "=========================================="
echo ""

# Create temporary test environment
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# Set up failure log
FAILURES_LOG="$TEST_DIR/failures.txt"
export FAILURES_LOG

source "$DOTFILES_DIR/management/orchestration/run-installer.sh"

# Remove fzf if it exists
FZF_PATH="$HOME/.local/bin/fzf"
FZF_BACKUP=""
if [[ -f "$FZF_PATH" ]]; then
  log_info "Temporarily removing existing fzf to force download"
  FZF_BACKUP="$TEST_DIR/fzf.backup"
  mv "$FZF_PATH" "$FZF_BACKUP"
fi

# Restore fzf on exit
cleanup_fzf() {
  if [[ -n "$FZF_BACKUP" ]] && [[ -f "$FZF_BACKUP" ]]; then
    mv "$FZF_BACKUP" "$FZF_PATH"
    log_info "Restored fzf binary"
  fi
}
trap 'cleanup_fzf; rm -rf "$TEST_DIR"' EXIT

# Create mock curl
MOCK_BIN="$TEST_DIR/bin"
mkdir -p "$MOCK_BIN"

cat > "$MOCK_BIN/curl" << 'MOCK_CURL_EOF'
#!/usr/bin/env bash
if [[ "$*" == *"github.com"* ]]; then
  echo "curl: (6) Could not resolve host: github.com" >&2
  exit 6
else
  /usr/bin/curl "$@"
fi
MOCK_CURL_EOF

chmod +x "$MOCK_BIN/curl"
export PATH="$MOCK_BIN:$PATH"

log_info "Running: run_installer fzf.sh fzf"
log_info "Expected: Installer output visible + failure log created"
echo ""
echo "--- run_installer Output ---"

if run_installer "$DOTFILES_DIR/management/common/install/github-releases/fzf.sh" "fzf"; then
  echo "--- End Output ---"
  log_error "✗ FAIL: run_installer returned 0 despite failure"
  exit 1
else
  echo "--- End Output ---"
  echo ""
  log_success "✓ run_installer returned non-zero (expected for failure)"
fi

# Validate failure log was created
if [[ ! -f "$FAILURES_LOG" ]]; then
  log_error "✗ FAIL: Failures log not created at $FAILURES_LOG"
  exit 1
fi

log_success "✓ Failures log created"

# Validate log contents
if ! grep -q "fzf - Installation Failed" "$FAILURES_LOG"; then
  log_error "✗ FAIL: fzf failure not in log"
  cat "$FAILURES_LOG"
  exit 1
fi

log_success "✓ fzf failure logged"

if ! grep -q "Download URL:" "$FAILURES_LOG"; then
  log_error "✗ FAIL: Download URL not in log"
  exit 1
fi

log_success "✓ Download URL in log"

if ! grep -q "Reason:" "$FAILURES_LOG"; then
  log_error "✗ FAIL: Reason not in log"
  exit 1
fi

log_success "✓ Reason in log"

if ! grep -q "Manual Installation Steps:" "$FAILURES_LOG"; then
  log_error "✗ FAIL: Manual steps not in log"
  exit 1
fi

log_success "✓ Manual steps in log"

echo ""
log_info "Failure log contents:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat "$FAILURES_LOG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

log_success "=========================================="
log_success "run_installer + fzf test PASSED"
log_success "  - Installer output was visible"
log_success "  - run_installer returned non-zero"
log_success "  - Failure log created and populated"
log_success "  - All structured fields captured"
log_success "=========================================="
