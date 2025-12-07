#!/usr/bin/env bash
# Test font installers integration with run_installer

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/orchestration/run-installer.sh"

# Test setup
TEST_DIR="/tmp/font-installer-test-$$"
export FAILURES_LOG="$TEST_DIR/failures.log"
mkdir -p "$TEST_DIR"
trap 'rm -rf "$TEST_DIR"' EXIT

common_install="$DOTFILES_DIR/management/common/install"

test_font_installer_success() {
  print_section "Test: Font Installer Success" "yellow"

  # Test with a font that should skip (already installed)
  run_installer "$common_install/fonts/jetbrains.sh" "jetbrains-font"

  if [[ -f "$FAILURES_LOG" ]]; then
    log_error "Unexpected failure log found"
    cat "$FAILURES_LOG"
    return 1
  fi

  log_success "Font installer success test passed"
}

test_font_installer_via_run_installer() {
  print_section "Test: Multiple Font Installers" "yellow"

  # Test several font installers
  run_installer "$common_install/fonts/cascadia.sh" "cascadia-font"
  run_installer "$common_install/fonts/firacode.sh" "firacode-font"
  run_installer "$common_install/fonts/comicmono.sh" "comicmono-font"

  if [[ -f "$FAILURES_LOG" ]]; then
    log_error "Unexpected failure log found"
    cat "$FAILURES_LOG"
    return 1
  fi

  log_success "Multiple font installers test passed"
}

test_font_installer_output() {
  print_section "Test: Font Installer Output Format" "yellow"

  # Verify installer produces expected output format
  output=$(bash "$common_install/fonts/jetbrains.sh" 2>&1)

  if ! echo "$output" | grep -q "Installing JetBrains Mono Nerd Font"; then
    log_error "Expected header not found in output"
    echo "$output"
    return 1
  fi

  if ! echo "$output" | grep -q "already installed\|installation complete"; then
    log_error "Expected completion message not found"
    echo "$output"
    return 1
  fi

  log_success "Font installer output format test passed"
}

# Run tests
print_header "Font Installers Integration Tests" "cyan"
echo ""

test_font_installer_success
echo ""

test_font_installer_via_run_installer
echo ""

test_font_installer_output
echo ""

print_header "All Font Installer Tests Passed" "green"
log_success "Font installers work correctly with run_installer pattern"
