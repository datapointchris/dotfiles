#!/usr/bin/env bash
#
# Installing the personal Python CLIs that ship from a git repo rather than PyPI
# (packages.yml `git_uv_tools`).
#
# Usage:
#   source "$DOTFILES_DIR/install/common/lib/uv-git-tools.sh"
#
#   ref=$(uv_git_tool_latest_ref "$repo") || return 1
#   uv tool install "$(uv_git_tool_requirement syncer "$repo" "$ref")"
#
# These installs are pinned to a release tag rather than left tracking the
# default branch, because each tool's own updater reads uv's receipt to decide
# what it may do. pyselfupdate treats a git requirement with no `rev=` as a dev
# checkout: it never prints an update notice for one, and refuses to reinstall
# over it ("installed from a branch rather than a tag"). So a bare
# `uv tool install <url>` produces a tool whose own `update` command is dead —
# and once anything else pins it, `uv tool upgrade` re-resolves that pin to the
# same commit forever and reports "already at latest" however far behind it is.
# syncer sat eight releases back that way while the update phase called it
# current.
#
# Pinning here means dotfiles writes the same receipt shape `<tool> update`
# writes, so the two agree instead of each undoing the other. Both resolve a
# version from the GitHub releases API, so they cannot disagree about which
# release is newest.
#
# packages.yml marks the exception with `tracks_branch: true`: a repo that
# publishes no releases has no tag to pin, so it follows its default branch and
# is upgraded with `uv tool upgrade`.

# Named for this library rather than SCRIPT_DIR, which the sourcing script owns.
UV_GIT_TOOLS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$UV_GIT_TOOLS_LIB_DIR/version-helpers.sh"

# Echoes "owner/name" for a GitHub clone URL, in either the https or ssh form.
# Returns 1 for a URL on any other host, which has no releases API to ask.
#
# The shape is asserted rather than merely "contains a slash, contains no colon".
# That weaker test passed a trailing slash straight through as part of the slug,
# building `/repos/owner/name//releases/latest`, and accepted a three-segment
# path as if it were a repo.
github_slug_from_url() {
  local url="${1%/}"
  url="${url%.git}"
  url="${url#https://github.com/}"
  url="${url#git@github.com:}"
  [[ "$url" =~ ^[^/:]+/[^/:]+$ ]] || return 1
  echo "$url"
}

# Echoes the newest release tag of a git tool's repo, e.g. "v6.0.0". Returns 1
# when the host is not GitHub or the repo has published no release.
uv_git_tool_latest_ref() {
  local repo="$1"
  local slug

  slug=$(github_slug_from_url "$repo") || return 1
  fetch_github_latest_version "$slug"
}

# Echoes the requirement string installing one release of a git tool. The name
# is repeated ahead of the URL so uv records the requirement under the tool's
# own name, which is what makes the receipt readable by `uv_tool_pinned_rev`.
uv_git_tool_requirement() {
  local tool="$1" repo="$2" ref="$3"
  echo "$tool @ git+$repo@$ref"
}
