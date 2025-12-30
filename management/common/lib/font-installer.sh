#!/usr/bin/env bash

get_system_font_dir() {
  local platform
  platform=$(detect_platform)
  case "$platform" in
    macos) echo "$HOME/Library/Fonts" ;;
    wsl)   echo "/mnt/c/Windows/Fonts" ;;
    linux|arch) echo "$HOME/.local/share/fonts" ;;
    *)
      log_error "Unsupported platform: $platform"
      return 1
      ;;
  esac
}

is_font_installed() {
  local target_dir="$1"
  local pattern="$2"
  [[ ! -d "$target_dir" ]] && return 1
  local count
  count=$(find "$target_dir" -type f -name "$pattern" 2>/dev/null | wc -l | tr -d ' ')
  [[ $count -gt 0 ]]
}

count_font_files() {
  local dir="$1"
  [[ ! -d "$dir" ]] && echo "0" && return
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) 2>/dev/null | wc -l | tr -d ' '
}

find_font_files() {
  local dir="$1"
  shift
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) "$@"
}

download_nerd_font() {
  local package="$1"
  local extension="$2"
  local download_dir="$3"
  local _system_font_dir="$4"  # Unused - kept for backward compatibility

  local temp_dir
  temp_dir=$(mktemp -d)
  cd "$temp_dir" || return 1

  local url="https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${package}.tar.xz"
  local archive_file="${package}.tar.xz"

  # Try download, fallback to home directory
  log_info "Downloading from: $url"
  if ! curl -fsSL "$url" -o "$archive_file"; then
    # Download failed - check home directory for manual download
    log_warning "Download failed, checking home directory..."
    local home_file
    home_file=$(find "$HOME" -maxdepth 1 -name "${package}*.tar.xz" -type f 2>/dev/null | head -1)

    if [[ -n "$home_file" ]]; then
      log_info "Found in home directory: $home_file"
      cp "$home_file" "$archive_file"
    else
      manual_steps="1. Download manually:
   ${url}

2. Save to home directory (~/)

3. Re-run the font installer"
      output_failure_data "$package" "https://github.com/ryanoasis/nerd-fonts/releases/latest" "latest" "$manual_steps" "Download failed"
      cd - > /dev/null || return 1
      rm -rf "$temp_dir"
      return 1
    fi
  fi

  tar -xf "$archive_file" || return 1
  mkdir -p "$download_dir"
  find . -maxdepth 1 -name "*NerdFont*.$extension" -exec mv {} "$download_dir/" \; 2>/dev/null || true

  cd - > /dev/null || return 1
  rm -rf "$temp_dir"

  local count
  count=$(count_font_files "$download_dir")
  [[ $count -eq 0 ]] && log_error "No fonts found after extraction" && return 1
  log_success "Downloaded $count files"
}

prune_font_family() {
  local font_dir="$1"
  [[ ! -d "$font_dir" ]] && return 0

  local before
  before=$(count_font_files "$font_dir")
  [[ $before -eq 0 ]] && return 0

  log_info "Pruning unwanted variants: ExtraLight, Light, Thin, Medium, SemiBold, ExtraBold, Black, Retina, Propo"

  find "$font_dir" -type f \( \
    -iname "*ExtraLight*" -o -iname "*Light*" -o -iname "*Thin*" -o \
    -iname "*Medium*" -o -iname "*SemiBold*" -o -iname "*ExtraBold*" -o \
    -iname "*Black*" -o -iname "*Retina*" \
  \) -delete 2>/dev/null || true

  find "$font_dir" -type f -name "*NerdFontPropo-*" -delete 2>/dev/null || true

  local after
  after=$(count_font_files "$font_dir")
  local pruned=$((before - after))

  if [[ $pruned -gt 0 ]]; then
    log_success "Pruned $pruned files (kept $after)"
  else
    log_info "No pruning needed (kept $after files)"
  fi
}

standardize_font_family() {
  local font_dir="$1"
  [[ ! -d "$font_dir" ]] && return 0

  local files_with_spaces
  files_with_spaces=$(find "$font_dir" -type f -name "* *" 2>/dev/null | wc -l | tr -d ' ')

  if [[ $files_with_spaces -eq 0 ]]; then
    log_info "No filename standardization needed"
    return 0
  fi

  log_info "Standardizing filenames (replacing spaces with hyphens)"

  find "$font_dir" -type f -name "* *" 2>/dev/null | while read -r file; do
    local dir base new_name
    dir=$(dirname "$file")
    base=$(basename "$file")
    new_name="${base// /-}"
    log_info "  $(basename "$file") → $new_name"
    mv "$file" "$dir/$new_name" 2>/dev/null || true
  done

  log_success "Standardized $files_with_spaces filenames"
}

install_font_files() {
  local source_dir="$1"
  local target_dir="$2"
  local platform="$3"

  log_info "Installing to: $target_dir"
  mkdir -p "$target_dir"

  local installed=0 skipped=0

  while IFS= read -r -d '' font_file; do
    local filename target_file
    filename=$(basename "$font_file")
    target_file="$target_dir/$filename"

    if [[ -f "$target_file" ]]; then
      skipped=$((skipped + 1))
      continue
    fi

    if [[ "$platform" == "wsl" ]]; then
      if cp "$font_file" "$target_dir/" 2>/dev/null; then
        installed=$((installed + 1))
      fi
    else
      cp "$font_file" "$target_dir/"
      installed=$((installed + 1))
    fi
  done < <(find_font_files "$source_dir" -print0)

  if [[ $installed -eq 0 ]] && [[ $skipped -eq 0 ]]; then
    log_error "Copy failed - no files found in $target_dir"
    return 1
  fi

  if [[ $installed -gt 0 ]] && [[ $skipped -gt 0 ]]; then
    log_success "Installed $installed new fonts to $target_dir ($skipped already present)"
  elif [[ $installed -gt 0 ]]; then
    log_success "Installed $installed fonts to $target_dir"
  elif [[ $skipped -gt 0 ]]; then
    log_success "All $skipped fonts already installed in $target_dir"
  fi
}

refresh_font_cache() {
  local platform="$1"
  local target_dir="$2"

  case "$platform" in
    linux|arch)
      if command -v fc-cache &> /dev/null; then
        log_info "Refreshing font cache: fc-cache -f $target_dir"
        if fc-cache -f "$target_dir" 2>&1 | grep -q "succeeded\|fc-cache"; then
          log_success "Font cache refreshed successfully"
        fi
      else
        log_info "fc-cache not available, skipping font cache refresh"
      fi
      ;;
    macos)
      log_info "Font cache refresh not needed on macOS (automatic)"
      ;;
    wsl)
      log_info "Font cache managed by Windows (restart applications to see new fonts)"
      ;;
  esac
}

fetch_github_release_asset() {
  local repo="$1"
  local pattern="$2"
  local release_json
  release_json=$(curl -fsSL "https://api.github.com/repos/$repo/releases/latest") || return 1
  echo "$release_json" | grep -o "\"browser_download_url\": *\"[^\"]*$pattern\"" | head -1 | sed 's/.*": *"//' | sed 's/"$//'
}
