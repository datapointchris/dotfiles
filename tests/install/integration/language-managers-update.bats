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
  run bash "$DOTFILES_DIR/install/common/language-managers/go.sh" --update
  assert_success
}

@test "go: normal install mode works" {
  run bash "$DOTFILES_DIR/install/common/language-managers/go.sh"
  assert_success
}

@test "go: shows already at latest version when current" {
  # First install to latest version
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/language-managers/go.sh"
  assert_success

  # Then run update - should show already at latest
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/language-managers/go.sh --update"
  assert_success
}

# Node.js is installed as a system package (brew/pacman), not via a language
# manager, so it has no --update installer to exercise here.
