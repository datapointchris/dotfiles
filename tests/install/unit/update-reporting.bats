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

  # report_snapshot_changes lives in update.sh, which runs nothing on source.
  # Same refusal-to-source guard as update-phases.bats: a copy predating the
  # guard would run a full system update per test.
  BATS_FILE_TMPDIR="${BATS_FILE_TMPDIR:-$(mktemp -d)}"
  export REPORT="$BATS_FILE_TMPDIR/report.sh"
  cat > "$REPORT" << SCRIPT
#!/usr/bin/env bash
if ! grep -q 'BASH_SOURCE\[0\]}" == "\${0}' "$DOTFILES_DIR/update.sh"; then
  echo "refusing to source update.sh: it has no execute-only guard" >&2
  exit 1
fi
source "$DOTFILES_DIR/update.sh"
report_snapshot_changes "\$1" "\$2" "\$3"
SCRIPT
  chmod +x "$REPORT"
}

# Creates a git checkout with one commit and echoes its short HEAD.
make_checkout() {
  local checkout_dir="$1" content="$2"
  mkdir -p "$checkout_dir"
  git -C "$checkout_dir" init --quiet
  git -C "$checkout_dir" config user.email test@example.com
  git -C "$checkout_dir" config user.name Test
  echo "$content" > "$checkout_dir/file"
  git -C "$checkout_dir" add file
  git -C "$checkout_dir" commit --quiet -m "$content"
  git -C "$checkout_dir" rev-parse --short HEAD
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
# go_binary_module_version
# ================================================================
# The version this replaced ran the tool and grepped the first version-shaped
# token out of whatever it printed, which is the Go toolchain version for any
# tool whose --version says "built with go1.x".

GO_BUILDINFO_STUB='printf "toolbox: go1.26.5\n\tpath\tgithub.com/datapointchris/toolbox\n\tmod\tgithub.com/datapointchris/toolbox\tv1.7.1\th1:abc=\n\tdep\tgithub.com/spf13/cobra\tv1.10.2\th1:def=\n"'

@test "go_binary_module_version: reports the module version, not the toolchain or a dep" {
  local stub_dir
  stub_dir=$(make_stub go "$GO_BUILDINFO_STUB")
  touch "$BATS_TEST_TMPDIR/toolbox"

  run env PATH="$stub_dir:$PATH" bash -c \
    "source '$LIB'; go_binary_module_version '$BATS_TEST_TMPDIR/toolbox'"
  assert_success
  assert_output "v1.7.1"
}

@test "go_binary_module_version: a binary with no build info fails" {
  local stub_dir
  stub_dir=$(make_stub go 'echo "could not read Go build info" >&2; exit 1')
  touch "$BATS_TEST_TMPDIR/notgo"

  run env PATH="$stub_dir:$PATH" bash -c \
    "source '$LIB'; go_binary_module_version '$BATS_TEST_TMPDIR/notgo'"
  assert_failure
  assert_output ""
}

@test "go_binary_module_version: a missing binary fails without invoking go" {
  local stub_dir
  stub_dir=$(make_stub go 'echo "go should not have run" >&2; exit 1')

  run env PATH="$stub_dir:$PATH" bash -c \
    "source '$LIB'; go_binary_module_version '$BATS_TEST_TMPDIR/absent'"
  assert_failure
  assert_output ""
}

# ================================================================
# git_checkout_commit / git_checkouts_snapshot
# ================================================================

@test "git_checkout_commit: reports the short HEAD of a checkout" {
  local commit
  commit=$(make_checkout "$BATS_TEST_TMPDIR/plugin" one)

  run bash -c "source '$LIB'; git_checkout_commit '$BATS_TEST_TMPDIR/plugin'"
  assert_success
  assert_output "$commit"
}

@test "git_checkout_commit: a directory that is not a checkout fails" {
  mkdir -p "$BATS_TEST_TMPDIR/plain"

  run bash -c "source '$LIB'; git_checkout_commit '$BATS_TEST_TMPDIR/plain'"
  assert_failure
  assert_output ""
}

@test "git_checkouts_snapshot: one sorted line per checkout, skipping non-checkouts" {
  local plugins="$BATS_TEST_TMPDIR/plugins"
  local yank_commit resurrect_commit
  yank_commit=$(make_checkout "$plugins/tmux-yank" yank)
  resurrect_commit=$(make_checkout "$plugins/tmux-resurrect" resurrect)
  mkdir -p "$plugins/not-a-checkout"

  run bash -c "source '$LIB'; git_checkouts_snapshot '$plugins'"
  assert_success
  assert_line --index 0 "tmux-resurrect $resurrect_commit"
  assert_line --index 1 "tmux-yank $yank_commit"
  refute_output --partial "not-a-checkout"
}

@test "git_checkouts_snapshot: a missing parent directory fails" {
  run bash -c "source '$LIB'; git_checkouts_snapshot '$BATS_TEST_TMPDIR/absent'"
  assert_failure
}

# ================================================================
# report_snapshot_changes
# ================================================================

@test "report_snapshot_changes: identical snapshots report the up-to-date message" {
  local snapshot="blink.cmp aaaaaaaaaaaa
telescope.nvim bbbbbbbbbbbb"

  run "$REPORT" "$snapshot" "$snapshot" "Neovim plugins already at latest"
  assert_success
  assert_output --partial "Neovim plugins already at latest"
  refute_output --partial "updated"
}

@test "report_snapshot_changes: a moved commit reports both sides" {
  run "$REPORT" "blink.cmp aaaaaaaaaaaa" "blink.cmp cccccccccccc" "already at latest"
  assert_success
  assert_output --partial "blink.cmp updated: aaaaaaaaaaaa → cccccccccccc"
  refute_output --partial "already at latest"
}

@test "report_snapshot_changes: an added entry is not reported as an update" {
  run "$REPORT" "blink.cmp aaaaaaaaaaaa" "blink.cmp aaaaaaaaaaaa
oil.nvim dddddddddddd" "already at latest"
  assert_success
  assert_output --partial "oil.nvim installed (dddddddddddd)"
  refute_output --partial "updated"
}

@test "report_snapshot_changes: a removed entry is reported as removed" {
  run "$REPORT" "blink.cmp aaaaaaaaaaaa
oil.nvim dddddddddddd" "blink.cmp aaaaaaaaaaaa" "already at latest"
  assert_success
  assert_output --partial "oil.nvim removed"
  refute_output --partial "already at latest"
}

@test "report_snapshot_changes: an empty before snapshot reports installs, not updates" {
  run "$REPORT" "" "blink.cmp aaaaaaaaaaaa" "already at latest"
  assert_success
  assert_output --partial "blink.cmp installed (aaaaaaaaaaaa)"
  refute_output --partial "removed"
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
