#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"

BINARY_NAME="neovim"
REPO="neovim/neovim"

get_download_url() {
  local version="$1" os="$2" arch="$3"
  local binary_name
  if [[ "$os" == "darwin" ]]; then
    [[ "$arch" == "arm64" ]] && binary_name="nvim-macos-arm64" || binary_name="nvim-macos-x86_64"
  else
    binary_name="nvim-linux-x86_64"
  fi
  echo "https://github.com/${REPO}/releases/download/${version}/${binary_name}.tar.gz"
}

if [[ "${1:-}" == "--print-url" ]]; then
  OS="${2:-linux}"
  ARCH="${3:-x86_64}"
  VERSION=$(fetch_github_latest_version "$REPO")
  URL=$(get_download_url "$VERSION" "$OS" "$ARCH")
  echo "$BINARY_NAME|$VERSION|$URL"
  exit 0
fi

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

UPDATE_MODE=false
[[ "${1:-}" == "--update" ]] && UPDATE_MODE=true

OS=$(detect_os)
ARCH=$(detect_arch)

if [[ "$OS" == "darwin" ]]; then
  if [[ "$ARCH" == "amd64" ]]; then
    NVIM_BINARY="nvim-macos-x86_64"
  else
    NVIM_BINARY="nvim-macos-arm64"
  fi
else
  NVIM_BINARY="nvim-linux-x86_64"
fi

NVIM_INSTALL_DIR="$HOME/.local/${NVIM_BINARY}"
NVIM_BIN_LINK="$HOME/.local/bin/nvim"

NVIM_VERSION=$(fetch_github_latest_version "$REPO" 2>/dev/null || true)
if [[ -z "$NVIM_VERSION" ]]; then
  manual_steps="Failed to fetch latest version from GitHub API.

Manual installation:
1. Visit: https://github.com/${REPO}/releases/latest
2. Download: ${NVIM_BINARY}.tar.gz
3. Extract: tar -C ~/.local -xzf ~/Downloads/${NVIM_BINARY}.tar.gz
4. Link: ln -sf ~/.local/${NVIM_BINARY}/bin/nvim ~/.local/bin/nvim
5. Verify: nvim --version"
  output_failure_data "neovim" "https://github.com/${REPO}/releases/latest" "latest" "$manual_steps" "Failed to fetch version from GitHub API"
  log_error "Neovim installation failed"
  exit 1
fi

log_info "Latest nvim version: $NVIM_VERSION"

if [[ "$UPDATE_MODE" == "true" ]]; then
  if ! command -v nvim >/dev/null 2>&1; then
    log_info "nvim not installed, will install"
  else
    CURRENT_VERSION=$(nvim --version 2>&1 | head -1)
    CURRENT_VERSION=$(parse_version "$CURRENT_VERSION")

    if [[ -z "$CURRENT_VERSION" ]]; then
      log_warning "Could not parse current version, will reinstall"
    elif version_compare "$CURRENT_VERSION" "$NVIM_VERSION"; then
      log_success "Already at latest version: $NVIM_VERSION"
      exit 0
    else
      log_info "Update available: $CURRENT_VERSION → $NVIM_VERSION"
    fi
  fi
else
  if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -L "$NVIM_BIN_LINK" ]] && command -v nvim >/dev/null 2>&1; then
    log_success "nvim already installed, skipping"
    exit 0
  fi
fi

if [[ ! -L "$NVIM_BIN_LINK" ]] && command -v nvim >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v nvim)
  log_warning " nvim found at $ALTERNATE_LOCATION"
  log_info "Installing to $NVIM_BIN_LINK anyway (PATH priority will use this one)"
fi

NVIM_URL="https://github.com/${REPO}/releases/download/${NVIM_VERSION}/${NVIM_BINARY}.tar.gz"
NVIM_TARBALL="/tmp/${NVIM_BINARY}.tar.gz"
OFFLINE_CACHE_DIR="${HOME}/installers/binaries"
CACHED_FILE="$OFFLINE_CACHE_DIR/$(basename "$NVIM_URL")"

if [[ -f "$CACHED_FILE" ]]; then
  log_info "Using cached file: $CACHED_FILE"
  cp "$CACHED_FILE" "$NVIM_TARBALL"
else
  log_info "Download URL: $NVIM_URL"
  log_info "Downloading Neovim..."
fi

if [[ ! -f "$NVIM_TARBALL" ]] && ! curl -fsSL "$NVIM_URL" -o "$NVIM_TARBALL"; then
  manual_steps="1. Download in your browser (bypasses firewall):
   $NVIM_URL

2. After downloading, extract and install:
   tar -C ~/.local -xzf ~/Downloads/${NVIM_BINARY}.tar.gz
   ln -sf ~/.local/${NVIM_BINARY}/bin/nvim ~/.local/bin/nvim

3. Verify installation:
   nvim --version"
  output_failure_data "neovim" "$NVIM_URL" "$NVIM_VERSION" "$manual_steps" "Download failed"
  log_error "Neovim installation failed"
  exit 1
fi

# Verify it's a valid gzip file
if ! file "$NVIM_TARBALL" | grep -q "gzip compressed"; then
  log_error "Not a valid gzip archive: $(file "$NVIM_TARBALL")"
  log_info "URL: $NVIM_URL"
  manual_steps="Downloaded file is not a valid gzip archive.

1. Download in your browser:
   $NVIM_URL

2. Verify the download is complete
3. Extract and install:
   tar -C ~/.local -xzf ~/Downloads/${NVIM_BINARY}.tar.gz
   ln -sf ~/.local/${NVIM_BINARY}/bin/nvim ~/.local/bin/nvim

4. Verify:
   nvim --version"
  output_failure_data "neovim" "$NVIM_URL" "$NVIM_VERSION" "$manual_steps" "Invalid gzip archive"
  log_error "Neovim installation failed"
  exit 1
fi

log_info "Installing to ~/.local/..."
if [[ -d "$NVIM_INSTALL_DIR" ]]; then
  rm -rf "$NVIM_INSTALL_DIR"
fi

tar -C "$HOME/.local" -xzf "$NVIM_TARBALL"
rm "$NVIM_TARBALL"

log_info "Creating symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$NVIM_INSTALL_DIR/bin/nvim" "$NVIM_BIN_LINK"

if command -v nvim >/dev/null 2>&1; then
  INSTALLED_VERSION=$(nvim --version | head -n1)
  log_success " $INSTALLED_VERSION"
else
  log_error " Installation verification failed"
  log_info "Make sure ~/.local/bin is in your PATH"
  exit 1
fi
