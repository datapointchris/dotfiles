#!/usr/bin/env bats
#
# Docker-based integration tests for GitHub release installers
# Proof of concept for Phase 3: Testing with real network calls

setup_file() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
  source "${BATS_TEST_DIRNAME}/docker-helpers.sh"

  docker_test_setup

  # Start one shared container for all tests in this file
  BATS_SHARED_CONTAINER=$(start_test_container)
  export BATS_SHARED_CONTAINER
}

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
  source "${BATS_TEST_DIRNAME}/docker-helpers.sh"
}

teardown_file() {
  docker_shared_test_teardown
}

# Test installers with --update flag (real network calls)

@test "lazygit: accepts --update flag and makes real GitHub API call" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/install/github-releases/lazygit.sh --update"
  [[ "$status" -le 1 ]]
}

@test "fzf: accepts --update flag and downloads from GitHub" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/install/github-releases/fzf.sh --update"
  [[ "$status" -le 1 ]]
}

@test "glow: installs successfully with real network call" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/install/github-releases/glow.sh"
  assert_success

  run docker_exec "$BATS_SHARED_CONTAINER" "test -x ~/.local/bin/glow"
  assert_success
}

# Test that binaries are actually installed and executable

@test "lazygit: installed binary is executable after installation" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/install/github-releases/lazygit.sh && ~/.local/bin/lazygit --version"
  assert_success
}

@test "duf: can be installed and run in isolated container" {
  run docker_exec "$BATS_SHARED_CONTAINER" \
    "bash install/common/install/github-releases/duf.sh && ~/.local/bin/duf --version"
  assert_success
}
