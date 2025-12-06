#!/usr/bin/env bash
# ================================================================
# Test: fzf Installer Failure Case
# ================================================================
# Tests that fzf installer fails gracefully when downloads are blocked
# Validates: exit code non-zero, structured failure data output
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

echo "=========================================="
echo "Test: fzf Installer Failure (Blocked Network)"
echo "=========================================="
echo ""

# Create temporary test environment
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# First, remove fzf if it exists so we trigger actual download
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
trap cleanup_fzf EXIT

log_warning "Creating mock curl that always fails..."
echo ""

# Create a mock curl that always fails for github downloads
MOCK_BIN="$TEST_DIR/bin"
mkdir -p "$MOCK_BIN"

cat > "$MOCK_BIN/curl" << 'MOCK_CURL_EOF'
#!/usr/bin/env bash
# Mock curl that fails for GitHub downloads
if [[ "$*" == *"github.com"* ]]; then
  echo "curl: (6) Could not resolve host: github.com" >&2
  exit 6
else
  # Pass through to real curl for non-GitHub URLs
  /usr/bin/curl "$@"
fi
MOCK_CURL_EOF

chmod +x "$MOCK_BIN/curl"

# Prepend mock bin to PATH so our fake curl is used
export PATH="$MOCK_BIN:$PATH"

log_info "Mock curl created at: $MOCK_BIN/curl"

log_info "Running fzf installer with blocked network..."
echo ""
echo "--- Installer Output ---"

# Capture stderr to check for structured failure data
STDERR_FILE="$TEST_DIR/stderr.txt"

if bash "$DOTFILES_DIR/management/common/install/github-releases/fzf.sh" 2>"$STDERR_FILE"; then
  EXIT_CODE=0
else
  EXIT_CODE=$?
fi

echo "--- End Output ---"
echo ""

# Check exit code
if [[ $EXIT_CODE -ne 0 ]]; then
  log_success "✓ Installer exited with non-zero code: $EXIT_CODE"
else
  log_error "✗ FAIL: Installer exited with code 0 despite blocked network"
  exit 1
fi

# Check for structured failure data in stderr
log_info "Checking for structured failure data in stderr..."
if grep -q "FAILURE_TOOL='fzf'" "$STDERR_FILE"; then
  log_success "✓ FAILURE_TOOL found in stderr"
else
  log_error "✗ FAILURE_TOOL not found in stderr"
  echo "Stderr contents:"
  cat "$STDERR_FILE"
  exit 1
fi

if grep -q "FAILURE_URL=" "$STDERR_FILE"; then
  log_success "✓ FAILURE_URL found in stderr"
else
  log_error "✗ FAILURE_URL not found in stderr"
  exit 1
fi

if grep -q "FAILURE_REASON=" "$STDERR_FILE"; then
  log_success "✓ FAILURE_REASON found in stderr"
else
  log_error "✗ FAILURE_REASON not found in stderr"
  exit 1
fi

if grep -q "FAILURE_MANUAL" "$STDERR_FILE"; then
  log_success "✓ FAILURE_MANUAL found in stderr"
else
  log_error "✗ FAILURE_MANUAL not found in stderr"
  exit 1
fi

echo ""
log_success "=========================================="
log_success "fzf installer failure test PASSED"
log_success "  - Exit code: non-zero ($EXIT_CODE)"
log_success "  - Structured failure data output to stderr"
log_success "  - All required fields present"
log_success "=========================================="
