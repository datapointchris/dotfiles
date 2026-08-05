#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Unit tests for go-tools.sh: install_go_tool
# ================================================================
# Which source wins, and when. The bundle exists for machines that cannot reach
# proxy.golang.org, so an update on one of those has to be able to fall back to
# it — bbkt sat at 1.0.2 on the work box for a week with 2.1.0 in the bundle
# because the cache was consulted on install only.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  DOTFILES_DIR="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  export DOTFILES_DIR
}

setup() {
  TEST_DIR=$(mktemp -d)
  CACHE_DIR="$TEST_DIR/go-binaries"
  GOBIN="$TEST_DIR/bin"
  FAKE_PATH_DIR="$TEST_DIR/fake-path"
  mkdir -p "$CACHE_DIR" "$GOBIN" "$FAKE_PATH_DIR"

  HELPER_SCRIPT="$TEST_DIR/run-fn.sh"
  cat >"$HELPER_SCRIPT" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
export DOTFILES_DIR="$DOTFILES_DIR"
export PATH="$FAKE_PATH_DIR:\$PATH"
# Refuse to source a go-tools.sh that would install on source: without the guard
# this runs go install for every package in packages.yml, once per test.
if ! grep -q 'BASH_SOURCE\[0\]}" == "\${0}' "\$DOTFILES_DIR/install/common/language-tools/go-tools.sh"; then
  echo "refusing to source go-tools.sh: it has no execute-only guard" >&2
  exit 1
fi
source "\$DOTFILES_DIR/install/common/language-tools/go-tools.sh"
"\$@"
SCRIPT
  chmod +x "$HELPER_SCRIPT"

  export TEST_DIR CACHE_DIR GOBIN FAKE_PATH_DIR HELPER_SCRIPT
}

teardown() {
  rm -rf "$TEST_DIR"
}

# A `go` that reports what the real one cannot do here: reach the proxy. The
# succeeding variant writes the binary itself, since that is the only evidence
# that the proxy path — rather than the cache — produced the result.
fake_go_that_installs() {
  cat >"$FAKE_PATH_DIR/go" <<SCRIPT
#!/usr/bin/env bash
touch "$TEST_DIR/go-was-called"
printf 'PROXY-BINARY' >"$GOBIN/tool"
SCRIPT
  chmod +x "$FAKE_PATH_DIR/go"
}

fake_go_that_cannot_reach_the_proxy() {
  cat >"$FAKE_PATH_DIR/go" <<SCRIPT
#!/usr/bin/env bash
touch "$TEST_DIR/go-was-called"
echo "go: module lookup disabled: tls: failed to verify certificate" >&2
exit 1
SCRIPT
  chmod +x "$FAKE_PATH_DIR/go"
}

cache_a_binary() {
  printf 'BUNDLED-BINARY' >"$CACHE_DIR/tool"
}

# ================================================================
# install: the bundle is authoritative
# ================================================================

@test "install: takes the bundled binary without touching the proxy" {
  fake_go_that_installs
  cache_a_binary

  run env UPDATE_MODE=false bash "$HELPER_SCRIPT" \
    install_go_tool example.com/tool "$GOBIN/tool" "$CACHE_DIR/tool"

  assert_success
  assert_equal "$(cat "$GOBIN/tool")" "BUNDLED-BINARY"
  assert [ -x "$GOBIN/tool" ]
  assert [ ! -f "$TEST_DIR/go-was-called" ]
}

@test "install: falls through to the proxy when nothing is bundled" {
  fake_go_that_installs

  run env UPDATE_MODE=false bash "$HELPER_SCRIPT" \
    install_go_tool example.com/tool "$GOBIN/tool" "$CACHE_DIR/tool"

  assert_success
  assert_equal "$(cat "$GOBIN/tool")" "PROXY-BINARY"
  assert [ -f "$TEST_DIR/go-was-called" ]
}

# ================================================================
# update: the proxy is authoritative, the bundle is the fallback
# ================================================================

@test "update: prefers the proxy over a bundle that may be months old" {
  fake_go_that_installs
  cache_a_binary

  run env UPDATE_MODE=true bash "$HELPER_SCRIPT" \
    install_go_tool example.com/tool "$GOBIN/tool" "$CACHE_DIR/tool"

  assert_success
  assert_equal "$(cat "$GOBIN/tool")" "PROXY-BINARY"
}

@test "update: falls back to the bundle when the proxy is unreachable" {
  fake_go_that_cannot_reach_the_proxy
  cache_a_binary
  printf 'STALE-BINARY' >"$GOBIN/tool"

  run env UPDATE_MODE=true bash "$HELPER_SCRIPT" \
    install_go_tool example.com/tool "$GOBIN/tool" "$CACHE_DIR/tool"

  assert_success
  assert_equal "$(cat "$GOBIN/tool")" "BUNDLED-BINARY"
  assert [ -x "$GOBIN/tool" ]
  # The TLS error is still the diagnosis for why the proxy was skipped.
  assert_output --partial "failed to verify certificate"
}

@test "update: fails with go's output when the proxy is unreachable and nothing is bundled" {
  fake_go_that_cannot_reach_the_proxy
  printf 'STALE-BINARY' >"$GOBIN/tool"

  run env UPDATE_MODE=true bash "$HELPER_SCRIPT" \
    install_go_tool example.com/tool "$GOBIN/tool" "$CACHE_DIR/tool"

  assert_failure
  assert_output --partial "failed to verify certificate"
  assert_equal "$(cat "$GOBIN/tool")" "STALE-BINARY"
}

# ================================================================
# install_go_binary_from_cache
# ================================================================

@test "cache copy: lands executable, and survives the binary being in use" {
  cache_a_binary
  # cp onto a running binary fails with ETXTBSY; the copy-then-rename is what
  # makes updating a tool from inside a script that tool is running safe.
  printf 'IN-USE' >"$GOBIN/tool"
  chmod +x "$GOBIN/tool"

  run bash "$HELPER_SCRIPT" install_go_binary_from_cache "$CACHE_DIR/tool" "$GOBIN/tool"

  assert_success
  assert_equal "$(cat "$GOBIN/tool")" "BUNDLED-BINARY"
  assert [ -x "$GOBIN/tool" ]
  assert [ ! -f "$GOBIN/tool.new" ]
}

@test "cache copy: refuses when the bundle has no such binary" {
  run bash "$HELPER_SCRIPT" install_go_binary_from_cache "$CACHE_DIR/absent" "$GOBIN/absent"

  assert_failure
  assert [ ! -f "$GOBIN/absent" ]
}
