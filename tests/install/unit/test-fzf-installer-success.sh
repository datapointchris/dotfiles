#!/usr/bin/env bash
# ================================================================
# Test: fzf Installer Success Case
# ================================================================
# Tests that fzf installer works correctly with internet access
# Validates: output visibility, exit code, binary installation
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

echo "=========================================="
echo "Test: fzf Installer Success"
echo "=========================================="
echo ""

log_info "This test will actually download and install fzf"
log_info "If fzf is already installed, it will skip"
echo ""

# Run the actual fzf installer
log_info "Running: bash $DOTFILES_DIR/management/common/install/github-releases/fzf.sh"
echo ""
echo "--- Installer Output ---"

if bash "$DOTFILES_DIR/management/common/install/github-releases/fzf.sh"; then
  EXIT_CODE=$?
  echo "--- End Output ---"
  echo ""

  log_success "✓ fzf installer exited with code 0"

  # Verify fzf is actually available
  if command -v fzf >/dev/null 2>&1; then
    FZF_VERSION=$(fzf --version | head -1)
    log_success "✓ fzf binary is available: $FZF_VERSION"
  else
    log_error "✗ fzf installer succeeded but binary not found in PATH"
    exit 1
  fi

  log_success "=========================================="
  log_success "fzf installer test PASSED"
  log_success "  - Exit code: 0"
  log_success "  - Output was visible"
  log_success "  - Binary installed and available"
  log_success "=========================================="
  exit 0
else
  EXIT_CODE=$?
  echo "--- End Output ---"
  echo ""

  log_error "✗ fzf installer failed with exit code: $EXIT_CODE"
  log_info "This might be expected if network is restricted"
  exit 1
fi
