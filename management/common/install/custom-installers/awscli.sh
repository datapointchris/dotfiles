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

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
enable_error_traps

# Source helper functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/program-helpers.sh"

print_banner "Installing AWS CLI v2"

# Initialize failure registry for resilient installation
init_failure_registry

# Detect platform and architecture
PLATFORM=$(uname -s)
ARCH=$(uname -m)

# macOS: AWS CLI installed via Homebrew (see packages.yml)
if [[ "$PLATFORM" == "Darwin" ]]; then
  if command -v aws >/dev/null 2>&1; then
    CURRENT_VERSION=$(aws --version 2>&1 | awk '{print $1}' | cut -d/ -f2)
    log_success "macOS: AWS CLI managed by Homebrew"
    log_success "Current version: $CURRENT_VERSION"
  else
    log_info "macOS: AWS CLI will be installed via Homebrew"
    log_info "Add 'awscli' to packages.yml and run: task macos:install-packages"
  fi
  exit 0
fi

# Linux: Check if AWS CLI is already installed at expected location (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [ -f "$HOME/.local/bin/aws" ] && command -v aws >/dev/null 2>&1; then
  CURRENT_VERSION=$(aws --version 2>&1 | awk '{print $1}' | cut -d/ -f2)
  log_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Check for alternate installations
if [ ! -f "$HOME/.local/bin/aws" ] && command -v aws >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v aws)
  log_warning "aws found at $ALTERNATE_LOCATION"
  log_info "AWS CLI official installer will be used"
fi

case $PLATFORM in
  Linux)
    # Linux installation (WSL/Arch)
    log_info "Platform: Linux ($ARCH)"

    # Detect architecture
    case $ARCH in
      x86_64)
        ZIP_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
        ;;
      aarch64|arm64)
        ZIP_URL="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"
        ;;
      *)
        log_error "Unsupported architecture: $ARCH"
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
    log_info "Extracting installer..."
    rm -rf "$EXTRACT_DIR"
    mkdir -p "$EXTRACT_DIR"
    unzip -q "$ZIP_FILE" -d "$EXTRACT_DIR"

    # Install to user directory (no sudo needed)
    log_info "Installing AWS CLI v2 to ~/.local/..."
    if ! "$EXTRACT_DIR/aws/install" --install-dir "$HOME/.local/aws-cli" --bin-dir "$HOME/.local/bin" --update; then
      # Report failure if registry exists
      if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
        manual_steps="The AWS CLI installer failed. Try manually:
   1. Download: $ZIP_URL
   2. Extract: unzip ~/Downloads/awscliv2.zip
   3. Install: ./aws/install --install-dir ~/.local/aws-cli --bin-dir ~/.local/bin

Official docs: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        report_failure "aws" "$ZIP_URL" "latest" "$manual_steps" "AWS installer failed"
      fi
      # Cleanup
      rm -rf "$ZIP_FILE" "$EXTRACT_DIR"
      log_warning "AWS CLI installation failed (see summary)"
      display_failure_summary
      exit 1
    fi

    # Cleanup
    rm -rf "$ZIP_FILE" "$EXTRACT_DIR"
    ;;

  *)
    log_error "Unsupported platform: $PLATFORM"
    exit 1
    ;;
esac

# Verify installation
if command -v aws >/dev/null 2>&1; then
  INSTALLED_VERSION=$(aws --version 2>&1)
  log_success "$INSTALLED_VERSION"
else
  # Report verification failure
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="AWS CLI installed but not found in PATH.

Check installation:
   ls -la ~/.local/bin/aws
   ls -la ~/.local/aws-cli/

Ensure ~/.local/bin is in PATH:
   export PATH=\"\$HOME/.local/bin:\$PATH\"

Re-run verification:
   aws --version"
    report_failure "aws" "unknown" "latest" "$manual_steps" "Installation verification failed"
  fi
  log_warning "AWS CLI installation verification failed (see summary)"
  display_failure_summary
  exit 1
fi

# Display failure summary if there were any failures
display_failure_summary

print_banner_success "AWS CLI v2 installation complete"
