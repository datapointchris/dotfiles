#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Unit tests for cargo-tools.sh: install_from_cache function
# ================================================================
# Tests the offline cache installation logic for standard single-platform
# tarballs. Fat-zip handling (e.g. broot) is done at bundle creation time
# in create-bundle.sh, so install_from_cache never sees a fat zip.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

setup() {
  TEST_DIR=$(mktemp -d)
  CACHE_DIR="$TEST_DIR/binaries"
  FAKE_HOME="$TEST_DIR/home"
  mkdir -p "$CACHE_DIR" "$FAKE_HOME/.cargo/bin"
  touch "$FAKE_HOME/.cargo/env" # empty mock — cargo-tools.sh sources this

  HELPER_SCRIPT="$TEST_DIR/run-fn.sh"
  cat >"$HELPER_SCRIPT" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
export HOME="$FAKE_HOME"
export OFFLINE_CACHE_DIR="$CACHE_DIR"
export DOTFILES_DIR="$DOTFILES_DIR"
# Refuse to source a cargo-tools.sh that would install on source. Without this a
# copy predating the guard runs cargo binstall for every package in packages.yml
# once per test — the failure mode that hit update.sh when a pre-commit stash
# rolled it back to a version with no guard.
if ! grep -q 'BASH_SOURCE\[0\]}" == "\${0}' "$DOTFILES_DIR/install/common/language-tools/cargo-tools.sh"; then
  echo "refusing to source cargo-tools.sh: it has no execute-only guard" >&2
  exit 1
fi
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
source "$DOTFILES_DIR/install/common/language-tools/cargo-tools.sh"
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
  printf 'SINGLE-PLATFORM-BINARY' >"$build_dir/$binary_name"
  (cd "$build_dir" && tar czf "$tar_path" "$binary_name")
  rm -rf "$build_dir"
}

# ================================================================
# install_from_cache
# ================================================================
# Grouped by outcome rather than by archive name: what matters is that the
# lookup finds the cached archive under each naming scheme create-bundle.sh
# produces, and refuses to install anything when it does not.

@test "cache/hit: finds the archive under every naming scheme, executable" {
  create_single_tarball "bat" "$CACHE_DIR/bat_v0.25.0_x86_64-unknown-linux-gnu.tar.gz"
  run bash "$HELPER_SCRIPT" install_from_cache bat bat
  assert_success
  assert_equal "$(cat "$FAKE_HOME/.cargo/bin/bat")" "SINGLE-PLATFORM-BINARY"
  assert [ -x "$FAKE_HOME/.cargo/bin/bat" ]

  # fnm's release assets are fnm-linux.zip / fnm-macos.zip, so the repackaged
  # tarball carries the OS word and no target-triple pattern matches it.
  create_single_tarball "fnm" "$CACHE_DIR/fnm_1.39.0_linux.tar.gz"
  run bash "$HELPER_SCRIPT" install_from_cache fnm fnm
  assert_success
  assert_equal "$(cat "$FAKE_HOME/.cargo/bin/fnm")" "SINGLE-PLATFORM-BINARY"

  # The crate and the binary it installs are not always the same name.
  create_single_tarball "fd" "$CACHE_DIR/fd-find_v10.2.0_x86_64-unknown-linux-gnu.tar.gz"
  run bash "$HELPER_SCRIPT" install_from_cache fd-find fd
  assert_success
  assert_equal "$(cat "$FAKE_HOME/.cargo/bin/fd")" "SINGLE-PLATFORM-BINARY"
}

@test "cache/miss: fails rather than installing when nothing matches" {
  run bash "$HELPER_SCRIPT" install_from_cache broot broot
  assert_failure

  create_single_tarball "bat" "$CACHE_DIR/bat_v0.25.0_x86_64-unknown-linux-gnu.tar.gz"
  run bash "$HELPER_SCRIPT" install_from_cache completely-different-tool ctdtool
  assert_failure

  rm -rf "$CACHE_DIR"
  run bash "$HELPER_SCRIPT" install_from_cache broot broot
  assert_failure
}

@test "get_target_string: a triple carrying this machine's architecture" {
  run bash "$HELPER_SCRIPT" get_target_string
  assert_success
  assert_output --regexp '(x86_64|aarch64)'

  if [[ "$(uname -s)" == "Linux" ]]; then
    assert_output --partial "$(uname -m)"
  fi
}
