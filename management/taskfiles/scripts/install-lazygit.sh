#!/usr/bin/env bash
# ================================================================
# Install Latest LazyGit from GitHub Releases
# ================================================================
# Downloads and installs the latest stable LazyGit release
# Installation location: ~/.local/bin/lazygit
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

LAZYGIT_BIN="$HOME/.local/bin/lazygit"

print_banner "Installing LazyGit"

# Check if LazyGit is already installed
if [[ -f "$LAZYGIT_BIN" ]] && command -v lazygit >/dev/null 2>&1; then
  CURRENT_VERSION=$(lazygit --version | head -n1)
  print_info "Current version: $CURRENT_VERSION"
  exit 0
fi

# Get latest version
print_info "Fetching latest version..."
LAZYGIT_VERSION=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" | grep -Po '"tag_name": *"v\K[^"]*')
print_info "Latest: v$LAZYGIT_VERSION"

# Download URL
LAZYGIT_URL="https://github.com/jesseduffield/lazygit/releases/download/v${LAZYGIT_VERSION}/lazygit_${LAZYGIT_VERSION}_linux_x86_64.tar.gz"
LAZYGIT_URL="https://github.com/jesseduffield/lazygit/releases/download/v0.56.0/lazygit_0.56.0_linux_x86_64.tar.gz"
LAZYGIT_TARBALL="/tmp/lazygit.tar.gz"

# Download and install
print_info "Downloading..."
curl -# -L "$LAZYGIT_URL" -o "$LAZYGIT_TARBALL"

print_info "Extracting..."
tar -xzf "$LAZYGIT_TARBALL" -C /tmp lazygit

print_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
mv /tmp/lazygit "$LAZYGIT_BIN"
chmod +x "$LAZYGIT_BIN"
rm "$LAZYGIT_TARBALL"

# Verify
if command -v lazygit >/dev/null 2>&1; then
  INSTALLED_VERSION=$(lazygit --version | head -n1)
  print_success " $INSTALLED_VERSION"
else
  print_error " Installation verification failed"
  print_info "Make sure ~/.local/bin is in your PATH"
  exit 1
fi

print_banner_success "LazyGit installation complete"
