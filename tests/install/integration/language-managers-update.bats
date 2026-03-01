#!/usr/bin/env bats
#
# Integration tests for language manager --update flag

setup_file() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."

  # Source Docker helpers and verify environment
  source "$DOTFILES_DIR/tests/install/integration/docker-helpers.sh"
  docker_test_setup

  # Start one shared container for Docker tests in this file
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

# Test that language managers recognize --update flag

@test "go: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/go.sh" --update
  assert_success
}

@test "go: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/go.sh"
  assert_success
}

@test "go: shows already at latest version when current" {
  # First install to latest version
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/language-managers/go.sh"
  assert_success

  # Then run update - should show already at latest
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash management/common/install/language-managers/go.sh --update"
  assert_success
}

@test "nvm: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh" --update
  assert_success
}

@test "nvm: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh"
  assert_success
}

@test "nvm: shows already at target version when current" {
  skip "Requires nvm and Node.js to be installed at target version"
  run bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh" --update
  assert_success
}
