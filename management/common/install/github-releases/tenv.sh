#!/usr/bin/env bash
# ================================================================
# Install tenv from GitHub Releases
# ================================================================
# Downloads and installs tenv (Terraform/OpenTofu version manager)
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/tenv
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
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=tenv --field=repo)

# Detect platform and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="Darwin"
  ARCH=$(uname -m)
  # tenv uses x86_64 and arm64 directly (not amd64)
else
  PLATFORM="Linux"
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    ARCH="x86_64"
  elif [[ "$ARCH" == "aarch64" ]]; then
    ARCH="arm64"
  fi
fi

TENV_BIN="$HOME/.local/bin/tenv"

print_banner "Installing tenv"

# Check if tenv is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$TENV_BIN" ]] && command -v tenv >/dev/null 2>&1; then
  CURRENT_VERSION=$(tenv --version 2>&1 | head -n1 || echo "unknown")
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Get latest version from GitHub API
LATEST_VERSION=$(get_latest_github_release "$REPO")
print_info "Target version: $LATEST_VERSION"

# Check for alternate installations
if [[ ! -f "$TENV_BIN" ]] && command -v tenv >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v tenv)
  print_warning " tenv found at $ALTERNATE_LOCATION"
  print_info "Installing to $TENV_BIN anyway (PATH priority will use this one)"
fi

# Download URL
TENV_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/tenv_${LATEST_VERSION}_${PLATFORM}_${ARCH}.tar.gz"
TENV_TARBALL="/tmp/tenv.tar.gz"

# Download
if ! download_file "$TENV_URL" "$TENV_TARBALL" "tenv"; then
  print_manual_install "tenv" "$TENV_URL" "$LATEST_VERSION" "tenv_${LATEST_VERSION}_${PLATFORM}_${ARCH}.tar.gz" \
    "tar -xzf ~/Downloads/tenv_${LATEST_VERSION}_${PLATFORM}_${ARCH}.tar.gz -C /tmp && mv /tmp/tenv ~/.local/bin/ && chmod +x ~/.local/bin/tenv"
  exit 1
fi

# Extract
print_info "Extracting..."
tar -xzf "$TENV_TARBALL" -C /tmp

# Install
print_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"

# Move all binaries from tarball (tenv + proxy binaries)
for binary in tenv terraform tofu terragrunt terramate atmos tf; do
  if [ -f "/tmp/$binary" ]; then
    mv "/tmp/$binary" "$HOME/.local/bin/"
    chmod +x "$HOME/.local/bin/$binary"
  fi
done

# Cleanup
rm -f "$TENV_TARBALL"

# Verify installation
if command -v tenv >/dev/null 2>&1; then
  INSTALLED_VERSION=$(tenv --version 2>&1 | head -n1 || echo "unknown")
  print_success "Installed: $INSTALLED_VERSION"
else
  print_error "Installation failed - tenv command not found in PATH"
  exit 1
fi
