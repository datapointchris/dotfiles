#!/usr/bin/env bash
# ================================================================
# Install Latest fzf by Building from Source
# ================================================================
# Clones fzf repository and builds from source with Go
# Installation location: ~/.local/bin/fzf
# Requires: Go toolchain (/usr/local/go/bin/go)
# ================================================================

set -euo pipefail

FZF_BIN="$HOME/.local/bin/fzf"
FZF_BUILD_DIR="/tmp/fzf-build"
REQUIRED_FZF_VERSION="0.50"  # Minimum acceptable version

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Building fzf from Source"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verify Go is installed and add to PATH if needed
if ! command -v go >/dev/null 2>&1; then
  # Check if Go is installed in /usr/local/go/bin (standard location)
  if [[ -f "/usr/local/go/bin/go" ]]; then
    echo "  Adding Go to PATH..."
    export PATH="/usr/local/go/bin:$PATH"
  else
    echo "  ✗ Go not found (required for building)"
    echo "  Run: task wsl:install-go"
    exit 1
  fi
fi

GO_VERSION=$(go version | awk '{print $3}')
echo "  Using $GO_VERSION"

# Check if fzf is already installed with acceptable version
if [[ -f "$FZF_BIN" ]] && command -v fzf >/dev/null 2>&1; then
  CURRENT_VERSION=$(fzf --version | awk '{print $1}')
  echo "  Current version: $CURRENT_VERSION"

  # Simple version comparison
  if [[ $(echo -e "$REQUIRED_FZF_VERSION\n$CURRENT_VERSION" | sort -V | head -n1) == "$REQUIRED_FZF_VERSION" ]]; then
    echo "  ✓ Acceptable version (>= $REQUIRED_FZF_VERSION), skipping"
    exit 0
  fi

  echo "  Rebuilding..."
fi

# Clean build directory
if [[ -d "$FZF_BUILD_DIR" ]]; then
  rm -rf "$FZF_BUILD_DIR"
fi

# Clone and build
echo "  Cloning repository..."
git clone https://github.com/junegunn/fzf.git "$FZF_BUILD_DIR"

echo "  Building..."
cd "$FZF_BUILD_DIR"
make

# Install
echo "  Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
cp target/fzf-linux_* "$FZF_BIN" 2>/dev/null || cp bin/fzf "$FZF_BIN"
chmod +x "$FZF_BIN"

# Cleanup
cd - > /dev/null
rm -rf "$FZF_BUILD_DIR"

# Verify
if command -v fzf >/dev/null 2>&1; then
  INSTALLED_VERSION=$(fzf --version)
  echo "  ✓ $INSTALLED_VERSION"
else
  echo "  ✗ Installation verification failed"
  echo "  Make sure ~/.local/bin is in your PATH"
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " fzf build complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
