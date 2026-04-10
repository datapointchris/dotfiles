#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Unit tests for cargo-tools.sh: install_from_cache function
# ================================================================
# Tests the offline cache installation logic, with specific focus
# on broot's non-standard "fat zip" format (one zip, all platforms
# in subdirs named by target triple). This format burned us twice:
#   1. Wrong binary_pattern in packages.yml (target vs version_num)
#   2. Non-deterministic arch selection from multi-platform zip
#
# Each test runs cargo-tools.sh in a subprocess via HELPER_SCRIPT,
# which mocks HOME and OFFLINE_CACHE_DIR to isolated temp dirs.
# CARGO_TOOLS_SOURCE_ONLY=true prevents the install loop from running.
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."

  if ! command -v zip >/dev/null 2>&1; then
    skip "zip not installed"
  fi
  if ! command -v unzip >/dev/null 2>&1; then
    skip "unzip not installed"
  fi
}

setup() {
  TEST_DIR=$(mktemp -d)
  CACHE_DIR="$TEST_DIR/binaries"
  FAKE_HOME="$TEST_DIR/home"
  mkdir -p "$CACHE_DIR" "$FAKE_HOME/.cargo/bin"
  touch "$FAKE_HOME/.cargo/env"  # empty mock — cargo-tools.sh sources this

  # Create a subprocess helper that sources cargo-tools.sh with a mocked
  # environment and then calls whatever function is passed as $@.
  HELPER_SCRIPT="$TEST_DIR/run-fn.sh"
  cat > "$HELPER_SCRIPT" << SCRIPT
#!/usr/bin/env bash
set -euo pipefail
export HOME="$FAKE_HOME"
export OFFLINE_CACHE_DIR="$CACHE_DIR"
export DOTFILES_DIR="$DOTFILES_DIR"
export CARGO_TOOLS_SOURCE_ONLY=true
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
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

# Create a broot-style fat zip: one zip containing binaries for all platforms
# in subdirectories named by Rust target triple. Each fake binary is a plain
# text marker so tests can assert which one was installed.
create_fat_zip() {
  local binary_name="$1" zip_path="$2"
  local build_dir="$TEST_DIR/build-fat-$$"
  mkdir -p "$build_dir"

  local platforms=(
    x86_64-unknown-linux-gnu
    x86_64-unknown-linux-musl
    aarch64-unknown-linux-gnu
    x86_64-apple-darwin
    aarch64-apple-darwin
  )
  for platform in "${platforms[@]}"; do
    mkdir -p "$build_dir/$platform"
    printf 'BINARY-FOR-%s' "$platform" > "$build_dir/$platform/$binary_name"
  done

  (cd "$build_dir" && zip -qr "$zip_path" .)
  rm -rf "$build_dir"
}

# Create a standard single-platform tarball (e.g. bat, eza).
# Binary sits at the root of the archive.
create_single_tarball() {
  local binary_name="$1" tar_path="$2"
  local build_dir="$TEST_DIR/build-single-$$"
  mkdir -p "$build_dir"
  printf 'SINGLE-PLATFORM-BINARY' > "$build_dir/$binary_name"
  (cd "$build_dir" && tar czf "$tar_path" "$binary_name")
  rm -rf "$build_dir"
}

# ================================================================
# Tests: fat zip (broot-style, multiple platforms in one zip)
# ================================================================

@test "cache/fat-zip: installs binary matching current target" {
  create_fat_zip "broot" "$CACHE_DIR/broot_1.56.2.zip"

  run bash "$HELPER_SCRIPT" install_from_cache broot broot
  assert_success

  expected_target=$(bash "$HELPER_SCRIPT" get_target_string)
  run cat "$FAKE_HOME/.cargo/bin/broot"
  assert_output --partial "$expected_target"
}

@test "cache/fat-zip: does not install aarch64 binary on x86_64" {
  [[ "$(uname -m)" == "x86_64" ]] || skip "x86_64-only assertion"
  create_fat_zip "broot" "$CACHE_DIR/broot_1.56.2.zip"

  run bash "$HELPER_SCRIPT" install_from_cache broot broot
  assert_success

  run cat "$FAKE_HOME/.cargo/bin/broot"
  refute_output --partial "aarch64"
}

@test "cache/fat-zip: does not install darwin binary on linux" {
  [[ "$(uname -s)" == "Linux" ]] || skip "Linux-only assertion"
  create_fat_zip "broot" "$CACHE_DIR/broot_1.56.2.zip"

  run bash "$HELPER_SCRIPT" install_from_cache broot broot
  assert_success

  run cat "$FAKE_HOME/.cargo/bin/broot"
  refute_output --partial "darwin"
}

@test "cache/fat-zip: installed binary is executable" {
  create_fat_zip "broot" "$CACHE_DIR/broot_1.56.2.zip"

  run bash "$HELPER_SCRIPT" install_from_cache broot broot
  assert_success

  [[ -x "$FAKE_HOME/.cargo/bin/broot" ]]
}

@test "cache/fat-zip: falls back to any binary when no target matches" {
  # Zip contains only one platform dir that won't match any target string
  local build_dir="$TEST_DIR/build-exotic-$$"
  mkdir -p "$build_dir/exotic-unknown-TempleOS"
  printf 'FALLBACK-BINARY' > "$build_dir/exotic-unknown-TempleOS/mytool"
  (cd "$build_dir" && zip -qr "$CACHE_DIR/mytool_v1.0.0.zip" .)
  rm -rf "$build_dir"

  run bash "$HELPER_SCRIPT" install_from_cache mytool mytool
  assert_success

  run cat "$FAKE_HOME/.cargo/bin/mytool"
  assert_output "FALLBACK-BINARY"
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

# ================================================================
# Tests: cache miss
# ================================================================

@test "cache/miss: returns 1 when OFFLINE_CACHE_DIR does not exist" {
  rm -rf "$CACHE_DIR"

  run bash "$HELPER_SCRIPT" install_from_cache broot broot
  assert_failure
}

@test "cache/miss: returns 1 when cache dir exists but has no matching file" {
  # Cache dir is empty
  run bash "$HELPER_SCRIPT" install_from_cache broot broot
  assert_failure
}

@test "cache/miss: returns 1 when package name does not match any cached file" {
  create_fat_zip "broot" "$CACHE_DIR/broot_1.56.2.zip"

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
