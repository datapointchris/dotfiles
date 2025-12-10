#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

font_name="Victor Mono"
font_extension="ttf"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-${font_name// /}"
trap 'rm -rf "$download_dir"' EXIT

download_victor() {
  local temp_dir
  temp_dir=$(mktemp -d)
  cd "$temp_dir" || exit 1

  local victor_version
  if ! victor_version=$(curl -fsSL https://api.github.com/repos/rubjo/victor-mono/releases/latest | grep '"tag_name"' | cut -d '"' -f 4); then
    manual_steps="Download manually from GitHub:
   https://github.com/rubjo/victor-mono/releases/latest

Look for:
   VictorMonoAll.zip or source code

Extract TTF fonts and install to:
   $system_font_dir/"

    output_failure_data "VictorMono" "https://github.com/rubjo/victor-mono/releases/latest" "latest" "$manual_steps" "Failed to fetch release version"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi

  if ! curl -fsSL "https://api.github.com/repos/rubjo/victor-mono/zipball/$victor_version" -o victor-source.zip; then
    manual_steps="Download manually from:
   https://github.com/rubjo/victor-mono/archive/refs/tags/$victor_version.zip

Extract and install:
   unzip victor-mono-$victor_version.zip
   Find VictorMonoAll.zip in public/ folder
   Extract TTF fonts to $system_font_dir/"

    output_failure_data "VictorMono" "https://github.com/rubjo/victor-mono/releases/latest" "$victor_version" "$manual_steps" "Download failed"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi

  unzip -qo victor-source.zip || exit 1

  local victor_dir
  victor_dir=$(find . -maxdepth 1 -type d -name "rubjo-victor-mono-*" | head -1)

  if [[ ! -d "$victor_dir" ]]; then
    log_error "Victor Mono source directory not found"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi

  if [[ -f "$victor_dir/public/VictorMonoAll.zip" ]]; then
    unzip -qo "$victor_dir/public/VictorMonoAll.zip" || exit 1
    mkdir -p "$download_dir"
    find . -type f -name "*.ttf" -path "*/TTF/*" -exec mv {} "$download_dir/" \; 2>/dev/null || true

    cd - > /dev/null
    rm -rf "$temp_dir"

    local count
    count=$(count_font_files "$download_dir")
    [[ $count -eq 0 ]] && log_error "No fonts found after extraction" && exit 1
    log_success "Downloaded $count files"
  else
    log_error "VictorMonoAll.zip not found in source"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi
}

print_section "Installing $font_name"

if is_font_installed "$system_font_dir" "*VictorMono*.$font_extension"; then
  log_success "$font_name already installed: $system_font_dir"
  exit 0
fi

log_info "Downloading $font_name..."
download_victor

log_info "Pruning unwanted variants..."
prune_font_family "$download_dir"

log_info "Standardizing filenames..."
standardize_font_family "$download_dir"

log_info "Installing to system fonts directory..."
install_font_files "$download_dir" "$system_font_dir" "$platform"

log_info "Refreshing font cache..."
refresh_font_cache "$platform" "$system_font_dir"

log_success "$font_name installed: $system_font_dir"
