#!/usr/bin/env bash
# ================================================================
# Install Latest Neovim from GitHub Releases
# ================================================================
# Downloads and installs the latest stable Neovim release
# Installation location: ~/.local/nvim-linux64/
# Binary symlink: ~/.local/bin/nvim
# No sudo required (user space)
# ================================================================

set -euo pipefail

NVIM_INSTALL_DIR="$HOME/.local/nvim-linux-x86_64"
NVIM_BIN_LINK="$HOME/.local/bin/nvim"
REQUIRED_NVIM_VERSION="0.11"  # Minimum acceptable version

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Installing Neovim"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if Neovim is already installed with acceptable version
if [[ -L "$NVIM_BIN_LINK" ]] && command -v nvim >/dev/null 2>&1; then
  CURRENT_VERSION=$(nvim --version | head -n1 | grep -oP 'v\K[0-9]+\.[0-9]+')
  echo "  Current version: $CURRENT_VERSION"

  # Simple version comparison (major.minor)
  if [[ $(echo -e "$REQUIRED_NVIM_VERSION\n$CURRENT_VERSION" | sort -V | head -n1) == "$REQUIRED_NVIM_VERSION" ]]; then
    echo "  ✓ Acceptable version (>= $REQUIRED_NVIM_VERSION), skipping"
    exit 0
  fi

  echo "  Upgrading..."
fi

# Get latest version
echo "  Fetching latest version..."
NVIM_VERSION=$(curl -s "https://api.github.com/repos/neovim/neovim/releases/latest" | grep -Po '"tag_name": *"\K[^"]*')
echo "  Latest: $NVIM_VERSION"

# Download URL (neovim changed filename from nvim-linux64 to nvim-linux-x86_64)
NVIM_URL="https://github.com/neovim/neovim/releases/download/${NVIM_VERSION}/nvim-linux-x86_64.tar.gz"
NVIM_TARBALL="/tmp/nvim-linux-x86_64.tar.gz"

# Download
echo "  Downloading..."
if ! curl -# -L "$NVIM_URL" -o "$NVIM_TARBALL"; then
  echo "  ✗ Download failed"
  exit 1
fi

# Verify download
if [[ ! -f "$NVIM_TARBALL" ]] || [[ ! -s "$NVIM_TARBALL" ]]; then
  echo "  ✗ Downloaded file is missing or empty"
  exit 1
fi

# Verify it's a valid gzip file
if ! file "$NVIM_TARBALL" | grep -q "gzip compressed"; then
  echo "  ✗ Not a valid gzip archive: $(file "$NVIM_TARBALL")"
  echo "  URL: $NVIM_URL"
  exit 1
fi

# Install
echo "  Installing to ~/.local/..."
if [[ -d "$NVIM_INSTALL_DIR" ]]; then
  rm -rf "$NVIM_INSTALL_DIR"
fi

tar -C "$HOME/.local" -xzf "$NVIM_TARBALL"
rm "$NVIM_TARBALL"

echo "  Creating symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$NVIM_INSTALL_DIR/bin/nvim" "$NVIM_BIN_LINK"

# Verify
if command -v nvim >/dev/null 2>&1; then
  INSTALLED_VERSION=$(nvim --version | head -n1)
  echo "  ✓ $INSTALLED_VERSION"
else
  echo "  ✗ Installation verification failed"
  echo "  Make sure ~/.local/bin is in your PATH"
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Neovim installation complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
