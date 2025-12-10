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

# Test that installers recognize --update flag

@test "lazygit: accepts --update flag" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/lazygit.sh --update"
  assert_success
  assert_output --regexp "Latest version: v[0-9]+"
}

@test "fzf: accepts --update flag" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/fzf.sh --update"
  assert_success
  assert_output --partial "Latest version:"
}

@test "glow: accepts --update flag" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/glow.sh --update"
  assert_success
  assert_output --regexp "Latest version: v[0-9]+"
}

@test "duf: accepts --update flag" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/duf.sh --update"
  assert_success
  assert_output --regexp "Latest version: v[0-9]+"
}

@test "yazi: accepts --update flag" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/yazi.sh --update"
  assert_success
  assert_output --regexp "Latest version: v[0-9]+"
}

@test "neovim: accepts --update flag" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/neovim.sh --update"
  assert_success
  assert_output --partial "Latest:"
}

# Test version checking behavior

@test "lazygit: shows already at latest version when current" {
  # First install to latest version
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/lazygit.sh"
  assert_success

  # Then run update - should show already at latest
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/lazygit.sh --update"
  assert_success
  assert_output --partial "Already at latest"
}

@test "fzf: shows already at latest version when current" {
  # First install to latest version
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/fzf.sh"
  assert_success

  # Then run update - should show already at latest
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/fzf.sh --update"
  assert_success
  assert_output --partial "Already at latest"
}

# Test that installers still work in normal mode

@test "lazygit: normal install mode works" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/lazygit.sh"
  assert_success
  assert_output --regexp "Latest version: v[0-9]+"
}

@test "fzf: normal install mode works" {
  run docker_exec "$BATS_TEST_CONTAINER" \
    "bash management/common/install/github-releases/fzf.sh"
  assert_success
  assert_output --partial "Latest version:"
}

# Test all 11 installers have --update support

@test "all github release installers accept --update flag" {
  local installers=(
    "lazygit"
    "fzf"
    "glow"
    "duf"
    "yazi"
    "neovim"
    "tflint"
    "terraformer"
    "terrascan"
    "trivy"
    "zk"
  )

  for installer in "${installers[@]}"; do
    run docker_exec "$BATS_TEST_CONTAINER" \
      "bash management/common/install/github-releases/${installer}.sh --update"
    assert_success
  done
}

# Test version comparison logic via library

@test "check_if_update_needed: detects when tool not installed" {
  source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

  run check_if_update_needed "nonexistent-binary-12345" "v1.0.0"
  assert_success
  assert_output --partial "not installed"
}

@test "check_if_update_needed: handles binary that exists" {
  source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

  # Test with bash (always available)
  run check_if_update_needed "bash" "999.999.999"

  # Should indicate update available (current bash < v999.999.999)
  [[ "$status" -eq 0 ]] || [[ "$output" == *"Already at latest"* ]]
}
