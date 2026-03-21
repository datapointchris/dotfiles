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

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

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
  local max_retries=3 retry=0 curl_error=""

  TOTAL_DOWNLOADS=$((TOTAL_DOWNLOADS + 1))

  while [[ $retry -lt $max_retries ]]; do
    if curl_error=$(curl -fsSL --connect-timeout 30 --max-time 300 "$url" -o "$output" 2>&1); then
      return 0
    fi
    retry=$((retry + 1))
    if [[ $retry -lt $max_retries ]]; then
      log_warning "Retry $retry/$max_retries for $name ($curl_error)"
    fi
    sleep 2
  done

  log_error "Failed to download: $name"
  log_error "  url: $url"
  log_error "  error: $curl_error"
  exit 1
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
    "$github_releases/tree-sitter.sh"
  )

  local tool version url filename
  for script in "${installers[@]}"; do
    if ! IFS='|' read -r tool version url < <(bash "$script" --print-url "$OS" "$ARCH"); then
      log_error "Could not get URL for $(basename "$script" .sh)"
      exit 1
    fi
    filename=$(basename "$url")
    log_info "  $tool ($version)..."
    download_file "$url" "$CACHE_DIR/binaries/$filename" "$tool"
    echo "binary|$tool|$version|$filename" >> "$MANIFEST_FILE"
  done
}

# ============================================================================
# Go Tool Binaries (from packages.yml - data-driven, extracted to binaries)
# ============================================================================

download_go_binaries() {
  log_info "Downloading Go tool binaries..."

  # Platform mappings
  local os arch go_arch Os Arch
  os="$OS"
  arch="$ARCH"
  [[ "$arch" == "x86_64" ]] && go_arch="amd64" || go_arch="arm64"
  # Capitalized variants used by some projects (gum, lazydocker)
  [[ "$os" == "linux" ]] && Os="Linux" || Os="Darwin"
  Arch="$arch"

  local binary_name repo pattern version version_num asset_url filename
  while IFS='|' read -r binary_name repo pattern; do
    [[ -z "$binary_name" ]] && continue

    if ! version=$(fetch_github_latest_version "$repo"); then
      log_error "Could not fetch version for $binary_name ($repo)"
      exit 1
    fi
    version_num="${version#v}"

    # Expand pattern placeholders
    local expanded="$pattern"
    expanded="${expanded//\{version\}/$version}"
    expanded="${expanded//\{version_num\}/$version_num}"
    expanded="${expanded//\{os\}/$os}"
    expanded="${expanded//\{arch\}/$arch}"
    expanded="${expanded//\{go_arch\}/$go_arch}"
    expanded="${expanded//\{Os\}/$Os}"
    expanded="${expanded//\{Arch\}/$Arch}"

    asset_url="https://github.com/${repo}/releases/download/${version}/${expanded}"

    log_info "  $binary_name ($version)..."

    local download_path="$CACHE_DIR/go-binaries/${expanded}"
    download_file "$asset_url" "$download_path" "$binary_name"

    # Extract binary from archive and save as ready-to-use binary
    local extract_dir="/tmp/go-binary-extract-$$"
    mkdir -p "$extract_dir"
    local final_binary="$CACHE_DIR/go-binaries/$binary_name"

    if [[ "$expanded" == *.tar.gz ]] || [[ "$expanded" == *.tgz ]]; then
      tar -xf "$download_path" -C "$extract_dir"
      # Find the binary — may be at root or in a subdirectory
      # Some archives name the binary with platform suffix (e.g. gdu_linux_amd64)
      local found_bin
      found_bin=$(find "$extract_dir" -name "$binary_name" -type f | head -1)
      [[ -z "$found_bin" ]] && found_bin=$(find "$extract_dir" -name "${binary_name}_*" -type f | head -1)
      if [[ -z "$found_bin" ]]; then
        log_error "Could not find $binary_name binary in archive"
        exit 1
      fi
      mv "$found_bin" "$final_binary"
    elif [[ "$expanded" == *.gz ]]; then
      gunzip -c "$download_path" > "$final_binary"
    else
      # Raw binary (goose, gofumpt)
      mv "$download_path" "$final_binary"
    fi

    chmod +x "$final_binary"
    # Remove the archive now that we have the binary
    [[ -f "$download_path" ]] && [[ "$download_path" != "$final_binary" ]] && rm -f "$download_path"
    rm -rf "$extract_dir"

    echo "go-binary|$binary_name|$version|$binary_name" >> "$MANIFEST_FILE"
  done < <(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=go --format=binary_info)
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
    if ! IFS='|' read -r name version url < <(bash "$script" --print-url); then
      log_error "Could not get URL for $(basename "$script" .sh)"
      exit 1
    fi
    filename="${name}-install.sh"
    log_info "  $name..."
    download_file "$url" "$CACHE_DIR/scripts/$filename" "$name"
    echo "script|$name|$version|$filename" >> "$MANIFEST_FILE"
  done
}

# ============================================================================
# Cargo Binaries (from packages.yml - data-driven)
# ============================================================================

download_cargo_binaries() {
  log_info "Downloading Cargo tool binaries..."

  # Platform/arch names for tools that don't use Rust target triples (e.g. oxker)
  local platform arch_name
  if [[ "$OS" == "darwin" ]]; then
    platform="apple_darwin"
  else
    platform="linux"
  fi
  [[ "$ARCH" == "arm64" ]] && arch_name="aarch64" || arch_name="$ARCH"

  local tool repo pattern linux_target version target filename url
  while IFS='|' read -r tool repo pattern linux_target; do
    [[ -z "$tool" ]] && continue

    if ! version=$(fetch_github_latest_version "$repo"); then
      log_error "Could not fetch version for $tool"
      exit 1
    fi

    target=$(get_cargo_target "$OS" "$ARCH" "$linux_target")
    filename=$(expand_pattern "$pattern" "$version" "$target")
    filename="${filename//\{platform\}/$platform}"
    filename="${filename//\{arch\}/$arch_name}"
    url="https://github.com/${repo}/releases/download/${version}/${filename}"

    log_info "  $tool ($version)..."
    download_file "$url" "$CACHE_DIR/binaries/$filename" "$tool"
    echo "cargo|$tool|$version|$filename" >> "$MANIFEST_FILE"
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
    exit 1
  fi

  while IFS= read -r package; do
    [[ -z "$package" ]] && continue

    filename="${package}.tar.xz"
    url="https://github.com/ryanoasis/nerd-fonts/releases/download/${version}/${filename}"

    log_info "  $package ($version)..."
    download_file "$url" "$CACHE_DIR/fonts/$filename" "$package"
    echo "font|$package|$version|$filename" >> "$MANIFEST_FILE"
  done < <(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=nerd-fonts --format=packages)
}

# ============================================================================
# Other Fonts (non-Nerd Font families)
# ============================================================================

download_other_fonts() {
  [[ "$INCLUDE_FONTS" != "true" ]] && return 0

  log_info "Downloading other fonts..."

  # FiraCode (pinned release)
  log_info "  FiraCode (6.2)..."
  download_file \
    "https://github.com/tonsky/FiraCode/releases/download/6.2/Fira_Code_v6.2.zip" \
    "$CACHE_DIR/fonts/FiraCode.zip" "FiraCode"

  # SGr-IosevkaTermSlab (latest release)
  local iosevka_url
  iosevka_url=$(curl -fsSL "https://api.github.com/repos/be5invis/Iosevka/releases/latest" \
    | grep -o '"browser_download_url": *"[^"]*SuperTTC-SGr-IosevkaTermSlab-[0-9.]*\.zip"' | head -1 | sed 's/.*": *"//' | sed 's/"$//')
  if [[ -z "$iosevka_url" ]]; then
    log_error "Could not fetch SGr-IosevkaTermSlab release URL"
    exit 1
  fi
  log_info "  SGr-IosevkaTermSlab (latest)..."
  download_file "$iosevka_url" "$CACHE_DIR/fonts/SGr-IosevkaTermSlab.zip" "SGr-IosevkaTermSlab"

  # ComicMonoNF (individual TTF files)
  local comic_base="https://raw.githubusercontent.com/xtevenx/ComicMonoNF/master/v1"
  log_info "  ComicMonoNF (v1)..."
  download_file "$comic_base/ComicMonoNF-Regular.ttf" "$CACHE_DIR/fonts/ComicMonoNF-Regular.ttf" "ComicMonoNF-Regular"
  download_file "$comic_base/ComicMonoNF-Bold.ttf" "$CACHE_DIR/fonts/ComicMonoNF-Bold.ttf" "ComicMonoNF-Bold"

  # SeriousShannsNerdFontMono
  log_info "  SeriousShannsNerdFontMono..."
  download_file \
    "https://kaBeech.github.io/serious-shanns/SeriousShanns/SeriousShannsNerdFontMono.zip" \
    "$CACHE_DIR/fonts/SeriousShannsNerdFontMono.zip" "SeriousShannsNerdFontMono"
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
  trap 'rm -rf "${WORK_DIR:-}"' EXIT
  CACHE_DIR="$WORK_DIR/installers"
  MANIFEST_FILE="$CACHE_DIR/manifest.txt"

  mkdir -p "$CACHE_DIR/binaries" "$CACHE_DIR/scripts" "$CACHE_DIR/go-binaries"
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
  ├── go-binaries/    # Pre-built Go tool binaries
  ├── scripts/        # Install scripts (nvm, uv, theme, font, claude-code)
  └── fonts/          # Nerd Fonts (only if --with-fonts was used)
EOF
}

create_tarball() {
  log_info "Creating tarball..."

  local tarball_path="$DOTFILES_DIR/$BUNDLE_NAME.tar.gz"
  (cd "$WORK_DIR" && tar -czf "$tarball_path" installers)

  local tarball_size
  tarball_size=$(du -h "$tarball_path" | cut -f1)

  echo ""
  log_success "Bundle created successfully!"
  echo ""
  echo "  File: $tarball_path"
  echo "  Size: $tarball_size"
  echo "  Downloads: $TOTAL_DOWNLOADS"
  echo ""
  echo "To use this bundle:"
  echo "  1. Copy tarball to ~/ or ~/dotfiles/ on the target machine"
  echo "  2. Run: ./install.sh --machine <name> --offline"
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
  download_go_binaries
  download_cargo_binaries
  download_install_scripts
  download_nerd_fonts
  download_other_fonts

  create_readme
  create_tarball
}

main "$@"
