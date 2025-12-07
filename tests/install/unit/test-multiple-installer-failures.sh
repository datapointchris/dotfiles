#!/usr/bin/env bash
# ================================================================
# Test: Multiple Installers with Failure Accumulation
# ================================================================
# Tests that multiple installer failures accumulate in single log file
# Simulates what happens during Phase 5 of installation
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

echo "=========================================="
echo "Test: Multiple Installer Failures"
echo "=========================================="
echo ""

# Create temporary test environment
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# Set up failure log
FAILURES_LOG="$TEST_DIR/failures.txt"
export FAILURES_LOG

source "$DOTFILES_DIR/management/orchestration/run-installer.sh"

# Backup binaries we're going to test
declare -A BACKUPS
for tool in fzf lazygit neovim; do
  TOOL_PATH="$HOME/.local/bin/$tool"
  if [[ -f "$TOOL_PATH" ]]; then
    BACKUP_PATH="$TEST_DIR/${tool}.backup"
    BACKUPS[$tool]="$BACKUP_PATH"
    mv "$TOOL_PATH" "$BACKUP_PATH"
    log_info "Backed up $tool"
  fi
done

# Restore on exit
cleanup_tools() {
  for tool in "${!BACKUPS[@]}"; do
    if [[ -f "${BACKUPS[$tool]}" ]]; then
      mv "${BACKUPS[$tool]}" "$HOME/.local/bin/$tool"
      log_info "Restored $tool"
    fi
  done
}
trap 'cleanup_tools; rm -rf "$TEST_DIR"' EXIT

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

log_info "Running 3 installers that will all fail..."
echo ""

# Run multiple installers (all will fail)
run_installer "$DOTFILES_DIR/management/common/install/github-releases/fzf.sh" "fzf" || true
echo ""

run_installer "$DOTFILES_DIR/management/common/install/github-releases/lazygit.sh" "lazygit" || true
echo ""

run_installer "$DOTFILES_DIR/management/common/install/github-releases/neovim.sh" "neovim" || true
echo ""

# Validate single log file with multiple failures
if [[ ! -f "$FAILURES_LOG" ]]; then
  log_error "✗ FAIL: No failure log created"
  exit 1
fi

log_success "✓ Single failure log created"

# Count failures (each has separator line)
FAILURE_COUNT=$(grep -c "^---$" "$FAILURES_LOG" || echo 0)

if [[ $FAILURE_COUNT -ge 2 ]]; then
  log_success "✓ Multiple failures logged (found $FAILURE_COUNT failures)"
else
  log_error "✗ FAIL: Expected at least 2 failures, found $FAILURE_COUNT"
  cat "$FAILURES_LOG"
  exit 1
fi

# Verify fzf and lazygit are in the log (neovim might skip if already installed)
for tool in fzf lazygit; do
  if grep -q "$tool - Installation Failed" "$FAILURES_LOG"; then
    log_success "✓ $tool failure logged"
  else
    log_error "✗ FAIL: $tool not in failure log"
    exit 1
  fi
done

# Check if neovim failed or was skipped
if grep -q "neovim - Installation Failed" "$FAILURES_LOG"; then
  log_success "✓ neovim failure logged"
else
  log_info "  (neovim was skipped - already installed with acceptable version)"
fi

echo ""
log_info "Failure log summary:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
grep "Installation Failed" "$FAILURES_LOG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

log_success "=========================================="
log_success "Multiple installer failures test PASSED"
log_success "  - $FAILURE_COUNT installers failed as expected"
log_success "  - Single log file created"
log_success "  - All failures accumulated correctly"
log_success "=========================================="
