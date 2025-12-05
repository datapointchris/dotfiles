#!/usr/bin/env bash
# ================================================================
# Test Dotfiles Installation on Current User
# ================================================================
# Runs full installation and verification on current user
# Useful for debugging on local machine without isolation
#
# WARNING: This will modify your current user's environment!
# Use with caution - primarily for development/debugging
# ================================================================

set -euo pipefail

# Source structured logging library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Timing arrays
declare -a STEP_NAMES
declare -a STEP_TIMES
declare -a STEP_STATUS

print_header "Testing Dotfiles Installation on Current User" "blue"
log_warning "⚠️  This will modify your current environment!"
log_warning "⚠️  Not isolated - changes affect your real setup"
echo ""
log_info "User: $(whoami)"
log_info "Home: $HOME"
log_info "Dotfiles: $DOTFILES_DIR"
echo ""

# Track overall start time
OVERALL_START=$(date +%s)

# ================================================================
# STEP 1: Run Installation
# ================================================================
STEP_START=$(date +%s)
print_header "STEP 1/4: Running Installation" "cyan"
echo "Running: bash install.sh"
echo ""

if bash "$DOTFILES_DIR/install.sh"; then
  log_success "Installation completed"
else
  EXIT_CODE=$?
  log_error "Installation failed with exit code: $EXIT_CODE"
  log_info "Check output above for errors"
fi
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Installation")
STEP_TIMES+=("$STEP_ELAPSED")
echo ""

# ================================================================
# STEP 2: Run Verification
# ================================================================
STEP_START=$(date +%s)
print_header "STEP 2/4: Running Verification" "cyan"
echo "Running: bash management/tests/verify-installed-packages.sh"
echo ""

if bash "$DOTFILES_DIR/management/tests/verify-installed-packages.sh"; then
  log_success "Verification passed"
else
  EXIT_CODE=$?
  log_warning "Verification failed with exit code: $EXIT_CODE"
  log_info "Some tools may not be installed or configured correctly"
fi
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Verification")
STEP_TIMES+=("$STEP_ELAPSED")
echo ""

# ================================================================
# STEP 3: Check for Alternate Installations
# ================================================================
STEP_START=$(date +%s)
print_header "STEP 3/4: Checking for Alternate Installations" "cyan"
echo "Running: bash management/tests/detect-installed-duplicates.sh"
echo ""

bash "$DOTFILES_DIR/management/tests/detect-installed-duplicates.sh"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Detect alternates")
STEP_TIMES+=("$STEP_ELAPSED")
echo ""

# ================================================================
# STEP 4: Test all apps and configs
# ================================================================
STEP_START=$(date +%s)
print_header "STEP 4/4: Testing All Apps and Configs" "cyan"
echo "Running comprehensive dotfiles verification test..."
echo ""

if bash "$DOTFILES_DIR/tests/apps/all-apps.sh"; then
  STEP_STATUS+=("PASS")
  log_success "Test-all-apps passed"
else
  STEP_STATUS+=("FAIL")
  log_warning "Test-all-apps had failures"
fi
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Test all apps")
STEP_TIMES+=("$STEP_ELAPSED")
echo ""

# Calculate overall time
OVERALL_END=$(date +%s)
OVERALL_ELAPSED=$((OVERALL_END - OVERALL_START))

# ================================================================
# Summary
# ================================================================
print_header "Test Complete" "green"
echo ""

# Test Results Summary
print_section "Test Results" "cyan"
echo ""
echo "  Installation Verification:"
echo "    • verify-installed-packages.sh: $(print_cyan "Completed")"
echo "    • detect-installed-duplicates.sh: $(print_cyan "Completed")"
if [[ "${STEP_STATUS[0]:-}" == "PASS" ]]; then
  echo "    • test-all-apps.sh: $(print_green "✓ PASS") (34 checks)"
else
  echo "    • test-all-apps.sh: $(print_red "✗ FAIL")"
fi
echo ""

print_section "Timing Summary" "cyan"
echo ""
for i in "${!STEP_NAMES[@]}"; do
  formatted_time=$(format_time "${STEP_TIMES[$i]}")
  printf "  %s Step %d: %-20s %s\n" "$(print_green "✓")" $((i + 1)) "${STEP_NAMES[$i]}" "$formatted_time"
done
echo "  ─────────────────────────────────────────────"
formatted_total=$(format_time "$OVERALL_ELAPSED")
printf "  %-27s %s\n" "Total time:" "$(print_cyan "$formatted_total")"
echo ""

print_section "Test Information" "cyan"
echo ""
echo "  User: $(whoami)"
echo "  Home: $HOME"
echo "  Dotfiles: $DOTFILES_DIR"
echo ""

print_section "Next Steps" "cyan"
echo "  • Review output above for any errors or warnings"
echo "  • Check verification results for missing tools"
echo "  • Review alternate installations if any were found"
echo "  • Source your shell config: exec zsh (or exec bash)"
echo ""
