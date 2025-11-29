#!/usr/bin/env bash
# ================================================================
# Install tflint from GitHub Releases
# ================================================================
# Downloads and installs TFLint (Terraform linter)
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/tflint
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Source helper functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/program-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=tflint --field=repo)

# Detect platform and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="darwin"
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    ARCH="amd64"
  elif [[ "$ARCH" == "arm64" ]]; then
    ARCH="arm64"
  fi
else
  PLATFORM="linux"
  ARCH="amd64"
fi

TFLINT_BIN="$HOME/.local/bin/tflint"

print_banner "Installing tflint"

# Check if tflint is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$TFLINT_BIN" ]] && command -v tflint >/dev/null 2>&1; then
  CURRENT_VERSION=$(tflint --version 2>&1 | head -n1 || echo "unknown")
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Get latest version from GitHub API
LATEST_VERSION=$(get_latest_github_release "$REPO")
print_info "Target version: $LATEST_VERSION"

# Check for alternate installations
if [[ ! -f "$TFLINT_BIN" ]] && command -v tflint >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v tflint)
  print_warning " tflint found at $ALTERNATE_LOCATION"
  print_info "Installing to $TFLINT_BIN anyway (PATH priority will use this one)"
fi

# Download URL
TFLINT_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/tflint_${PLATFORM}_${ARCH}.zip"
TFLINT_ZIP="/tmp/tflint.zip"

# Download
if ! download_file "$TFLINT_URL" "$TFLINT_ZIP" "tflint"; then
  print_manual_install "tflint" "$TFLINT_URL" "$LATEST_VERSION" "tflint_${PLATFORM}_${ARCH}.zip" \
    "unzip ~/Downloads/tflint_${PLATFORM}_${ARCH}.zip -d /tmp && mv /tmp/tflint ~/.local/bin/ && chmod +x ~/.local/bin/tflint"
  exit 1
fi

# Extract
print_info "Extracting..."
unzip -q "$TFLINT_ZIP" -d /tmp

# Install
print_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
mv /tmp/tflint "$TFLINT_BIN"
chmod +x "$TFLINT_BIN"

# Cleanup
rm -f "$TFLINT_ZIP"

# Verify installation
if command -v tflint >/dev/null 2>&1; then
  INSTALLED_VERSION=$(tflint --version 2>&1 | head -n1 || echo "unknown")
  print_success "Installed: $INSTALLED_VERSION"
else
  print_error "Installation failed - tflint command not found in PATH"
  exit 1
fi
