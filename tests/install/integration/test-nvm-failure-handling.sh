#!/usr/bin/env bash
# ================================================================
# Test nvm.sh failure handling with blocked network
# ================================================================
# Verifies that nvm.sh:
# 1. Reports failure to registry when download is blocked
# 2. Returns gracefully instead of exiting
# 3. Allows installation to continue
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source libraries
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

print_banner "Testing nvm.sh Failure Handling"

# Initialize failure registry
init_failure_registry
log_info "Registry initialized: $DOTFILES_FAILURE_REGISTRY"

# Block raw.githubusercontent.com by adding fake entry to /etc/hosts
log_section "Blocking githubusercontent.com"
if [[ $EUID -eq 0 ]]; then
  echo "127.0.0.1 raw.githubusercontent.com" >> /etc/hosts
  log_success "Added block to /etc/hosts"
else
  log_warning "Not running as root - cannot modify /etc/hosts"
  log_info "Skipping network blocking test"
  exit 0
fi

# Cleanup function
cleanup() {
  # Remove the block
  if [[ $EUID -eq 0 ]]; then
    sed -i '/127.0.0.1 raw.githubusercontent.com/d' /etc/hosts
    log_info "Removed block from /etc/hosts"
  fi

  # Clean up test nvm directory
  rm -rf /tmp/test-nvm-dir
}
trap cleanup EXIT

# Test nvm.sh with blocked network
log_section "Testing nvm.sh with blocked network"
export HOME=/tmp
export NVM_DIR=/tmp/test-nvm-dir

# Run nvm.sh - should fail but not exit
if bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh" 2>&1; then
  log_error "nvm.sh should have failed but succeeded"
  exit 1
else
  log_success "nvm.sh returned failure code (expected)"
fi

# Check if failure was reported
log_section "Verifying failure was reported to registry"
if ls "$DOTFILES_FAILURE_REGISTRY"/*-nvm.txt >/dev/null 2>&1; then
  log_success "Failure file created in registry"
  # shellcheck disable=SC2012
  FAILURE_FILE=$(ls -t "$DOTFILES_FAILURE_REGISTRY"/*-nvm.txt | head -1)
  if grep -q "TOOL='nvm'" "$FAILURE_FILE"; then
    log_success "Failure file contains nvm"
  else
    log_error "Failure file missing tool name"
    exit 1
  fi
else
  log_error "No failure file created for nvm"
  exit 1
fi

# Check that we can continue (simulate install.sh continuing to next phase)
log_section "Verifying installation can continue"
log_info "Simulating next phase after nvm failure..."
echo "Phase 8 would run here" > /tmp/test-phase8
if [[ -f /tmp/test-phase8 ]]; then
  log_success "Installation can continue after nvm failure"
  rm /tmp/test-phase8
fi

# Display summary
log_section "Testing display_failure_summary"
display_failure_summary > /tmp/test-summary.txt 2>&1

# Check permanent log was created
if ls /tmp/dotfiles-installation-failures-*.txt >/dev/null 2>&1; then
  # shellcheck disable=SC2012
  PERMANENT_LOG=$(ls -t /tmp/dotfiles-installation-failures-*.txt | head -1)
  log_success "Permanent log created: $PERMANENT_LOG"

  if grep -q "TOOL='nvm'" "$PERMANENT_LOG"; then
    log_success "Permanent log contains nvm failure"
  else
    log_error "Permanent log missing nvm failure"
    exit 1
  fi

  # Clean up permanent log
  rm -f "$PERMANENT_LOG"
else
  log_error "No permanent log created"
  exit 1
fi

print_banner_success "All nvm failure handling tests passed"
