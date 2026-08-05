#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Unit tests for create-bundle.sh: zip repackaging and target selection
# ================================================================
# Both are pure functions over names and archives, so they are tested without
# building a bundle. What they protect is the offline install: a wrong target
# 404s at bundle time, and a zip layout the repackager cannot read means the
# tool silently never reaches ~/.cargo/bin on the target machine.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

setup() {
  TEST_DIR=$(mktemp -d)

  HELPER_SCRIPT="$TEST_DIR/run-fn.sh"
  cat >"$HELPER_SCRIPT" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
export DOTFILES_DIR="$DOTFILES_DIR"
# Refuse to source a create-bundle.sh that would build a bundle on source —
# every binary in the manifest downloaded once per test.
if ! grep -q 'BASH_SOURCE\[0\]}" == "\${0}' "\$DOTFILES_DIR/install/offline/create-bundle.sh"; then
  echo "refusing to source create-bundle.sh: it has no execute-only guard" >&2
  exit 1
fi
source "\$DOTFILES_DIR/install/offline/create-bundle.sh"
"\$@"
SCRIPT

  chmod +x "$HELPER_SCRIPT"
  export TEST_DIR HELPER_SCRIPT
}

teardown() {
  rm -rf "$TEST_DIR"
}

# ================================================================
# Fixture helpers
# ================================================================

# Single-platform zip (fnm): the bare binary at the archive root.
create_flat_zip() {
  local binary_name="$1" zip_path="$2"
  local build_dir="$TEST_DIR/build-flat-$$"
  mkdir -p "$build_dir"
  printf 'FLAT-ZIP-BINARY' >"$build_dir/$binary_name"
  (cd "$build_dir" && zip -q "$zip_path" "$binary_name")
  rm -rf "$build_dir"
}

# Fat zip (broot): every platform in its own target-named subdirectory.
create_fat_zip() {
  local binary_name="$1" wanted_target="$2" zip_path="$3"
  local build_dir="$TEST_DIR/build-fat-$$"
  mkdir -p "$build_dir/$wanted_target" "$build_dir/some-other-target"
  printf 'WANTED-PLATFORM-BINARY' >"$build_dir/$wanted_target/$binary_name"
  printf 'WRONG-PLATFORM-BINARY' >"$build_dir/some-other-target/$binary_name"
  (cd "$build_dir" && zip -qr "$zip_path" .)
  rm -rf "$build_dir"
}

extract_tarball_binary() {
  local tarball="$1" binary_name="$2"
  local out_dir="$TEST_DIR/unpacked-$$"
  mkdir -p "$out_dir"
  tar -xf "$tarball" -C "$out_dir"
  cat "$out_dir/$binary_name"
}

# ================================================================
# Tests: repackage_zip_as_tarball
# ================================================================

@test "repackage/flat: rewrites a bare-binary zip as a tarball" {
  create_flat_zip "fnm" "$TEST_DIR/fnm-linux.zip"

  run bash "$HELPER_SCRIPT" repackage_zip_as_tarball "$TEST_DIR/fnm-linux.zip" fnm linux 1.39.0
  assert_success
  assert_output "fnm_1.39.0_linux.tar.gz"

  run extract_tarball_binary "$TEST_DIR/fnm_1.39.0_linux.tar.gz" fnm
  assert_output "FLAT-ZIP-BINARY"
}

@test "repackage/fat: picks the requested target out of a fat zip" {
  create_fat_zip "broot" "x86_64-unknown-linux-gnu" "$TEST_DIR/broot_1.56.2.zip"

  run bash "$HELPER_SCRIPT" repackage_zip_as_tarball \
    "$TEST_DIR/broot_1.56.2.zip" broot x86_64-unknown-linux-gnu 1.56.2
  assert_success
  assert_output "broot_1.56.2_x86_64-unknown-linux-gnu.tar.gz"

  run extract_tarball_binary "$TEST_DIR/broot_1.56.2_x86_64-unknown-linux-gnu.tar.gz" broot
  assert_output "WANTED-PLATFORM-BINARY"
}

@test "repackage: consumes the zip so only the tarball is bundled" {
  create_flat_zip "fnm" "$TEST_DIR/fnm-linux.zip"

  run bash "$HELPER_SCRIPT" repackage_zip_as_tarball "$TEST_DIR/fnm-linux.zip" fnm linux 1.39.0
  assert_success

  [[ ! -f "$TEST_DIR/fnm-linux.zip" ]]
}

@test "repackage: fails when the zip holds no binary by that name" {
  create_flat_zip "somethingelse" "$TEST_DIR/fnm-linux.zip"

  run bash "$HELPER_SCRIPT" repackage_zip_as_tarball "$TEST_DIR/fnm-linux.zip" fnm linux 1.39.0
  assert_failure
}

# ================================================================
# Tests: get_cargo_target
# ================================================================

@test "target/default: linux falls back to the gnu triple" {
  run bash "$HELPER_SCRIPT" get_cargo_target linux x86_64 "" ""
  assert_output "x86_64-unknown-linux-gnu"
}

@test "target/default: darwin picks the triple for the arch" {
  run bash "$HELPER_SCRIPT" get_cargo_target darwin arm64 "" ""
  assert_output "aarch64-apple-darwin"

  run bash "$HELPER_SCRIPT" get_cargo_target darwin x86_64 "" ""
  assert_output "x86_64-apple-darwin"
}

@test "target/override: linux override wins and does not leak to darwin" {
  run bash "$HELPER_SCRIPT" get_cargo_target linux x86_64 x86_64-unknown-linux-musl ""
  assert_output "x86_64-unknown-linux-musl"

  run bash "$HELPER_SCRIPT" get_cargo_target darwin arm64 x86_64-unknown-linux-musl ""
  assert_output "aarch64-apple-darwin"
}

@test "target/override: darwin override wins and does not leak to linux" {
  run bash "$HELPER_SCRIPT" get_cargo_target darwin arm64 linux macos
  assert_output "macos"

  run bash "$HELPER_SCRIPT" get_cargo_target linux x86_64 linux macos
  assert_output "linux"
}
