#!/usr/bin/env bash
#
# Cache management for downloaded installation files
#
# Manages ~/.cache/dotfiles/ for offline/blocked installation scenarios
#
# Usage:
#   source "$DOTFILES_DIR/management/common/lib/cache-manager.sh"
#
#   if cached=$(check_local_cache_for_version "lazygit" "v0.40.2" "tar.gz"); then
#     echo "Found cached file: $cached"
#   fi

# Check local cache for a specific version
# Returns the path to cached file if found, empty string if not
# Usage: check_local_cache_for_version <binary_name> <version> <extension>
# Example: check_local_cache_for_version "lazygit" "v0.40.2" "tar.gz"
check_local_cache_for_version() {
  local binary_name="$1"
  local version="$2"
  local extension="$3"
  local cache_dir="$HOME/.cache/dotfiles"

  mkdir -p "$cache_dir"

  # Strip 'v' prefix for matching
  local version_clean="${version#v}"

  # Look for: *{binary}*{version}*.{ext}
  local matches=()
  while IFS= read -r -d '' file; do
    matches+=("$file")
  done < <(find "$cache_dir" -maxdepth 1 -type f -name "*${binary_name}*${version_clean}*.${extension}" -print0 2>/dev/null)

  if [[ ${#matches[@]} -gt 0 ]]; then
    echo "${matches[0]}"
    return 0
  fi

  return 1
}
