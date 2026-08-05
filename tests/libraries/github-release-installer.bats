#!/usr/bin/env bats
#
# Tests for github-release-installer.sh library
#
# Tests core functions for GitHub release installation

setup() {
  load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."

  # Source dependencies first
  source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
  source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"

  # Source library under test
  source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"
}

# get_platform_arch tests

@test "get_platform_arch picks the darwin triple, whatever the case of the names" {
  skip_if_not_macos

  run get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64"
  assert_success
  assert_output --regexp "Darwin_(x86_64|arm64)"

  run get_platform_arch "darwin_x86_64" "darwin_arm64" "linux_x86_64"
  assert_success
  assert_output --regexp "darwin_(x86_64|arm64)"
}

# get_latest_version tests
#
# These stub the fetch rather than calling GitHub. The wrapper's whole job is to
# turn a failed fetch into a logged non-zero exit, and asserting that against the
# live API tested GitHub's uptime, cost a network round trip per commit, and
# failed outright behind the work firewall.

# Answers the releases API with a fixed body, the way uv-git-tools.bats does.
# Stubbing curl rather than the fetch function keeps the jq parse and the
# empty/null handling inside version-helpers.sh under test.
stub_releases_api() {
  local body="$1"
  local stub_dir="$BATS_TEST_TMPDIR/stubs"
  mkdir -p "$stub_dir"
  printf '#!/usr/bin/env bash\nprintf %%s %s\n' "'$body'" >"$stub_dir/curl"
  chmod +x "$stub_dir/curl"
  PATH="$stub_dir:$PATH"
}

@test "get_latest_version passes a fetched version through" {
  stub_releases_api '{"tag_name": "v1.2.3"}'

  run get_latest_version "owner/repo"
  assert_success
  assert_output "v1.2.3"
}

@test "get_latest_version fails rather than echoing an empty version" {
  # The bug this guards: a caller doing VERSION=$(get_latest_version ...) with no
  # exit guard built ".../releases/download//tool_.tar.gz" and downloaded nothing.
  stub_releases_api '{}'

  run get_latest_version "owner/repo"
  assert_failure
  # It logs the failure, so the assertion is that no version came out with it.
  assert_output --partial "Failed to fetch latest version"
  refute_output --regexp 'v[0-9]'
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

# Release-asset URL parsing
#
# install_from_tarball derives repo and tag from the download URL so that every
# existing caller gains private-repo support without a signature change. A
# nested module's tag contains a slash (cli/v1.2.0), which is the case most
# likely to be parsed wrong -- the tag is everything between /releases/download/
# and the final filename segment, not the single segment after it.
#
# This calls the library's parser. The version it replaced defined its own copy
# of the regex in the test file, so the two could drift apart and the test would
# still pass.

@test "release url parsing: repo and tag, including a tag with slashes in it" {
  run parse_github_release_url "https://github.com/owner/repo/releases/download/v1.2.0/tool_1.2.0_linux_amd64.tar.gz"
  assert_success
  assert_output "owner/repo|v1.2.0"

  run parse_github_release_url "https://github.com/datapointchris/nomad/releases/download/cli/v0.1.0/nomad_0.1.0_darwin_amd64.tar.gz"
  assert_success
  assert_output "datapointchris/nomad|cli/v0.1.0"

  # A non-GitHub source echoes nothing, which is how callers tell it apart.
  run parse_github_release_url "https://example.com/some/file.tar.gz"
  assert_output ""
}

@test "checksum lookup: case-insensitive on the asset name, empty when absent" {
  local checksums="$BATS_TEST_TMPDIR/checksums.txt"
  local digest
  digest=$(printf 'a%.0s' {1..64})
  printf '%s  %s\n' "$digest" "lazygit_0.63.1_linux_x86_64.tar.gz" >"$checksums"

  run checksum_for_asset "$checksums" "lazygit_0.63.1_Linux_x86_64.tar.gz"
  assert_success
  assert_output "$digest"

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

@test "offline bundle: verifies, rejects a tamper, and defers when it should" {
  setup_bundle

  USED_OFFLINE_CACHE=true run verify_release_checksum "$CACHED_FILE" "$ASSET" "" ""
  assert_success
  assert_output --partial "verified from offline bundle"

  # A fresh download is not the bundle's business: status 2 means "not mine".
  USED_OFFLINE_CACHE=false run verify_release_checksum "$CACHED_FILE" "$ASSET" "" ""
  assert_equal "$status" 2

  local other="$BUNDLE_DIR/binaries/other.tar.gz"
  echo "payload" >"$other"
  USED_OFFLINE_CACHE=true run verify_release_checksum "$other" "other.tar.gz" "" ""
  assert_equal "$status" 2

  # Tampering is checked last: it deletes the cached file on the way out.
  echo "tampered" >"$CACHED_FILE"
  USED_OFFLINE_CACHE=true run verify_release_checksum "$CACHED_FILE" "$ASSET" "" ""
  assert_failure
  assert [ ! -f "$CACHED_FILE" ]
}

# Helper functions

skip_if_not_macos() {
  if [[ "$OSTYPE" != "darwin"* ]]; then
    skip "Test only runs on macOS"
  fi
}
