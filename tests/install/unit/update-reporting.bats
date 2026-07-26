#!/usr/bin/env bats
# ================================================================
# Unit tests for update.sh result reporting
# ================================================================
# Every phase used to print a success line off an exit code, and `uv tool
# upgrade`, `cargo binstall`, and `npm update -g` all exit 0 for a no-op — so a
# no-op, a real upgrade, and a failure were indistinguishable in the output.
# These lock down the two mechanisms that replaced that: the installed-state
# queries a phase diffs, and the theme/font delegation contract.
#
# Environment reaches the code under test through `env` rather than an `export`
# in the test body: bats runs each @test in a subshell, so an exported value is
# both invisible to shellcheck's dataflow and easy to leak between tests.
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  DOTFILES_DIR="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  export DOTFILES_DIR
  export LIB="$DOTFILES_DIR/install/common/lib/installed-versions.sh"
}

# Populates a fake `uv tool` layout and echoes the directory to hand to UV_TOOL_DIR.
make_uv_tool() {
  local uv_dir="$1" tool="$2" version="$3" commit="${4:-}"
  local normalized="${tool//[-.]/_}"
  local dist_info="$uv_dir/$tool/lib/python3.13/site-packages/${normalized}-${version}.dist-info"
  mkdir -p "$dist_info"
  if [[ -n "$commit" ]]; then
    echo "{\"url\":\"https://example.com/$tool\",\"vcs_info\":{\"vcs\":\"git\",\"commit_id\":\"$commit\"}}" \
      > "$dist_info/direct_url.json"
  fi
}

# Writes an executable stub and echoes the directory to prepend to PATH.
make_stub() {
  local name="$1" body="$2"
  local stub_dir="$BATS_TEST_TMPDIR/stubs"
  mkdir -p "$stub_dir"
  printf '#!/usr/bin/env bash\n%s\n' "$body" > "$stub_dir/$name"
  chmod +x "$stub_dir/$name"
  echo "$stub_dir"
}

CARGO_LIST_STUB='cat << LIST
bat v0.26.1:
    bat
fd-find v10.4.2:
    fd
ripgrep v15.2.0:
    rg
LIST'

# ================================================================
# uv_tool_installed_ref
# ================================================================

@test "uv_tool_installed_ref: a git-installed tool reports version and commit" {
  local uv_dir="$BATS_TEST_TMPDIR/uv"
  make_uv_tool "$uv_dir" indy 0.1.0 852933d3fbaa0ac3aa1f1024c701ccf5e28e2b25

  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref indy"
  assert_success
  assert_output "0.1.0 (852933d3fbaa)"
}

@test "uv_tool_installed_ref: the commit distinguishes builds sharing a version" {
  local uv_dir="$BATS_TEST_TMPDIR/uv"
  make_uv_tool "$uv_dir" indy 0.1.0 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref indy"
  local before="$output"

  rm -rf "${uv_dir:?}/indy"
  make_uv_tool "$uv_dir" indy 0.1.0 bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref indy"

  refute_output "$before"
}

@test "uv_tool_installed_ref: an index-installed tool reports the version alone" {
  local uv_dir="$BATS_TEST_TMPDIR/uv"
  make_uv_tool "$uv_dir" codespell 2.4.3

  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref codespell"
  assert_success
  assert_output "2.4.3"
}

@test "uv_tool_installed_ref: a hyphenated name matches its normalized dist-info" {
  local uv_dir="$BATS_TEST_TMPDIR/uv"
  make_uv_tool "$uv_dir" keymap-align 0.1.0 3e42d3960257000000000000000000000000000f

  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref keymap-align"
  assert_success
  assert_output "0.1.0 (3e42d3960257)"
}

@test "uv_tool_installed_ref: an uninstalled tool fails rather than echoing empty" {
  local uv_dir="$BATS_TEST_TMPDIR/uv"
  mkdir -p "$uv_dir"

  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref nonexistent"
  assert_failure
  assert_output ""
}

# ================================================================
# cargo_installed_version
# ================================================================

@test "cargo_installed_version: reports the version of an installed crate" {
  local stub_dir
  stub_dir=$(make_stub cargo "$CARGO_LIST_STUB")

  run env PATH="$stub_dir:$PATH" bash -c "source '$LIB'; cargo_installed_version fd-find"
  assert_success
  assert_output "v10.4.2"
}

@test "cargo_installed_version: a crate name is not matched by a binary name" {
  local stub_dir
  stub_dir=$(make_stub cargo "$CARGO_LIST_STUB")

  run env PATH="$stub_dir:$PATH" bash -c "source '$LIB'; cargo_installed_version fd"
  assert_failure
}

@test "cargo_installed_version: an uninstalled crate fails" {
  local stub_dir
  stub_dir=$(make_stub cargo "$CARGO_LIST_STUB")

  run env PATH="$stub_dir:$PATH" bash -c "source '$LIB'; cargo_installed_version nonexistent-crate"
  assert_failure
  assert_output ""
}

# ================================================================
# npm_global_versions
# ================================================================

@test "npm_global_versions: emits one sorted name/version pair per package" {
  local stub_dir
  stub_dir=$(make_stub npm \
    "echo '{\"dependencies\":{\"prettier\":{\"version\":\"3.9.6\"},\"eslint\":{\"version\":\"10.8.0\"},\"broken\":{}}}'")

  run env PATH="$stub_dir:$PATH" bash -c "source '$LIB'; npm_global_versions"
  assert_success
  assert_line --index 0 "broken unknown"
  assert_line --index 1 "eslint 10.8.0"
  assert_line --index 2 "prettier 3.9.6"
}

# ================================================================
# theme/font --update delegation
# ================================================================
# The installers must not re-derive a result. Matching on the tool's output was
# how `theme upgraded` came to be printed on every run, and swallowing the exit
# code hid genuine failures from run-installer.sh entirely.

@test "theme.sh --update: passes the tool's own no-op report through" {
  local stub_dir
  stub_dir=$(make_stub theme 'echo "✓ theme already at latest: v4.10.0"')

  run env PATH="$stub_dir:$PATH" bash "$DOTFILES_DIR/install/common/custom-installers/theme.sh" --update
  assert_success
  assert_output --partial "already at latest: v4.10.0"
  refute_output --partial "theme upgraded"
}

@test "theme.sh --update: propagates a failing upgrade" {
  local stub_dir
  stub_dir=$(make_stub theme 'echo "✗ theme upgrade failed: could not fetch from remote" >&2; exit 1')

  run env PATH="$stub_dir:$PATH" bash "$DOTFILES_DIR/install/common/custom-installers/theme.sh" --update
  assert_failure
  assert_output --partial "could not fetch from remote"
}

@test "theme.sh --update: skips cleanly when theme is not installed" {
  run env PATH="/usr/bin:/bin" bash "$DOTFILES_DIR/install/common/custom-installers/theme.sh" --update
  assert_success
  assert_output --partial "not installed"
}

@test "font.sh --update: passes the tool's own no-op report through" {
  local stub_dir
  stub_dir=$(make_stub font 'echo "✓ font already at latest: v3.1.0"')

  run env PATH="$stub_dir:$PATH" bash "$DOTFILES_DIR/install/common/custom-installers/font.sh" --update
  assert_success
  assert_output --partial "already at latest: v3.1.0"
  refute_output --partial "font upgraded"
}

@test "font.sh --update: propagates a failing upgrade" {
  local stub_dir
  stub_dir=$(make_stub font 'echo "✗ font upgrade failed: no releases found" >&2; exit 1')

  run env PATH="$stub_dir:$PATH" bash "$DOTFILES_DIR/install/common/custom-installers/font.sh" --update
  assert_failure
  assert_output --partial "no releases found"
}
