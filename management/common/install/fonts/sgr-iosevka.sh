#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

font_name="SGr-Iosevka Term Slab"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-${font_name// /}"
trap 'rm -rf "$download_dir"' EXIT

download_sgriosevka_termslab() {
  local temp_dir
  temp_dir=$(mktemp -d)
  cd "$temp_dir" || exit 1

  local manual_steps="1. Visit GitHub releases page:
   https://github.com/be5invis/Iosevka/releases/latest

2. Download:
   SuperTTC-SGr-IosevkaTermSlab-*.zip

3. Extract and install:
   unzip SuperTTC-SGr-IosevkaTermSlab-*.zip
   mkdir -p ${system_font_dir}
   mv *.ttc ${system_font_dir}/

4. Refresh font cache (Linux only):
   fc-cache -fv

5. Verify installation:
   fc-list | grep -i 'Iosevka.*Term.*Slab'"

  if check_font_cache "SGr-IosevkaTermSlab.zip" "SGr-IosevkaTermSlab.zip"; then
    log_info "Using offline cache for SGr-IosevkaTermSlab"
    mkdir -p "$download_dir/SGr-IosevkaTermSlab"
    unzip -qo SGr-IosevkaTermSlab.zip || exit 1
    find . -maxdepth 1 -name "*.ttc" -exec mv {} "$download_dir/SGr-IosevkaTermSlab/" \; 2>/dev/null || true

    cd - > /dev/null
    rm -rf "$temp_dir"

    local count
    count=$(count_font_files "$download_dir")
    [[ $count -eq 0 ]] && log_error "No fonts found after extraction" && exit 1
    log_success "Downloaded $count files (1 TTC collection)"
    return
  fi

  local release_json
  if ! release_json=$(curl -fsSL https://api.github.com/repos/be5invis/Iosevka/releases/latest); then
    output_failure_data "SGr-Iosevka Term Slab" "https://github.com/be5invis/Iosevka/releases/latest" "latest" "$manual_steps" "Failed to fetch release info"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi

  local sgr_termslab_url
  sgr_termslab_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*SuperTTC-SGr-IosevkaTermSlab-[0-9.]*\.zip"' | head -1 | sed 's/.*": *"//' | sed 's/"$//')

  mkdir -p "$download_dir/SGr-IosevkaTermSlab"

  if ! curl -fsSL "$sgr_termslab_url" -o SGr-IosevkaTermSlab.zip; then
    output_failure_data "SGr-IosevkaTermSlab" "$sgr_termslab_url" "latest" "$manual_steps" "Download failed"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi
  unzip -qo SGr-IosevkaTermSlab.zip || exit 1
  find . -maxdepth 1 -name "*.ttc" -exec mv {} "$download_dir/SGr-IosevkaTermSlab/" \; 2>/dev/null || true

  cd - > /dev/null
  rm -rf "$temp_dir"

  local count
  count=$(count_font_files "$download_dir")
  [[ $count -eq 0 ]] && log_error "No fonts found after extraction" && exit 1
  log_success "Downloaded $count files (1 TTC collection)"
}

# Check if Term Slab is installed
sgr_termslab_installed() {
  local font_dir="$1"
  [[ -f "$font_dir/SGr-IosevkaTermSlab.ttc" ]]
}

if sgr_termslab_installed "$system_font_dir"; then
  log_success "$font_name already installed: $system_font_dir"
  exit 0
fi

log_info "Downloading $font_name..."
download_sgriosevka_termslab

prune_font_family "$download_dir"

standardize_font_family "$download_dir"

install_font_files "$download_dir" "$system_font_dir" "$platform"

refresh_font_cache "$platform" "$system_font_dir"

log_success "$font_name installed: $system_font_dir"
