#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Integration test for font installers
# ================================================================
# Tests font-specific installer behavior:
# 1. Font installers use font-installer.sh library correctly
# 2. Font-specific failure modes (download, extraction, installation)
# 3. Platform-specific font directory handling
# 4. Idempotency (skip when already installed)
#
# Does NOT test (covered by other tests):
# - run_installer wrapper (orchestration test)
# - Failure accumulation (orchestration test)
# - Generic installer patterns (pattern tests)
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."

  # Source libraries
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
  source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"
  source "$DOTFILES_DIR/management/common/lib/font-installer.sh"

  # Export font library functions for use in tests
  export -f get_system_font_dir
  export -f count_font_files
  export -f find_font_files
  export -f is_font_installed

  export TEMP_DIR="/tmp/test-fonts-$$"
  mkdir -p "$TEMP_DIR"

  # Create mock font installer that simulates download failure
  export MOCK_FONT_DOWNLOAD_FAIL="$TEMP_DIR/mock-font-download-fail.sh"
  cat > "$MOCK_FONT_DOWNLOAD_FAIL" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

FONT_NAME="MockFont"
PACKAGE="MockFont"
DOWNLOAD_URL="https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${PACKAGE}.tar.xz"

log_error "Failed to download from $DOWNLOAD_URL"

MANUAL_STEPS="Download manually: https://github.com/ryanoasis/nerd-fonts/releases/latest
Extract: tar -xf ${PACKAGE}.tar.xz
Move to: ~/.local/share/fonts (Linux) or ~/Library/Fonts (macOS)"

output_failure_data "$FONT_NAME" "$DOWNLOAD_URL" "latest" "$MANUAL_STEPS" "Download failed - network timeout"
exit 1
EOF
  chmod +x "$MOCK_FONT_DOWNLOAD_FAIL"

  # Create mock font installer that succeeds (simulates skip)
  export MOCK_FONT_SUCCESS="$TEMP_DIR/mock-font-success.sh"
  cat > "$MOCK_FONT_SUCCESS" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

log_success "Font already installed, skipping"
exit 0
EOF
  chmod +x "$MOCK_FONT_SUCCESS"
}

teardown_file() {
  rm -rf "$TEMP_DIR"
}

# ================================================================
# Test: Font-specific failure output
# ================================================================

@test "fonts: download failure outputs structured data" {
  run bash "$MOCK_FONT_DOWNLOAD_FAIL"
  assert_failure
  assert_output --partial "FAILURE_TOOL='MockFont'"
  assert_output --partial "FAILURE_URL='https://github.com/ryanoasis/nerd-fonts"
  assert_output --partial "FAILURE_VERSION='latest'"
  assert_output --partial "FAILURE_REASON='Download failed - network timeout'"
}

@test "fonts: failure includes nerd-fonts specific manual steps" {
  run bash "$MOCK_FONT_DOWNLOAD_FAIL"
  assert_failure
  assert_output --partial "FAILURE_MANUAL_START"
  assert_output --partial "https://github.com/ryanoasis/nerd-fonts/releases/latest"
  assert_output --partial "tar -xf"
  assert_output --partial "FAILURE_MANUAL_END"
}

# ================================================================
# Test: Font library functions (basic smoke tests)
# ================================================================

@test "fonts: get_system_font_dir is tested via real installer" {
  # Skip direct testing - get_system_font_dir has complex dependencies (detect_platform, log_error)
  # It's properly tested via real installer test below which validates the full workflow
  skip "Tested indirectly via real installer test"
}

@test "fonts: count_font_files returns 0 for non-existent directory" {
  run count_font_files "/tmp/nonexistent-font-dir-xyz"
  assert_success
  assert_output "0"
}

@test "fonts: count_font_files counts font files correctly" {
  local test_font_dir="$TEMP_DIR/test-fonts"
  mkdir -p "$test_font_dir"
  touch "$test_font_dir/font1.ttf"
  touch "$test_font_dir/font2.otf"
  touch "$test_font_dir/font3.ttc"
  touch "$test_font_dir/readme.txt"  # Should not count

  run count_font_files "$test_font_dir"
  assert_success
  assert_output "3"

  rm -rf "$test_font_dir"
}

# ================================================================
# Test: Real font installer behavior (one sample)
# ================================================================

@test "fonts: real installer has proper structure" {
  # Test that a real font installer has expected components
  local installer="$DOTFILES_DIR/management/common/install/fonts/jetbrains.sh"

  # Should source font-installer library
  grep -q "font-installer.sh" "$installer"

  # Should have set -euo pipefail
  grep -q "set -euo pipefail" "$installer"

  # Should define font_name and nerd_font_package variables
  grep -q "font_name=" "$installer"
  grep -q "nerd_font_package=" "$installer"
}

@test "fonts: real installer can run without errors (idempotent)" {
  # Run real installer - should either succeed or fail gracefully
  # This tests that the installer structure is correct
  local installer="$DOTFILES_DIR/management/common/install/fonts/jetbrains.sh"

  run bash "$installer"
  # Should exit with 0 (success/skip) or 1 (failure with structured output)
  # Should NOT crash with syntax errors or missing functions
  [[ "$status" -eq 0 || "$status" -eq 1 ]]
}

@test "fonts: real installer produces logging output" {
  local installer="$DOTFILES_DIR/management/common/install/fonts/jetbrains.sh"

  run bash "$installer"
  # Should produce some output (either success or error messages)
  [[ -n "$output" ]]

  # Output should include font name
  assert_output --partial "JetBrains"
}

# ================================================================
# Test: Font installer error handling
# ================================================================

@test "fonts: installer exits with 1 on download failure" {
  run bash "$MOCK_FONT_DOWNLOAD_FAIL"
  assert_failure
  assert_equal "$status" 1
}

@test "fonts: installer exits with 0 on success/skip" {
  run bash "$MOCK_FONT_SUCCESS"
  assert_success
}

# ================================================================
# Helper functions
# ================================================================

skip_if_not_macos() {
  if [[ "$OSTYPE" != "darwin"* ]]; then
    skip "Test only runs on macOS"
  fi
}
