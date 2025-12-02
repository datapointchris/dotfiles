#!/usr/bin/env bash
# ================================================================
# Install Latest Neovim from GitHub Releases
# ================================================================
# Downloads and installs the latest stable Neovim release
# Configuration read from: management/packages.yml
# Installation location: ~/.local/nvim-{platform}-{arch}/
# Binary symlink: ~/.local/bin/nvim
# No sudo required (user space)
# ================================================================

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
enable_error_traps

# Source helper functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/program-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
MIN_VERSION=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=neovim --field=min_version)
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=neovim --field=repo)

# Detect platform and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    NVIM_BINARY="nvim-macos-x86_64"
  else
    NVIM_BINARY="nvim-macos-arm64"
  fi
else
  NVIM_BINARY="nvim-linux-x86_64"
fi

NVIM_INSTALL_DIR="$HOME/.local/${NVIM_BINARY}"
NVIM_BIN_LINK="$HOME/.local/bin/nvim"

print_banner "Installing Neovim"

# Check if Neovim is already installed with acceptable version (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -L "$NVIM_BIN_LINK" ]] && command -v nvim >/dev/null 2>&1; then
  CURRENT_VERSION=$(nvim --version | head -n1 | sed 's/.*v\([0-9]*\.[0-9]*\).*/\1/')
  log_info "Current version: $CURRENT_VERSION"

  # Simple version comparison (major.minor)
  if [[ $(echo -e "$MIN_VERSION\n$CURRENT_VERSION" | sort -V | head -n1) == "$MIN_VERSION" ]]; then
    log_success " Acceptable version (>= $MIN_VERSION), skipping"
    exit 0
  fi

  log_info "Upgrading..."
fi

# Fetch latest version
NVIM_VERSION=$(get_latest_github_release "$REPO")
if [[ -z "$NVIM_VERSION" ]]; then
  print_manual_install "neovim" "https://github.com/${REPO}/releases/latest" "latest" "${NVIM_BINARY}.tar.gz" \
    "tar -C ~/.local -xzf ~/Downloads/${NVIM_BINARY}.tar.gz && ln -sf ~/.local/${NVIM_BINARY}/bin/nvim ~/.local/bin/nvim"
  exit 1
fi

log_info "Latest: $NVIM_VERSION"

# Check for alternate installations
if [[ ! -L "$NVIM_BIN_LINK" ]] && command -v nvim >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v nvim)
  log_warning " nvim found at $ALTERNATE_LOCATION"
  log_info "Installing to $NVIM_BIN_LINK anyway (PATH priority will use this one)"
fi

# Download URL
NVIM_URL="https://github.com/${REPO}/releases/download/${NVIM_VERSION}/${NVIM_BINARY}.tar.gz"
NVIM_TARBALL="/tmp/${NVIM_BINARY}.tar.gz"

# Download
if ! download_file "$NVIM_URL" "$NVIM_TARBALL" "neovim"; then
  print_manual_install "neovim" "$NVIM_URL" "$NVIM_VERSION" "${NVIM_BINARY}.tar.gz" \
    "tar -C ~/.local -xzf ~/Downloads/${NVIM_BINARY}.tar.gz && ln -sf ~/.local/${NVIM_BINARY}/bin/nvim ~/.local/bin/nvim"
  exit 1
fi

# Verify it's a valid gzip file
if ! file "$NVIM_TARBALL" | grep -q "gzip compressed"; then
  log_error " Not a valid gzip archive: $(file "$NVIM_TARBALL")"
  log_info "URL: $NVIM_URL"
  print_manual_install "neovim" "$NVIM_URL" "$NVIM_VERSION" "${NVIM_BINARY}.tar.gz" \
    "tar -C ~/.local -xzf ~/Downloads/${NVIM_BINARY}.tar.gz && ln -sf ~/.local/${NVIM_BINARY}/bin/nvim ~/.local/bin/nvim"
  exit 1
fi

# Install
log_info "Installing to ~/.local/..."
if [[ -d "$NVIM_INSTALL_DIR" ]]; then
  rm -rf "$NVIM_INSTALL_DIR"
fi

tar -C "$HOME/.local" -xzf "$NVIM_TARBALL"
rm "$NVIM_TARBALL"

log_info "Creating symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$NVIM_INSTALL_DIR/bin/nvim" "$NVIM_BIN_LINK"

# Verify
if command -v nvim >/dev/null 2>&1; then
  INSTALLED_VERSION=$(nvim --version | head -n1)
  log_success " $INSTALLED_VERSION"
else
  log_error " Installation verification failed"
  log_info "Make sure ~/.local/bin is in your PATH"
  exit 1
fi

print_banner_success "Neovim installation complete"
