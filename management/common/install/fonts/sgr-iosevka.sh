#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/lib/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

font_name="SGr-Iosevka Variants"
font_extension="ttc"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-${font_name// /}"
trap 'rm -rf "$download_dir"' EXIT

download_sgriosevka() {
  local temp_dir
  temp_dir=$(mktemp -d)
  cd "$temp_dir" || exit 1

  local release_json
  if ! release_json=$(curl -fsSL https://api.github.com/repos/be5invis/Iosevka/releases/latest); then
    manual_steps="Download manually from GitHub:
   https://github.com/be5invis/Iosevka/releases/latest

Look for these 4 files:
   SuperTTC-SGr-Iosevka-*.zip
   SuperTTC-SGr-IosevkaTerm-*.zip
   SuperTTC-SGr-IosevkaSlab-*.zip
   SuperTTC-SGr-IosevkaTermSlab-*.zip

Extract and install:
   unzip SuperTTC-SGr-Iosevka-*.zip
   mkdir -p $system_font_dir/SGr-Iosevka
   mv *.ttc $system_font_dir/SGr-Iosevka/
   (Repeat for each variant)"

    output_failure_data "SGr-Iosevka" "https://github.com/be5invis/Iosevka/releases/latest" "latest" "$manual_steps" "Failed to fetch release info"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi

  # Extract download URLs for SGr variants
  local sgr_iosevka_url
  local sgr_term_url
  local sgr_slab_url
  local sgr_termslab_url

  sgr_iosevka_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*SuperTTC-SGr-Iosevka-[0-9.]*\.zip"' | grep -v "Term\|Slab" | head -1 | sed 's/.*": *"//' | sed 's/"$//')
  sgr_term_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*SuperTTC-SGr-IosevkaTerm-[0-9.]*\.zip"' | grep -v "Slab" | head -1 | sed 's/.*": *"//' | sed 's/"$//')
  sgr_slab_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*SuperTTC-SGr-IosevkaSlab-[0-9.]*\.zip"' | grep -v "Term" | head -1 | sed 's/.*": *"//' | sed 's/"$//')
  sgr_termslab_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*SuperTTC-SGr-IosevkaTermSlab-[0-9.]*\.zip"' | head -1 | sed 's/.*": *"//' | sed 's/"$//')

  # Download and extract each variant
  mkdir -p "$download_dir/SGr-Iosevka"
  mkdir -p "$download_dir/SGr-IosevkaTerm"
  mkdir -p "$download_dir/SGr-IosevkaSlab"
  mkdir -p "$download_dir/SGr-IosevkaTermSlab"

  if ! curl -fsSL "$sgr_iosevka_url" -o SGr-Iosevka.zip; then
    output_failure_data "SGr-Iosevka" "$sgr_iosevka_url" "latest" "Download failed" "Download failed"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi
  unzip -qo SGr-Iosevka.zip || exit 1
  find . -maxdepth 1 -name "*.ttc" -exec mv {} "$download_dir/SGr-Iosevka/" \; 2>/dev/null || true

  if ! curl -fsSL "$sgr_term_url" -o SGr-IosevkaTerm.zip; then
    output_failure_data "SGr-IosevkaTerm" "$sgr_term_url" "latest" "Download failed" "Download failed"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi
  unzip -qo SGr-IosevkaTerm.zip || exit 1
  find . -maxdepth 1 -name "*.ttc" -exec mv {} "$download_dir/SGr-IosevkaTerm/" \; 2>/dev/null || true

  if ! curl -fsSL "$sgr_slab_url" -o SGr-IosevkaSlab.zip; then
    output_failure_data "SGr-IosevkaSlab" "$sgr_slab_url" "latest" "Download failed" "Download failed"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi
  unzip -qo SGr-IosevkaSlab.zip || exit 1
  find . -maxdepth 1 -name "*.ttc" -exec mv {} "$download_dir/SGr-IosevkaSlab/" \; 2>/dev/null || true

  if ! curl -fsSL "$sgr_termslab_url" -o SGr-IosevkaTermSlab.zip; then
    output_failure_data "SGr-IosevkaTermSlab" "$sgr_termslab_url" "latest" "Download failed" "Download failed"
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
  log_success "Downloaded $count files (4 TTC collections)"
}

print_section "Installing $font_name" "yellow"

# Check if any variant is already installed
if is_font_installed "$system_font_dir" "*SGr-Iosevka*.$font_extension"; then
  log_success "$font_name already installed"
  exit 0
fi

log_info "Downloading $font_name..."
download_sgriosevka

log_info "Pruning unwanted variants..."
prune_font_family "$download_dir"

log_info "Standardizing filenames..."
standardize_font_family "$download_dir"

log_info "Installing to system fonts directory..."
install_font_files "$download_dir" "$system_font_dir" "$platform"

log_info "Refreshing font cache..."
refresh_font_cache "$platform" "$system_font_dir"

log_success "$font_name installation complete"
