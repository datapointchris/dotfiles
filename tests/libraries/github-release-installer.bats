#!/usr/bin/env bats
#
# Tests for github-release-installer.sh library
#
# Tests core functions for GitHub release installation

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."

  # Source dependencies first
  source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
  source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"

  # Source library under test
  source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"
}

# get_platform_arch tests

@test "get_platform_arch returns correct platform string for macOS" {
  skip_if_not_macos

  run get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64"
  assert_success
  assert_output --regexp "Darwin_(x86_64|arm64)"
}

@test "get_platform_arch handles lowercase platform names" {
  skip_if_not_macos

  run get_platform_arch "darwin_x86_64" "darwin_arm64" "linux_x86_64"
  assert_success
  assert_output --regexp "darwin_(x86_64|arm64)"
}

@test "get_platform_arch returns different values for different architectures" {
  skip_if_not_macos

  darwin_x86="x86_result"
  darwin_arm="arm_result"
  linux_x86="linux_result"

  result=$(get_platform_arch "$darwin_x86" "$darwin_arm" "$linux_x86")

  # Result should be one of the two darwin options
  [[ "$result" == "x86_result" || "$result" == "arm_result" ]]
}

# get_latest_version tests

@test "get_latest_version fetches real version from GitHub" {
  run get_latest_version "jesseduffield/lazygit"
  assert_success
  assert_output --regexp '^v[0-9]+\.[0-9]+\.[0-9]+$'
}

@test "get_latest_version handles different repos" {
  run get_latest_version "neovim/neovim"
  assert_success
  assert_output --regexp '^v[0-9]+\.[0-9]+\.[0-9]+$'
}

@test "get_latest_version fails on invalid repo" {
  run get_latest_version "invalid/nonexistent-repo-12345-test"
  assert_failure
}

# should_skip_install tests

@test "should_skip_install returns 1 (install) when binary not found" {
  run should_skip_install "/nonexistent/path/binary" "nonexistent-binary-xyz"
  assert_failure
  assert_equal "$status" 1
}

@test "should_skip_install returns 1 (install) when FORCE_INSTALL=true" {
  # Even if binary exists, should install when forced
  FORCE_INSTALL=true run should_skip_install "/bin/bash" "bash"
  assert_failure
  assert_equal "$status" 1
}

# check_if_update_needed tests

@test "check_if_update_needed returns 0 (update) when binary not installed" {
  run check_if_update_needed "nonexistent-binary-xyz" "v1.0.0"
  assert_success
  assert_output --partial "not installed"
}

@test "check_if_update_needed works with real binary (bash)" {
  # bash is always installed, so this tests the version comparison logic
  # We expect either "already at latest" or "update available" or "Could not determine"
  run check_if_update_needed "bash" "v999.999.999"

  # Should succeed (returns 0 = update needed or 1 = already latest)
  # Output should contain one of the expected messages
  [[ "$output" =~ "already at latest"|"update available"|"Could not determine" ]]
}

# version fetch failure tests

@test "installer exits on version fetch failure instead of continuing with empty version" {
  # This test catches the bug where scripts continued with VERSION="" after
  # get_latest_version failed, producing malformed download URLs like:
  #   .../releases/download//tool__macOS-64bit.tar.gz
  local test_script
  test_script=$(mktemp)
  cat >"$test_script" <<SCRIPT
#!/usr/bin/env bash
set -uo pipefail
DOTFILES_DIR="$DOTFILES_DIR"
source "\$DOTFILES_DIR/install/common/lib/version-helpers.sh"
source "\$DOTFILES_DIR/install/common/lib/github-release-installer.sh"
source "\$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "\$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "\$DOTFILES_DIR/configs/common/.local/shell/error-handling.sh"
source "\$DOTFILES_DIR/install/common/lib/failure-logging.sh"

# Override to simulate GitHub API failure
fetch_github_latest_version() { return 1; }

REPO="fake/repo"
VERSION=\$(get_latest_version "\$REPO") || exit 1
echo "SHOULD_NOT_REACH version=\$VERSION"
SCRIPT

  run bash "$test_script"
  rm -f "$test_script"
  assert_failure
  refute_output --partial "SHOULD_NOT_REACH"
}

@test "installer with empty version produces malformed URL without exit guard" {
  # Demonstrates what happens WITHOUT the || exit 1 guard:
  # an empty VERSION creates a broken download URL
  local version=""
  local url="https://github.com/org/tool/releases/download/${version}/tool_${version#v}_macOS.tar.gz"
  # The URL contains double slash and empty version components
  [[ "$url" == *"/download//tool_"* ]]
}

# Release-asset URL parsing
#
# install_from_tarball derives repo and tag from the download URL so that every
# existing caller gains private-repo support without a signature change. A
# nested module's tag contains a slash (cli/v1.2.0), which is the case most
# likely to be parsed wrong — the tag is everything between /releases/download/
# and the final filename segment, not the single segment after it.

parse_download_url() {
  local url="$1"
  if [[ "$url" =~ ^https://github\.com/([^/]+/[^/]+)/releases/download/(.+)/([^/]+)$ ]]; then
    echo "${BASH_REMATCH[1]}|${BASH_REMATCH[2]}|${BASH_REMATCH[3]}"
  else
    return 1
  fi
}

@test "download url parsing: extracts repo and plain tag" {
  run parse_download_url "https://github.com/owner/repo/releases/download/v1.2.0/tool_1.2.0_linux_amd64.tar.gz"
  assert_success
  assert_output "owner/repo|v1.2.0|tool_1.2.0_linux_amd64.tar.gz"
}

@test "download url parsing: keeps slashes inside a prefixed tag" {
  run parse_download_url "https://github.com/datapointchris/nomad/releases/download/cli/v0.1.0/nomad_0.1.0_darwin_amd64.tar.gz"
  assert_success
  assert_output "datapointchris/nomad|cli/v0.1.0|nomad_0.1.0_darwin_amd64.tar.gz"
}

@test "download url parsing: rejects a non-release URL" {
  run parse_download_url "https://example.com/some/file.tar.gz"
  assert_failure
}

@test "checksum lookup: matches an asset whose recorded name differs only by case" {
  local checksums="$BATS_TEST_TMPDIR/checksums.txt"
  printf '%s  %s\n' "$(printf 'a%.0s' {1..64})" "lazygit_0.63.1_linux_x86_64.tar.gz" >"$checksums"

  run checksum_for_asset "$checksums" "lazygit_0.63.1_Linux_x86_64.tar.gz"
  assert_success
  assert_output "$(printf 'a%.0s' {1..64})"
}

@test "checksum lookup: still finds nothing for an asset that is absent" {
  local checksums="$BATS_TEST_TMPDIR/checksums.txt"
  printf '%s  %s\n' "$(printf 'a%.0s' {1..64})" "lazygit_0.63.1_linux_x86_64.tar.gz" >"$checksums"

  run checksum_for_asset "$checksums" "someothertool.tar.gz"
  assert_output ""
}

# Offline bundle checksum tests
#
# The bundle exists for networks that cannot reach GitHub, so these must never
# fall through to a release lookup.

setup_bundle() {
  BUNDLE_DIR="$BATS_TEST_TMPDIR/installers"
  mkdir -p "$BUNDLE_DIR/binaries"
  OFFLINE_CHECKSUMS_FILE="$BUNDLE_DIR/checksums.txt"

  ASSET="tool-1.2.3-linux-amd64.tar.gz"
  CACHED_FILE="$BUNDLE_DIR/binaries/$ASSET"
  echo "payload bytes" >"$CACHED_FILE"
  printf '%s  %s\n' "$(compute_sha256 "$CACHED_FILE")" "$ASSET" >"$OFFLINE_CHECKSUMS_FILE"
}

@test "offline bundle: cached file matching the recorded digest verifies" {
  setup_bundle

  USED_OFFLINE_CACHE=true run verify_release_checksum "$CACHED_FILE" "$ASSET" "" ""
  assert_success
  assert_output --partial "verified from offline bundle"
}

@test "offline bundle: tampered cached file is rejected and deleted" {
  setup_bundle
  echo "tampered" >"$CACHED_FILE"

  USED_OFFLINE_CACHE=true run verify_release_checksum "$CACHED_FILE" "$ASSET" "" ""
  assert_failure
  [[ ! -f "$CACHED_FILE" ]]
}

@test "offline bundle: a freshly downloaded file ignores the bundle digests" {
  setup_bundle

  USED_OFFLINE_CACHE=false run verify_release_checksum "$CACHED_FILE" "$ASSET" "" ""
  [[ "$status" -eq 2 ]]
}

@test "offline bundle: an asset the bundle never recorded falls through" {
  setup_bundle
  local other="$BUNDLE_DIR/binaries/other.tar.gz"
  echo "payload" >"$other"

  USED_OFFLINE_CACHE=true run verify_release_checksum "$other" "other.tar.gz" "" ""
  [[ "$status" -eq 2 ]]
}

# Helper functions

skip_if_not_macos() {
  if [[ "$OSTYPE" != "darwin"* ]]; then
    skip "Test only runs on macOS"
  fi
}
