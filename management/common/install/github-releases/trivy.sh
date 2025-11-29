#!/usr/bin/env bash
# ================================================================
# Install Trivy from GitHub Releases
# ================================================================
# Downloads and installs Trivy (Container/IaC vulnerability scanner)
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/trivy
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
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=trivy --field=repo)

# Detect platform and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    PLATFORM_ARCH="macOS-64bit"
  else
    PLATFORM_ARCH="macOS-ARM64"
  fi
else
  ARCH=$(uname -m)
  if [[ "$ARCH" == "aarch64" ]]; then
    PLATFORM_ARCH="Linux-ARM64"
  else
    PLATFORM_ARCH="Linux-64bit"
  fi
fi

TRIVY_BIN="$HOME/.local/bin/trivy"

print_banner "Installing Trivy"

# Check if Trivy is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$TRIVY_BIN" ]] && command -v trivy >/dev/null 2>&1; then
  CURRENT_VERSION=$(trivy --version 2>&1 | head -n1 || echo "unknown")
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Get latest version from GitHub API
LATEST_VERSION=$(get_latest_github_release "$REPO")
print_info "Target version: $LATEST_VERSION"

# Check for alternate installations
if [[ ! -f "$TRIVY_BIN" ]] && command -v trivy >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v trivy)
  print_warning " trivy found at $ALTERNATE_LOCATION"
  print_info "Installing to $TRIVY_BIN anyway (PATH priority will use this one)"
fi

# Download URL
TRIVY_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/trivy_${LATEST_VERSION#v}_${PLATFORM_ARCH}.tar.gz"
TRIVY_TARBALL="/tmp/trivy.tar.gz"

# Download
if ! download_file "$TRIVY_URL" "$TRIVY_TARBALL" "trivy"; then
  print_manual_install "trivy" "$TRIVY_URL" "$LATEST_VERSION" "trivy_${LATEST_VERSION#v}_${PLATFORM_ARCH}.tar.gz" \
    "tar -xzf ~/Downloads/trivy_${LATEST_VERSION#v}_${PLATFORM_ARCH}.tar.gz -C /tmp && mv /tmp/trivy ~/.local/bin/ && chmod +x ~/.local/bin/trivy"
  exit 1
fi

# Extract
print_info "Extracting..."
tar -xzf "$TRIVY_TARBALL" -C /tmp

# Install
print_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
mv /tmp/trivy "$TRIVY_BIN"
chmod +x "$TRIVY_BIN"

# Cleanup
rm -f "$TRIVY_TARBALL"

# Verify installation
if command -v trivy >/dev/null 2>&1; then
  INSTALLED_VERSION=$(trivy --version 2>&1 | head -n1 || echo "unknown")
  print_success "Installed: $INSTALLED_VERSION"
else
  print_error "Installation failed - trivy command not found in PATH"
  exit 1
fi
