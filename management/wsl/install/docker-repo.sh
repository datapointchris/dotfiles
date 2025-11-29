#!/usr/bin/env bash
# ================================================================
# Setup Docker Official Repository - Ubuntu/Debian
# ================================================================
# Adds Docker's official apt repository for latest versions
# Run this BEFORE installing docker packages
# No sudo required if user has sudo access
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/management/common/lib/structured-logging.sh"

print_banner "Setting up Docker Official Repository (Ubuntu)"

# Check if already set up
if [ -f /etc/apt/sources.list.d/docker.list ]; then
  print_info "Docker repository already configured"
  exit 0
fi

# Check for WSL - skip if detected
if grep -q "Microsoft" /proc/version 2>/dev/null || grep -q "WSL" /proc/version 2>/dev/null; then
  print_warning "WSL detected - Docker uses Windows Docker Desktop"
  print_info "Skipping Docker repository setup"
  exit 0
fi

# Detect Ubuntu/Debian
if ! command -v lsb_release >/dev/null 2>&1; then
  print_error "lsb_release not found - is this Ubuntu/Debian?"
  exit 1
fi

DISTRO=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
if [[ "$DISTRO" != "ubuntu" ]] && [[ "$DISTRO" != "debian" ]]; then
  print_error "This script is for Ubuntu/Debian only (detected: $DISTRO)"
  exit 1
fi

print_info "Detected: $DISTRO"

# Install prerequisites
print_info "Installing prerequisites..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
print_info "Adding Docker's GPG key..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL "https://download.docker.com/linux/$DISTRO/gpg" | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
print_info "Adding Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/${DISTRO} \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update apt cache
print_info "Updating package cache..."
sudo apt-get update

print_banner_success "Docker Official Repository Setup Complete"
print_info "You can now install Docker with:"
print_info "  sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
