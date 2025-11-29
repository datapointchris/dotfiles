#!/usr/bin/env bash
# ================================================================
# Install tenv and Terraform
# ================================================================
# Installs tenv (if needed) and Terraform version from packages.yml
# Universal script for all platforms
# ================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps

export TERM=${TERM:-xterm}

# Check if packages.yml exists
if [[ ! -f "$DOTFILES_DIR/management/packages.yml" ]]; then
  print_error "packages.yml not found at $DOTFILES_DIR/management/packages.yml"
  exit 1
fi

# Install tenv if not already installed
if ! command -v tenv >/dev/null 2>&1; then
  print_section "Installing tenv" "cyan"
  if bash "$DOTFILES_DIR/management/common/install/github-releases/install-tenv.sh"; then
    echo "  ✓ tenv installed"
  else
    print_error "Failed to install tenv"
    exit 1
  fi
else
  echo "tenv already installed"
fi

# Read Terraform version from packages.yml using Python parser
TERRAFORM_VERSION=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --get=runtimes.terraform.version)

print_section "Installing Terraform ${TERRAFORM_VERSION}" "cyan"

# Check if tenv is available
if ! command -v tenv >/dev/null 2>&1; then
  print_error "tenv not found in PATH"
  exit 1
fi

# Install specific Terraform version
echo "  Installing Terraform ${TERRAFORM_VERSION}..."
if tenv tf install "${TERRAFORM_VERSION}"; then
  echo "    ✓ Terraform installed"
else
  print_error "Failed to install Terraform"
  exit 1
fi

# Set as default version
echo "  Setting Terraform ${TERRAFORM_VERSION} as default..."
tenv tf use "${TERRAFORM_VERSION}"

print_success "Terraform ${TERRAFORM_VERSION} installed and set as default"
