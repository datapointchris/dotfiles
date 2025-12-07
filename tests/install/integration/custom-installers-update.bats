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
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/terraform-ls.sh" --update
  assert_success
  assert_output --partial "Checking Terraform Language Server for updates"
}

@test "terraform-ls: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/terraform-ls.sh"
  assert_success
  assert_output --partial "Installing Terraform Language Server"
}

@test "awscli: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/awscli.sh" --update
  assert_success
  assert_output --partial "Checking AWS CLI for updates"
}

@test "awscli: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/awscli.sh"
  assert_success
  assert_output --partial "Installing AWS CLI"
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
  assert_output --partial "Current version"
}

@test "bats: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/bats.sh" --update
  assert_success
  assert_output --partial "Checking BATS for updates"
}

@test "bats: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/bats.sh"
  assert_success
  assert_output --partial "Installing BATS Testing Framework"
}

@test "bats: shows already at latest version when current" {
  run bash "$DOTFILES_DIR/management/common/install/custom-installers/bats.sh" --update
  assert_success
  assert_output --partial "Already at latest version"
}
