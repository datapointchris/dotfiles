#!/usr/bin/env bash
# ================================================================
# Install terraformer from GitHub Releases
# ================================================================
# Downloads and installs Terraformer (reverse Terraform)
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/terraformer
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
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=terraformer --field=repo)

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

# Use 'all' provider to support all cloud providers
PROVIDER="all"
TERRAFORMER_BIN="$HOME/.local/bin/terraformer"

print_banner "Installing terraformer"

# Check if terraformer is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$TERRAFORMER_BIN" ]] && command -v terraformer >/dev/null 2>&1; then
  CURRENT_VERSION=$(terraformer version 2>&1 | head -n1 || echo "unknown")
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Get latest version from GitHub API
LATEST_VERSION=$(get_latest_github_release "$REPO")
print_info "Target version: $LATEST_VERSION"

# Check for alternate installations
if [[ ! -f "$TERRAFORMER_BIN" ]] && command -v terraformer >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v terraformer)
  print_warning " terraformer found at $ALTERNATE_LOCATION"
  print_info "Installing to $TERRAFORMER_BIN anyway (PATH priority will use this one)"
fi

# Download URL (direct binary, not archived)
TERRAFORMER_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/terraformer-${PROVIDER}-${PLATFORM}-${ARCH}"

# Download directly to final location
print_info "Downloading..."
mkdir -p "$HOME/.local/bin"

if ! download_file "$TERRAFORMER_URL" "$TERRAFORMER_BIN" "terraformer"; then
  print_manual_install "terraformer" "$TERRAFORMER_URL" "$LATEST_VERSION" "terraformer-${PROVIDER}-${PLATFORM}-${ARCH}" \
    "mv ~/Downloads/terraformer-${PROVIDER}-${PLATFORM}-${ARCH} ~/.local/bin/terraformer && chmod +x ~/.local/bin/terraformer"
  exit 1
fi

# Make executable
chmod +x "$TERRAFORMER_BIN"

# Verify installation
if command -v terraformer >/dev/null 2>&1; then
  INSTALLED_VERSION=$(terraformer version 2>&1 | head -n1 || echo "unknown")
  print_success "Installed: $INSTALLED_VERSION"
else
  print_error "Installation failed - terraformer command not found in PATH"
  exit 1
fi
