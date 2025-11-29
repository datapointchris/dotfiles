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

# Source formatting library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

print_header "Testing Dotfiles Installation on Current User" "blue"
print_warning "⚠️  This will modify your current environment!"
print_warning "⚠️  Not isolated - changes affect your real setup"
echo ""
print_info "User: $(whoami)"
print_info "Home: $HOME"
print_info "Dotfiles: $DOTFILES_DIR"
echo ""

# ================================================================
# STEP 1: Run Installation
# ================================================================
print_header "STEP 1/3: Running Installation" "cyan"
echo "Running: bash install.sh"
echo ""

if bash "$DOTFILES_DIR/install.sh"; then
  print_success "Installation completed"
else
  EXIT_CODE=$?
  print_error "Installation failed with exit code: $EXIT_CODE"
  print_info "Check output above for errors"
fi
echo ""

# ================================================================
# STEP 2: Run Verification
# ================================================================
print_header "STEP 2/3: Running Verification" "cyan"
echo "Running: bash management/lib/verify-installed-packages.sh"
echo ""

if bash "$DOTFILES_DIR/management/lib/verify-installed-packages.sh"; then
  print_success "Verification passed"
else
  EXIT_CODE=$?
  print_warning "Verification failed with exit code: $EXIT_CODE"
  print_info "Some tools may not be installed or configured correctly"
fi
echo ""

# ================================================================
# STEP 3: Check for Alternate Installations
# ================================================================
print_header "STEP 3/3: Checking for Alternate Installations" "cyan"
echo "Running: bash management/lib/detect-installed-duplicates.sh"
echo ""

bash "$DOTFILES_DIR/management/lib/detect-installed-duplicates.sh"
echo ""

# ================================================================
# Summary
# ================================================================
print_header "Test Complete" "green"
print_info "All steps executed on current user: $(whoami)"
echo ""
print_section "Next Steps" "cyan"
echo "  • Review output above for any errors or warnings"
echo "  • Check verification results for missing tools"
echo "  • Review alternate installations if any were found"
echo "  • Source your shell config: exec zsh (or exec bash)"
echo ""
