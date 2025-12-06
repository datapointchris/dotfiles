#!/usr/bin/env bash
# ================================================================
# Test GitHub Release Installer Exit Codes
# ================================================================
# Creates a mock install_from_tarball that fails, then tests
# if installer scripts propagate the failure correctly
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

print_banner "Testing Installer Exit Code Propagation"

# Create a mock fzf installer that sources real libraries but uses mock install_from_tarball
MOCK_INSTALLER=$(mktemp)
cat > "$MOCK_INSTALLER" << 'ENDMOCK'
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

# Mock install_from_tarball that always fails
install_from_tarball() {
  log_error "Mock failure"
  output_failure_data "mock-tool" "https://example.com/mock.tar.gz" "v1.0" "Manual steps" "Download failed"
  return 1
}

# This is the pattern from fzf.sh (and all other GitHub release installers)
BINARY_NAME="mock-tool"
VERSION="v1.0"
DOWNLOAD_URL="https://example.com/mock.tar.gz"

print_banner "Installing mock-tool"

# Call install_from_tarball (will fail)
install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "mock-tool" "$VERSION"

# BUG: These lines execute even after failure!
print_banner_success "mock-tool installation complete"
exit_success
ENDMOCK

chmod +x "$MOCK_INSTALLER"

# Run the mock installer
log_info "Running mock installer (should fail but currently succeeds)..."
if bash "$MOCK_INSTALLER" > /tmp/mock-installer-output.txt 2>&1; then
  EXIT_CODE=0
else
  EXIT_CODE=$?
fi

rm -f "$MOCK_INSTALLER"

# Validate
echo ""
log_info "Current Behavior:"
log_info "  Exit code: $EXIT_CODE"
log_info "  Output:"
cat /tmp/mock-installer-output.txt
echo ""

if [[ $EXIT_CODE -eq 0 ]]; then
  log_error "✗ BUG CONFIRMED: Installer returned exit code 0 despite failure"

  if grep -q "installation complete" /tmp/mock-installer-output.txt; then
    log_error "✗ BUG CONFIRMED: Success message printed after failure"
  fi

  echo ""
  log_warning "The bug is: installers unconditionally call exit_success after install_from_tarball"
  log_warning "They don't check if install_from_tarball succeeded or failed"
  echo ""
  exit 1
else
  log_success "✓ PASS: Installer correctly propagated failure (exit code $EXIT_CODE)"
  exit 0
fi
