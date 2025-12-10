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
}

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
  source "${BATS_TEST_DIRNAME}/docker-helpers.sh"

  # Start fresh container for each test
  BATS_TEST_CONTAINER=$(start_test_container)
}

teardown() {
  docker_test_teardown
}

# Test installers with --update flag (real network calls)

@test "lazygit: accepts --update flag and makes real GitHub API call" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/lazygit.sh --update"
  assert_success
  assert_output --regexp "Latest version: v[0-9]+\.[0-9]+\.[0-9]+"
}

@test "fzf: accepts --update flag and downloads from GitHub" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/fzf.sh --update"
  assert_success
  assert_output --partial "Latest version:"
}

@test "glow: installs successfully with real network call" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/glow.sh"
  assert_success
  assert_output --partial "installed to:"
}

# Test that binaries are actually installed and executable

@test "lazygit: installed binary is executable after installation" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/lazygit.sh && ~/.local/bin/lazygit --version"
  assert_success
  assert_output --regexp "version.*[0-9]+\.[0-9]+"
}

@test "duf: can be installed and run in isolated container" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/duf.sh && ~/.local/bin/duf --version"
  assert_success
}
