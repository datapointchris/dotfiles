#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/lib/platform-detection.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/install-helpers.sh"

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
MIN_VERSION=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=neovim --field=min_version)
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=neovim --field=repo)

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

print_banner "Installing Neovim"

if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -L "$NVIM_BIN_LINK" ]] && command -v nvim >/dev/null 2>&1; then
  CURRENT_VERSION=$(nvim --version | head -n1 | sed 's/.*v\([0-9]*\.[0-9]*\).*/\1/')
  log_info "Current version: $CURRENT_VERSION"

  # Simple version comparison (major.minor)
  if [[ $(echo -e "$MIN_VERSION\n$CURRENT_VERSION" | sort -V | head -n1) == "$MIN_VERSION" ]]; then
    log_success " Acceptable version (>= $MIN_VERSION), skipping"
    exit 0
  fi

  log_info "Upgrading..."
fi

NVIM_VERSION=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name":' | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
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

log_info "Latest: $NVIM_VERSION"

if [[ ! -L "$NVIM_BIN_LINK" ]] && command -v nvim >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v nvim)
  log_warning " nvim found at $ALTERNATE_LOCATION"
  log_info "Installing to $NVIM_BIN_LINK anyway (PATH priority will use this one)"
fi

NVIM_URL="https://github.com/${REPO}/releases/download/${NVIM_VERSION}/${NVIM_BINARY}.tar.gz"
NVIM_TARBALL="/tmp/${NVIM_BINARY}.tar.gz"

log_info "Downloading Neovim..."
if ! curl -fsSL "$NVIM_URL" -o "$NVIM_TARBALL"; then
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
