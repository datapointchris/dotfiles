#!/usr/bin/env bats
#
# Integration tests for custom installer --update flag

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

# Test that custom installers recognize --update flag

@test "terraform-ls: accepts --update flag" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/custom-installers/terraform-ls.sh --update"
  assert_success
  assert_output --partial "terraform-ls"
}

@test "terraform-ls: normal install mode works" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/custom-installers/terraform-ls.sh"
  assert_success
  assert_output --partial "terraform-ls"
}

@test "awscli: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/awscli.sh" --update
  assert_success
}

@test "awscli: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/awscli.sh"
  assert_success
}

# Test version checking behavior

@test "terraform-ls: shows already at latest version when current" {
  # First install to latest version
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/custom-installers/terraform-ls.sh"
  assert_success

  # Then run update - should show already at latest
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/custom-installers/terraform-ls.sh --update"
  assert_success
  assert_output --partial "already at latest"
}

@test "awscli: reports current version on macOS" {
  if [[ "$OSTYPE" != "darwin"* ]]; then
    skip "macOS-specific test"
  fi

  run bash "$DOTFILES_DIR/management/common/install/custom-installers/awscli.sh" --update
  assert_success
}

@test "bats: accepts --update flag" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/custom-installers/bats.sh --update"
  assert_success
  assert_output --partial "Installing BATS"
}

@test "bats: normal install mode works" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/custom-installers/bats.sh"
  assert_success
  assert_output --partial "Installing BATS"
}

@test "bats: shows already at latest version when current" {
  # First install to latest version
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/custom-installers/bats.sh"
  assert_success

  # Then run update - should show already at latest
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/custom-installers/bats.sh --update"
  assert_success
  assert_output --partial "already at latest"
}

@test "claude-code: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/claude-code.sh" --update
  assert_success
  assert_output --partial "claude-code"
}

@test "claude-code: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/claude-code.sh"
  assert_success
  assert_output --partial "claude-code"
}

@test "claude-code: shows already installed or self-updates" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/claude-code.sh" --update
  assert_success
  # Claude Code self-updates, so it may show installed status
  assert_output --partial "claude-code"
}
