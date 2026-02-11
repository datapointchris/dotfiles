#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

font_name="SeriousShanns Nerd Font"
font_extension="otf"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-${font_name// /}"
trap 'rm -rf "$download_dir"' EXIT

download_seriousshanns() {
  mkdir -p "$download_dir"

  # SeriousShanns Nerd Font Mono - modified Comic Mono with improved legibility
  # Changes: 'a' less like 'o', 'l' less like '1', 'Y' less like 'y'
  local zip_url="https://kaBeech.github.io/serious-shanns/SeriousShanns/SeriousShannsNerdFontMono.zip"

  local manual_steps="1. Visit the SeriousShanns GitHub page:
   https://github.com/kaBeech/serious-shanns

2. Download the Nerd Font Mono zip:
   https://kaBeech.github.io/serious-shanns/SeriousShanns/SeriousShannsNerdFontMono.zip

3. Extract and install:
   unzip SeriousShannsNerdFontMono.zip
   mkdir -p ${system_font_dir}
   mv *.otf ${system_font_dir}/

4. Refresh font cache (Linux only):
   fc-cache -fv

5. Verify installation:
   fc-list | grep -i 'SeriousShanns'"

  if check_font_cache "SeriousShannsNerdFontMono.zip" "$download_dir/SeriousShannsNerdFontMono.zip"; then
    log_info "Using offline cache for SeriousShannsNerdFontMono"
  elif ! curl -fsSL "$zip_url" -o "$download_dir/SeriousShannsNerdFontMono.zip"; then
    output_failure_data "SeriousShanns" "$zip_url" "latest" "$manual_steps" "Download failed"
    exit 1
  fi

  unzip -qo "$download_dir/SeriousShannsNerdFontMono.zip" -d "$download_dir" || exit 1

  local count
  count=$(count_font_files "$download_dir")
  [[ $count -eq 0 ]] && log_error "No fonts found after extraction" && exit 1
  log_success "Downloaded $count files"
}

if is_font_installed "$system_font_dir" "*SeriousShannsNerdFontMono*.$font_extension"; then
  log_success "$font_name already installed: $system_font_dir"
  exit 0
fi

log_info "Downloading $font_name (kaBeech)..."
download_seriousshanns

prune_font_family "$download_dir"

standardize_font_family "$download_dir"

fix_font_metadata "$download_dir"

install_font_files "$download_dir" "$system_font_dir" "$platform"

refresh_font_cache "$platform" "$system_font_dir"

log_success "$font_name installed: $system_font_dir"
