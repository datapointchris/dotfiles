#!/usr/bin/env bash
# ================================================================
# GitHub Release Installer Library
# ================================================================
# Focused helpers for GitHub release installers
# - Platform detection (handles capitalization variations)
# - Skip checking (FORCE_INSTALL + existence)
# - Latest version fetching
# - Standard install patterns (tarball, zip)
# ================================================================

# This library requires error-handling.sh (for structured logging)
# and install-helpers.sh (for failure reporting)
# They should already be sourced by the calling script

# ================================================================
# Platform Detection
# ================================================================

# Get platform_arch string with customizable capitalization
# Usage: get_platform_arch <darwin_x86> <darwin_arm> <linux_x86>
# Example: get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64"
# Example: get_platform_arch "darwin_x86_64" "darwin_arm64" "linux_x86_64"
get_platform_arch() {
  local darwin_x86="${1}"
  local darwin_arm="${2}"
  local linux_x86="${3}"

  local machine_arch
  machine_arch=$(uname -m)

  if [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ "$machine_arch" == "x86_64" ]]; then
      echo "$darwin_x86"
    else
      echo "$darwin_arm"
    fi
  else
    echo "$linux_x86"
  fi
}

# ================================================================
# Version and Installation Checking
# ================================================================

# Get latest GitHub release version
# Usage: get_latest_version <repo>
# Example: get_latest_version "jesseduffield/lazygit"
get_latest_version() {
  local repo="$1"

  local version
  version=$(curl -fsSL "https://api.github.com/repos/${repo}/releases/latest" \
    | grep '"tag_name":' \
    | head -1 \
    | sed -E 's/.*"([^"]+)".*/\1/')

  if [[ -z "$version" ]]; then
    log_error "Failed to fetch latest version from GitHub API" "${BASH_SOURCE[0]}" "$LINENO"
    return 1
  fi

  echo "$version"
}

# Check if should skip installation
# Returns 0 (skip) or 1 (install)
# Usage: should_skip_install <binary_path> <binary_name>
should_skip_install() {
  local binary_path="$1"
  local binary_name="$2"

  # FORCE_INSTALL overrides everything
  if [[ "${FORCE_INSTALL:-false}" == "true" ]]; then
    return 1  # Don't skip, install
  fi

  # Check if exists and in PATH
  if [[ -f "$binary_path" ]] && command -v "$binary_name" >/dev/null 2>&1; then
    log_success "$binary_name already installed, skipping"
    return 0  # Skip
  fi

  return 1  # Don't skip, install
}

# ================================================================
# Standard Installation Patterns
# ================================================================

# Install from tarball (most common pattern)
# Downloads, extracts, installs binary to ~/.local/bin
# Usage: install_from_tarball <binary_name> <download_url> <binary_path_in_tarball> <version>
#
# Example (binary at root):
#   install_from_tarball "lazygit" "$URL" "lazygit" "v0.40.0"
#
# Example (binary in nested dir):
#   install_from_tarball "glow" "$URL" "glow_*_Darwin_arm64/glow" "v1.5.0"
install_from_tarball() {
  local binary_name="$1"
  local download_url="$2"
  local binary_path_in_tarball="$3"
  local version="${4:-latest}"

  local temp_tarball="/tmp/${binary_name}.tar.gz"
  local target_bin="$HOME/.local/bin/$binary_name"

  # Download
  log_info "Downloading $binary_name..."
  if ! curl -fsSL "$download_url" -o "$temp_tarball"; then
    # Report failure if registry exists
    if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
      local manual_steps="1. Download in your browser (bypasses firewall):
   $download_url

2. After downloading, extract and install:
   tar -xzf ~/Downloads/${binary_name}.tar.gz
   mv ${binary_path_in_tarball} ~/.local/bin/
   chmod +x ~/.local/bin/${binary_name}

3. Verify installation:
   ${binary_name} --version"
      report_failure "$binary_name" "$download_url" "$version" "$manual_steps" "Download failed"
    fi
    log_fatal "Failed to download from $download_url" "${BASH_SOURCE[0]}" "$LINENO"
  fi
  register_cleanup "rm -f '$temp_tarball' 2>/dev/null || true"

  # Extract
  log_info "Extracting..."
  tar -xzf "$temp_tarball" -C /tmp

  # Install
  log_info "Installing to ~/.local/bin..."
  mkdir -p "$HOME/.local/bin"

  # Handle wildcards in path
  if [[ "$binary_path_in_tarball" == *"*"* ]]; then
    # shellcheck disable=SC2086
    mv /tmp/$binary_path_in_tarball "$target_bin"
  else
    mv "/tmp/$binary_path_in_tarball" "$target_bin"
  fi

  chmod +x "$target_bin"

  # Verify
  if command -v "$binary_name" >/dev/null 2>&1; then
    log_success "$binary_name installed successfully"
  else
    # Report failure if registry exists
    if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
      local manual_steps="Binary installed but not found in PATH.

Check that ~/.local/bin is in your PATH:
   echo \$PATH | grep -q \"\$HOME/.local/bin\" || export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify the binary exists:
   ls -la ~/.local/bin/${binary_name}"
      report_failure "$binary_name" "$download_url" "$version" "$manual_steps" "Binary not found in PATH after installation"
    fi
    log_fatal "$binary_name not found in PATH after installation" "${BASH_SOURCE[0]}" "$LINENO"
  fi
}

# Install from zip file
# Downloads, extracts, installs binary to ~/.local/bin
# Usage: install_from_zip <binary_name> <download_url> <binary_path_in_zip> <version>
#
# Example:
#   install_from_zip "yazi" "$URL" "yazi-x86_64-apple-darwin/yazi" "v0.2.0"
install_from_zip() {
  local binary_name="$1"
  local download_url="$2"
  local binary_path_in_zip="$3"
  local version="${4:-latest}"

  local temp_zip="/tmp/${binary_name}.zip"
  local extract_dir="/tmp/${binary_name}-extract"
  local target_bin="$HOME/.local/bin/$binary_name"

  # Download
  log_info "Downloading $binary_name..."
  if ! curl -fsSL "$download_url" -o "$temp_zip"; then
    # Report failure if registry exists
    if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
      local manual_steps="1. Download in your browser (bypasses firewall):
   $download_url

2. After downloading, extract and install:
   unzip ~/Downloads/${binary_name}.zip
   mv ${binary_path_in_zip} ~/.local/bin/
   chmod +x ~/.local/bin/${binary_name}

3. Verify installation:
   ${binary_name} --version"
      report_failure "$binary_name" "$download_url" "$version" "$manual_steps" "Download failed"
    fi
    log_fatal "Failed to download from $download_url" "${BASH_SOURCE[0]}" "$LINENO"
  fi
  register_cleanup "rm -f '$temp_zip' 2>/dev/null || true"
  register_cleanup "rm -rf '$extract_dir' 2>/dev/null || true"

  # Extract
  log_info "Extracting..."
  mkdir -p "$extract_dir"
  unzip -q "$temp_zip" -d "$extract_dir"

  # Install
  log_info "Installing to ~/.local/bin..."
  mkdir -p "$HOME/.local/bin"
  mv "$extract_dir/$binary_path_in_zip" "$target_bin"
  chmod +x "$target_bin"

  # Verify
  if command -v "$binary_name" >/dev/null 2>&1; then
    log_success "$binary_name installed successfully"
  else
    # Report failure if registry exists
    if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
      local manual_steps="Binary installed but not found in PATH.

Check that ~/.local/bin is in your PATH:
   echo \$PATH | grep -q \"\$HOME/.local/bin\" || export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify the binary exists:
   ls -la ~/.local/bin/${binary_name}"
      report_failure "$binary_name" "$download_url" "$version" "$manual_steps" "Binary not found in PATH after installation"
    fi
    log_fatal "$binary_name not found in PATH after installation" "${BASH_SOURCE[0]}" "$LINENO"
  fi
}
