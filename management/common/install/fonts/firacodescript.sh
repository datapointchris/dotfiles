#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

font_name="FiraCodeiScript"
font_extension="ttf"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-${font_name// /}"
trap 'rm -rf "$download_dir"' EXIT

download_firacodescript() {
  mkdir -p "$download_dir"

  local base_url="https://github.com/kencrocken/FiraCodeiScript/raw/master"
  local files=("FiraCodeiScript-Regular.ttf" "FiraCodeiScript-Bold.ttf" "FiraCodeiScript-Italic.ttf")

  for file in "${files[@]}"; do
    if ! curl -fsSL "$base_url/$file" -o "$download_dir/$file"; then
      manual_steps="1. Download font files:
   curl -fsSL ${base_url}/FiraCodeiScript-Regular.ttf -o FiraCodeiScript-Regular.ttf
   curl -fsSL ${base_url}/FiraCodeiScript-Bold.ttf -o FiraCodeiScript-Bold.ttf
   curl -fsSL ${base_url}/FiraCodeiScript-Italic.ttf -o FiraCodeiScript-Italic.ttf

   Or download in browser:
   https://github.com/kencrocken/FiraCodeiScript/tree/master

2. Install to system fonts:
   cp FiraCodeiScript-*.ttf ${system_font_dir}/

3. Refresh font cache (Linux only):
   fc-cache -fv

4. Verify installation:
   fc-list | grep -i 'FiraCodeiScript'"

      output_failure_data "FiraCodeiScript" "${base_url}/${file}" "latest" "$manual_steps" "Download failed for $file"
      exit 1
    fi
  done

  local count
  count=$(count_font_files "$download_dir")
  [[ $count -eq 0 ]] && log_error "No fonts found after download" && exit 1
  log_success "Downloaded $count files"
}

print_section "Installing $font_name"

if is_font_installed "$system_font_dir" "*FiraCodeiScript*.$font_extension"; then
  log_success "$font_name already installed"
  exit 0
fi

log_info "Downloading $font_name..."
download_firacodescript

log_info "Pruning unwanted variants..."
prune_font_family "$download_dir"

log_info "Standardizing filenames..."
standardize_font_family "$download_dir"

log_info "Installing to system fonts directory..."
install_font_files "$download_dir" "$system_font_dir" "$platform"

log_info "Refreshing font cache..."
refresh_font_cache "$platform" "$system_font_dir"
