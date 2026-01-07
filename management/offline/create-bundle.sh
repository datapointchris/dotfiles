#!/usr/bin/env bash
# Create offline installation bundle for dotfiles
#
# Downloads all GitHub release binaries, Cargo tool binaries, and install scripts
# needed for offline installation on restricted networks.
#
# Usage:
#   ./create-bundle.sh                          # Standard bundle (no fonts)
#   ./create-bundle.sh --with-fonts             # Include Nerd Fonts (~400MB extra)
#   ./create-bundle.sh --platform linux-arm64   # Different platform
#
# Output:
#   dotfiles-offline-v{YYYYMMDD}-{platform}.tar.gz
#
# The bundle extracts to ~/dotfiles-offline-cache/ on the target machine.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$SCRIPT_DIR/bundle-urls.sh"

# Default options
INCLUDE_FONTS=false
TARGET_PLATFORM="linux-x86_64"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-fonts)
      INCLUDE_FONTS=true
      shift
      ;;
    --platform)
      TARGET_PLATFORM="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --with-fonts           Include Nerd Fonts in bundle (~400MB extra)"
      echo "  --platform PLATFORM    Target platform (default: linux-x86_64)"
      echo "                         Supported: linux-x86_64, linux-arm64,"
      echo "                                    darwin-x86_64, darwin-arm64"
      echo "  --help                 Show this help message"
      exit 0
      ;;
    *)
      log_error "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Parse platform
case "$TARGET_PLATFORM" in
  linux-x86_64|linux-amd64)
    OS="linux"
    ARCH="x86_64"
    ;;
  linux-arm64|linux-aarch64)
    OS="linux"
    ARCH="arm64"
    ;;
  darwin-x86_64|darwin-amd64|macos-x86_64)
    OS="darwin"
    ARCH="x86_64"
    ;;
  darwin-arm64|darwin-aarch64|macos-arm64)
    OS="darwin"
    ARCH="arm64"
    ;;
  *)
    log_error "Unsupported platform: $TARGET_PLATFORM"
    log_info "Supported platforms: linux-x86_64, linux-arm64, darwin-x86_64, darwin-arm64"
    exit 1
    ;;
esac

# Setup
DATE=$(date +%Y%m%d)
BUNDLE_NAME="dotfiles-offline-v${DATE}-${OS}-${ARCH}"
WORK_DIR=$(mktemp -d)
CACHE_DIR="$WORK_DIR/installers"
MANIFEST_FILE="$CACHE_DIR/manifest.txt"

log_info "Creating offline bundle: $BUNDLE_NAME"
log_info "Target platform: $OS/$ARCH"
log_info "Include fonts: $INCLUDE_FONTS"
log_info "Working directory: $WORK_DIR"

# Create directory structure
mkdir -p "$CACHE_DIR/binaries"
mkdir -p "$CACHE_DIR/scripts"
if [[ "$INCLUDE_FONTS" == "true" ]]; then
  mkdir -p "$CACHE_DIR/fonts"
fi

# Initialize manifest
{
  echo "# Dotfiles Offline Bundle"
  echo "# Created: $(date)"
  echo "# Platform: $OS/$ARCH"
  echo "# Include fonts: $INCLUDE_FONTS"
  echo ""
  echo "# Format: category|name|version|filename"
  echo ""
} > "$MANIFEST_FILE"

# Track downloads
TOTAL_DOWNLOADS=0
FAILED_DOWNLOADS=()

# Download a file with retry - fails the whole bundle if download fails
download_file() {
  local url="$1"
  local output="$2"
  local name="$3"
  local max_retries=3
  local retry=0

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
  log_error "Failed to download: $name ($url)"
  return 1
}

# Download GitHub binary releases
log_info "Downloading GitHub binary releases..."
while IFS='|' read -r tool version url; do
  [[ "$tool" == \#* ]] && continue  # Skip comments
  [[ -z "$tool" ]] && continue

  filename=$(basename "$url")
  log_info "  $tool ($version)..."

  if download_file "$url" "$CACHE_DIR/binaries/$filename" "$tool"; then
    echo "binary|$tool|$version|$filename" >> "$MANIFEST_FILE"
    log_success "  $tool downloaded"
  fi
done < <(print_github_binary_urls "$OS" "$ARCH")

# Download Cargo tool binaries
log_info "Downloading Cargo tool binaries..."
while IFS='|' read -r tool version url; do
  [[ "$tool" == \#* ]] && continue
  [[ -z "$tool" ]] && continue

  filename=$(basename "$url")
  log_info "  $tool ($version)..."

  if download_file "$url" "$CACHE_DIR/binaries/$filename" "$tool"; then
    echo "cargo|$tool|$version|$filename" >> "$MANIFEST_FILE"
    log_success "  $tool downloaded"
  fi
done < <(print_cargo_binary_urls "$OS" "$ARCH")

# Download install scripts
log_info "Downloading install scripts..."
while IFS='|' read -r script version url; do
  [[ "$script" == \#* ]] && continue
  [[ -z "$script" ]] && continue

  filename="${script}-install.sh"
  log_info "  $script..."

  if download_file "$url" "$CACHE_DIR/scripts/$filename" "$script"; then
    echo "script|$script|$version|$filename" >> "$MANIFEST_FILE"
    log_success "  $script downloaded"
  fi
done < <(print_install_script_urls)

# Download fonts if requested
if [[ "$INCLUDE_FONTS" == "true" ]]; then
  log_info "Downloading Nerd Fonts..."
  while IFS='|' read -r font version url; do
    [[ "$font" == \#* ]] && continue
    [[ -z "$font" ]] && continue

    filename=$(basename "$url")
    log_info "  $font ($version)..."

    if download_file "$url" "$CACHE_DIR/fonts/$filename" "$font"; then
      echo "font|$font|$version|$filename" >> "$MANIFEST_FILE"
      log_success "  $font downloaded"
    fi
  done < <(print_nerd_font_urls)
fi

# Check for failures before creating tarball
if [[ ${#FAILED_DOWNLOADS[@]} -gt 0 ]]; then
  echo ""
  log_error "Bundle creation FAILED - ${#FAILED_DOWNLOADS[@]} download(s) failed:"
  for failed in "${FAILED_DOWNLOADS[@]}"; do
    echo "  - $failed"
  done
  echo ""
  log_info "Fix the failing downloads and try again."
  rm -rf "$WORK_DIR"
  exit 1
fi

# Add summary to manifest
{
  echo ""
  echo "# Summary"
  echo "# Total downloads: $TOTAL_DOWNLOADS"
  echo "# All downloads successful"
} >> "$MANIFEST_FILE"

# Create README for the bundle
cat > "$CACHE_DIR/README.txt" << 'EOF'
Dotfiles Offline Installers
============================

This directory contains pre-downloaded binaries and scripts for offline
installation of the datapointchris/dotfiles repository.

Usage:
------
1. Extract this archive to your home directory:
   cd ~ && tar -xzf dotfiles-offline-v*.tar.gz

2. Clone the dotfiles repository:
   git clone https://github.com/datapointchris/dotfiles.git

3. Run the installer in offline mode:
   cd dotfiles && ./install.sh --offline

The installer will automatically find cached files in ~/installers/

Directory Structure:
--------------------
installers/
├── manifest.txt    # List of included files with versions
├── README.txt      # This file
├── binaries/       # GitHub release binaries (neovim, lazygit, cargo tools, etc.)
├── scripts/        # Install scripts (nvm, uv, theme, font)
└── fonts/          # Nerd Fonts (only if --with-fonts was used)

Note:
-----
This bundle does NOT include:
- The dotfiles repository itself (use git clone)
- System packages (apt/brew/pacman)
- npm packages (npm registry works on most networks)
- Python packages (PyPI works on most networks)
- Go tools (go proxy works on most networks)

These are not blocked on most restricted networks.
EOF

# Create the tarball
log_info "Creating tarball..."
TARBALL_PATH="$SCRIPT_DIR/$BUNDLE_NAME.tar.gz"

# Create tarball from work directory
(cd "$WORK_DIR" && tar -czf "$TARBALL_PATH" installers)

# Calculate size
TARBALL_SIZE=$(du -h "$TARBALL_PATH" | cut -f1)

# Cleanup
rm -rf "$WORK_DIR"

# Summary
echo ""
log_success "Bundle created successfully!"
echo ""
echo "  File: $TARBALL_PATH"
echo "  Size: $TARBALL_SIZE"
echo "  Downloads: $TOTAL_DOWNLOADS"
echo ""
echo "To use this bundle:"
echo "  1. Copy to target machine"
echo "  2. Extract: cd ~ && tar -xzf $BUNDLE_NAME.tar.gz"
echo "  3. Clone dotfiles: git clone https://github.com/datapointchris/dotfiles.git"
echo "  4. Install: cd dotfiles && ./install.sh --offline"
