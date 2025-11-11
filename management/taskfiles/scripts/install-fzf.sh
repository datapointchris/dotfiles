#!/usr/bin/env bash
# ================================================================
# Install Latest fzf by Building from Source
# ================================================================
# Clones fzf repository and builds from source with Go
# Installation location: ~/.local/bin/fzf
# Requires: Go toolchain (/usr/local/go/bin/go)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

FZF_BIN="$HOME/.local/bin/fzf"
FZF_BUILD_DIR="/tmp/fzf-build"
REQUIRED_FZF_VERSION="0.50"  # Minimum acceptable version

print_banner "Building fzf from Source"

# Verify Go is installed and add to PATH if needed
if ! command -v go >/dev/null 2>&1; then
  # Check if Go is installed in /usr/local/go/bin (standard location)
  if [[ -f "/usr/local/go/bin/go" ]]; then
    print_info "Adding Go to PATH..."
    export PATH="/usr/local/go/bin:$PATH"
  else
    print_error "Go not found (required for building)"
    echo "  Run: task wsl:install-go"
    exit 1
  fi
fi

GO_VERSION=$(go version | awk '{print $3}')
print_info "Using $GO_VERSION"

# Check if fzf is already installed with acceptable version
if [[ -f "$FZF_BIN" ]] && command -v fzf >/dev/null 2>&1; then
  CURRENT_VERSION=$(fzf --version | awk '{print $1}')
  print_info "Current version: $CURRENT_VERSION"

  # Simple version comparison
  if [[ $(echo -e "$REQUIRED_FZF_VERSION\n$CURRENT_VERSION" | sort -V | head -n1) == "$REQUIRED_FZF_VERSION" ]]; then
    print_success "Acceptable version (>= $REQUIRED_FZF_VERSION), skipping"
    exit 0
  fi

  print_info "Rebuilding..."
fi

# Clean build directory
if [[ -d "$FZF_BUILD_DIR" ]]; then
  rm -rf "$FZF_BUILD_DIR"
fi

# Clone and build
print_info "Cloning repository..."
git clone https://github.com/junegunn/fzf.git "$FZF_BUILD_DIR"

print_info "Building..."
cd "$FZF_BUILD_DIR"
make

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

print_banner_success "fzf build complete"
