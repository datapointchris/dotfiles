#!/usr/bin/env bash
# ================================================================
# Test GitHub Release Installer Failure Handling
# ================================================================
# Validates that installers exit with non-zero when downloads fail
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

print_banner() {
  echo "=========================================="
  echo "$1"
  echo "=========================================="
  echo ""
}

print_banner "Testing GitHub Release Installer Failure Handling"

# Test: fzf installer should fail with blocked downloads
log_info "Test: fzf installer with blocked downloads"

# Block GitHub release downloads locally
TEMP_HOSTS=$(mktemp)
cat > "$TEMP_HOSTS" << 'EOF'
127.0.0.1 release-assets.githubusercontent.com
127.0.0.1 objects.githubusercontent.com
127.0.0.1 github-releases.githubusercontent.com
EOF

log_info "Blocking GitHub release CDN (requires sudo)..."
sudo cat /etc/hosts | sudo tee /tmp/hosts-backup >/dev/null
cat /tmp/hosts-backup "$TEMP_HOSTS" | sudo tee /etc/hosts >/dev/null

# Run fzf installer - should FAIL
log_info "Running fzf installer (should fail)..."
if bash "$DOTFILES_DIR/management/common/install/github-releases/fzf.sh" > /tmp/fzf-test-output.txt 2>&1; then
  EXIT_CODE=0
else
  EXIT_CODE=$?
fi

# Restore /etc/hosts
log_info "Restoring /etc/hosts..."
sudo mv /tmp/hosts-backup /etc/hosts
rm -f "$TEMP_HOSTS"

# Validate
echo ""
log_info "Validation:"
log_info "  Exit code: $EXIT_CODE"

if [[ $EXIT_CODE -eq 0 ]]; then
  log_error "✗ FAIL: Installer returned exit code 0 (should be non-zero)"
  log_info "Output:"
  cat /tmp/fzf-test-output.txt
  exit 1
fi

if ! grep -q "FAILURE_TOOL='fzf'" /tmp/fzf-test-output.txt; then
  log_error "✗ FAIL: No structured failure data found"
  cat /tmp/fzf-test-output.txt
  exit 1
fi

if grep -q "installation complete" /tmp/fzf-test-output.txt; then
  log_error "✗ FAIL: Success message printed after failure"
  cat /tmp/fzf-test-output.txt
  exit 1
fi

log_success "✓ PASS: Installer correctly failed with exit code $EXIT_CODE"
log_success "✓ PASS: Structured failure data present"
log_success "✓ PASS: No success message after failure"

echo ""
print_banner "Test Passed!"
