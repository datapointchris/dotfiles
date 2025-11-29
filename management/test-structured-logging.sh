#!/usr/bin/env bash
# ================================================================
# Test Script for Structured Logging Library
# ================================================================
# Tests dual-mode output:
#   - Visual mode (terminal)
#   - Structured mode (pipe/log)
#
# Usage:
#   ./test-structured-logging.sh              # Visual mode (TTY)
#   ./test-structured-logging.sh | cat        # Structured mode (pipe)
#   DOTFILES_LOG_MODE=structured ./test-structured-logging.sh  # Force structured
# ================================================================

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export DOTFILES_DIR

# Source structured logging library
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Show current mode
echo "Testing structured logging library"
echo "Current log mode: $(get_log_mode)"
echo ""

# ================================================================
# Test Basic Logging Functions
# ================================================================

log_section "Basic Logging Functions" "cyan"

log_info "This is an info message"
log_success "This is a success message"
log_warning "This is a warning message"
log_error "This is an error message"
echo ""

# ================================================================
# Test Error Messages with Context
# ================================================================

log_section "Error Messages with File:Line Context" "cyan"

log_error "Download failed" "${BASH_SOURCE[0]}" "$LINENO"
log_error "Missing dependency" "${BASH_SOURCE[0]}" "$LINENO"
echo ""

# ================================================================
# Test Structural Elements
# ================================================================

log_section "Structural Elements" "cyan"

log_header "This is a Header" "blue"
log_banner "This is a Banner" "green"
echo ""

# ================================================================
# Test Success/Error Variants
# ================================================================

log_section "Success/Error Variants" "cyan"

log_header_success "Installation Complete"
log_banner_success "All Tests Passed"
echo ""

# ================================================================
# Test Backward Compatibility
# ================================================================

log_section "Backward Compatibility (print_* functions)" "cyan"

log_info "Using print_info (backward compatible)"
log_success "Using print_success (backward compatible)"
log_warning "Using print_warning (backward compatible)"
log_error "Using print_error (backward compatible)"
echo ""

# ================================================================
# Summary
# ================================================================

log_title_success "Structured Logging Test Complete"

echo "Test completed successfully in $(get_log_mode) mode"
echo ""
echo "To test structured mode:"
echo "  ./test-structured-logging.sh | cat"
echo "  DOTFILES_LOG_MODE=structured ./test-structured-logging.sh"
echo ""
echo "To test with logsift:"
echo "  ./test-structured-logging.sh 2>&1 | tee test.log"
echo "  logsift analyze test.log"
echo ""
