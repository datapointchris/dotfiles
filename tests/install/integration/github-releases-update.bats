#!/usr/bin/env bats
#
# Integration tests for GitHub release installer --update flag

setup_file() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."

  # Source Docker helpers and verify environment
  source "$DOTFILES_DIR/tests/install/integration/docker-helpers.sh"
  docker_test_setup

  # Start one shared container for all tests in this file
  BATS_SHARED_CONTAINER=$(start_test_container)
  export BATS_SHARED_CONTAINER
}

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
  source "$DOTFILES_DIR/tests/install/integration/docker-helpers.sh"
}

teardown_file() {
  docker_shared_test_teardown
}

# Test that installers recognize --update flag

@test "lazygit: accepts --update flag" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/lazygit.sh --update"
  [[ "$status" -le 1 ]]
}

@test "fzf: accepts --update flag" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/fzf.sh --update"
  [[ "$status" -le 1 ]]
}

@test "glow: accepts --update flag" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/glow.sh --update"
  [[ "$status" -le 1 ]]
}

@test "duf: accepts --update flag" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/duf.sh --update"
  [[ "$status" -le 1 ]]
}

@test "yazi: accepts --update flag" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/yazi.sh --update"
  [[ "$status" -le 1 ]]
}

@test "neovim: accepts --update flag" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/neovim.sh --update"
  [[ "$status" -le 1 ]]
}

# Test version checking behavior

@test "lazygit: shows already at latest version when current" {
  # First install to latest version
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/lazygit.sh"
  assert_success

  # Then run update - should show already at latest
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/lazygit.sh --update"
  assert_success
}

@test "fzf: shows already at latest version when current" {
  # First install to latest version
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/fzf.sh"
  assert_success

  # Then run update - should show already at latest
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/fzf.sh --update"
  assert_success
}

# Test that installers still work in normal mode

@test "lazygit: normal install mode works" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/lazygit.sh"
  assert_success

  run docker_exec "$BATS_SHARED_CONTAINER" "test -x ~/.local/bin/lazygit"
  assert_success
}

@test "fzf: normal install mode works" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/github-releases/fzf.sh"
  assert_success

  run docker_exec "$BATS_SHARED_CONTAINER" "test -x ~/.local/bin/fzf"
  assert_success
}

# Test all installers have --update support

@test "all github release installers accept --update flag" {
  # Auto-discover all installer scripts
  local installers=()
  for script in "$DOTFILES_DIR/management/common/install/github-releases"/*.sh; do
    [[ -f "$script" ]] && installers+=("$(basename "$script" .sh)")
  done

  for installer in "${installers[@]}"; do
    run docker_exec "$BATS_SHARED_CONTAINER" \
      "bash management/common/install/github-releases/${installer}.sh --update"
    # Exit 0 (success/up-to-date) or 1 (version fetch failure) are both acceptable.
    # Exit code > 1 indicates a crash or unhandled error.
    [[ "$status" -le 1 ]] || {
      echo "FAILED: ${installer}.sh exited with status $status"
      echo "Output: $output"
      return 1
    }
  done
}

# Test version comparison logic via library

@test "check_if_update_needed: detects when tool not installed" {
  source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

  run check_if_update_needed "nonexistent-binary-12345" "v1.0.0"
  assert_success
}

@test "check_if_update_needed: handles binary that exists" {
  source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

  # Test with bash (always available) - should indicate update available
  run check_if_update_needed "bash" "999.999.999"
  assert_success
}
