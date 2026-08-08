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

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  DOTFILES_DIR="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  export DOTFILES_DIR
  export LIB="$DOTFILES_DIR/install/common/lib/installed-versions.sh"

  # report_snapshot_changes lives in update.sh, which runs nothing on source.
  # Same refusal-to-source guard as update-phases.bats: a copy predating the
  # guard would run a full system update per test.
  BATS_FILE_TMPDIR="${BATS_FILE_TMPDIR:-$(mktemp -d)}"
  export REPORT="$BATS_FILE_TMPDIR/report.sh"
  cat >"$REPORT" <<SCRIPT
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
#
# The inherited git environment is cleared first. `-C` changes directory but does
# not override GIT_INDEX_FILE, and pre-commit exports one pointing at its staged
# index of the dotfiles repo — so `git add` here built a tree from *that* index
# inside this throwaway repo's object store and died on blobs it has never seen.
# The tests passed standalone and failed only under the commit hook.
make_checkout() {
  local checkout_dir="$1" content="$2"
  mkdir -p "$checkout_dir"
  echo "$content" >"$checkout_dir/file"
  (
    unset GIT_INDEX_FILE GIT_DIR GIT_WORK_TREE GIT_OBJECT_DIRECTORY \
      GIT_ALTERNATE_OBJECT_DIRECTORIES
    git -C "$checkout_dir" init --quiet
    git -C "$checkout_dir" config user.email test@example.com
    git -C "$checkout_dir" config user.name Test
    git -C "$checkout_dir" add file
    git -C "$checkout_dir" commit --quiet -m "$content"
    git -C "$checkout_dir" rev-parse --short HEAD
  )
}

# Populates a fake `uv tool` layout and echoes the directory to hand to UV_TOOL_DIR.
make_uv_tool() {
  local uv_dir="$1" tool="$2" version="$3" commit="${4:-}"
  local normalized="${tool//[-.]/_}"
  local dist_info="$uv_dir/$tool/lib/python3.13/site-packages/${normalized}-${version}.dist-info"
  mkdir -p "$dist_info"
  if [[ -n "$commit" ]]; then
    echo "{\"url\":\"https://example.com/$tool\",\"vcs_info\":{\"vcs\":\"git\",\"commit_id\":\"$commit\"}}" \
      >"$dist_info/direct_url.json"
  fi
}

# Writes the receipt uv keeps beside an installed tool, for a git requirement.
make_uv_receipt() {
  local uv_dir="$1" tool="$2" git_url="$3"
  mkdir -p "$uv_dir/$tool"
  cat >"$uv_dir/$tool/uv-receipt.toml" <<RECEIPT
[tool]
requirements = [{ name = "$tool", git = "$git_url" }]
entrypoints = [
    { name = "$tool", install-path = "$HOME/.local/bin/$tool", from = "$tool" },
]
RECEIPT
}

# Writes an executable stub and echoes the directory to prepend to PATH.
make_stub() {
  local name="$1" body="$2"
  local stub_dir="$BATS_TEST_TMPDIR/stubs"
  mkdir -p "$stub_dir"
  printf '#!/usr/bin/env bash\n%s\n' "$body" >"$stub_dir/$name"
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

@test "uv_tool_installed_ref: version alone, or version and commit for a git install" {
  local uv_dir="$BATS_TEST_TMPDIR/uv"

  make_uv_tool "$uv_dir" indy 0.1.0 852933d3fbaa0ac3aa1f1024c701ccf5e28e2b25
  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref indy"
  assert_success
  assert_output "0.1.0 (852933d3fbaa)"

  # The commit is what distinguishes two builds of the same version -- without it
  # a rebuilt git tool reads as unchanged.
  rm -rf "${uv_dir:?}/indy"
  make_uv_tool "$uv_dir" indy 0.1.0 bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref indy"
  refute_output "0.1.0 (852933d3fbaa)"

  make_uv_tool "$uv_dir" codespell 2.4.3
  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref codespell"
  assert_output "2.4.3"

  # uv normalizes - and . to _ in the dist-info directory name.
  make_uv_tool "$uv_dir" keymap-align 0.1.0 3e42d3960257000000000000000000000000000f
  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref keymap-align"
  assert_output "0.1.0 (3e42d3960257)"

  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_installed_ref nonexistent"
  assert_failure
  assert_output ""
}

# ================================================================
# uv_tool_pinned_rev
# ================================================================
# The pin, not the installed version, decides whether `uv tool upgrade` can move
# a git-installed tool at all — a pinned tag re-resolves to the same commit and
# exits 0, which is how syncer was reported current eight releases behind.

@test "uv_tool_pinned_rev: the tag from the receipt, wherever rev sits in the URL" {
  local uv_dir="$BATS_TEST_TMPDIR/uv"

  make_uv_receipt "$uv_dir" syncer "https://github.com/datapointchris/syncer.git?rev=v6.0.0"
  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_pinned_rev syncer"
  assert_success
  assert_output "v6.0.0"

  # rev is not always the first query parameter.
  make_uv_receipt "$uv_dir" syncer "https://github.com/datapointchris/syncer.git?subdirectory=cli&rev=v6.0.0"
  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_pinned_rev syncer"
  assert_output "v6.0.0"

  # A branch install is unpinned: a success with no tag, not a failure.
  make_uv_receipt "$uv_dir" relate "https://github.com/datapointchris/relate.git"
  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_pinned_rev relate"
  assert_success
  assert_output ""

  run env UV_TOOL_DIR="$uv_dir" bash -c "source '$LIB'; uv_tool_pinned_rev nonexistent"
  assert_failure
  assert_output ""
}

# ================================================================
# cargo_installed_version
# ================================================================

@test "cargo_installed_version: matches the crate name, never a binary name" {
  local stub_dir
  stub_dir=$(make_stub cargo "$CARGO_LIST_STUB")

  run env PATH="$stub_dir:$PATH" bash -c "source '$LIB'; cargo_installed_version fd-find"
  assert_success
  assert_output "v10.4.2"

  # `fd` is the binary fd-find installs; matching on it reports the wrong crate.
  run env PATH="$stub_dir:$PATH" bash -c "source '$LIB'; cargo_installed_version fd"
  assert_failure

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

@test "go_binary_module_version: the module version, and nothing at all on failure" {
  local stub_dir
  stub_dir=$(make_stub go "$GO_BUILDINFO_STUB")
  touch "$BATS_TEST_TMPDIR/toolbox"

  run env PATH="$stub_dir:$PATH" bash -c \
    "source '$LIB'; go_binary_module_version '$BATS_TEST_TMPDIR/toolbox'"
  assert_success
  assert_output "v1.7.1"

  # A missing binary must not reach go at all, and a binary go cannot read must
  # not leak go's error text as if it were a version.
  stub_dir=$(make_stub go 'echo "go should not have run" >&2; exit 1')
  run env PATH="$stub_dir:$PATH" bash -c \
    "source '$LIB'; go_binary_module_version '$BATS_TEST_TMPDIR/absent'"
  assert_failure
  assert_output ""

  touch "$BATS_TEST_TMPDIR/notgo"
  stub_dir=$(make_stub go 'echo "could not read Go build info" >&2; exit 1')
  run env PATH="$stub_dir:$PATH" bash -c \
    "source '$LIB'; go_binary_module_version '$BATS_TEST_TMPDIR/notgo'"
  assert_failure
  assert_output ""
}

# ================================================================
# git_checkout_commit / git_checkouts_snapshot
# ================================================================

@test "git_checkout_commit: the short HEAD, and failure for anything else" {
  local commit
  commit=$(make_checkout "$BATS_TEST_TMPDIR/plugin" one)

  run bash -c "source '$LIB'; git_checkout_commit '$BATS_TEST_TMPDIR/plugin'"
  assert_success
  assert_output "$commit"

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

  run bash -c "source '$LIB'; git_checkouts_snapshot '$BATS_TEST_TMPDIR/absent'"
  assert_failure
}

# ================================================================
# report_snapshot_changes
# ================================================================

@test "report_snapshot_changes: tells a move, an install, and a removal apart" {
  local snapshot="blink.cmp aaaaaaaaaaaa
telescope.nvim bbbbbbbbbbbb"

  # Unchanged is the case that used to print a success line off an exit code.
  run "$REPORT" "$snapshot" "$snapshot" "Neovim plugins already at latest"
  assert_success
  assert_output --partial "Neovim plugins already at latest"
  refute_output --partial "updated"

  run "$REPORT" "blink.cmp aaaaaaaaaaaa" "blink.cmp cccccccccccc" "already at latest"
  assert_output --partial "blink.cmp updated: aaaaaaaaaaaa → cccccccccccc"
  refute_output --partial "already at latest"

  run "$REPORT" "blink.cmp aaaaaaaaaaaa" "blink.cmp aaaaaaaaaaaa
oil.nvim dddddddddddd" "already at latest"
  assert_output --partial "oil.nvim installed (dddddddddddd)"
  refute_output --partial "updated"

  run "$REPORT" "blink.cmp aaaaaaaaaaaa
oil.nvim dddddddddddd" "blink.cmp aaaaaaaaaaaa" "already at latest"
  assert_output --partial "oil.nvim removed"

  # An empty before-snapshot is a first install, not an update of everything.
  run "$REPORT" "" "blink.cmp aaaaaaaaaaaa" "already at latest"
  assert_output --partial "blink.cmp installed (aaaaaaaaaaaa)"
  refute_output --partial "removed"
}
