#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

CLAUDE_CODE_INSTALL_URL="https://claude.ai/install.sh"

# Support --print-url for offline bundle creator
if [[ "${1:-}" == "--print-url" ]]; then
  echo "claude-code|latest|$CLAUDE_CODE_INSTALL_URL"
  exit 0
fi

UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

# Fetch latest stable version from Claude Code distribution
GCS_BUCKET="https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases"
LATEST_VERSION=$(curl -fsSL "$GCS_BUCKET/stable" 2>/dev/null || echo "")

if [[ -z "$LATEST_VERSION" ]]; then
  log_warning "Could not fetch latest version from Claude Code distribution"
  if [[ "$UPDATE_MODE" == "true" ]]; then
    log_info "Will proceed with official installer"
  fi
else
  log_info "Latest version: $LATEST_VERSION"
fi

# Check if Claude is already installed
if [[ "$UPDATE_MODE" == "true" ]]; then
  if ! command -v claude >/dev/null 2>&1; then
    log_info "Claude Code not installed, will install"
  else
    CURRENT_VERSION=$(claude --version 2>&1 | head -n1)
    CURRENT_VERSION=$(parse_version "$CURRENT_VERSION")

    if [[ -n "$CURRENT_VERSION" ]] && [[ -n "$LATEST_VERSION" ]]; then
      if version_compare "$CURRENT_VERSION" "$LATEST_VERSION"; then
        log_success "Already at latest version: $LATEST_VERSION"
        exit 0
      else
        log_info "Update available: $CURRENT_VERSION → $LATEST_VERSION"
      fi
    else
      log_info "Will check for updates via installer"
    fi
  fi
else
  if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v claude >/dev/null 2>&1; then
    CURRENT_VERSION=$(claude --version 2>&1 | head -n1 || echo "installed")
    log_success "Current version: $CURRENT_VERSION, skipping"
    exit 0
  fi
fi

if pgrep -i "claude" >/dev/null 2>&1; then
  log_warning "Claude appears to be running"
  log_info "The installer may fail if Claude is running"
  log_info "If installation fails, close Claude and try again"
fi

if command -v claude >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v claude)
  log_info "claude found at $ALTERNATE_LOCATION"
fi

log_info "Installing via official installer..."

# Download and run official installer
# The installer script handles platform detection and installs to ~/.local/bin
# If it fails due to Claude running, skip gracefully
INSTALLER_OUTPUT=$(curl -fsSL "$CLAUDE_CODE_INSTALL_URL" | bash 2>&1)
INSTALLER_EXIT=$?

if [[ $INSTALLER_EXIT -eq 0 ]]; then
  if [[ "$UPDATE_MODE" == "true" ]]; then
    log_success "Claude Code updated successfully"
  else
    log_success "Claude Code installed successfully"
  fi
elif echo "$INSTALLER_OUTPUT" | grep -qi "another process is currently installing\|claude.*running"; then
  log_warning "Installation skipped - Claude is currently running"
  log_info "Claude Code will be available after closing Claude"
  log_success "Skipping (non-blocking)"
  exit 0
else
  manual_steps="The Claude Code installer failed.

Try manually:
   1. Download installer: curl -fsSL $CLAUDE_CODE_INSTALL_URL -o /tmp/claude-install.sh
   2. Review script: less /tmp/claude-install.sh
   3. Run installer: bash /tmp/claude-install.sh

If Claude is running, close it first and try again.

Official docs: https://docs.claude.ai/docs/claude-code"

  output_failure_data "claude-code" "$CLAUDE_CODE_INSTALL_URL" "latest" "$manual_steps" "Installer failed"
  if [[ "$UPDATE_MODE" == "true" ]]; then
    log_warning "Claude Code update failed (see summary)"
  else
    log_warning "Claude Code installation failed (see summary)"
  fi
  exit 1
fi

if command -v claude >/dev/null 2>&1; then
  INSTALLED_VERSION=$(claude --version 2>&1 | head -n1 || echo "installed")
  log_success "Verified: $INSTALLED_VERSION"
else
  manual_steps="Claude Code installed but not found in PATH.

Check installation:
   ls -la ~/.local/bin/claude
   which claude

Ensure ~/.local/bin is in PATH:
   export PATH=\"\$HOME/.local/bin:\$PATH\"

Try closing and reopening your terminal, then verify:
   claude --version"

  output_failure_data "claude-code" "unknown" "latest" "$manual_steps" "Installation verification failed"
  log_warning "Claude Code installation verification failed (see summary)"
  exit 1
fi
