#!/usr/bin/env bash
# ================================================================
# Install Latest LazyGit from GitHub Releases
# ================================================================
# Downloads and installs the latest stable LazyGit release
# Installation location: ~/.local/bin/lazygit
# No sudo required (user space)
# ================================================================

set -euo pipefail

LAZYGIT_BIN="$HOME/.local/bin/lazygit"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Installing LazyGit"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if LazyGit is already installed
if [[ -f "$LAZYGIT_BIN" ]] && command -v lazygit >/dev/null 2>&1; then
  CURRENT_VERSION=$(lazygit --version | head -n1)
  echo "  Current version: $CURRENT_VERSION"
fi

# Get latest version
echo "  Fetching latest version..."
LAZYGIT_VERSION=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" | grep -Po '"tag_name": *"v\K[^"]*')
echo "  Latest: v$LAZYGIT_VERSION"

# Download URL
LAZYGIT_URL="https://github.com/jesseduffield/lazygit/releases/download/v${LAZYGIT_VERSION}/lazygit_${LAZYGIT_VERSION}_Linux_x86_64.tar.gz"
LAZYGIT_TARBALL="/tmp/lazygit.tar.gz"

# Download and install
echo "  Downloading..."
curl -# -L "$LAZYGIT_URL" -o "$LAZYGIT_TARBALL"

echo "  Extracting..."
tar -xzf "$LAZYGIT_TARBALL" -C /tmp lazygit

echo "  Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
mv /tmp/lazygit "$LAZYGIT_BIN"
chmod +x "$LAZYGIT_BIN"
rm "$LAZYGIT_TARBALL"

# Verify
if command -v lazygit >/dev/null 2>&1; then
  INSTALLED_VERSION=$(lazygit --version | head -n1)
  echo "  ✓ $INSTALLED_VERSION"
else
  echo "  ✗ Installation verification failed"
  echo "  Make sure ~/.local/bin is in your PATH"
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " LazyGit installation complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
