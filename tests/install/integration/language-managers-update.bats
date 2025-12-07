#!/usr/bin/env bats
#
# Integration tests for language manager --update flag

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

# Test that language managers recognize --update flag

@test "go: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/go.sh" --update
  assert_success
  assert_output --partial "Checking Go for updates"
}

@test "go: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/go.sh"
  assert_success
  assert_output --partial "Installing Go"
}

@test "go: shows already at latest version when current" {
  skip "Requires Go to be installed and up to date"
  run bash "$DOTFILES_DIR/management/common/install/language-managers/go.sh" --update
  assert_success
  assert_output --partial "Already at latest version"
}

@test "nvm: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh" --update
  assert_success
  assert_output --partial "Checking nvm and Node.js for updates"
}

@test "nvm: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh"
  assert_success
  assert_output --partial "Installing nvm and Node.js"
}

@test "nvm: shows already at target version when current" {
  skip "Requires nvm and Node.js to be installed at target version"
  run bash "$DOTFILES_DIR/management/common/install/language-managers/nvm.sh" --update
  assert_success
  assert_output --partial "Already at target Node.js version"
}
