#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

source "$HOME/.cargo/env"

# Offline cache directory for pre-built binaries
OFFLINE_CACHE_DIR="${HOME}/installers/binaries"

# Get platform target string for finding cached binaries
get_target_string() {
  local machine_arch
  machine_arch=$(uname -m)

  if [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ "$machine_arch" == "x86_64" ]]; then
      echo "x86_64-apple-darwin"
    else
      echo "aarch64-apple-darwin"
    fi
  else
    echo "x86_64-unknown-linux"
  fi
}

# Try to install from cached pre-built binary
# Returns 0 if successful, 1 if not found/failed
install_from_cache() {
  local package="$1"
  local binary_name="$2"

  [[ ! -d "$OFFLINE_CACHE_DIR" ]] && return 1

  local target
  target=$(get_target_string)

  # Search for matching tarball (handle different naming conventions)
  local cached_file=""
  for pattern in "${package}-"*"${target}"*.tar.gz "${package}_${target}"*.tar.gz; do
    local found
    found=$(find "$OFFLINE_CACHE_DIR" -maxdepth 1 -name "$pattern" -type f 2>/dev/null | head -1)
    if [[ -n "$found" ]]; then
      cached_file="$found"
      break
    fi
  done

  [[ -z "$cached_file" ]] && return 1

  log_info "Found cached binary: $cached_file"

  local extract_dir="/tmp/${package}-extract-$$"
  mkdir -p "$extract_dir"

  # Extract tarball
  if ! tar -xf "$cached_file" -C "$extract_dir" 2>/dev/null; then
    rm -rf "$extract_dir"
    return 1
  fi

  # Find the binary (search recursively for exact match)
  local binary_path
  binary_path=$(find "$extract_dir" -type f -name "$binary_name" 2>/dev/null | head -1)

  if [[ -z "$binary_path" ]]; then
    rm -rf "$extract_dir"
    return 1
  fi

  # Install to cargo bin directory
  mkdir -p "$HOME/.cargo/bin"
  cp "$binary_path" "$HOME/.cargo/bin/$binary_name"
  chmod +x "$HOME/.cargo/bin/$binary_name"

  rm -rf "$extract_dir"
  return 0
}

log_info "Reading packages from packages.yml..."

FAILURE_COUNT=0
while IFS='|' read -r package binary_name; do
  if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v "$binary_name" >/dev/null 2>&1; then
    log_success "$package already installed: $HOME/.cargo/bin/$binary_name"
    continue
  fi

  log_info "Installing $package..."

  # Try cached binary first, then fall back to cargo binstall
  if install_from_cache "$package" "$binary_name"; then
    log_success "$package installed from cache: $HOME/.cargo/bin/$binary_name"
  elif cargo binstall -y "$package"; then
    log_success "$package installed: $HOME/.cargo/bin/$binary_name"
  else
    manual_steps="Install manually with cargo:
   cargo install $package

Or download pre-built binary and place in:
   $OFFLINE_CACHE_DIR/${package}-*.tar.gz"

    output_failure_data "$package" "https://crates.io/crates/$package" "latest" "$manual_steps" "Failed to install via cargo-binstall"
    log_warning "$package installation failed (see summary)"
    FAILURE_COUNT=$((FAILURE_COUNT + 1))
  fi
done < <(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=cargo --format=name_command)

if [[ $FAILURE_COUNT -gt 0 ]]; then
  log_warning "$FAILURE_COUNT package(s) failed to install"
  exit 1
else
  log_success "All Rust CLI tools installed successfully"
  log_info "Installed to: ~/.cargo/bin (highest PATH priority)"
fi
