#!/usr/bin/env bash
set -euo pipefail

# Generic Nerd Font installer - reads font list from packages.yml
# Usage:
#   ./nerd-fonts.sh              # Install all Nerd Fonts
#   ./nerd-fonts.sh JetBrainsMono  # Install specific font by package name

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

SPECIFIC_FONT="${1:-}"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)

install_nerd_font() {
  local font_name="$1"
  local package="$2"
  local check_pattern="$3"
  local font_extension="$4"

  local download_dir="/tmp/fonts-${package}"

  # Check if already installed
  if is_font_installed "$system_font_dir" "${check_pattern}.${font_extension}"; then
    log_success "$font_name already installed: $system_font_dir"
    return 0
  fi

  log_info "Installing $font_name..."

  # Setup cleanup trap for this font
  trap 'rm -rf "$download_dir"' RETURN

  # Download
  if ! download_nerd_font "$package" "$font_extension" "$download_dir" "$system_font_dir"; then
    log_error "Failed to download $font_name"
    return 1
  fi

  # Process and install
  prune_font_family "$download_dir"
  prune_font_variants "$download_dir" "$package"
  standardize_font_family "$download_dir"
  install_font_files "$download_dir" "$system_font_dir" "$platform"

  log_success "$font_name installed: $system_font_dir"
}

# Read fonts from packages.yml
installed_count=0
failed_count=0

while IFS='|' read -r font_name package check_pattern extension; do
  # Skip if specific font requested and this isn't it
  if [[ -n "$SPECIFIC_FONT" && "$package" != "$SPECIFIC_FONT" ]]; then
    continue
  fi

  if install_nerd_font "$font_name" "$package" "$check_pattern" "$extension"; then
    installed_count=$((installed_count + 1))
  else
    failed_count=$((failed_count + 1))
  fi
done < <(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=nerd-fonts --format=full)

# Refresh font cache once at the end (more efficient than per-font)
refresh_font_cache "$platform" "$system_font_dir"

# Summary
if [[ -n "$SPECIFIC_FONT" ]]; then
  if [[ $failed_count -gt 0 ]]; then
    log_error "Failed to install $SPECIFIC_FONT"
    exit 1
  fi
else
  if [[ $failed_count -gt 0 ]]; then
    log_warning "Nerd Fonts: $installed_count installed, $failed_count failed"
    exit 1
  else
    log_success "All Nerd Fonts processed ($installed_count total)"
  fi
fi
