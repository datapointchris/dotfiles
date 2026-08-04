#!/usr/bin/env bash
#
# Queries for what is currently installed, one per distribution mechanism.
#
# Usage:
#   source "$DOTFILES_DIR/install/common/lib/installed-versions.sh"
#
#   before=$(uv_tool_installed_ref indy) || before=""
#   uv tool upgrade indy
#   after=$(uv_tool_installed_ref indy) || after=""
#
# These exist for the update commands that exit 0 whether or not anything
# changed and print nothing distinguishing — `uv tool upgrade`, `cargo binstall`,
# `npm update -g`, tpm's `update_plugins`, `:Lazy update`. For those, observed
# state is the only thing that separates "updated" from "nothing to do".
#
# Not everything needs one. brew/pacman/apt, rustup, `uv self update`, and the
# `theme`/`font` update commands all report their own outcome accurately, and
# the GitHub release installers compare the installed version against the release
# tag before downloading. Re-deriving a result those already state is duplicated
# logic that can only drift away from the truth.

# Whether uv has this tool at all. Distinct from uv_tool_installed_ref failing,
# which also covers an installed tool whose dist-info could not be read — an
# update should still run for that one.
uv_tool_is_installed() {
  [[ -d "${UV_TOOL_DIR:-$HOME/.local/share/uv/tools}/$1" ]]
}

# Echoes "<version> (<commit>)" for a git-installed tool, or "<version>" for one
# from an index. Returns 1 when the tool has no installed record.
#
# Read from the dist-info directory and its PEP 610 direct_url.json — the commit
# is the load-bearing half for the git-installed tools, whose version string
# routinely stays put across real upgrades.
uv_tool_installed_ref() {
  local tool="$1"
  local tool_dir="${UV_TOOL_DIR:-$HOME/.local/share/uv/tools}/$tool"

  local normalized="${tool//[-.]/_}"
  local dist_info_dirs=("$tool_dir"/lib/python*/site-packages/"$normalized"-*.dist-info)
  local dist_info="${dist_info_dirs[0]}"
  [[ -d "$dist_info" ]] || return 1

  local version
  version=$(basename "$dist_info")
  version="${version#"${normalized}"-}"
  version="${version%.dist-info}"

  local direct_url="$dist_info/direct_url.json"
  if [[ -f "$direct_url" ]] && command -v jq >/dev/null 2>&1; then
    local commit
    commit=$(jq -r '.vcs_info.commit_id // empty' "$direct_url" 2>/dev/null)
    if [[ -n "$commit" ]]; then
      echo "$version (${commit:0:12})"
      return 0
    fi
  fi

  echo "$version"
}

# Echoes the release a git-installed tool's receipt pins, e.g. "v6.0.0", or
# nothing when the install follows the default branch. Returns 1 when the tool
# has no receipt.
#
# uv records `git+<url>@<tag>` as `git+<url>?rev=<tag>`, and re-resolves that pin
# on every `uv tool upgrade` — so the pin, not the installed version, is what
# says whether an upgrade can move at all. An install with no pin also has the
# tool's own update notice disabled, which is why converting one is worth doing
# even when the versions already match. See lib/uv-git-tools.sh.
uv_tool_pinned_rev() {
  local tool="$1"
  local receipt="${UV_TOOL_DIR:-$HOME/.local/share/uv/tools}/$tool/uv-receipt.toml"
  [[ -f "$receipt" ]] || return 1

  sed -n 's/.*git = "[^"]*[?&]rev=\([^"&]*\)".*/\1/p' "$receipt" | head -n1
}

# Echoes the installed version of a crate, e.g. "v0.26.1". Returns 1 when the
# crate is not cargo-managed — true for the packages that fall back to a system
# package on platforms with no prebuilt binary.
cargo_installed_version() {
  local crate="$1"
  cargo install --list 2>/dev/null | awk -v crate="$crate" '
    $1 == crate && $2 ~ /^v[0-9]/ {
      sub(/:$/, "", $2)
      print $2
      found = 1
      exit
    }
    END { exit !found }
  '
}

# Echoes "<package> <version>" per line for every top-level global npm package.
npm_global_versions() {
  command -v npm >/dev/null 2>&1 || return 1
  command -v jq >/dev/null 2>&1 || return 1
  npm ls -g --depth=0 --json 2>/dev/null \
    | jq -r '.dependencies // {} | to_entries[] | "\(.key) \(.value.version // "unknown")"' \
    | sort
}

# Echoes the module version stamped into a Go binary, e.g. "v1.7.1", or "(devel)"
# for one built outside a tagged module. Returns 1 when the file carries no Go
# build info.
#
# Read from the binary's embedded build info rather than by running it: the
# version is what `go install <pkg>@latest` actually resolved, no tool needs a
# --version flag, and nothing has to guess which of several version-shaped tokens
# in a tool's own output is the tool's.
go_binary_module_version() {
  local binary_path="$1"
  [[ -f "$binary_path" ]] || return 1
  command -v go >/dev/null 2>&1 || return 1
  go version -m "$binary_path" 2>/dev/null | awk '
    $1 == "mod" {
      print $3
      found = 1
      exit
    }
    END { exit !found }
  '
}

# Echoes the short HEAD commit of a git checkout. Returns 1 when the path is not
# one.
git_checkout_commit() {
  local checkout_dir="$1"
  [[ -d "$checkout_dir/.git" ]] || return 1
  git -C "$checkout_dir" rev-parse --short HEAD 2>/dev/null
}

# Echoes "<name> <commit>" per line for every git checkout directly inside a
# parent directory — the shape tpm, lazy.nvim, and any other clone-per-thing
# manager leaves on disk.
#
# The checkouts are the state to diff even where a manager keeps a lockfile:
# lazy-lock.json only moves when upstream does, so a plugin dragged back to its
# pinned commit would leave it untouched.
git_checkouts_snapshot() {
  local parent_dir="$1"
  [[ -d "$parent_dir" ]] || return 1
  local checkout_dir commit
  for checkout_dir in "$parent_dir"/*/; do
    commit=$(git_checkout_commit "${checkout_dir%/}") || continue
    echo "$(basename "$checkout_dir") $commit"
  done | sort
}
