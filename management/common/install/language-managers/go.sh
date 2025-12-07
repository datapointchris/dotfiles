#!/usr/bin/env bash
set -uo pipefail

UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

if [[ "$UPDATE_MODE" == "true" ]]; then
  print_banner "Checking Go for updates"
else
  print_banner "Installing Go"
fi

# Check if Go is already installed
GO_BIN=""
if command -v go >/dev/null 2>&1; then
  GO_BIN="go"
elif [[ -x "/usr/local/go/bin/go" ]]; then
  GO_BIN="/usr/local/go/bin/go"
fi

# Check for alternate installations
if [[ ! -x "/usr/local/go/bin/go" ]] && command -v go >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v go)
  log_warning "go found at $ALTERNATE_LOCATION"
  log_info "Installing to /usr/local/go/bin/go anyway (PATH priority will use this one)"
fi

OS=$(detect_os)
ARCH=$(detect_arch)

case $ARCH in
  amd64)
    GO_ARCH="amd64"
    ;;
  arm64)
    GO_ARCH="arm64"
    ;;
  *)
    log_error "Unsupported architecture: $ARCH"
    exit 1
    ;;
esac

case $OS in
  darwin)
    GO_OS="darwin"
    ;;
  linux)
    GO_OS="linux"
    ;;
  *)
    log_error "Unsupported OS: $OS"
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

log_info "Latest version: $GO_VERSION"

# Check if update/install needed
if [[ "$UPDATE_MODE" == "true" ]]; then
  if [[ -z "$GO_BIN" ]]; then
    log_info "Go not installed, installing..."
  else
    CURRENT_VERSION_RAW=$($GO_BIN version | awk '{print $3}'); CURRENT_VERSION=${CURRENT_VERSION_RAW#go}
    LATEST_VERSION=${GO_VERSION#go}
    log_info "Current version: $CURRENT_VERSION"

    if [[ "$CURRENT_VERSION" == "$LATEST_VERSION" ]]; then
      log_success "Already at latest version ($LATEST_VERSION)"
      if [[ "$UPDATE_MODE" == "true" ]]; then
        print_banner_success "Go is up to date"
      fi
      exit 0
    fi

    log_info "Upgrading from $CURRENT_VERSION to $LATEST_VERSION..."
  fi
else
  # Install mode - skip if already installed (unless FORCE_INSTALL)
  if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -n "$GO_BIN" ]]; then
    CURRENT_VERSION_RAW=$($GO_BIN version | awk '{print $3}'); CURRENT_VERSION=${CURRENT_VERSION_RAW#go}
    log_success "Go $CURRENT_VERSION already installed, skipping"
    exit 0
  fi
fi

log_info "Platform: $PLATFORM/$ARCH → $GO_OS/$GO_ARCH"

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
  log_success "$INSTALLED_VERSION"
else
  manual_steps="Binary installed but not working.

Verify installation:
   /usr/local/go/bin/go version

Add to PATH:
   export PATH=\$PATH:/usr/local/go/bin

Verify in PATH:
   go version"
  output_failure_data "go" "$GO_URL" "$GO_VERSION" "$manual_steps" "Installation verification failed"
  log_error "Installation verification failed"
  exit 1
fi

if [[ "$UPDATE_MODE" == "true" ]]; then
  print_banner_success "Go update complete"
else
  print_banner_success "Go installation complete"
fi
