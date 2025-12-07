#!/usr/bin/env bash
# ================================================================
# Test run_installer wrapper with real duf installer
# ================================================================
# This tests that the new wrapper works with existing installers
# that don't yet output structured failure data
# ================================================================

set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
cd "$DOTFILES_DIR" || exit 1

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"
source "$DOTFILES_DIR/management/orchestration/run-installer.sh"

FAILURES_LOG="/tmp/test-install-$(date +%s).log"
export FAILURES_LOG

print_banner "Testing run_installer with duf.sh"

show_failures_summary() {
  if [[ ! -f "$FAILURES_LOG" ]] || [[ ! -s "$FAILURES_LOG" ]]; then
    return 0
  fi

  local failure_count
  failure_count=$(grep -c "^---$" "$FAILURES_LOG" || echo 0)

  if [[ $failure_count -eq 0 ]]; then
    return 0
  fi

  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "Installation Summary"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
  log_warning "$failure_count installation(s) failed"
  log_info "This is common in restricted network environments"
  echo ""
  cat "$FAILURES_LOG"
  echo "════════════════════════════════════════════════════════════════"
  echo "Full report saved to: $FAILURES_LOG"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
}

# Test with duf
echo ""
print_section "Running duf installer with new wrapper"
if run_installer management/common/install/github-releases/duf.sh "duf"; then
  log_success "Duf installation succeeded"
else
  log_info "Duf installation failed (expected in some environments)"
fi

# Show summary
echo ""
print_section "Displaying failure summary"
show_failures_summary

echo ""
print_banner_success "Test completed"
echo "Failures log: $FAILURES_LOG"

# Keep the log file for inspection
echo ""
log_info "To inspect the failures log:"
echo "  cat $FAILURES_LOG"
