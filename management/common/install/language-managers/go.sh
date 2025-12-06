#!/usr/bin/env bash
# ================================================================
# Install Latest Go from go.dev
# ================================================================
# Downloads and installs the latest stable Go release
# Configuration read from: management/packages.yml
# Installation location: /usr/local/go (official recommendation)
# Requires: sudo (for system-wide installation)
# ================================================================

set -uo pipefail

# Source formatting library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Source helper functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/install-helpers.sh"

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

if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -n "$GO_BIN" ]]; then
  CURRENT_VERSION=$($GO_BIN version | awk '{print $3}' | sed 's/go//')
  log_info "Current version: $CURRENT_VERSION"

  # Compare versions (simple major.minor comparison)
  CURRENT_MAJOR=$(echo "$CURRENT_VERSION" | cut -d. -f1)
  CURRENT_MINOR=$(echo "$CURRENT_VERSION" | cut -d. -f2)
  REQUIRED_MAJOR=$(echo "$MIN_VERSION" | cut -d. -f1)
  REQUIRED_MINOR=$(echo "$MIN_VERSION" | cut -d. -f2)

  if [[ $CURRENT_MAJOR -gt $REQUIRED_MAJOR ]] || \
     [[ $CURRENT_MAJOR -eq $REQUIRED_MAJOR && $CURRENT_MINOR -ge $REQUIRED_MINOR ]]; then
    log_success "Acceptable version (>= $MIN_VERSION), skipping"
    exit 0
  fi

  log_info "Upgrading from $CURRENT_VERSION..."
fi

# Check for alternate installations
if [[ ! -x "/usr/local/go/bin/go" ]] && command -v go >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v go)
  log_warning " go found at $ALTERNATE_LOCATION"
  log_info "Installing to /usr/local/go/bin/go anyway (PATH priority will use this one)"
fi

# Detect platform and architecture
PLATFORM=$(uname -s)
ARCH=$(uname -m)
case $ARCH in
  x86_64)
    GO_ARCH="amd64"
    ;;
  aarch64|arm64)
    GO_ARCH="arm64"
    ;;
  *)
    log_error " Unsupported architecture: $ARCH"
    exit 1
    ;;
esac

# Detect platform
case $PLATFORM in
  Darwin)
    GO_OS="darwin"
    ;;
  Linux)
    GO_OS="linux"
    ;;
  *)
    log_error " Unsupported platform: $PLATFORM"
    exit 1
    ;;
esac

# Get latest version
log_info "Fetching latest version..."
if ! GO_VERSION=$(curl -sf https://go.dev/VERSION?m=text | head -n1); then
  log_error "Failed to fetch Go version from go.dev"
  manual_steps="Failed to fetch latest version.

Manual installation:
1. Visit: https://go.dev/dl/
2. Download: go*.${GO_OS}-${GO_ARCH}.tar.gz
3. Install: sudo rm -rf /usr/local/go && sudo tar -C /usr/local -xzf ~/Downloads/go*.tar.gz
4. Add to PATH: export PATH=\$PATH:/usr/local/go/bin
5. Verify: go version"
  output_failure_data "go" "https://go.dev/dl/" "latest" "$manual_steps" "Failed to fetch version"
  log_error "Go installation failed"
  exit 1
fi

log_info "Latest: $GO_VERSION ($PLATFORM/$ARCH → $GO_OS/$GO_ARCH)"

# Download URL
GO_URL="https://go.dev/dl/${GO_VERSION}.${GO_OS}-${GO_ARCH}.tar.gz"
GO_TARBALL="/tmp/${GO_VERSION}.${GO_OS}-${GO_ARCH}.tar.gz"

# Download
log_info "Downloading Go..."
if ! curl -fsSL "$GO_URL" -o "$GO_TARBALL"; then
  manual_steps="1. Download in your browser (bypasses firewall):
   $GO_URL

2. After downloading, install:
   sudo rm -rf /usr/local/go
   sudo tar -C /usr/local -xzf ~/Downloads/${GO_VERSION}.${GO_OS}-${GO_ARCH}.tar.gz

3. Add to PATH:
   export PATH=\$PATH:/usr/local/go/bin

4. Verify installation:
   go version"
  output_failure_data "go" "$GO_URL" "$GO_VERSION" "$manual_steps" "Download failed"
  log_error "Go installation failed"
  exit 1
fi

# Install
log_info "Installing to /usr/local/go..."
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf "$GO_TARBALL"
rm "$GO_TARBALL"

# Verify
if /usr/local/go/bin/go version >/dev/null 2>&1; then
  INSTALLED_VERSION=$(/usr/local/go/bin/go version)
  log_success " $INSTALLED_VERSION"
else
  log_error " Installation verification failed"
  exit 1
fi

print_banner_success "Go installation complete"
