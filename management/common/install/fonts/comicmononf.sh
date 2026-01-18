#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

font_name="ComicMonoNF"
font_extension="ttf"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-${font_name// /}"
trap 'rm -rf "$download_dir"' EXIT

download_comicmono() {
  mkdir -p "$download_dir"

  # Using xtevenx/ComicMonoNF v1 - has proper PANOSE values for Ghostty compatibility
  # and isFixedPitch=1 for Kitty compatibility
  local base_url="https://raw.githubusercontent.com/xtevenx/ComicMonoNF/master/v1"
  local files=("ComicMonoNF-Regular.ttf" "ComicMonoNF-Bold.ttf")

  for file in "${files[@]}"; do
    if ! curl -fsSL "$base_url/$file" -o "$download_dir/$file"; then
      manual_steps="Download manually from:
   ${base_url}/${file}

Or browse the repo:
   https://github.com/xtevenx/ComicMonoNF/tree/master/v1

Save files to:
   $system_font_dir/"

      output_failure_data "ComicMonoNF" "${base_url}/${file}" "latest" "$manual_steps" "Download failed for $file"
      exit 1
    fi
  done

  local count
  count=$(count_font_files "$download_dir")
  [[ $count -eq 0 ]] && log_error "No fonts found after download" && exit 1
  log_success "Downloaded $count files"
}


if is_font_installed "$system_font_dir" "*ComicMonoNF*.$font_extension"; then
  log_success "$font_name already installed: $system_font_dir"
  exit 0
fi

log_info "Downloading $font_name (xtevenx v1)..."
download_comicmono

prune_font_family "$download_dir"

standardize_font_family "$download_dir"

install_font_files "$download_dir" "$system_font_dir" "$platform"

refresh_font_cache "$platform" "$system_font_dir"

log_success "$font_name installed: $system_font_dir"
