#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

font_name="3270 Nerd Font"
nerd_font_package="3270"
font_extension="ttf"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-${font_name// /}"
trap 'rm -rf "$download_dir"' EXIT


if is_font_installed "$system_font_dir" "*3270*NerdFont*.$font_extension"; then
  log_success "$font_name already installed: $system_font_dir"
  exit 0
fi

log_info "Downloading $font_name..."
download_nerd_font "$nerd_font_package" "$font_extension" "$download_dir" "$system_font_dir"

prune_font_family "$download_dir"

standardize_font_family "$download_dir"

install_font_files "$download_dir" "$system_font_dir" "$platform"

refresh_font_cache "$platform" "$system_font_dir"

log_success "$font_name installed: $system_font_dir"
