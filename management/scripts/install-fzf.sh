#!/usr/bin/env bash
# ================================================================
# Install fzf (Fuzzy Finder) by Building from Source
# ================================================================
# Builds latest fzf from source using Go
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/fzf
# Requires: Go (must be installed first)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Source helper functions
source "$(dirname "$0")/install-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
MIN_VERSION=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=fzf --field=min_version)
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=fzf --field=repo)

FZF_BIN="$HOME/.local/bin/fzf"
FZF_BUILD_DIR="/tmp/fzf-build"

print_banner "Installing fzf (Fuzzy Finder)"

# Check for Go
if ! command -v go >/dev/null 2>&1; then
  if [[ -x /usr/local/go/bin/go ]]; then
    print_info "Using Go from /usr/local/go/bin"
    export PATH="/usr/local/go/bin:$PATH"
  else
    print_error "Go not found (required for building)"
    echo "  Run: task wsl:install-go"
    exit 1
  fi
fi

GO_VERSION=$(go version | awk '{print $3}')
print_info "Using $GO_VERSION"

# Check if fzf is already installed
if [[ -f "$FZF_BIN" ]] && command -v fzf >/dev/null 2>&1; then
  CURRENT_VERSION=$(fzf --version | awk '{print $1}')
  print_info "Current version: $CURRENT_VERSION"

  # Simple version comparison
  if [[ $(echo -e "$MIN_VERSION\n$CURRENT_VERSION" | sort -V | head -n1) == "$MIN_VERSION" ]]; then
    print_success "Acceptable version (>= $MIN_VERSION), skipping"
    exit 0
  fi
fi

# Clone repository
print_info "Cloning fzf repository..."
if [[ -d "$FZF_BUILD_DIR" ]]; then
  rm -rf "$FZF_BUILD_DIR"
fi

if ! git clone "https://github.com/${REPO}.git" "$FZF_BUILD_DIR" 2>/dev/null; then
  print_error " Failed to clone repository"
  print_manual_install "fzf" "https://github.com/${REPO}/releases/latest" "latest" "fzf-*-linux_amd64.tar.gz" \
    "tar -xzf ~/Downloads/fzf-*-linux_amd64.tar.gz -C ~/.local/bin && chmod +x ~/.local/bin/fzf"
  exit 1
fi

# Build
print_info "Building from source..."
cd "$FZF_BUILD_DIR"
if ! make; then
  print_error " Build failed"
  rm -rf "$FZF_BUILD_DIR"
  exit 1
fi

# Install
print_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
cp target/fzf-linux_* "$FZF_BIN" 2>/dev/null || cp bin/fzf "$FZF_BIN"
chmod +x "$FZF_BIN"

# Cleanup
cd - > /dev/null
rm -rf "$FZF_BUILD_DIR"

# Verify
if command -v fzf >/dev/null 2>&1; then
  INSTALLED_VERSION=$(fzf --version)
  print_success "$INSTALLED_VERSION"
else
  print_error "Installation verification failed"
  echo "  Make sure ~/.local/bin is in your PATH"
  exit 1
fi

print_banner_success "fzf installation complete"
