#!/usr/bin/env bash
#
# Version comparison and GitHub API helpers for installer scripts
#
# Usage:
#   source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
#
#   if version_compare "$current" "$latest"; then
#     echo "Already at latest version"
#   fi

version_compare() {
  local current="$1"
  local latest="$2"

  [[ -z "$current" || -z "$latest" ]] && return 1

  current="${current#v}"
  latest="${latest#v}"

  if [[ "$current" == "$latest" ]]; then
    return 0
  fi

  if [[ $(printf '%s\n' "$current" "$latest" | sort -V | head -n1) == "$current" ]]; then
    return 1
  else
    return 2
  fi
}

fetch_github_latest_version() {
  local repo="$1"

  [[ -z "$repo" ]] && return 1

  local api_url="https://api.github.com/repos/${repo}/releases/latest"
  local version

  version=$(curl -fsSL "$api_url" 2>/dev/null | jq -r '.tag_name')

  if [[ -z "$version" || "$version" == "null" ]]; then
    return 1
  fi

  echo "$version"
  return 0
}

parse_version() {
  local output="$1"

  [[ -z "$output" ]] && return 1

  local version
  version=$(echo "$output" | grep -oE 'v?[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)

  if [[ -z "$version" ]]; then
    return 1
  fi

  echo "$version"
  return 0
}
