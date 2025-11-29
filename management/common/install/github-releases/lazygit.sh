#!/usr/bin/env bash
# ================================================================
# Install LazyGit from GitHub Releases
# ================================================================
# Downloads and installs stable LazyGit release
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/lazygit
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source structured logging library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/structured-logging.sh"

# Source helper functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/program-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
LAZYGIT_VERSION=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=lazygit --field=version)
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=lazygit --field=repo)

# Detect platform and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    PLATFORM_ARCH="Darwin_x86_64"
  else
    PLATFORM_ARCH="Darwin_arm64"
  fi
else
  PLATFORM_ARCH="Linux_x86_64"
fi

LAZYGIT_BIN="$HOME/.local/bin/lazygit"

print_banner "Installing LazyGit"

# Check if LazyGit is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$LAZYGIT_BIN" ]] && command -v lazygit >/dev/null 2>&1; then
  CURRENT_VERSION=$(lazygit --version 2>&1 | head -n1 || echo "unknown")
  print_info "Current version: $CURRENT_VERSION"

  # Check if current version matches desired version
  if echo "$CURRENT_VERSION" | grep -q "$LAZYGIT_VERSION"; then
    print_success " Version $LAZYGIT_VERSION already installed, skipping"
    exit 0
  fi
fi

print_info "Target version: v$LAZYGIT_VERSION"

# Check for alternate installations
if [[ ! -f "$LAZYGIT_BIN" ]] && command -v lazygit >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v lazygit)
  print_warning " lazygit found at $ALTERNATE_LOCATION"
  print_info "Installing to $LAZYGIT_BIN anyway (PATH priority will use this one)"
fi

# Download URL
LAZYGIT_URL="https://github.com/${REPO}/releases/download/v${LAZYGIT_VERSION}/lazygit_${LAZYGIT_VERSION}_${PLATFORM_ARCH}.tar.gz"
LAZYGIT_TARBALL="/tmp/lazygit.tar.gz"

# Download
if ! download_file "$LAZYGIT_URL" "$LAZYGIT_TARBALL" "lazygit"; then
  print_manual_install "lazygit" "$LAZYGIT_URL" "v$LAZYGIT_VERSION" "lazygit_${LAZYGIT_VERSION}_${PLATFORM_ARCH}.tar.gz" \
    "tar -xzf ~/Downloads/lazygit_${LAZYGIT_VERSION}_${PLATFORM_ARCH}.tar.gz -C /tmp && mv /tmp/lazygit ~/.local/bin/ && chmod +x ~/.local/bin/lazygit"
  exit 1
fi

# Extract
print_info "Extracting..."
tar -xzf "$LAZYGIT_TARBALL" -C /tmp lazygit

# Install
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
