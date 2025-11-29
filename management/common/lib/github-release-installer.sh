#!/usr/bin/env bash
# ================================================================
# GitHub Release Installer Library
# ================================================================
# Reusable functions for installing binaries from GitHub releases
# Handles common patterns: tarball/zip archives, version checking,
# platform detection, cleanup, and verification
#
# Design Philosophy:
# - Function-based helpers, not complex YAML parsing
# - Configuration stays in installer scripts (inline, explicit)
# - Handles common variations through parameters
# - Built on structured logging and error handling
# ================================================================

# This library requires structured-logging.sh and error-handling.sh
# They should already be sourced by the calling script

# ================================================================
# Platform Detection Helpers
# ================================================================

# Get platform string with customizable format
# Usage: get_platform <darwin_format> <linux_format>
# Example: get_platform "Darwin" "Linux" → "Darwin" or "Linux"
# Example: get_platform "darwin" "linux" → "darwin" or "linux"
get_platform() {
  local darwin_format="${1:-Darwin}"
  local linux_format="${2:-Linux}"

  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "$darwin_format"
  else
    echo "$linux_format"
  fi
}

# Get architecture string with customizable format
# Usage: get_arch <x86_darwin> <arm_darwin> <x86_linux> [arm_linux]
# Example: get_arch "x86_64" "arm64" "x86_64" "aarch64"
get_arch() {
  local x86_darwin="${1:-x86_64}"
  local arm_darwin="${2:-arm64}"
  local x86_linux="${3:-x86_64}"
  local arm_linux="${4:-aarch64}"

  local machine_arch
  machine_arch=$(uname -m)

  if [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ "$machine_arch" == "x86_64" ]]; then
      echo "$x86_darwin"
    else
      echo "$arm_darwin"
    fi
  else
    if [[ "$machine_arch" == "x86_64" ]]; then
      echo "$x86_linux"
    else
      echo "$arm_linux"
    fi
  fi
}

# Get combined platform_arch string
# Usage: get_platform_arch <darwin_x86> <darwin_arm> <linux_x86> [linux_arm]
# Example: get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64"
get_platform_arch() {
  local darwin_x86="${1}"
  local darwin_arm="${2}"
  local linux_x86="${3}"
  local linux_arm="${4:-}"

  local machine_arch
  machine_arch=$(uname -m)

  if [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ "$machine_arch" == "x86_64" ]]; then
      echo "$darwin_x86"
    else
      echo "$darwin_arm"
    fi
  else
    if [[ "$machine_arch" == "x86_64" ]]; then
      echo "$linux_x86"
    else
      echo "${linux_arm:-$linux_x86}"
    fi
  fi
}

# ================================================================
# Version Handling
# ================================================================

# Get latest GitHub release version
# Usage: get_latest_version <repo>
# Example: get_latest_version "jesseduffield/lazygit"
# Returns: Version string (with 'v' prefix if present in release)
get_latest_version() {
  local repo="$1"

  local version
  version=$(curl -fsSL "https://api.github.com/repos/${repo}/releases/latest" \
    | grep '"tag_name":' \
    | sed -E 's/.*"([^"]+)".*/\1/')

  if [[ -z "$version" ]]; then
    log_error "Failed to fetch latest version from GitHub API" "${BASH_SOURCE[0]}" "$LINENO"
    return 1
  fi

  echo "$version"
}

# Strip 'v' prefix from version string
# Usage: strip_v_prefix <version>
# Example: strip_v_prefix "v1.2.3" → "1.2.3"
strip_v_prefix() {
  local version="$1"
  echo "${version#v}"
}

# Check if current version meets minimum requirement
# Usage: version_meets_minimum <current> <minimum>
# Example: version_meets_minimum "1.2.3" "1.0.0" → returns 0 (success)
version_meets_minimum() {
  local current="$1"
  local minimum="$2"

  # Sort versions and check if minimum comes first (or equal)
  if [[ $(echo -e "$minimum\n$current" | sort -V | head -n1) == "$minimum" ]]; then
    return 0
  else
    return 1
  fi
}

# ================================================================
# Installation Check
# ================================================================

# Check if binary is already installed with acceptable version
# Usage: check_existing_installation <binary_path> <binary_name> [version_check_cmd] [minimum_version]
# Returns: 0 if skip installation, 1 if should install
#
# The version check behavior depends on the parameters:
# - If minimum_version is provided: Checks if current version >= minimum (using version_meets_minimum)
# - If no minimum_version: Any installed version is acceptable
# - If no version_check_cmd: Just checks if binary exists
#
# Examples:
#   check_existing_installation "$HOME/.local/bin/lazygit" "lazygit" "lazygit --version | grep -oP 'version=\K[0-9.]+'" "0.40.2"
#   check_existing_installation "$HOME/.local/bin/yazi" "yazi" "yazi --version | grep -oP 'Yazi \K[0-9.]+'"
#   check_existing_installation "$HOME/.local/bin/duf" "duf"  # Just check existence
check_existing_installation() {
  local binary_path="$1"
  local binary_name="$2"
  local version_check_cmd="${3:-}"
  local minimum_version="${4:-}"

  # Respect FORCE_INSTALL flag
  if [[ "${FORCE_INSTALL:-false}" == "true" ]]; then
    return 1  # Should install
  fi

  # Check if file exists and is in PATH
  if [[ ! -f "$binary_path" ]] || ! command -v "$binary_name" >/dev/null 2>&1; then
    return 1  # Should install
  fi

  # If no version check specified, assume installed version is acceptable
  if [[ -z "$version_check_cmd" ]]; then
    log_success "$binary_name already installed, skipping"
    return 0  # Skip installation
  fi

  # Get current version
  local current_version
  current_version=$(eval "$version_check_cmd" 2>&1 || echo "unknown")

  if [[ "$current_version" == "unknown" ]]; then
    log_warning "Could not determine current version"
    return 1  # Should install
  fi

  log_info "Current version: $current_version"

  # If minimum version specified, check if current meets requirement
  if [[ -n "$minimum_version" ]]; then
    if version_meets_minimum "$current_version" "$minimum_version"; then
      log_success "Version $current_version meets minimum requirement ($minimum_version), skipping"
      return 0  # Skip installation
    else
      log_info "Current version $current_version < minimum $minimum_version, upgrading..."
      return 1  # Should install
    fi
  else
    # No minimum specified, any version is acceptable
    log_success "Already installed, skipping"
    return 0
  fi
}

# Check for alternate installations (not at expected path but in PATH)
# Usage: check_alternate_installation <binary_path> <binary_name>
check_alternate_installation() {
  local binary_path="$1"
  local binary_name="$2"

  if [[ ! -f "$binary_path" ]] && command -v "$binary_name" >/dev/null 2>&1; then
    local alternate_location
    alternate_location=$(command -v "$binary_name")
    log_warning "$binary_name found at $alternate_location"
    log_info "Installing to $binary_path anyway (PATH priority will use this one)"
  fi
}

# ================================================================
# Download and Extract
# ================================================================

# Download file from URL with automatic cleanup registration
# Usage: download_release <url> <output_path> <description>
# Example: download_release "$DOWNLOAD_URL" "/tmp/lazygit.tar.gz" "lazygit"
download_release() {
  local url="$1"
  local output="$2"
  local description="${3:-file}"

  log_info "Downloading $description..."
  log_info "URL: $url"

  # Use error-handling.sh helper with retry logic
  download_file_with_retry "$url" "$output" "$description" 3

  # Register for cleanup
  register_cleanup "rm -f '$output' 2>/dev/null || true"
}

# Extract tarball to directory
# Usage: extract_tarball <tarball_path> <extract_dir> [specific_file]
# Example: extract_tarball "/tmp/app.tar.gz" "/tmp" "app"
# Example: extract_tarball "/tmp/app.tar.gz" "/tmp"  # Extract all
extract_tarball() {
  local tarball="$1"
  local extract_dir="$2"
  local specific_file="${3:-}"

  log_info "Extracting..."

  mkdir -p "$extract_dir"

  if [[ -n "$specific_file" ]]; then
    tar -xzf "$tarball" -C "$extract_dir" "$specific_file"
  else
    tar -xzf "$tarball" -C "$extract_dir"
  fi

  # Register extracted files for cleanup
  if [[ -n "$specific_file" ]]; then
    register_cleanup "rm -f '$extract_dir/$specific_file' 2>/dev/null || true"
  else
    register_cleanup "rm -rf '$extract_dir'/* 2>/dev/null || true"
  fi
}

# Extract zip file to directory
# Usage: extract_zip <zip_path> <extract_dir>
# Example: extract_zip "/tmp/app.zip" "/tmp/app-extract"
extract_zip() {
  local zipfile="$1"
  local extract_dir="$2"

  log_info "Extracting..."

  mkdir -p "$extract_dir"
  unzip -q "$zipfile" -d "$extract_dir"

  # Register extracted directory for cleanup
  register_cleanup "rm -rf '$extract_dir' 2>/dev/null || true"
}

# ================================================================
# Installation
# ================================================================

# Install binary to target location
# Usage: install_binary <source_path> <target_path>
# Example: install_binary "/tmp/lazygit" "$HOME/.local/bin/lazygit"
install_binary() {
  local source="$1"
  local target="$2"

  verify_file "$source" "Binary"

  log_info "Installing to $(dirname "$target")..."

  mkdir -p "$(dirname "$target")"
  mv "$source" "$target"
  chmod +x "$target"
}

# Install multiple binaries from directory
# Usage: install_binaries <source_dir> <target_dir> <binary1> [binary2] [binary3] ...
# Example: install_binaries "/tmp" "$HOME/.local/bin" "tenv" "terraform" "tofu"
install_binaries() {
  local source_dir="$1"
  local target_dir="$2"
  shift 2
  local binaries=("$@")

  log_info "Installing binaries to $target_dir..."

  mkdir -p "$target_dir"

  for binary in "${binaries[@]}"; do
    local source="$source_dir/$binary"
    if [[ -f "$source" ]]; then
      mv "$source" "$target_dir/"
      chmod +x "$target_dir/$binary"
    fi
  done
}

# Create symlink for binary
# Usage: create_binary_symlink <target_path> <link_path>
# Example: create_binary_symlink "$HOME/.local/nvim-macos-arm64/bin/nvim" "$HOME/.local/bin/nvim"
create_binary_symlink() {
  local target="$1"
  local link="$2"

  verify_file "$target" "Binary"

  log_info "Creating symlink..."

  mkdir -p "$(dirname "$link")"
  ln -sf "$target" "$link"
}

# ================================================================
# Verification
# ================================================================

# Verify installation by running command
# Usage: verify_installation <binary_name> [version_check_cmd]
# Example: verify_installation "lazygit" "lazygit --version | head -n1"
# Example: verify_installation "yazi"
verify_installation() {
  local binary_name="$1"
  local version_check_cmd="${2:-}"

  if ! command -v "$binary_name" >/dev/null 2>&1; then
    log_fatal "$binary_name command not found in PATH" "${BASH_SOURCE[0]}" "$LINENO"
  fi

  if [[ -n "$version_check_cmd" ]]; then
    local version
    version=$(eval "$version_check_cmd" 2>&1 || echo "unknown")
    log_success "$version"
  else
    log_success "$binary_name installed successfully"
  fi
}

# ================================================================
# High-Level Installer Patterns
# ================================================================

# Complete installation workflow for simple tarball -> binary pattern
# Usage: install_from_tarball <binary_name> <repo> <version> <download_url> <binary_path_in_tarball>
#
# Example:
#   install_from_tarball \
#     "lazygit" \
#     "jesseduffield/lazygit" \
#     "0.40.2" \
#     "https://github.com/jesseduffield/lazygit/releases/download/v0.40.2/lazygit_0.40.2_Darwin_arm64.tar.gz" \
#     "lazygit"
install_from_tarball() {
  local binary_name="$1"
  local repo="$2"
  local version="$3"
  local download_url="$4"
  local binary_path_in_tarball="$5"

  local target_bin="$HOME/.local/bin/$binary_name"
  local temp_tarball="/tmp/${binary_name}.tar.gz"

  # Download
  download_release "$download_url" "$temp_tarball" "$binary_name"

  # Extract
  extract_tarball "$temp_tarball" "/tmp" "$binary_path_in_tarball"

  # Install
  install_binary "/tmp/$binary_path_in_tarball" "$target_bin"

  # Verify
  verify_installation "$binary_name"
}
