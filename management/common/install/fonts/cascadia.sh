#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/lib/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

font_name="Cascadia Code Nerd Font"
nerd_font_package="CascadiaCode"
font_extension="ttf"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-$nerd_font_package"
trap 'rm -rf "$download_dir"' EXIT

print_section "Installing $font_name" "yellow"

if is_font_installed "$system_font_dir" "*CaskaydiaCove*NerdFont*.$font_extension"; then
  log_success "$font_name already installed"
  exit 0
fi

log_info "Downloading $nerd_font_package..."
download_nerd_font "$nerd_font_package" "$font_extension" "$download_dir"

log_info "Pruning unwanted variants..."
prune_font_family "$download_dir"

log_info "Standardizing filenames..."
standardize_font_family "$download_dir"

log_info "Installing to system fonts directory..."
install_font_files "$download_dir" "$system_font_dir" "$platform"

log_info "Refreshing font cache..."
refresh_font_cache "$platform" "$system_font_dir"

log_success "$font_name installation complete"
