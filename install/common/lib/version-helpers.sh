#!/usr/bin/env bash
#
# Version comparison and GitHub API helpers for installer scripts
#
# Usage:
#   source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"
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

# Resolve a GitHub token, if one is available. Private repos need it for both
# the API and the asset download; public repos work without it.
github_token() {
  local token="${GITHUB_TOKEN:-}"
  if [[ -z "$token" ]] && command -v gh &>/dev/null; then
    token=$(gh auth token 2>/dev/null || true)
  fi
  [[ -n "$token" ]] && echo "$token"
}

fetch_github_latest_version() {
  local repo="$1"

  [[ -z "$repo" ]] && return 1

  local api_url="https://api.github.com/repos/${repo}/releases/latest"
  local version

  local -a curl_opts=(-fsSL)
  local token
  token=$(github_token)
  if [[ -n "$token" ]]; then
    curl_opts+=(-H "Authorization: Bearer $token")
  fi

  version=$(curl "${curl_opts[@]}" "$api_url" 2>/dev/null | jq -r '.tag_name')

  if [[ -z "$version" || "$version" == "null" ]]; then
    return 1
  fi

  echo "$version"
  return 0
}

# Latest release whose tag carries a given prefix, e.g. "cli/" in a repo whose
# app owns the bare v* tags. /releases/latest cannot express this — it returns
# whatever release is newest overall — so this lists and filters instead.
# Usage: fetch_github_latest_version_prefixed <repo> <tag_prefix>
fetch_github_latest_version_prefixed() {
  local repo="$1"
  local prefix="$2"

  [[ -z "$repo" || -z "$prefix" ]] && return 1

  local -a curl_opts=(-fsSL)
  local token
  token=$(github_token)
  if [[ -n "$token" ]]; then
    curl_opts+=(-H "Authorization: Bearer $token")
  fi

  # Releases come back newest-first, so the first prefix match is the latest.
  local version
  version=$(curl "${curl_opts[@]}" "https://api.github.com/repos/${repo}/releases?per_page=100" 2>/dev/null |
    jq -r --arg p "$prefix" 'map(select(.draft | not) | select(.tag_name | startswith($p))) | .[0].tag_name // empty')

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
