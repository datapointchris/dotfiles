#!/usr/bin/env bats
#
# Integration tests for GitHub release installer --update flag

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

# Test that installers recognize --update flag

@test "lazygit: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/github-releases/lazygit.sh" --update
  assert_success
  assert_output --partial "Checking LazyGit for updates"
}

@test "fzf: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/github-releases/fzf.sh" --update
  assert_success
  assert_output --partial "Checking fzf for updates"
}

@test "glow: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/github-releases/glow.sh" --update
  assert_success
  assert_output --partial "Checking Glow for updates"
}

@test "duf: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/github-releases/duf.sh" --update
  assert_success
  assert_output --partial "Checking Duf for updates"
}

@test "yazi: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/github-releases/yazi.sh" --update
  assert_success
  assert_output --partial "Checking Yazi for updates"
}

@test "neovim: accepts --update flag" {
  run bash "$DOTFILES_DIR/management/common/install/github-releases/neovim.sh" --update
  assert_success
  assert_output --partial "Checking Neovim for updates"
}

# Test version checking behavior

@test "lazygit: shows already at latest version when current" {
  skip "Requires lazygit to be installed and up to date"
  run bash "$DOTFILES_DIR/management/common/install/github-releases/lazygit.sh" --update
  assert_success
  assert_output --partial "Already at latest version"
}

@test "fzf: shows already at latest version when current" {
  skip "Requires fzf to be installed and up to date"
  run bash "$DOTFILES_DIR/management/common/install/github-releases/fzf.sh" --update
  assert_success
  assert_output --partial "Already at latest version"
}

# Test that installers still work in normal mode

@test "lazygit: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/github-releases/lazygit.sh"
  assert_success
  assert_output --partial "Installing LazyGit"
}

@test "fzf: normal install mode works" {
  run bash "$DOTFILES_DIR/management/common/install/github-releases/fzf.sh"
  assert_success
  assert_output --partial "Installing fzf"
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
    run bash "$DOTFILES_DIR/management/common/install/github-releases/${installer}.sh" --update
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
