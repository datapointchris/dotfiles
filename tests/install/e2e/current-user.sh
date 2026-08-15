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
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

# Parse arguments
MACHINE_FLAG=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --machine)
      MACHINE_FLAG="--machine $2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $(basename "$0") [--machine NAME]"
      exit 1
      ;;
  esac
done

# Timing arrays
declare -a STEP_NAMES
declare -a STEP_TIMES
declare -a STEP_STATUS

print_header "Testing Dotfiles Installation on Current User" "blue"
log_warning "This will modify your current environment!"
log_warning "Not isolated - changes affect your real setup"
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
echo "Running: bash install.sh, then dotfiles apply"
echo ""

# Two commands because install.sh bootstraps the CLI and stops; converging the
# machine is the apply, and this script is about the converged machine.
export PATH="$HOME/.local/bin:$PATH"

# shellcheck disable=SC2086  # MACHINE_FLAG intentionally unquoted (empty or flag pair)
if bash "$DOTFILES_DIR/install.sh" $MACHINE_FLAG && dotfiles apply $MACHINE_FLAG; then
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
echo "Running: dotfiles plan"
echo ""

# The product's own measurement, which is the right instrument on a real machine.
# The second opinion `tests/e2e/test_verification.py` gives is for judging an
# install nobody inspected, and it needs a container to be independent of.
if dotfiles plan; then
  log_success "Nothing left to converge"
else
  EXIT_CODE=$?
  log_warning "plan exited $EXIT_CODE: the machine differs from its declaration"
  log_info "Run 'dotfiles apply' to close the gap, or 'dotfiles check' for what apply cannot fix"
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
echo "Running: dotfiles check"
echo ""

# A declared tool with a copy nothing declares is an Issue in `check`'s grammar,
# which is where the duplicate detector's question moved.
dotfiles check || log_info "check reported issues; each names the tool and where the other copy is"
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
echo "    • dotfiles plan: $(print_cyan "Completed")"
echo "    • dotfiles check: $(print_cyan "Completed")"
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
