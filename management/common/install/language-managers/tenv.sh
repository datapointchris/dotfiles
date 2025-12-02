#!/usr/bin/env bash
# ================================================================
# Install tenv and Terraform
# ================================================================
# Installs tenv (Terraform/OpenTofu version manager) and Terraform runtime
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/tenv + proxy binaries
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source error handling (includes structured logging)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
enable_error_traps

# Source GitHub release installer library
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

BINARY_NAME="tenv"
REPO="tofuutils/tenv"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing tenv"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# Detect platform (tenv uses x86_64 and arm64 directly)
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="Darwin"
else
  PLATFORM="Linux"
fi
ARCH=$(uname -m)

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/tenv_${VERSION}_${PLATFORM}_${ARCH}.tar.gz"

# Download and extract
TEMP_TARBALL="/tmp/${BINARY_NAME}.tar.gz"
log_info "Downloading tenv..."
if ! curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_TARBALL"; then
  log_fatal "Failed to download from $DOWNLOAD_URL" "${BASH_SOURCE[0]}" "$LINENO"
fi
register_cleanup "rm -f '$TEMP_TARBALL' 2>/dev/null || true"

log_info "Extracting..."
tar -xzf "$TEMP_TARBALL" -C /tmp

# Install all binaries (tenv + proxy binaries)
log_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"

for binary in tenv terraform tofu terragrunt terramate atmos tf; do
  if [ -f "/tmp/$binary" ]; then
    mv "/tmp/$binary" "$HOME/.local/bin/"
    chmod +x "$HOME/.local/bin/$binary"
  fi
done

# Verify
if command -v tenv >/dev/null 2>&1; then
  log_success "tenv and proxy binaries installed successfully"
else
  log_fatal "tenv not found in PATH after installation" "${BASH_SOURCE[0]}" "$LINENO"
fi

# Check if packages.yml exists for Terraform installation
if [[ ! -f "$DOTFILES_DIR/management/packages.yml" ]]; then
  log_warning "packages.yml not found, skipping Terraform installation"
  print_banner_success "tenv installation complete"
  exit_success
fi

# Read Terraform version from packages.yml
TERRAFORM_VERSION=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --get=runtimes.terraform.version)

print_section "Installing Terraform ${TERRAFORM_VERSION}" "cyan"

# Install specific Terraform version
echo "  Installing Terraform ${TERRAFORM_VERSION}..."
if tenv tf install "${TERRAFORM_VERSION}"; then
  echo "    ✓ Terraform installed"
else
  log_error "Failed to install Terraform"
  exit 1
fi

# Set as default version
echo "  Setting Terraform ${TERRAFORM_VERSION} as default..."
tenv tf use "${TERRAFORM_VERSION}"

log_success "Terraform ${TERRAFORM_VERSION} installed and set as default"
print_banner_success "tenv and Terraform installation complete"
exit_success
