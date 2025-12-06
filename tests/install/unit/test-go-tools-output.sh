#!/usr/bin/env bash
# ================================================================
# Test: Go Tools Installer Output Visibility
# ================================================================
# Validates that go install output is visible to users
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

echo "=========================================="
echo "Test: Go Tools Output Visibility"
echo "=========================================="
echo ""

# Set up failure log
FAILURES_LOG="/tmp/test-go-failures.txt"
export FAILURES_LOG
rm -f "$FAILURES_LOG"

# Source install.sh to get run_installer function
source "$DOTFILES_DIR/install.sh"

log_info "Running go-tools installer..."
log_info "Watch for 'go install' output from individual tools..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run the actual go-tools installer
# This will install tools like lazydocker, actionlint, etc.
run_installer "$DOTFILES_DIR/management/common/install/language-tools/go-tools.sh" "go-tools" || true

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

log_info "Check output above - you should see verbose 'go install' messages"
log_info "for each tool being installed (lazydocker, actionlint, etc.)"

rm -f "$FAILURES_LOG"
