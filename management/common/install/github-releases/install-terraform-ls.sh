#!/usr/bin/env bash
# ================================================================
# Install terraform-ls from GitHub Releases
# ================================================================
# Downloads and installs HashiCorp Terraform Language Server
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/terraform-ls
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Source helper functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../../utils/install-program-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=terraform-ls --field=repo)

# Detect platform and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="darwin"
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    ARCH="amd64"
  elif [[ "$ARCH" == "arm64" ]]; then
    ARCH="arm64"
  fi
else
  PLATFORM="linux"
  ARCH="amd64"
fi

TF_LS_BIN="$HOME/.local/bin/terraform-ls"

print_banner "Installing terraform-ls"

# Check if terraform-ls is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$TF_LS_BIN" ]] && command -v terraform-ls >/dev/null 2>&1; then
  CURRENT_VERSION=$(terraform-ls version 2>&1 | head -n1 || echo "unknown")
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Get latest version from GitHub API
LATEST_VERSION=$(get_latest_github_release "$REPO")
print_info "Target version: $LATEST_VERSION"

# Check for alternate installations
if [[ ! -f "$TF_LS_BIN" ]] && command -v terraform-ls >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v terraform-ls)
  print_warning " terraform-ls found at $ALTERNATE_LOCATION"
  print_info "Installing to $TF_LS_BIN anyway (PATH priority will use this one)"
fi

# HashiCorp uses releases.hashicorp.com, not GitHub releases
TF_LS_URL="https://releases.hashicorp.com/terraform-ls/${LATEST_VERSION#v}/terraform-ls_${LATEST_VERSION#v}_${PLATFORM}_${ARCH}.zip"
TF_LS_ZIP="/tmp/terraform-ls.zip"

# Download
if ! download_file "$TF_LS_URL" "$TF_LS_ZIP" "terraform-ls"; then
  print_manual_install "terraform-ls" "$TF_LS_URL" "$LATEST_VERSION" "terraform-ls_${LATEST_VERSION#v}_${PLATFORM}_${ARCH}.zip" \
    "unzip ~/Downloads/terraform-ls_${LATEST_VERSION#v}_${PLATFORM}_${ARCH}.zip -d /tmp && mv /tmp/terraform-ls ~/.local/bin/ && chmod +x ~/.local/bin/terraform-ls"
  exit 1
fi

# Extract
print_info "Extracting..."
unzip -qo "$TF_LS_ZIP" -d /tmp

# Install
print_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
mv /tmp/terraform-ls "$TF_LS_BIN"
chmod +x "$TF_LS_BIN"

# Cleanup
rm -f "$TF_LS_ZIP"

# Verify installation
if command -v terraform-ls >/dev/null 2>&1; then
  INSTALLED_VERSION=$(terraform-ls version 2>&1 | head -n1 || echo "unknown")
  print_success "Installed: $INSTALLED_VERSION"
else
  print_error "Installation failed - terraform-ls command not found in PATH"
  exit 1
fi
