#!/usr/bin/env bash
# URL definitions and version fetching for offline bundle creation
#
# This script provides functions to generate download URLs for all tools
# that need to be bundled for offline installation.
#
# Usage:
#   source bundle-urls.sh
#   get_github_binary_urls "linux" "x86_64"
#   get_cargo_binary_urls "linux" "x86_64"
#   get_font_urls
#   get_install_script_urls
#
# TODO: This duplicates URL logic from the actual installers. Future improvement:
# Add --print-url flag to each installer in github-releases/ and have this script
# call them instead of maintaining URL patterns in two places. This would ensure
# the bundle always uses the same URLs as the installers.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# GitHub repos for tools installed via GitHub releases
declare -A GITHUB_BINARY_REPOS=(
  ["neovim"]="neovim/neovim"
  ["lazygit"]="jesseduffield/lazygit"
  ["yazi"]="sxyazi/yazi"
  ["fzf"]="junegunn/fzf"
  ["glow"]="charmbracelet/glow"
  ["duf"]="muesli/duf"
  ["shellcheck"]="koalaman/shellcheck"
  ["tflint"]="terraform-linters/tflint"
  ["terraformer"]="GoogleCloudPlatform/terraformer"
  ["terrascan"]="tenable/terrascan"
  ["trivy"]="aquasecurity/trivy"
  ["zk"]="zk-org/zk"
  ["tenv"]="tofuutils/tenv"
)

# GitHub repos for Cargo tools (download binaries instead of cargo binstall)
declare -A CARGO_BINARY_REPOS=(
  ["bat"]="sharkdp/bat"
  ["fd"]="sharkdp/fd"
  ["eza"]="eza-community/eza"
  ["zoxide"]="ajeetdsouza/zoxide"
  ["delta"]="dandavison/delta"
)

# Nerd Fonts - read from packages.yml via parse_packages.py
# No hardcoded list - single source of truth in packages.yml

# Install scripts that need to be bundled
declare -A INSTALL_SCRIPTS=(
  ["nvm"]="https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh"
  ["uv"]="https://astral.sh/uv/install.sh"
  ["theme"]="https://raw.githubusercontent.com/datapointchris/theme/main/install.sh"
  ["font"]="https://raw.githubusercontent.com/datapointchris/font/main/install.sh"
)

# Fetch latest version from GitHub API
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

# Get download URL for a GitHub release binary
# Usage: get_binary_download_url "tool" "version" "os" "arch"
# os: linux, darwin
# arch: x86_64, arm64, aarch64
get_binary_download_url() {
  local tool="$1"
  local version="$2"
  local os="$3"
  local arch="$4"
  local repo="${GITHUB_BINARY_REPOS[$tool]:-}"

  [[ -z "$repo" ]] && return 1

  local version_num="${version#v}"  # Remove 'v' prefix if present

  case "$tool" in
    neovim)
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && arch="arm64" || arch="x86_64"
        echo "https://github.com/${repo}/releases/download/${version}/nvim-macos-${arch}.tar.gz"
      else
        echo "https://github.com/${repo}/releases/download/${version}/nvim-linux-x86_64.tar.gz"
      fi
      ;;
    lazygit)
      local plat_arch
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && plat_arch="Darwin_arm64" || plat_arch="Darwin_x86_64"
      else
        plat_arch="Linux_x86_64"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/lazygit_${version_num}_${plat_arch}.tar.gz"
      ;;
    yazi)
      local target
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && target="aarch64-apple-darwin" || target="x86_64-apple-darwin"
      else
        target="x86_64-unknown-linux-gnu"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/yazi-${target}.zip"
      ;;
    fzf)
      local plat_arch
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && plat_arch="darwin_arm64" || plat_arch="darwin_amd64"
      else
        plat_arch="linux_amd64"
      fi
      # fzf uses version without 'v' prefix in filename
      echo "https://github.com/${repo}/releases/download/${version}/fzf-${version_num}-${plat_arch}.tar.gz"
      ;;
    glow)
      local plat_arch
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && plat_arch="Darwin_arm64" || plat_arch="Darwin_x86_64"
      else
        plat_arch="Linux_x86_64"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/glow_${version_num}_${plat_arch}.tar.gz"
      ;;
    duf)
      local plat_arch
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && plat_arch="darwin_arm64" || plat_arch="darwin_x86_64"
      else
        plat_arch="linux_x86_64"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/duf_${version_num}_${plat_arch}.tar.gz"
      ;;
    shellcheck)
      local plat_arch
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && plat_arch="darwin.aarch64" || plat_arch="darwin.x86_64"
      else
        plat_arch="linux.x86_64"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/shellcheck-${version}.${plat_arch}.tar.xz"
      ;;
    tflint)
      local plat_arch
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && plat_arch="darwin_arm64" || plat_arch="darwin_amd64"
      else
        plat_arch="linux_amd64"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/tflint_${plat_arch}.zip"
      ;;
    terraformer)
      local plat_arch
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && plat_arch="darwin-arm64" || plat_arch="darwin-amd64"
      else
        plat_arch="linux-amd64"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/terraformer-all-${plat_arch}"
      ;;
    terrascan)
      local plat_arch
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && plat_arch="Darwin_arm64" || plat_arch="Darwin_x86_64"
      else
        plat_arch="Linux_x86_64"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/terrascan_${version_num}_${plat_arch}.tar.gz"
      ;;
    trivy)
      local plat_arch
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && plat_arch="macOS-ARM64" || plat_arch="macOS-64bit"
      else
        plat_arch="Linux-64bit"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/trivy_${version_num}_${plat_arch}.tar.gz"
      ;;
    zk)
      local plat_arch
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && plat_arch="macos-arm64" || plat_arch="macos-x86_64"
      else
        plat_arch="linux-amd64"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/zk-${version}-${plat_arch}.tar.gz"
      ;;
    tenv)
      local plat raw_arch
      if [[ "$os" == "darwin" ]]; then
        plat="Darwin"
        [[ "$arch" == "arm64" ]] && raw_arch="arm64" || raw_arch="x86_64"
      else
        plat="Linux"
        [[ "$arch" == "arm64" ]] && raw_arch="arm64" || raw_arch="x86_64"
      fi
      # tenv uses uname -m directly (x86_64, arm64) and capital D/L
      echo "https://github.com/${repo}/releases/download/${version}/tenv_${version}_${plat}_${raw_arch}.tar.gz"
      ;;
    *)
      return 1
      ;;
  esac
}

# Get download URL for a Cargo tool binary from GitHub releases
# Usage: get_cargo_binary_url "tool" "version" "os" "arch"
get_cargo_binary_url() {
  local tool="$1"
  local version="$2"
  local os="$3"
  local arch="$4"
  local repo="${CARGO_BINARY_REPOS[$tool]:-}"

  [[ -z "$repo" ]] && return 1

  local version_num="${version#v}"

  case "$tool" in
    bat)
      local target
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && target="aarch64-apple-darwin" || target="x86_64-apple-darwin"
      else
        target="x86_64-unknown-linux-gnu"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/bat-${version}-${target}.tar.gz"
      ;;
    fd)
      local target
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && target="aarch64-apple-darwin" || target="x86_64-apple-darwin"
      else
        target="x86_64-unknown-linux-gnu"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/fd-${version}-${target}.tar.gz"
      ;;
    eza)
      local target
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && target="aarch64-apple-darwin" || target="x86_64-apple-darwin"
      else
        target="x86_64-unknown-linux-gnu"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/eza_${target}.tar.gz"
      ;;
    zoxide)
      local target
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && target="aarch64-apple-darwin" || target="x86_64-apple-darwin"
      else
        target="x86_64-unknown-linux-musl"
      fi
      # zoxide uses version without 'v' prefix, and musl for linux
      echo "https://github.com/${repo}/releases/download/${version}/zoxide-${version_num}-${target}.tar.gz"
      ;;
    delta)
      local target
      if [[ "$os" == "darwin" ]]; then
        [[ "$arch" == "arm64" ]] && target="aarch64-apple-darwin" || target="x86_64-apple-darwin"
      else
        target="x86_64-unknown-linux-gnu"
      fi
      echo "https://github.com/${repo}/releases/download/${version}/delta-${version}-${target}.tar.gz"
      ;;
    *)
      return 1
      ;;
  esac
}

# Get Nerd Font download URL
# Usage: get_nerd_font_url "FontName" "version"
get_nerd_font_url() {
  local font="$1"
  local version="$2"
  echo "https://github.com/ryanoasis/nerd-fonts/releases/download/${version}/${font}.tar.xz"
}

# Print all GitHub binary URLs for a platform
# Usage: print_github_binary_urls "linux" "x86_64"
print_github_binary_urls() {
  local os="$1"
  local arch="$2"

  for tool in "${!GITHUB_BINARY_REPOS[@]}"; do
    local repo="${GITHUB_BINARY_REPOS[$tool]}"
    local version
    if ! version=$(fetch_latest_version "$repo"); then
      echo "# ERROR: Could not fetch version for $tool ($repo)" >&2
      continue
    fi
    local url
    if url=$(get_binary_download_url "$tool" "$version" "$os" "$arch"); then
      echo "$tool|$version|$url"
    else
      echo "# ERROR: Could not generate URL for $tool" >&2
    fi
  done
}

# Print all Cargo binary URLs for a platform
# Usage: print_cargo_binary_urls "linux" "x86_64"
print_cargo_binary_urls() {
  local os="$1"
  local arch="$2"

  for tool in "${!CARGO_BINARY_REPOS[@]}"; do
    local repo="${CARGO_BINARY_REPOS[$tool]}"
    local version
    if ! version=$(fetch_latest_version "$repo"); then
      echo "# ERROR: Could not fetch version for $tool ($repo)" >&2
      continue
    fi
    local url
    if url=$(get_cargo_binary_url "$tool" "$version" "$os" "$arch"); then
      echo "$tool|$version|$url"
    else
      echo "# ERROR: Could not generate URL for $tool" >&2
    fi
  done
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
