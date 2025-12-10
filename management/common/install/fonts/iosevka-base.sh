#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

font_name="Iosevka Base"
font_extension="ttc"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-${font_name// /}"
trap 'rm -rf "$download_dir"' EXIT

download_iosevkabase() {
  local temp_dir
  temp_dir=$(mktemp -d)
  cd "$temp_dir" || exit 1

  local release_url
  release_url=$(fetch_github_release_asset "be5invis/Iosevka" "PkgTTC-Iosevka-[0-9.]*\.zip")

  if [[ -z "$release_url" ]]; then
    manual_steps="Download manually from GitHub:
   https://github.com/be5invis/Iosevka/releases/latest

Look for file:
   PkgTTC-Iosevka-*.zip

Extract and install:
   unzip PkgTTC-Iosevka-*.zip
   mkdir -p $system_font_dir
   mv *.ttc $system_font_dir/"

    output_failure_data "IosevkaBase" "https://github.com/be5invis/Iosevka/releases/latest" "latest" "$manual_steps" "Failed to fetch release URL"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi

  if ! curl -fsSL "$release_url" -o Iosevka-base.zip; then
    manual_steps="Download manually from:
   $release_url

Extract and install:
   unzip Iosevka-base.zip
   mkdir -p $system_font_dir
   mv *.ttc $system_font_dir/"

    output_failure_data "IosevkaBase" "$release_url" "latest" "$manual_steps" "Download failed"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi

  unzip -qo Iosevka-base.zip || exit 1
  mkdir -p "$download_dir"
  find . -maxdepth 1 -name "*.ttc" -exec mv {} "$download_dir/" \; 2>/dev/null || true

  cd - > /dev/null
  rm -rf "$temp_dir"

  local count
  count=$(count_font_files "$download_dir")
  [[ $count -eq 0 ]] && log_error "No fonts found after extraction" && exit 1
  log_success "Downloaded $count files"
}

print_section "Installing $font_name"

if is_font_installed "$system_font_dir" "Iosevka-*.$font_extension"; then
  log_success "$font_name already installed"
  exit 0
fi

log_info "Downloading $font_name..."
download_iosevkabase

log_info "Pruning unwanted variants..."
prune_font_family "$download_dir"

log_info "Standardizing filenames..."
standardize_font_family "$download_dir"

log_info "Installing to system fonts directory..."
install_font_files "$download_dir" "$system_font_dir" "$platform"

log_info "Refreshing font cache..."
refresh_font_cache "$platform" "$system_font_dir"

log_success "$font_name installation complete"
