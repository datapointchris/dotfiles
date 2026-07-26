#!/usr/bin/env bash
#
# Queries for what a package manager currently has installed.
#
# Usage:
#   source "$DOTFILES_DIR/install/common/lib/installed-versions.sh"
#
#   before=$(uv_tool_installed_ref indy) || before=""
#   uv tool upgrade indy
#   after=$(uv_tool_installed_ref indy) || after=""
#
# Update phases compare a before/after snapshot rather than trusting an exit
# code: `uv tool upgrade`, `cargo binstall`, and `npm update -g` all exit 0 for a
# no-op, so only observed state distinguishes "upgraded" from "nothing to do".

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
  npm ls -g --depth=0 --json 2>/dev/null |
    jq -r '.dependencies // {} | to_entries[] | "\(.key) \(.value.version // "unknown")"' |
    sort
}
