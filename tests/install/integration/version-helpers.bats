#!/usr/bin/env bats
#
# Integration tests for version-helpers.sh library

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
  source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
}

# version_compare tests

@test "version_compare: equal versions without v prefix" {
  run version_compare "1.2.3" "1.2.3"
  assert_success
}

@test "version_compare: equal versions with v prefix" {
  run version_compare "v1.2.3" "v1.2.3"
  assert_success
}

@test "version_compare: equal versions mixed prefix" {
  run version_compare "v1.2.3" "1.2.3"
  assert_success
}

@test "version_compare: current older than latest (patch)" {
  run version_compare "1.2.3" "1.2.4"
  assert_failure
  assert_equal "$status" 1
}

@test "version_compare: current older than latest (minor)" {
  run version_compare "1.2.3" "1.3.0"
  assert_failure
  assert_equal "$status" 1
}

@test "version_compare: current older than latest (major)" {
  run version_compare "1.2.3" "2.0.0"
  assert_failure
  assert_equal "$status" 1
}

@test "version_compare: current newer than latest" {
  run version_compare "2.0.0" "1.9.9"
  assert_failure
  assert_equal "$status" 2
}

@test "version_compare: handles v prefix on current only" {
  run version_compare "v1.2.3" "1.2.4"
  assert_failure
  assert_equal "$status" 1
}

@test "version_compare: handles v prefix on latest only" {
  run version_compare "1.2.3" "v1.2.4"
  assert_failure
  assert_equal "$status" 1
}

@test "version_compare: missing current version" {
  run version_compare "" "1.2.3"
  assert_failure
  assert_equal "$status" 1
}

@test "version_compare: missing latest version" {
  run version_compare "1.2.3" ""
  assert_failure
  assert_equal "$status" 1
}

@test "version_compare: both versions missing" {
  run version_compare "" ""
  assert_failure
  assert_equal "$status" 1
}

@test "version_compare: two-part versions" {
  run version_compare "1.2" "1.3"
  assert_failure
  assert_equal "$status" 1
}

@test "version_compare: equal two-part versions" {
  run version_compare "1.2" "1.2"
  assert_success
}

# parse_version tests

@test "parse_version: extracts version from standard output" {
  run parse_version "neovim 0.9.5"
  assert_success
  assert_output "0.9.5"
}

@test "parse_version: extracts version with v prefix" {
  run parse_version "lazygit version v0.40.2"
  assert_success
  assert_output "v0.40.2"
}

@test "parse_version: extracts first version from multi-line output" {
  output="Version: 1.2.3
Build: 456
Extra: 7.8.9"
  run parse_version "$output"
  assert_success
  assert_output "1.2.3"
}

@test "parse_version: extracts two-part version" {
  run parse_version "tool v1.2"
  assert_success
  assert_output "v1.2"
}

@test "parse_version: handles complex output" {
  run parse_version "NVIM v0.9.5-dev+build123"
  assert_success
  assert_output "v0.9.5"
}

@test "parse_version: fails on missing version" {
  run parse_version "no version here"
  assert_failure
}

@test "parse_version: fails on empty input" {
  run parse_version ""
  assert_failure
}

@test "parse_version: extracts from version flag output" {
  run parse_version "go version go1.21.5 darwin/arm64"
  assert_success
  assert_output "1.21.5"
}

# fetch_github_latest_version tests

@test "fetch_github_latest_version: fetches neovim latest version" {
  skip "Requires network access to GitHub API"
  run fetch_github_latest_version "neovim/neovim"
  assert_success
  assert_output --regexp '^v[0-9]+\.[0-9]+\.[0-9]+$'
}

@test "fetch_github_latest_version: fetches lazygit latest version" {
  skip "Requires network access to GitHub API"
  run fetch_github_latest_version "jesseduffield/lazygit"
  assert_success
  assert_output --regexp '^v[0-9]+\.[0-9]+(\.[0-9]+)?$'
}

@test "fetch_github_latest_version: fails on invalid repo" {
  run fetch_github_latest_version "invalid/nonexistent-repo-12345"
  assert_failure
}

@test "fetch_github_latest_version: fails on missing argument" {
  run fetch_github_latest_version ""
  assert_failure
}

@test "fetch_github_latest_version: fails on malformed repo" {
  run fetch_github_latest_version "invalid-repo-format"
  assert_failure
}

# Integration tests (combining functions)

@test "integration: check if neovim update available" {
  skip "Requires network access to GitHub API"
  # Fetch latest version
  latest=$(fetch_github_latest_version "neovim/neovim")

  # Simulate current version (older)
  current="v0.9.0"

  run version_compare "$current" "$latest"

  # Should indicate update available (return 1)
  assert_failure
  assert_equal "$status" 1
}

@test "integration: parse and compare versions" {
  # Simulate version command output
  current_output="neovim v0.9.5"
  current=$(parse_version "$current_output")

  # Compare with same version
  run version_compare "$current" "0.9.5"
  assert_success
}

@test "integration: detect already at latest" {
  skip "Requires network access to GitHub API"
  # Fetch real latest version
  latest=$(fetch_github_latest_version "neovim/neovim")

  # Compare with itself
  run version_compare "$latest" "$latest"
  assert_success
}
