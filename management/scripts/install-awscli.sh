#!/usr/bin/env bash
# ================================================================
# Install AWS CLI v2 (Official Installer)
# ================================================================
# Downloads and installs AWS CLI v2 using official AWS installer
# Official docs: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
# Installation location: ~/.local/aws-cli (user space)
# Binary symlink: ~/.local/bin/aws
# No sudo required
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Source helper functions
source "$(dirname "$0")/install-program-helpers.sh"

print_banner "Installing AWS CLI v2"

# Detect platform and architecture
PLATFORM=$(uname -s)
ARCH=$(uname -m)

# macOS: AWS CLI installed via Homebrew (see Brewfile)
if [[ "$PLATFORM" == "Darwin" ]]; then
  if command -v aws >/dev/null 2>&1; then
    CURRENT_VERSION=$(aws --version 2>&1 | awk '{print $1}' | cut -d/ -f2)
    print_success "macOS: AWS CLI managed by Homebrew"
    print_success "Current version: $CURRENT_VERSION"
  else
    print_info "macOS: AWS CLI will be installed via Homebrew"
    print_info "Run: brew install awscli"
  fi
  exit 0
fi

# Linux: Check if AWS CLI is already installed at expected location (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [ -f "$HOME/.local/bin/aws" ] && command -v aws >/dev/null 2>&1; then
  CURRENT_VERSION=$(aws --version 2>&1 | awk '{print $1}' | cut -d/ -f2)
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Check for alternate installations
if [ ! -f "$HOME/.local/bin/aws" ] && command -v aws >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v aws)
  print_warning " aws found at $ALTERNATE_LOCATION"
  print_info "AWS CLI official installer will be used"
fi

case $PLATFORM in
  Linux)
    # Linux installation (WSL/Arch)
    print_info "Platform: Linux ($ARCH)"

    # Detect architecture
    case $ARCH in
      x86_64)
        ZIP_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
        ;;
      aarch64|arm64)
        ZIP_URL="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"
        ;;
      *)
        print_error "Unsupported architecture: $ARCH"
        exit 1
        ;;
    esac

    ZIP_FILE="/tmp/awscliv2.zip"
    EXTRACT_DIR="/tmp/aws-cli-install"

    # Download
    if ! download_file "$ZIP_URL" "$ZIP_FILE" "awscli"; then
      print_manual_install "aws" "$ZIP_URL" "latest" "awscliv2.zip" \
        "unzip ~/Downloads/awscliv2.zip && sudo ./aws/install"
      exit 1
    fi

    # Extract
    print_info "Extracting installer..."
    rm -rf "$EXTRACT_DIR"
    mkdir -p "$EXTRACT_DIR"
    unzip -q "$ZIP_FILE" -d "$EXTRACT_DIR"

    # Install to user directory (no sudo needed)
    print_info "Installing AWS CLI v2 to ~/.local/..."
    "$EXTRACT_DIR/aws/install" --install-dir "$HOME/.local/aws-cli" --bin-dir "$HOME/.local/bin" --update

    # Cleanup
    rm -rf "$ZIP_FILE" "$EXTRACT_DIR"
    ;;

  *)
    print_error "Unsupported platform: $PLATFORM"
    exit 1
    ;;
esac

# Verify installation
if command -v aws >/dev/null 2>&1; then
  INSTALLED_VERSION=$(aws --version 2>&1)
  print_success "$INSTALLED_VERSION"
else
  print_error "Installation verification failed"
  exit 1
fi

print_banner_success "AWS CLI v2 installation complete"
