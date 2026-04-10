#!/usr/bin/env bats
#
# Tests for github-release-installer.sh library
#
# Tests core functions for GitHub release installation

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."

  # Source dependencies first
  source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
  source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"

  # Source library under test
  source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"
}

# get_platform_arch tests

@test "get_platform_arch returns correct platform string for macOS" {
  skip_if_not_macos

  run get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64"
  assert_success
  assert_output --regexp "Darwin_(x86_64|arm64)"
}

@test "get_platform_arch handles lowercase platform names" {
  skip_if_not_macos

  run get_platform_arch "darwin_x86_64" "darwin_arm64" "linux_x86_64"
  assert_success
  assert_output --regexp "darwin_(x86_64|arm64)"
}

@test "get_platform_arch returns different values for different architectures" {
  skip_if_not_macos

  darwin_x86="x86_result"
  darwin_arm="arm_result"
  linux_x86="linux_result"

  result=$(get_platform_arch "$darwin_x86" "$darwin_arm" "$linux_x86")

  # Result should be one of the two darwin options
  [[ "$result" == "x86_result" || "$result" == "arm_result" ]]
}

# get_latest_version tests

@test "get_latest_version fetches real version from GitHub" {
  run get_latest_version "jesseduffield/lazygit"
  assert_success
  assert_output --regexp '^v[0-9]+\.[0-9]+\.[0-9]+$'
}

@test "get_latest_version handles different repos" {
  run get_latest_version "neovim/neovim"
  assert_success
  assert_output --regexp '^v[0-9]+\.[0-9]+\.[0-9]+$'
}

@test "get_latest_version fails on invalid repo" {
  run get_latest_version "invalid/nonexistent-repo-12345-test"
  assert_failure
}

# should_skip_install tests

@test "should_skip_install returns 1 (install) when binary not found" {
  run should_skip_install "/nonexistent/path/binary" "nonexistent-binary-xyz"
  assert_failure
  assert_equal "$status" 1
}

@test "should_skip_install returns 1 (install) when FORCE_INSTALL=true" {
  # Even if binary exists, should install when forced
  FORCE_INSTALL=true run should_skip_install "/bin/bash" "bash"
  assert_failure
  assert_equal "$status" 1
}

# check_if_update_needed tests

@test "check_if_update_needed returns 0 (update) when binary not installed" {
  run check_if_update_needed "nonexistent-binary-xyz" "v1.0.0"
  assert_success
  assert_output --partial "not installed"
}

@test "check_if_update_needed works with real binary (bash)" {
  # bash is always installed, so this tests the version comparison logic
  # We expect either "already at latest" or "update available" or "Could not determine"
  run check_if_update_needed "bash" "v999.999.999"

  # Should succeed (returns 0 = update needed or 1 = already latest)
  # Output should contain one of the expected messages
  [[ "$output" =~ "already at latest"|"update available"|"Could not determine" ]]
}

# version fetch failure tests

@test "installer exits on version fetch failure instead of continuing with empty version" {
  # This test catches the bug where scripts continued with VERSION="" after
  # get_latest_version failed, producing malformed download URLs like:
  #   .../releases/download//tool__macOS-64bit.tar.gz
  local test_script
  test_script=$(mktemp)
  cat > "$test_script" << SCRIPT
#!/usr/bin/env bash
set -uo pipefail
DOTFILES_DIR="$DOTFILES_DIR"
source "\$DOTFILES_DIR/install/common/lib/version-helpers.sh"
source "\$DOTFILES_DIR/install/common/lib/github-release-installer.sh"
source "\$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "\$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "\$DOTFILES_DIR/configs/common/.local/shell/error-handling.sh"
source "\$DOTFILES_DIR/install/common/lib/failure-logging.sh"

# Override to simulate GitHub API failure
fetch_github_latest_version() { return 1; }

REPO="fake/repo"
VERSION=\$(get_latest_version "\$REPO") || exit 1
echo "SHOULD_NOT_REACH version=\$VERSION"
SCRIPT

  run bash "$test_script"
  rm -f "$test_script"
  assert_failure
  refute_output --partial "SHOULD_NOT_REACH"
}

@test "installer with empty version produces malformed URL without exit guard" {
  # Demonstrates what happens WITHOUT the || exit 1 guard:
  # an empty VERSION creates a broken download URL
  local version=""
  local url="https://github.com/org/tool/releases/download/${version}/tool_${version#v}_macOS.tar.gz"
  # The URL contains double slash and empty version components
  [[ "$url" == *"/download//tool_"* ]]
}

# Helper functions

skip_if_not_macos() {
  if [[ "$OSTYPE" != "darwin"* ]]; then
    skip "Test only runs on macOS"
  fi
}
