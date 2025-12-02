#!/usr/bin/env bash
# ================================================================
# Install Claude Code (Official Installer)
# ================================================================
# Downloads and installs Claude Code CLI using official installer
# Official docs: https://docs.claude.ai/docs/claude-code
# Installation location: ~/.local/bin/claude-code
# No sudo required
#
# Platform support:
#   - macOS: Supported
#   - Linux (Arch): Supported
#   - WSL: NOT supported (skipped - would conflict with Windows installation)
# ================================================================

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
enable_error_traps

print_banner "Installing Claude Code"

# Detect platform
PLATFORM=$(uname -s)

# Skip on WSL - Claude Code should be installed on Windows host
if [[ "$PLATFORM" == "Linux" ]]; then
  if grep -q "Microsoft\|WSL" /proc/version 2>/dev/null; then
    log_info "WSL detected - skipping Claude Code installation"
    log_info "Install Claude Code on your Windows host instead"
    exit 0
  fi
fi

# Check if Claude is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v claude >/dev/null 2>&1; then
  CURRENT_VERSION=$(claude --version 2>&1 | head -n1 || echo "installed")
  log_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Check if Claude is currently running (which blocks installation)
if pgrep -i "claude" >/dev/null 2>&1; then
  log_warning "Claude appears to be running"
  log_info "The installer may fail if Claude is running"
  log_info "If installation fails, close Claude and try again"
fi

# Check for alternate installations
if command -v claude >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v claude)
  log_info "claude found at $ALTERNATE_LOCATION"
fi

log_info "Platform: $PLATFORM"
log_info "Installing via official installer..."

# Download and run official installer
# The installer script handles platform detection and installs to ~/.local/bin
# If it fails due to Claude running, skip gracefully
INSTALLER_OUTPUT=$(curl -fsSL https://claude.ai/install.sh | bash 2>&1)
INSTALLER_EXIT=$?

if [[ $INSTALLER_EXIT -eq 0 ]]; then
  log_success "Claude Code installed successfully"
elif echo "$INSTALLER_OUTPUT" | grep -qi "another process is currently installing\|claude.*running"; then
  log_warning "Installation skipped - Claude is currently running"
  log_info "Claude Code will be available after closing Claude"
  log_success "Skipping (non-blocking)"
  exit 0
else
  log_error "Installation failed with exit code: $INSTALLER_EXIT"
  exit 1
fi

# Verify installation
if command -v claude >/dev/null 2>&1; then
  INSTALLED_VERSION=$(claude --version 2>&1 | head -n1 || echo "installed")
  log_success "Verified: $INSTALLED_VERSION"
else
  log_error "Installation verification failed"
  log_info "claude not found in PATH"
  log_info "Try closing and reopening your terminal"
  exit 1
fi

print_banner_success "Claude Code installation complete"
