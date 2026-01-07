#!/usr/bin/env bash
# URL generation for offline bundle creation
#
# This script dynamically generates download URLs by calling the actual installers
# with --print-url. No hardcoded URLs - single source of truth in each installer.
#
# Usage:
#   source bundle-urls.sh
#   print_github_binary_urls "linux" "x86_64"
#   print_cargo_binary_urls "linux" "x86_64"
#   print_nerd_font_urls
#   print_install_script_urls

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Install scripts that need to be bundled (external URLs, rarely change)
declare -A INSTALL_SCRIPTS=(
  ["nvm"]="https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh"
  ["uv"]="https://astral.sh/uv/install.sh"
  ["theme"]="https://raw.githubusercontent.com/datapointchris/theme/main/install.sh"
  ["font"]="https://raw.githubusercontent.com/datapointchris/font/main/install.sh"
)

# Fetch latest version from GitHub API (used for cargo binaries)
# Usage: fetch_latest_version "owner/repo"
fetch_latest_version() {
  local repo="$1"
  local version

  version=$(curl -fsSL "https://api.github.com/repos/${repo}/releases/latest" 2>/dev/null | \
    grep '"tag_name":' | head -1 | sed -E 's/.*"([^"]+)".*/\1/')

  if [[ -z "$version" || "$version" == "null" ]]; then
    return 1
  fi

  echo "$version"
}

# Compute target string for cargo binaries
# Usage: get_cargo_target "os" "arch" "linux_target_override"
get_cargo_target() {
  local os="$1"
  local arch="$2"
  local linux_override="$3"

  if [[ "$os" == "darwin" ]]; then
    [[ "$arch" == "arm64" ]] && echo "aarch64-apple-darwin" || echo "x86_64-apple-darwin"
  else
    if [[ -n "$linux_override" ]]; then
      echo "$linux_override"
    else
      echo "x86_64-unknown-linux-gnu"
    fi
  fi
}

# Expand binary pattern with version and target
# Usage: expand_binary_pattern "pattern" "version" "target"
expand_binary_pattern() {
  local pattern="$1"
  local version="$2"
  local target="$3"
  local version_num="${version#v}"

  local result="$pattern"
  result="${result//\{version\}/$version}"
  result="${result//\{version_num\}/$version_num}"
  result="${result//\{target\}/$target}"
  echo "$result"
}

# Get Nerd Font download URL
# Usage: get_nerd_font_url "FontName" "version"
get_nerd_font_url() {
  local font="$1"
  local version="$2"
  echo "https://github.com/ryanoasis/nerd-fonts/releases/download/${version}/${font}.tar.xz"
}

# Print all GitHub binary URLs for a platform
# Dynamically calls each installer with --print-url (single source of truth)
# Usage: print_github_binary_urls "linux" "x86_64"
print_github_binary_urls() {
  local os="$1"
  local arch="$2"
  local github_releases_dir="$DOTFILES_DIR/management/common/install/github-releases"

  for script in "$github_releases_dir"/*.sh; do
    [[ ! -f "$script" ]] && continue
    local output
    if output=$(bash "$script" --print-url "$os" "$arch" 2>/dev/null); then
      echo "$output"
    else
      echo "# ERROR: $(basename "$script") failed" >&2
    fi
  done
}

# Print all Cargo binary URLs for a platform
# Reads cargo packages from packages.yml (single source of truth)
# Usage: print_cargo_binary_urls "linux" "x86_64"
print_cargo_binary_urls() {
  local os="$1"
  local arch="$2"

  while IFS='|' read -r tool repo pattern linux_target; do
    [[ -z "$tool" ]] && continue
    local version
    if ! version=$(fetch_latest_version "$repo"); then
      echo "# ERROR: Could not fetch version for $tool ($repo)" >&2
      continue
    fi
    local target
    target=$(get_cargo_target "$os" "$arch" "$linux_target")
    local filename
    filename=$(expand_binary_pattern "$pattern" "$version" "$target")
    local url="https://github.com/${repo}/releases/download/${version}/${filename}"
    echo "$tool|$version|$url"
  done < <(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=cargo --format=binary_info)
}

# Print all Nerd Font URLs
# Usage: print_nerd_font_urls
# Reads font list from packages.yml (single source of truth)
print_nerd_font_urls() {
  local version
  if ! version=$(fetch_latest_version "ryanoasis/nerd-fonts"); then
    echo "# ERROR: Could not fetch Nerd Fonts version" >&2
    return 1
  fi

  # Read font packages from packages.yml
  while IFS= read -r package; do
    local url
    url=$(get_nerd_font_url "$package" "$version")
    echo "$package|$version|$url"
  done < <(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=nerd-fonts --format=packages)
}

# Print all install script URLs
# Usage: print_install_script_urls
print_install_script_urls() {
  for script in "${!INSTALL_SCRIPTS[@]}"; do
    echo "$script|latest|${INSTALL_SCRIPTS[$script]}"
  done
}

# Main: if run directly, print all URLs for testing
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  OS="${1:-linux}"
  ARCH="${2:-x86_64}"

  echo "=== GitHub Binary Releases (${OS}/${ARCH}) ==="
  print_github_binary_urls "$OS" "$ARCH"
  echo ""

  echo "=== Cargo Tool Binaries (${OS}/${ARCH}) ==="
  print_cargo_binary_urls "$OS" "$ARCH"
  echo ""

  echo "=== Nerd Fonts ==="
  print_nerd_font_urls
  echo ""

  echo "=== Install Scripts ==="
  print_install_script_urls
fi
