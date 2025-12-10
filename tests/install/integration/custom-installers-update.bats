#!/usr/bin/env bats
#
# Integration tests for custom installer --update flag

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

# Test that custom installers recognize --update flag

@test "terraform-ls: accepts --update flag" {
  skip "Requires network access to GitHub API"
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/terraform-ls.sh" --update
  assert_success
}

@test "terraform-ls: normal install mode works" {
  skip "Requires network access to GitHub API"
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/terraform-ls.sh"
  assert_success
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
  skip "Requires terraform-ls to be installed and up to date"
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/terraform-ls.sh" --update
  assert_success
  assert_output --partial "Already at latest version"
}

@test "awscli: reports current version on macOS" {
  if [[ "$OSTYPE" != "darwin"* ]]; then
    skip "macOS-specific test"
  fi

  run bash "$DOTFILES_DIR/management/common/install/custom-installers/awscli.sh" --update
  assert_success
}

@test "bats: accepts --update flag" {
  skip "Requires network access to GitHub API"
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/bats.sh" --update
  assert_success
}

@test "bats: normal install mode works" {
  skip "Requires network access to GitHub API"
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/bats.sh"
  assert_success
}

@test "bats: shows already at latest version when current" {
  skip "Requires bats to be installed and at latest version"
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/bats.sh" --update
  assert_success
}

@test "claude-code: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/claude-code.sh" --update
  assert_success
  assert_output --partial "Latest version:"
}

@test "claude-code: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/claude-code.sh"
  assert_success
  assert_output --partial "Latest version:"
}

@test "claude-code: shows already at latest version when current" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/claude-code.sh" --update
  assert_success
  assert_output --partial "Already at latest version"
}
