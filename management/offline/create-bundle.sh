#!/usr/bin/env bash
# Create offline installation bundle for dotfiles
#
# Downloads all GitHub release binaries, Cargo tool binaries, install scripts,
# and optionally Nerd Fonts for offline installation on restricted networks.
#
# Usage:
#   ./create-bundle.sh                          # Standard bundle (no fonts)
#   ./create-bundle.sh --with-fonts             # Include Nerd Fonts (~400MB extra)
#   ./create-bundle.sh --platform linux-arm64   # Different platform
#
# Output:
#   dotfiles-offline-v{YYYYMMDD}-{platform}.tar.gz

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"

# ============================================================================
# Configuration
# ============================================================================

INCLUDE_FONTS=false
TARGET_PLATFORM="linux-x86_64"
OS=""
ARCH=""
BUNDLE_NAME=""
WORK_DIR=""
CACHE_DIR=""
MANIFEST_FILE=""
TOTAL_DOWNLOADS=0
FAILED_DOWNLOADS=()

# ============================================================================
# Helpers
# ============================================================================

get_cargo_target() {
  local os="$1" arch="$2" linux_override="${3:-}"
  if [[ "$os" == "darwin" ]]; then
    [[ "$arch" == "arm64" ]] && echo "aarch64-apple-darwin" || echo "x86_64-apple-darwin"
  else
    [[ -n "$linux_override" ]] && echo "$linux_override" || echo "x86_64-unknown-linux-gnu"
  fi
}

expand_pattern() {
  local pattern="$1" version="$2" target="$3"
  local version_num="${version#v}"
  pattern="${pattern//\{version\}/$version}"
  pattern="${pattern//\{version_num\}/$version_num}"
  pattern="${pattern//\{target\}/$target}"
  echo "$pattern"
}

download_file() {
  local url="$1" output="$2" name="$3"
  local max_retries=3 retry=0

  TOTAL_DOWNLOADS=$((TOTAL_DOWNLOADS + 1))

  while [[ $retry -lt $max_retries ]]; do
    if curl -fsSL --connect-timeout 30 --max-time 300 "$url" -o "$output" 2>/dev/null; then
      return 0
    fi
    retry=$((retry + 1))
    [[ $retry -lt $max_retries ]] && log_warning "Retry $retry/$max_retries for $name..."
    sleep 2
  done

  FAILED_DOWNLOADS+=("$name")
  log_error "Failed to download: $name"
  return 1
}

# ============================================================================
# GitHub Binary Releases (explicit listing - matches install.sh)
# ============================================================================

download_github_binaries() {
  log_info "Downloading GitHub binary releases..."
  local github_releases="$DOTFILES_DIR/management/common/install/github-releases"

  # Explicit listing - same tools as install.sh
  local installers=(
    "$github_releases/fzf.sh"
    "$github_releases/neovim.sh"
    "$github_releases/lazygit.sh"
    "$github_releases/yazi.sh"
    "$github_releases/glow.sh"
    "$github_releases/duf.sh"
    "$github_releases/tflint.sh"
    "$github_releases/terraformer.sh"
    "$github_releases/terrascan.sh"
    "$github_releases/trivy.sh"
    "$github_releases/zk.sh"
    "$github_releases/shellcheck.sh"
    "$github_releases/tenv.sh"
  )

  local tool version url filename
  for script in "${installers[@]}"; do
    if IFS='|' read -r tool version url < <(bash "$script" --print-url "$OS" "$ARCH" 2>/dev/null); then
      filename=$(basename "$url")
      log_info "  $tool ($version)..."
      if download_file "$url" "$CACHE_DIR/binaries/$filename" "$tool"; then
        echo "binary|$tool|$version|$filename" >> "$MANIFEST_FILE"
      fi
    else
      log_warning "  Could not get URL for $(basename "$script" .sh)"
    fi
  done
}

# ============================================================================
# Install Scripts (explicit listing - each supports --print-url)
# ============================================================================

download_install_scripts() {
  log_info "Downloading install scripts..."
  local lang_managers="$DOTFILES_DIR/management/common/install/language-managers"
  local custom_installers="$DOTFILES_DIR/management/common/install/custom-installers"

  # Explicit listing
  local installers=(
    "$lang_managers/nvm.sh"
    "$lang_managers/uv.sh"
    "$custom_installers/theme.sh"
    "$custom_installers/font.sh"
    "$custom_installers/claude-code.sh"
  )

  local name version url filename
  for script in "${installers[@]}"; do
    if IFS='|' read -r name version url < <(bash "$script" --print-url 2>/dev/null); then
      filename="${name}-install.sh"
      log_info "  $name..."
      if download_file "$url" "$CACHE_DIR/scripts/$filename" "$name"; then
        echo "script|$name|$version|$filename" >> "$MANIFEST_FILE"
      fi
    else
      log_warning "  Could not get URL for $(basename "$script" .sh)"
    fi
  done
}

# ============================================================================
# Cargo Binaries (from packages.yml - data-driven)
# ============================================================================

download_cargo_binaries() {
  log_info "Downloading Cargo tool binaries..."

  local tool repo pattern linux_target version target filename url
  while IFS='|' read -r tool repo pattern linux_target; do
    [[ -z "$tool" ]] && continue

    if ! version=$(fetch_github_latest_version "$repo"); then
      log_warning "  Could not fetch version for $tool"
      continue
    fi

    target=$(get_cargo_target "$OS" "$ARCH" "$linux_target")
    filename=$(expand_pattern "$pattern" "$version" "$target")
    url="https://github.com/${repo}/releases/download/${version}/${filename}"

    log_info "  $tool ($version)..."
    if download_file "$url" "$CACHE_DIR/binaries/$filename" "$tool"; then
      echo "cargo|$tool|$version|$filename" >> "$MANIFEST_FILE"
    fi
  done < <(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=cargo --format=binary_info)
}

# ============================================================================
# Nerd Fonts (from packages.yml - data-driven)
# ============================================================================

download_nerd_fonts() {
  [[ "$INCLUDE_FONTS" != "true" ]] && return 0

  log_info "Downloading Nerd Fonts..."

  local version package filename url
  if ! version=$(fetch_github_latest_version "ryanoasis/nerd-fonts"); then
    log_error "Could not fetch Nerd Fonts version"
    return 1
  fi

  while IFS= read -r package; do
    [[ -z "$package" ]] && continue

    filename="${package}.tar.xz"
    url="https://github.com/ryanoasis/nerd-fonts/releases/download/${version}/${filename}"

    log_info "  $package ($version)..."
    if download_file "$url" "$CACHE_DIR/fonts/$filename" "$package"; then
      echo "font|$package|$version|$filename" >> "$MANIFEST_FILE"
    fi
  done < <(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=nerd-fonts --format=packages)
}

# ============================================================================
# Setup and Teardown
# ============================================================================

usage() {
  echo "Usage: $0 [options]"
  echo ""
  echo "Options:"
  echo "  --with-fonts           Include Nerd Fonts in bundle (~400MB extra)"
  echo "  --platform PLATFORM    Target platform (default: linux-x86_64)"
  echo "                         Supported: linux-x86_64, linux-arm64,"
  echo "                                    darwin-x86_64, darwin-arm64"
  echo "  --help                 Show this help message"
  exit 0
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --with-fonts) INCLUDE_FONTS=true; shift ;;
      --platform)   TARGET_PLATFORM="$2"; shift 2 ;;
      --help|-h)    usage ;;
      *)            log_error "Unknown option: $1"; exit 1 ;;
    esac
  done
}

parse_platform() {
  case "$TARGET_PLATFORM" in
    linux-x86_64|linux-amd64)     OS="linux";  ARCH="x86_64" ;;
    linux-arm64|linux-aarch64)    OS="linux";  ARCH="arm64" ;;
    darwin-x86_64|macos-x86_64)   OS="darwin"; ARCH="x86_64" ;;
    darwin-arm64|macos-arm64)     OS="darwin"; ARCH="arm64" ;;
    *)
      log_error "Unsupported platform: $TARGET_PLATFORM"
      log_info "Supported: linux-x86_64, linux-arm64, darwin-x86_64, darwin-arm64"
      exit 1
      ;;
  esac
}

setup_directories() {
  BUNDLE_NAME="dotfiles-offline-v$(date +%Y%m%d)-${OS}-${ARCH}"
  WORK_DIR=$(mktemp -d)
  CACHE_DIR="$WORK_DIR/installers"
  MANIFEST_FILE="$CACHE_DIR/manifest.txt"

  mkdir -p "$CACHE_DIR/binaries" "$CACHE_DIR/scripts"
  [[ "$INCLUDE_FONTS" == "true" ]] && mkdir -p "$CACHE_DIR/fonts"

  cat > "$MANIFEST_FILE" << EOF
# Dotfiles Offline Bundle
# Created: $(date)
# Platform: $OS/$ARCH
# Include fonts: $INCLUDE_FONTS
#
# Format: category|name|version|filename
EOF
}

create_readme() {
  cat > "$CACHE_DIR/README.txt" << 'EOF'
Dotfiles Offline Installers
============================

Extract to home directory, then run installer in offline mode:

  cd ~ && tar -xzf dotfiles-offline-*.tar.gz
  git clone https://github.com/datapointchris/dotfiles.git
  cd dotfiles && ./install.sh --offline

The installer will find cached files in ~/installers/

Directory Structure:
  installers/
  ├── manifest.txt    # List of included files with versions
  ├── README.txt      # This file
  ├── binaries/       # GitHub release binaries + cargo tools
  ├── scripts/        # Install scripts (nvm, uv, theme, font, claude-code)
  └── fonts/          # Nerd Fonts (only if --with-fonts was used)
EOF
}

check_failures() {
  if [[ ${#FAILED_DOWNLOADS[@]} -gt 0 ]]; then
    echo ""
    log_error "Bundle creation FAILED - ${#FAILED_DOWNLOADS[@]} download(s) failed:"
    printf '  - %s\n' "${FAILED_DOWNLOADS[@]}"
    rm -rf "$WORK_DIR"
    exit 1
  fi
}

create_tarball() {
  log_info "Creating tarball..."

  local tarball_path="$SCRIPT_DIR/$BUNDLE_NAME.tar.gz"
  (cd "$WORK_DIR" && tar -czf "$tarball_path" installers)

  local tarball_size
  tarball_size=$(du -h "$tarball_path" | cut -f1)

  rm -rf "$WORK_DIR"

  echo ""
  log_success "Bundle created successfully!"
  echo ""
  echo "  File: $tarball_path"
  echo "  Size: $tarball_size"
  echo "  Downloads: $TOTAL_DOWNLOADS"
  echo ""
  echo "To use this bundle:"
  echo "  1. Copy to target machine"
  echo "  2. Extract: cd ~ && tar -xzf $BUNDLE_NAME.tar.gz"
  echo "  3. Clone dotfiles: git clone https://github.com/datapointchris/dotfiles.git"
  echo "  4. Install: cd dotfiles && ./install.sh --offline"
}

# ============================================================================
# Main
# ============================================================================

main() {
  parse_args "$@"
  parse_platform
  setup_directories

  log_info "Creating offline bundle: $BUNDLE_NAME"
  log_info "Target platform: $OS/$ARCH"
  log_info "Include fonts: $INCLUDE_FONTS"
  echo ""

  download_github_binaries
  download_cargo_binaries
  download_install_scripts
  download_nerd_fonts

  check_failures
  create_readme
  create_tarball
}

main "$@"
