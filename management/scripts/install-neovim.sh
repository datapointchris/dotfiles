#!/usr/bin/env bash
# ================================================================
# Install Latest Neovim from GitHub Releases
# ================================================================
# Downloads and installs the latest stable Neovim release
# Configuration read from: management/packages.yml
# Installation location: ~/.local/nvim-linux-x86_64/
# Binary symlink: ~/.local/bin/nvim
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Source helper functions
source "$(dirname "$0")/install-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
MIN_VERSION=$(python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=neovim --field=min_version)
REPO=$(python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=neovim --field=repo)

NVIM_INSTALL_DIR="$HOME/.local/nvim-linux-x86_64"
NVIM_BIN_LINK="$HOME/.local/bin/nvim"

print_banner "Installing Neovim"

# Check if Neovim is already installed with acceptable version
if [[ -L "$NVIM_BIN_LINK" ]] && command -v nvim >/dev/null 2>&1; then
  CURRENT_VERSION=$(nvim --version | head -n1 | grep -oP 'v\K[0-9]+\.[0-9]+')
  print_info "Current version: $CURRENT_VERSION"

  # Simple version comparison (major.minor)
  if [[ $(echo -e "$MIN_VERSION\n$CURRENT_VERSION" | sort -V | head -n1) == "$MIN_VERSION" ]]; then
    print_success " Acceptable version (>= $MIN_VERSION), skipping"
    exit 0
  fi

  print_info "Upgrading..."
fi

# Fetch latest version
NVIM_VERSION=$(fetch_latest_version "$REPO")
if [[ -z "$NVIM_VERSION" ]]; then
  print_manual_install "neovim" "https://github.com/${REPO}/releases/latest" "latest" "nvim-linux-x86_64.tar.gz" \
    "tar -C ~/.local -xzf ~/Downloads/nvim-linux-x86_64.tar.gz && ln -sf ~/.local/nvim-linux-x86_64/bin/nvim ~/.local/bin/nvim"
  exit 1
fi

print_info "Latest: $NVIM_VERSION"

# Download URL
NVIM_URL="https://github.com/${REPO}/releases/download/${NVIM_VERSION}/nvim-linux-x86_64.tar.gz"
NVIM_TARBALL="/tmp/nvim-linux-x86_64.tar.gz"

# Download
if ! download_file "$NVIM_URL" "$NVIM_TARBALL" "neovim"; then
  print_manual_install "neovim" "$NVIM_URL" "$NVIM_VERSION" "nvim-linux-x86_64.tar.gz" \
    "tar -C ~/.local -xzf ~/Downloads/nvim-linux-x86_64.tar.gz && ln -sf ~/.local/nvim-linux-x86_64/bin/nvim ~/.local/bin/nvim"
  exit 1
fi

# Verify it's a valid gzip file
if ! file "$NVIM_TARBALL" | grep -q "gzip compressed"; then
  print_error " Not a valid gzip archive: $(file "$NVIM_TARBALL")"
  print_info "URL: $NVIM_URL"
  print_manual_install "neovim" "$NVIM_URL" "$NVIM_VERSION" "nvim-linux-x86_64.tar.gz" \
    "tar -C ~/.local -xzf ~/Downloads/nvim-linux-x86_64.tar.gz && ln -sf ~/.local/nvim-linux-x86_64/bin/nvim ~/.local/bin/nvim"
  exit 1
fi

# Install
print_info "Installing to ~/.local/..."
if [[ -d "$NVIM_INSTALL_DIR" ]]; then
  rm -rf "$NVIM_INSTALL_DIR"
fi

tar -C "$HOME/.local" -xzf "$NVIM_TARBALL"
rm "$NVIM_TARBALL"

print_info "Creating symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$NVIM_INSTALL_DIR/bin/nvim" "$NVIM_BIN_LINK"

# Verify
if command -v nvim >/dev/null 2>&1; then
  INSTALLED_VERSION=$(nvim --version | head -n1)
  print_success " $INSTALLED_VERSION"
else
  print_error " Installation verification failed"
  print_info "Make sure ~/.local/bin is in your PATH"
  exit 1
fi

print_banner_success "Neovim installation complete"
