#!/usr/bin/env bash

# This library requires the following to be sourced by calling script:
#   - error-handling.sh (for structured logging)
#   - failure-logging.sh (for failure reporting)
#
# This library sources:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/version-helpers.sh"
source "$SCRIPT_DIR/cache-manager.sh"

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

# Get latest GitHub release version
# Wrapper for fetch_github_latest_version() from version-helpers.sh
# Usage: get_latest_version <repo>
# Example: get_latest_version "jesseduffield/lazygit"
get_latest_version() {
  local repo="$1"
  local version

  if ! version=$(fetch_github_latest_version "$repo"); then
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

  if [[ "${FORCE_INSTALL:-false}" == "true" ]]; then
    return 1  # Don't skip, install
  fi

  if [[ -f "$binary_path" ]] && command -v "$binary_name" >/dev/null 2>&1; then
    log_success "$binary_name already installed: $binary_path"
    return 0  # Skip
  fi

  return 1  # Don't skip, install
}

# Check if update is needed for a binary
# Returns 0 (update needed) or 1 (already up to date)
# Usage: check_if_update_needed <binary_name> <latest_version>
# Example: check_if_update_needed "lazygit" "v0.40.2"
#
# Requires version-helpers.sh to be sourced by calling script
check_if_update_needed() {
  local binary_name="$1"
  local latest_version="$2"

  if ! command -v "$binary_name" >/dev/null 2>&1; then
    log_info "$binary_name not installed, will install"
    return 0
  fi

  local current_version
  current_version=$("$binary_name" --version 2>&1 | head -1)

  if [[ -z "$current_version" ]]; then
    log_warning "Could not determine current version, will reinstall"
    return 0
  fi

  current_version=$(parse_version "$current_version")

  if [[ -z "$current_version" ]]; then
    log_warning "Could not parse current version, will reinstall"
    return 0
  fi

  if version_compare "$current_version" "$latest_version"; then
    log_success "Already at latest version: $latest_version"
    return 1
  fi

  log_info "Update available: $current_version → $latest_version"
  return 0
}

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

  local tarball_path
  local using_cache=false

  # Check cache first if version is specified
  if [[ "$version" != "latest" ]]; then
    local cached_file
    if cached_file=$(check_local_cache_for_version "$binary_name" "$version" "tar.gz"); then
      log_info "Using cached archive: $cached_file"
      tarball_path="$cached_file"
      using_cache=true
    fi
  fi

  # Download if not in cache
  if [[ "$using_cache" == "false" ]]; then
    tarball_path="/tmp/${binary_name}.tar.gz"
    log_info "Download URL: $download_url"
    log_info "Downloading $binary_name..."
    if ! curl -fsSL "$download_url" -o "$tarball_path"; then
      local manual_steps="1. Download in your browser (bypasses firewall):
   $download_url

2. Move to cache directory:
   mv ~/Downloads/${binary_name}*.tar.gz ~/.cache/dotfiles/

3. Re-run this installer

Or install manually:
   tar -xzf ~/Downloads/${binary_name}*.tar.gz
   mv ${binary_path_in_tarball} ~/.local/bin/
   chmod +x ~/.local/bin/${binary_name}

Verify installation:
   ${binary_name} --version"

      output_failure_data "$binary_name" "$download_url" "$version" "$manual_steps" "Download failed"
      log_error "Failed to download from $download_url"
      return 1
    fi
  fi

  log_info "Extraction directory: /tmp"
  log_info "Extracting..."
  tar -xzf "$tarball_path" -C /tmp

  local target_bin="$HOME/.local/bin/$binary_name"
  log_info "Installation target: $target_bin"
  log_info "Installing to ~/.local/bin..."
  mkdir -p "$HOME/.local/bin"

  if [[ "$binary_path_in_tarball" == *"*"* ]]; then
    # shellcheck disable=SC2086
    mv /tmp/$binary_path_in_tarball "$target_bin"
  else
    mv "/tmp/$binary_path_in_tarball" "$target_bin"
  fi

  chmod +x "$target_bin"

  if command -v "$binary_name" >/dev/null 2>&1; then
    log_success "$binary_name installed to: $target_bin"
  else
    local manual_steps="Binary installed but not found in PATH.

Check that ~/.local/bin is in your PATH:
   echo \$PATH | grep -q \"\$HOME/.local/bin\" || export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify the binary exists:
   ls -la ~/.local/bin/${binary_name}"

    output_failure_data "$binary_name" "$download_url" "$version" "$manual_steps" "Binary not found in PATH after installation"
    log_error "$binary_name not found in PATH after installation"
    return 1
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

  local zip_path
  local using_cache=false

  # Check cache first if version is specified
  if [[ "$version" != "latest" ]]; then
    local cached_file
    if cached_file=$(check_local_cache_for_version "$binary_name" "$version" "zip"); then
      log_info "Using cached archive: $cached_file"
      zip_path="$cached_file"
      using_cache=true
    fi
  fi

  # Download if not in cache
  if [[ "$using_cache" == "false" ]]; then
    zip_path="/tmp/${binary_name}.zip"
    log_info "Download URL: $download_url"
    log_info "Downloading $binary_name..."
    if ! curl -fsSL "$download_url" -o "$zip_path"; then
      local manual_steps="1. Download in your browser (bypasses firewall):
   $download_url

2. Move to cache directory:
   mv ~/Downloads/${binary_name}*.zip ~/.cache/dotfiles/

3. Re-run this installer

Or install manually:
   unzip ~/Downloads/${binary_name}*.zip
   mv ${binary_path_in_zip} ~/.local/bin/
   chmod +x ~/.local/bin/${binary_name}

Verify installation:
   ${binary_name} --version"

      output_failure_data "$binary_name" "$download_url" "$version" "$manual_steps" "Download failed"
      log_error "Failed to download from $download_url"
      return 1
    fi
  fi

  local extract_dir="/tmp/${binary_name}-extract"
  log_info "Extraction directory: $extract_dir"
  log_info "Extracting..."
  mkdir -p "$extract_dir"
  unzip -q "$zip_path" -d "$extract_dir"

  local target_bin="$HOME/.local/bin/$binary_name"
  log_info "Installation target: $target_bin"
  log_info "Installing to ~/.local/bin..."
  mkdir -p "$HOME/.local/bin"
  mv "$extract_dir/$binary_path_in_zip" "$target_bin"
  chmod +x "$target_bin"

  if command -v "$binary_name" >/dev/null 2>&1; then
    log_success "$binary_name installed to: $target_bin"
  else
    local manual_steps="Binary installed but not found in PATH.

Check that ~/.local/bin is in your PATH:
   echo \$PATH | grep -q \"\$HOME/.local/bin\" || export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify the binary exists:
   ls -la ~/.local/bin/${binary_name}"

    output_failure_data "$binary_name" "$download_url" "$version" "$manual_steps" "Binary not found in PATH after installation"
    log_error "$binary_name not found in PATH after installation"
    return 1
  fi
}
