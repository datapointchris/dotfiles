#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Unit tests for cargo-tools.sh: install_from_cache function
# ================================================================
# Tests the offline cache installation logic for standard single-platform
# tarballs. Fat-zip handling (e.g. broot) is done at bundle creation time
# in create-bundle.sh, so install_from_cache never sees a fat zip.
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

setup() {
  TEST_DIR=$(mktemp -d)
  CACHE_DIR="$TEST_DIR/binaries"
  FAKE_HOME="$TEST_DIR/home"
  mkdir -p "$CACHE_DIR" "$FAKE_HOME/.cargo/bin"
  touch "$FAKE_HOME/.cargo/env"  # empty mock — cargo-tools.sh sources this

  HELPER_SCRIPT="$TEST_DIR/run-fn.sh"
  cat > "$HELPER_SCRIPT" << SCRIPT
#!/usr/bin/env bash
set -euo pipefail
export HOME="$FAKE_HOME"
export OFFLINE_CACHE_DIR="$CACHE_DIR"
export DOTFILES_DIR="$DOTFILES_DIR"
export CARGO_TOOLS_SOURCE_ONLY=true
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"
source "$DOTFILES_DIR/management/common/install/language-tools/cargo-tools.sh"
"\$@"
SCRIPT

  chmod +x "$HELPER_SCRIPT"
  export TEST_DIR CACHE_DIR FAKE_HOME HELPER_SCRIPT
}

teardown() {
  rm -rf "$TEST_DIR"
}

# ================================================================
# Fixture helpers
# ================================================================

# Create a standard single-platform tarball (e.g. bat, eza, broot after
# bundle pre-extraction). Binary sits at the root of the archive.
create_single_tarball() {
  local binary_name="$1" tar_path="$2"
  local build_dir="$TEST_DIR/build-single-$$"
  mkdir -p "$build_dir"
  printf 'SINGLE-PLATFORM-BINARY' > "$build_dir/$binary_name"
  (cd "$build_dir" && tar czf "$tar_path" "$binary_name")
  rm -rf "$build_dir"
}

# ================================================================
# Tests: single-platform tarball (standard Rust tool format)
# ================================================================

@test "cache/tarball: installs binary from standard tarball" {
  create_single_tarball "bat" "$CACHE_DIR/bat_v0.25.0_x86_64-unknown-linux-gnu.tar.gz"

  run bash "$HELPER_SCRIPT" install_from_cache bat bat
  assert_success

  run cat "$FAKE_HOME/.cargo/bin/bat"
  assert_output "SINGLE-PLATFORM-BINARY"
}

@test "cache/tarball: installed binary is executable" {
  create_single_tarball "bat" "$CACHE_DIR/bat_v0.25.0_x86_64-unknown-linux-gnu.tar.gz"

  run bash "$HELPER_SCRIPT" install_from_cache bat bat
  assert_success

  [[ -x "$FAKE_HOME/.cargo/bin/bat" ]]
}

@test "cache/tarball: finds archive by binary name when package name differs" {
  create_single_tarball "fd" "$CACHE_DIR/fd-find_v10.2.0_x86_64-unknown-linux-gnu.tar.gz"

  run bash "$HELPER_SCRIPT" install_from_cache fd-find fd
  assert_success

  run cat "$FAKE_HOME/.cargo/bin/fd"
  assert_output "SINGLE-PLATFORM-BINARY"
}

# ================================================================
# Tests: cache miss
# ================================================================

@test "cache/miss: returns 1 when OFFLINE_CACHE_DIR does not exist" {
  rm -rf "$CACHE_DIR"

  run bash "$HELPER_SCRIPT" install_from_cache broot broot
  assert_failure
}

@test "cache/miss: returns 1 when cache dir exists but has no matching file" {
  run bash "$HELPER_SCRIPT" install_from_cache broot broot
  assert_failure
}

@test "cache/miss: returns 1 when package name does not match any cached file" {
  create_single_tarball "bat" "$CACHE_DIR/bat_v0.25.0_x86_64-unknown-linux-gnu.tar.gz"

  run bash "$HELPER_SCRIPT" install_from_cache completely-different-tool ctdtool
  assert_failure
}

# ================================================================
# Tests: get_target_string
# ================================================================

@test "get_target_string: returns non-empty string" {
  run bash "$HELPER_SCRIPT" get_target_string
  assert_success
  [[ -n "$output" ]]
}

@test "get_target_string: output contains architecture" {
  run bash "$HELPER_SCRIPT" get_target_string
  assert_success
  [[ "$output" == *"x86_64"* || "$output" == *"aarch64"* ]]
}

@test "get_target_string: output matches uname -m on linux" {
  [[ "$(uname -s)" == "Linux" ]] || skip "Linux-only assertion"
  arch=$(uname -m)
  run bash "$HELPER_SCRIPT" get_target_string
  assert_output --partial "$arch"
}
