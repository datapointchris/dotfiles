#!/usr/bin/env bash
# ================================================================
# Install Latest Go from go.dev
# ================================================================
# Downloads and installs the latest stable Go release
# Installation location: /usr/local/go (official recommendation)
# Requires: sudo (for system-wide installation)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

REQUIRED_GO_VERSION="1.23"  # Minimum acceptable version

print_banner "Installing Go"

# Check if Go is already installed with acceptable version
if command -v go >/dev/null 2>&1; then
  CURRENT_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
  print_info "Current version: $CURRENT_VERSION"

  # Compare versions (simple major.minor comparison)
  CURRENT_MAJOR=$(echo "$CURRENT_VERSION" | cut -d. -f1)
  CURRENT_MINOR=$(echo "$CURRENT_VERSION" | cut -d. -f2)
  REQUIRED_MAJOR=$(echo "$REQUIRED_GO_VERSION" | cut -d. -f1)
  REQUIRED_MINOR=$(echo "$REQUIRED_GO_VERSION" | cut -d. -f2)

  if [[ $CURRENT_MAJOR -gt $REQUIRED_MAJOR ]] || \
     [[ $CURRENT_MAJOR -eq $REQUIRED_MAJOR && $CURRENT_MINOR -ge $REQUIRED_MINOR ]]; then
    print_success "Acceptable version (>= $REQUIRED_GO_VERSION), skipping"
    exit 0
  fi

  print_info "Upgrading from $CURRENT_VERSION..."
fi

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
  x86_64)
    GO_ARCH="amd64"
    ;;
  aarch64|arm64)
    GO_ARCH="arm64"
    ;;
  *)
    print_error " Unsupported architecture: $ARCH"
    exit 1
    ;;
esac

# Get latest version
 Fetching latest version..."
GO_VERSION=$(curl -s https://go.dev/VERSION?m=text | head -n1)
 Latest: $GO_VERSION ($ARCH → $GO_ARCH)"

# Download URL
GO_URL="https://go.dev/dl/${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
GO_TARBALL="/tmp/${GO_VERSION}.linux-${GO_ARCH}.tar.gz"

# Download and install
print_info "Downloading..."
curl -# -L "$GO_URL" -o "$GO_TARBALL"

print_info "Installing to /usr/local/go..."
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf "$GO_TARBALL"
rm "$GO_TARBALL"

# Verify
if /usr/local/go/bin/go version >/dev/null 2>&1; then
  INSTALLED_VERSION=$(/usr/local/go/bin/go version)
  print_success " $INSTALLED_VERSION"
else
  print_error " Installation verification failed"
  exit 1
fi

print_banner_success "Go installation complete"
