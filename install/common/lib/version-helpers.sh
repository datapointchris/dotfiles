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

# The version an offline bundle carries for a tool, read from its manifest.
#
# An offline install cannot ask GitHub what the latest version is — the network
# that makes the bundle necessary is the same one that blocks the API. Resolving
# from the manifest is also what makes the cache hit at all: the asset filename
# is built from the version, so a version fetched live names a file the bundle
# does not contain the moment upstream ships a release.
#
# Usage: offline_bundle_version <tool_name>
offline_bundle_version() {
  local tool="$1"
  local manifest="${HOME}/installers/manifest.txt"

  [[ -z "$tool" || ! -f "$manifest" ]] && return 1

  local version
  version=$(awk -F'|' -v want="$tool" \
    '$1 ~ /^(binary|extra|go-binary|cargo|script)$/ && $2 == want { print $3; exit }' "$manifest")

  [[ -n "$version" ]] || return 1
  echo "$version"
}

fetch_github_latest_version() {
  local repo="$1"

  [[ -z "$repo" ]] && return 1

  # Every installer sets BINARY_NAME before resolving a version, and both fetch
  # paths short-circuit here rather than in get_latest_version, because neovim
  # and the personal CLIs call these directly and would otherwise still hit the
  # API on a network that blocks it.
  if [[ "${OFFLINE_MODE:-false}" == "true" ]] && offline_bundle_version "${BINARY_NAME:-}"; then
    return 0
  fi

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

  if [[ "${OFFLINE_MODE:-false}" == "true" ]] && offline_bundle_version "${BINARY_NAME:-}"; then
    return 0
  fi

  local -a curl_opts=(-fsSL)
  local token
  token=$(github_token)
  if [[ -n "$token" ]]; then
    curl_opts+=(-H "Authorization: Bearer $token")
  fi

  # Releases come back newest-first, so the first prefix match is the latest.
  local version
  version=$(curl "${curl_opts[@]}" "https://api.github.com/repos/${repo}/releases?per_page=100" 2>/dev/null \
    | jq -r --arg p "$prefix" 'map(select(.draft | not) | select(.tag_name | startswith($p))) | .[0].tag_name // empty')

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
