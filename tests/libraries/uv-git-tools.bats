#!/usr/bin/env bats
#
# Tests for uv-git-tools.sh library
#
# The library exists so a git-installed Python tool is pinned to a release tag
# rather than left tracking a branch — an unpinned install has the tool's own
# update notice disabled, and once pinned by anything else, `uv tool upgrade`
# re-resolves the pin forever and reports "already at latest" however far behind
# it is. These lock down the URL parsing and the requirement string, which are
# what decide whether the receipt comes out pinned.

setup() {
  load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."
  source "$DOTFILES_DIR/install/common/lib/uv-git-tools.sh"
}

# Stubs curl on PATH and echoes nothing; the release lookup runs for real against
# it, rather than replacing the function under test with one that returns a tag.
stub_releases_api() {
  local body="$1"
  local stub_dir="$BATS_TEST_TMPDIR/stubs"
  mkdir -p "$stub_dir"
  printf '#!/usr/bin/env bash\nprintf %%s %s\n' "'$body'" >"$stub_dir/curl"
  chmod +x "$stub_dir/curl"
  PATH="$stub_dir:$PATH"
}

@test "github_slug_from_url: owner/name from any GitHub clone URL, and only GitHub" {
  run github_slug_from_url "https://github.com/datapointchris/syncer.git"
  assert_success
  assert_output "datapointchris/syncer"

  run github_slug_from_url "https://github.com/datapointchris/relate"
  assert_output "datapointchris/relate"

  run github_slug_from_url "git@github.com:datapointchris/syncer.git"
  assert_output "datapointchris/syncer"

  # Another host must fail rather than echo a slug the caller would then query
  # against GitHub.
  run github_slug_from_url "https://gitlab.com/datapointchris/syncer.git"
  assert_failure
  assert_output ""

  run github_slug_from_url "https://github.com/syncer"
  assert_failure
}

@test "uv_git_tool_latest_ref: the release tag, and nothing without one" {
  stub_releases_api '{"tag_name": "v6.0.0"}'
  run uv_git_tool_latest_ref "https://github.com/datapointchris/syncer.git"
  assert_success
  assert_output "v6.0.0"

  stub_releases_api '{}'
  run uv_git_tool_latest_ref "https://github.com/datapointchris/keymap-align.git"
  assert_failure
  assert_output ""

  # The stub would answer with a tag, so success here would mean the host check
  # was skipped and some other repo's release used.
  stub_releases_api '{"tag_name": "v9.9.9"}'
  run uv_git_tool_latest_ref "https://gitlab.com/datapointchris/syncer.git"
  assert_failure
  assert_output ""
}

@test "uv_git_tool_requirement: names the tool ahead of the pinned URL" {
  run uv_git_tool_requirement syncer "https://github.com/datapointchris/syncer.git" v6.0.0
  assert_success
  assert_output "syncer @ git+https://github.com/datapointchris/syncer.git@v6.0.0"

  run uv_git_tool_requirement keymap-align "https://github.com/datapointchris/keymap-align.git" v1.0.0
  assert_output "keymap-align @ git+https://github.com/datapointchris/keymap-align.git@v1.0.0"
}
