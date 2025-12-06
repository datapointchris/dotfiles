#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="/root/dotfiles"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

# Set up failure log
FAILURES_LOG="/tmp/dotfiles-install-failures-test.txt"
export FAILURES_LOG

# Define run_installer function (from install.sh)
run_installer() {
  local script="$1"
  local tool_name="$2"

  # Capture stderr only for parsing failure data, let stdout flow through
  local stderr_file
  stderr_file=$(mktemp)

  bash "$script" 2>"$stderr_file"
  exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    rm -f "$stderr_file"
    log_success "$tool_name installed"
    return 0
  else
    log_warning "$tool_name installation failed (see $FAILURES_LOG)"

    # Parse structured failure data from stderr
    local output
    output=$(cat "$stderr_file")
    rm -f "$stderr_file"

    local failure_tool failure_url failure_version failure_reason failure_manual
    failure_tool=$(echo "$output" | grep "^FAILURE_TOOL=" | cut -d"'" -f2 || echo "$tool_name")
    failure_url=$(echo "$output" | grep "^FAILURE_URL=" | cut -d"'" -f2 || echo "")
    failure_version=$(echo "$output" | grep "^FAILURE_VERSION=" | cut -d"'" -f2 || echo "")
    failure_reason=$(echo "$output" | grep "^FAILURE_REASON=" | cut -d"'" -f2 || echo "")

    # Extract multiline manual steps
    if echo "$output" | grep -q "^FAILURE_MANUAL<<"; then
      failure_manual=$(echo "$output" | sed -n '/^FAILURE_MANUAL<</,/^END_MANUAL/p' | sed '1d;$d')
    fi

    # Append to failures log
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

log_info "Testing run_installer wrapper with fzf..."
echo ""

# Run fzf installer through run_installer wrapper
run_installer "$DOTFILES_DIR/management/common/install/github-releases/fzf.sh" "fzf" || true

echo ""
log_info "Checking results..."

# Check failure log was created
if [[ -f "$FAILURES_LOG" ]]; then
  log_success "✓ Failure log created: $FAILURES_LOG"
else
  log_error "✗ Failure log not created"
  exit 1
fi

# Validate log contents
if grep -q "fzf - Installation Failed" "$FAILURES_LOG"; then
  log_success "✓ fzf failure logged"
else
  log_error "✗ fzf not in failure log"
  exit 1
fi

if grep -q "Download URL:" "$FAILURES_LOG"; then
  log_success "✓ Download URL in log"
else
  log_error "✗ Download URL missing"
  exit 1
fi

echo ""
log_info "Failure log contents:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat "$FAILURES_LOG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_success "run_installer test passed!"
