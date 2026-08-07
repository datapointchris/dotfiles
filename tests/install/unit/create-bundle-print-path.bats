#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Unit tests for create-bundle.sh: --print-path stream split
# ================================================================
# The point of the flag is that stdout carries the tarball path and nothing
# else, so `ifiles put "$(...)"` receives a usable filename. That contract is
# broken by any log line that forgets to go to stderr, which is invisible until
# something downstream is handed a path with a progress line glued to it.
#
# A real build is not needed to test it: the downloads are stubbed out, and what
# is exercised is the redirect, the ordering, and the tarball naming.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

setup() {
  TEST_DIR=$(mktemp -d)
  SANDBOX_DIR="$TEST_DIR/sandbox"
  STDERR_FILE="$TEST_DIR/stderr.log"
  mkdir -p "$SANDBOX_DIR"

  HELPER_SCRIPT="$TEST_DIR/run-main.sh"
  cat >"$HELPER_SCRIPT" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
export DOTFILES_DIR="$DOTFILES_DIR"
source "\$DOTFILES_DIR/install/offline/create-bundle.sh"

# Point the build at a sandbox only after sourcing, so the shared libraries
# resolve against the repo but the tarball never lands in it.
DOTFILES_DIR="$SANDBOX_DIR"

validate_manifest() { :; }
download_github_releases() { log_info "Downloading GitHub releases..."; }
download_go_binaries() { log_info "Downloading Go tool binaries..."; }
download_cargo_binaries() { log_info "Downloading Cargo tool binaries..."; }
download_install_scripts() { log_info "Downloading install scripts..."; }

main "\$@"
SCRIPT

  chmod +x "$HELPER_SCRIPT"
  export TEST_DIR SANDBOX_DIR STDERR_FILE HELPER_SCRIPT
}

teardown() {
  rm -rf "$TEST_DIR"
}

# Run a build with the two streams kept apart, which is the whole point of the
# flag — merging them here would pass no matter what the script did.
build_capturing_stderr() {
  bash "$HELPER_SCRIPT" --no-cache "$@" 2>"$STDERR_FILE"
}

@test "print-path: stdout is the tarball path and nothing else" {
  run build_capturing_stderr --print-path
  assert_success
  assert_equal "${#lines[@]}" 1
  assert_output --regexp "^${SANDBOX_DIR}/dotfiles-offline-v[0-9]{8}-.*\.tar\.gz$"
}

@test "print-path: the path names a tarball that exists" {
  run build_capturing_stderr --print-path
  assert_success
  [[ -f "$output" ]]

  run tar -tzf "$output"
  assert_success
  assert_output --partial "installers/"
}

@test "print-path: the build log still reaches stderr" {
  run build_capturing_stderr --print-path
  assert_success

  run cat "$STDERR_FILE"
  assert_output --partial "Downloading GitHub releases..."
  assert_output --partial "Bundle created successfully!"
}

@test "print-path: stderr is where the summary path goes, not stdout" {
  run build_capturing_stderr --print-path
  assert_success

  run grep -c "  File: " "$STDERR_FILE"
  assert_output "1"
}

@test "default: without the flag the log stays on stdout" {
  run build_capturing_stderr
  assert_success
  assert_output --partial "Bundle created successfully!"

  run cat "$STDERR_FILE"
  refute_output --partial "Bundle created successfully!"
}
