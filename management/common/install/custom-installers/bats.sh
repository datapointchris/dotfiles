#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

print_banner "Installing BATS Testing Framework"

# Installation configuration
BATS_VERSION="${BATS_VERSION:-v1.13.0}"
INSTALL_PREFIX="$HOME/.local"
BATS_LIB_DIR="$INSTALL_PREFIX/lib"

# Repository URLs
BATS_CORE_REPO="https://github.com/bats-core/bats-core.git"
BATS_SUPPORT_REPO="https://github.com/bats-core/bats-support.git"
BATS_ASSERT_REPO="https://github.com/bats-core/bats-assert.git"

# Check if BATS is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v bats >/dev/null 2>&1; then
  CURRENT_VERSION=$(bats --version 2>&1 | head -n1 || echo "installed")
  CURRENT_PATH=$(command -v bats)

  # Check if it's installed in our target location
  if [[ "$CURRENT_PATH" == "$INSTALL_PREFIX/bin/bats" ]]; then
    log_success "Already installed: $CURRENT_VERSION at $CURRENT_PATH"
    exit 0
  else
    log_info "Found BATS at: $CURRENT_PATH"
    log_info "Will install to: $INSTALL_PREFIX/bin/bats"
  fi
fi

# Check for required commands
if ! command -v git >/dev/null 2>&1; then
  manual_steps="Git is required to install BATS.

Install git first:
  macOS: brew install git
  Ubuntu: sudo apt-get install git
  Arch: sudo pacman -S git"

  output_failure_data "bats" "$BATS_CORE_REPO" "$BATS_VERSION" "$manual_steps" "Git not found"
  log_error "Git is required but not found"
  exit 1
fi

# Create lib directory if it doesn't exist
mkdir -p "$BATS_LIB_DIR"

# Temporary directory for cloning
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

log_info "Installing BATS $BATS_VERSION to $INSTALL_PREFIX"

# Clone bats-core
log_info "Cloning bats-core..."
if ! git clone --quiet --depth 1 --branch "$BATS_VERSION" "$BATS_CORE_REPO" "$TMP_DIR/bats-core" 2>&1; then
  manual_steps="Failed to clone bats-core repository.

Try manually:
  1. Clone repository: git clone $BATS_CORE_REPO
  2. Checkout version: cd bats-core && git checkout $BATS_VERSION
  3. Run installer: ./install.sh $INSTALL_PREFIX

Check network connection and GitHub access."

  output_failure_data "bats-core" "$BATS_CORE_REPO" "$BATS_VERSION" "$manual_steps" "Git clone failed"
  log_error "Failed to clone bats-core"
  exit 1
fi

# Install bats-core
log_info "Running bats-core installer..."
cd "$TMP_DIR/bats-core" || exit 1

if ! ./install.sh "$INSTALL_PREFIX" >/dev/null 2>&1; then
  manual_steps="Failed to run bats-core install.sh script.

Try manually:
  1. Clone repository: git clone $BATS_CORE_REPO
  2. Checkout version: cd bats-core && git checkout $BATS_VERSION
  3. Run installer: ./install.sh $INSTALL_PREFIX
  4. Check permissions: ls -la $INSTALL_PREFIX/bin/

Check that $INSTALL_PREFIX is writable."

  output_failure_data "bats-core" "$BATS_CORE_REPO" "$BATS_VERSION" "$manual_steps" "install.sh failed"
  log_error "Failed to run install.sh"
  exit 1
fi

log_success "bats-core installed"

# Clone and install bats-support
log_info "Installing bats-support..."
if ! git clone --quiet --depth 1 "$BATS_SUPPORT_REPO" "$TMP_DIR/bats-support" 2>&1; then
  log_warning "Failed to clone bats-support (optional)"
else
  rm -rf "$BATS_LIB_DIR/bats-support"
  cp -r "$TMP_DIR/bats-support" "$BATS_LIB_DIR/bats-support"
  log_success "bats-support installed to $BATS_LIB_DIR/bats-support"
fi

# Clone and install bats-assert
log_info "Installing bats-assert..."
if ! git clone --quiet --depth 1 "$BATS_ASSERT_REPO" "$TMP_DIR/bats-assert" 2>&1; then
  log_warning "Failed to clone bats-assert (optional)"
else
  rm -rf "$BATS_LIB_DIR/bats-assert"
  cp -r "$TMP_DIR/bats-assert" "$BATS_LIB_DIR/bats-assert"
  log_success "bats-assert installed to $BATS_LIB_DIR/bats-assert"
fi

# Verify installation
log_info "Verifying installation..."

if ! command -v bats >/dev/null 2>&1; then
  manual_steps="BATS installed but not found in PATH.

Check installation:
  ls -la $INSTALL_PREFIX/bin/bats
  which bats

Ensure $INSTALL_PREFIX/bin is in PATH:
  export PATH=\"$INSTALL_PREFIX/bin:\$PATH\"

Add to your shell rc file (~/.zshrc, ~/.bashrc):
  export PATH=\"\$HOME/.local/bin:\$PATH\"

Try closing and reopening your terminal, then verify:
  bats --version"

  output_failure_data "bats" "unknown" "$BATS_VERSION" "$manual_steps" "Installation verification failed"
  log_error "BATS not found in PATH after installation"
  exit 1
fi

INSTALLED_VERSION=$(bats --version 2>&1 | head -n1 || echo "installed")
INSTALLED_PATH=$(command -v bats)

log_success "Verified: $INSTALLED_VERSION"
log_success "Location: $INSTALLED_PATH"

# Verify helper libraries
HELPERS_INSTALLED=true
if [[ ! -f "$BATS_LIB_DIR/bats-support/load.bash" ]]; then
  log_warning "bats-support not found at $BATS_LIB_DIR/bats-support"
  HELPERS_INSTALLED=false
fi

if [[ ! -f "$BATS_LIB_DIR/bats-assert/load.bash" ]]; then
  log_warning "bats-assert not found at $BATS_LIB_DIR/bats-assert"
  HELPERS_INSTALLED=false
fi

if [[ "$HELPERS_INSTALLED" == "true" ]]; then
  log_success "Helper libraries verified:"
  log_success "  - bats-support: $BATS_LIB_DIR/bats-support"
  log_success "  - bats-assert: $BATS_LIB_DIR/bats-assert"
  log_info "Load in tests with:"
  log_info "  load \"\$HOME/.local/lib/bats-support/load.bash\""
  log_info "  load \"\$HOME/.local/lib/bats-assert/load.bash\""
fi

print_banner_success "BATS installation complete"
