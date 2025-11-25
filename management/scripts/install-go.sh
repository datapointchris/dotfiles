#!/usr/bin/env bash
# ================================================================
# Install Latest Go from go.dev
# ================================================================
# Downloads and installs the latest stable Go release
# Configuration read from: management/packages.yml
# Installation location: /usr/local/go (official recommendation)
# Requires: sudo (for system-wide installation)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Source helper functions
source "$(dirname "$0")/install-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
MIN_VERSION=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --get=runtimes.go.min_version)

print_banner "Installing Go"

# Check if Go is already installed with acceptable version
# Check both in PATH and at standard installation location
GO_BIN=""
if command -v go >/dev/null 2>&1; then
  GO_BIN="go"
elif [[ -x "/usr/local/go/bin/go" ]]; then
  GO_BIN="/usr/local/go/bin/go"
fi

if [[ -n "$GO_BIN" ]]; then
  CURRENT_VERSION=$($GO_BIN version | awk '{print $3}' | sed 's/go//')
  print_info "Current version: $CURRENT_VERSION"

  # Compare versions (simple major.minor comparison)
  CURRENT_MAJOR=$(echo "$CURRENT_VERSION" | cut -d. -f1)
  CURRENT_MINOR=$(echo "$CURRENT_VERSION" | cut -d. -f2)
  REQUIRED_MAJOR=$(echo "$MIN_VERSION" | cut -d. -f1)
  REQUIRED_MINOR=$(echo "$MIN_VERSION" | cut -d. -f2)

  if [[ $CURRENT_MAJOR -gt $REQUIRED_MAJOR ]] || \
     [[ $CURRENT_MAJOR -eq $REQUIRED_MAJOR && $CURRENT_MINOR -ge $REQUIRED_MINOR ]]; then
    print_success "Acceptable version (>= $MIN_VERSION), skipping"
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
print_info "Fetching latest version..."
if ! GO_VERSION=$(curl -sf https://go.dev/VERSION?m=text | head -n1); then
  print_error " Failed to fetch Go version from go.dev"
  print_manual_install "go" "https://go.dev/dl/" "latest" "go*.linux-${GO_ARCH}.tar.gz" \
    "sudo rm -rf /usr/local/go && sudo tar -C /usr/local -xzf ~/Downloads/go*.linux-${GO_ARCH}.tar.gz"
  exit 1
fi

print_info "Latest: $GO_VERSION ($ARCH → $GO_ARCH)"

# Download URL
GO_URL="https://go.dev/dl/${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
GO_TARBALL="/tmp/${GO_VERSION}.linux-${GO_ARCH}.tar.gz"

# Download
if ! download_file "$GO_URL" "$GO_TARBALL" "go"; then
  print_manual_install "go" "$GO_URL" "$GO_VERSION" "${GO_VERSION}.linux-${GO_ARCH}.tar.gz" \
    "sudo rm -rf /usr/local/go && sudo tar -C /usr/local -xzf ~/Downloads/${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
  exit 1
fi

# Install
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
