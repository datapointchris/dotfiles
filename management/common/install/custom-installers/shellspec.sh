#!/usr/bin/env bash
# ================================================================
# Install ShellSpec (BDD Testing Framework)
# ================================================================
# Downloads and installs ShellSpec from GitHub releases
# Installation location: ~/.local/lib/shellspec/
# Binary symlink: ~/.local/bin/shellspec
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source structured logging library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
enable_error_traps

print_banner "Installing ShellSpec"

# Configuration
REPO="shellspec/shellspec"
INSTALL_DIR="$HOME/.local/lib/shellspec"
BIN_LINK="$HOME/.local/bin/shellspec"

# Check if already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -L "$BIN_LINK" ]] && command -v shellspec >/dev/null 2>&1; then
  CURRENT_VERSION=$(shellspec --version 2>&1 | head -n1 | awk '{print $2}')
  log_success "ShellSpec $CURRENT_VERSION already installed, skipping"
  exit 0
fi

# Get latest version from GitHub API
log_info "Fetching latest version..."
if ! VERSION=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name":' | head -1 | sed -E 's/.*"([^"]+)".*/\1/'); then
  log_error "Failed to fetch latest version from GitHub API"
  log_info "Manual installation:"
  log_info "  1. Visit: https://github.com/${REPO}/releases/latest"
  log_info "  2. Download source code (tar.gz)"
  log_info "  3. Extract to ~/.local/lib/shellspec"
  log_info "  4. Create symlink: ln -sf ~/.local/lib/shellspec/shellspec ~/.local/bin/shellspec"
  exit 1
fi

log_info "Latest version: $VERSION"

# Build download URL (source tarball from GitHub)
DOWNLOAD_URL="https://github.com/${REPO}/archive/refs/tags/${VERSION}.tar.gz"
TEMP_TARBALL="/tmp/shellspec-${VERSION}.tar.gz"
EXTRACT_DIR="/tmp/shellspec-extract-$$"

# Download
log_info "Downloading ShellSpec..."
if ! curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_TARBALL"; then
  log_error "Download failed"
  log_info "Manual installation:"
  log_info "  1. Download: $DOWNLOAD_URL"
  log_info "  2. Extract: tar -xzf ~/Downloads/shellspec-*.tar.gz -C /tmp"
  log_info "  3. Move: mv /tmp/shellspec-* ~/.local/lib/shellspec"
  log_info "  4. Link: ln -sf ~/.local/lib/shellspec/shellspec ~/.local/bin/shellspec"
  exit 1
fi

register_cleanup "rm -f '$TEMP_TARBALL' 2>/dev/null || true"
register_cleanup "rm -rf '$EXTRACT_DIR' 2>/dev/null || true"

# Extract
log_info "Extracting..."
mkdir -p "$EXTRACT_DIR"
tar -xzf "$TEMP_TARBALL" -C "$EXTRACT_DIR"

# Install
log_info "Installing to ~/.local/lib/shellspec..."
rm -rf "$INSTALL_DIR"
mkdir -p "$(dirname "$INSTALL_DIR")"

# Find extracted directory (will be shellspec-<version> without 'v' prefix)
EXTRACTED_DIR=$(find "$EXTRACT_DIR" -maxdepth 1 -type d -name "shellspec-*" | head -1)
if [[ -z "$EXTRACTED_DIR" ]]; then
  log_fatal "Could not find extracted directory" "${BASH_SOURCE[0]}" "$LINENO"
fi

mv "$EXTRACTED_DIR" "$INSTALL_DIR"

# Create symlink
log_info "Creating symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/shellspec" "$BIN_LINK"

# Verify installation
if command -v shellspec >/dev/null 2>&1; then
  INSTALLED_VERSION=$(shellspec --version 2>&1 | head -n1)
  log_success "$INSTALLED_VERSION"
else
  log_fatal "Installation verification failed - shellspec not found in PATH" "${BASH_SOURCE[0]}" "$LINENO"
fi

print_banner_success "ShellSpec installation complete"
exit_success
