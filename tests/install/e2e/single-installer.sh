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

source platforms/common/.local/shell/logging.sh
source platforms/common/.local/shell/formatting.sh
source management/common/lib/install-helpers.sh

# Initialize failures log
FAILURES_LOG="/tmp/test-install-$(date +%s).log"
export FAILURES_LOG

print_banner "Testing run_installer with duf.sh"

# Define run_installer function (from install.sh)
run_installer() {
  local script="$1"
  local tool_name="$2"

  local output
  local exit_code

  output=$(bash "$script" 2>&1)
  exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    log_success "$tool_name installed"
    return 0
  else
    log_warning "$tool_name installation failed (see $FAILURES_LOG)"

    local failure_tool failure_url failure_version failure_reason failure_manual
    failure_tool=$(echo "$output" | grep "^FAILURE_TOOL=" | cut -d"'" -f2 || echo "$tool_name")
    failure_url=$(echo "$output" | grep "^FAILURE_URL=" | cut -d"'" -f2 || echo "")
    failure_version=$(echo "$output" | grep "^FAILURE_VERSION=" | cut -d"'" -f2 || echo "")
    failure_reason=$(echo "$output" | grep "^FAILURE_REASON=" | cut -d"'" -f2 || echo "")

    if echo "$output" | grep -q "^FAILURE_MANUAL<<"; then
      failure_manual=$(echo "$output" | sed -n '/^FAILURE_MANUAL<</,/^END_MANUAL/p' | sed '1d;$d')
    fi

    cat >> "$FAILURES_LOG" << EOF
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

EOF
    return 1
  fi
}

# Define show_failures_summary (from install.sh)
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
