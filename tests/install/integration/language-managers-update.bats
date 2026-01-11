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
}

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."

  # Source Docker helpers for this test
  source "$DOTFILES_DIR/tests/install/integration/docker-helpers.sh"

  # Start fresh container for each test
  BATS_TEST_CONTAINER=$(start_test_container)
}

teardown() {
  # Clean up container after each test
  docker_test_teardown
}

# Test that language managers recognize --update flag

@test "go: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/go.sh" --update
  assert_success
  assert_output --partial "Checking for updates..."
}

@test "go: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/go.sh"
  assert_success
  assert_output --partial "go"
}

@test "go: shows already at latest version when current" {
  # First install to latest version
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/language-managers/go.sh"
  assert_success

  # Then run update - should show already at latest
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/language-managers/go.sh --update"
  assert_success
  assert_output --partial "already at latest"
}

@test "nvm: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh" --update
  assert_success
  assert_output --partial "Checking for updates..."
}

@test "nvm: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh"
  assert_success
  assert_output --partial "Installing..."
}

@test "nvm: shows already at target version when current" {
  skip "Requires nvm and Node.js to be installed at target version"
  run bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh" --update
  assert_success
  assert_output --partial "Already at target Node.js version"
}
