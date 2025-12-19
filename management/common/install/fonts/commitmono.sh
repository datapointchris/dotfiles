#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/font-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

font_name="Commit Mono"
font_extension="otf"

platform=$(detect_platform)
system_font_dir=$(get_system_font_dir)
download_dir="/tmp/fonts-${font_name// /}"
trap 'rm -rf "$download_dir"' EXIT

download_commitmono() {
  local temp_dir
  temp_dir=$(mktemp -d)
  cd "$temp_dir" || exit 1

  local release_url
  release_url=$(fetch_github_release_asset "eigilnikolajsen/commit-mono" "\.zip")

  if [[ -z "$release_url" ]]; then
    manual_steps="Download manually from GitHub:
   https://github.com/eigilnikolajsen/commit-mono/releases/latest

Extract and install:
   unzip CommitMono-*.zip
   mkdir -p $system_font_dir
   cp *.otf $system_font_dir/"

    output_failure_data "CommitMono" "https://github.com/eigilnikolajsen/commit-mono/releases/latest" "latest" "$manual_steps" "Failed to fetch release URL"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi

  if ! curl -fsSL "$release_url" -o CommitMono.zip; then
    manual_steps="Download manually from:
   $release_url

Extract and install:
   unzip CommitMono.zip
   mkdir -p $system_font_dir
   cp *.otf $system_font_dir/"

    output_failure_data "CommitMono" "$release_url" "latest" "$manual_steps" "Download failed"
    cd - > /dev/null
    rm -rf "$temp_dir"
    exit 1
  fi

  unzip -qo CommitMono.zip || exit 1
  mkdir -p "$download_dir"
  find . -type f -name "*.otf" -exec mv {} "$download_dir/" \; 2>/dev/null || true

  cd - > /dev/null
  rm -rf "$temp_dir"

  local count
  count=$(count_font_files "$download_dir")
  [[ $count -eq 0 ]] && log_error "No fonts found after extraction" && exit 1
  log_success "Downloaded $count files"
}


if is_font_installed "$system_font_dir" "*CommitMono*.$font_extension"; then
  log_success "$font_name already installed: $system_font_dir"
  exit 0
fi

log_info "Downloading $font_name..."
download_commitmono

prune_font_family "$download_dir"

standardize_font_family "$download_dir"

install_font_files "$download_dir" "$system_font_dir" "$platform"

refresh_font_cache "$platform" "$system_font_dir"

log_success "$font_name installed: $system_font_dir"
