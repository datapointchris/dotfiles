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

  local temp_dir
  temp_dir=$(mktemp -d)
  cd "$temp_dir" || return 1

  if ! curl -fsSL "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${package}.tar.xz" -o "${package}.tar.xz"; then
    manual_steps="Download manually: https://github.com/ryanoasis/nerd-fonts/releases/latest
Extract: tar -xf ${package}.tar.xz
Move to: $download_dir"
    output_failure_data "$package" "https://github.com/ryanoasis/nerd-fonts/releases/latest" "latest" "$manual_steps" "Download failed"
    cd - > /dev/null || return 1
    rm -rf "$temp_dir"
    return 1
  fi

  tar -xf "${package}.tar.xz" || return 1
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

  find "$font_dir" -type f \( \
    -iname "*ExtraLight*" -o -iname "*Light*" -o -iname "*Thin*" -o \
    -iname "*Medium*" -o -iname "*SemiBold*" -o -iname "*ExtraBold*" -o \
    -iname "*Black*" -o -iname "*Retina*" \
  \) -delete 2>/dev/null || true

  find "$font_dir" -type f -name "*NerdFontPropo-*" -delete 2>/dev/null || true

  local after
  after=$(count_font_files "$font_dir")
  local pruned=$((before - after))
  log_success "Pruned $pruned files (kept $after)"
}

standardize_font_family() {
  local font_dir="$1"
  [[ ! -d "$font_dir" ]] && return 0

  local files_with_spaces
  files_with_spaces=$(find "$font_dir" -type f -name "* *" 2>/dev/null | wc -l | tr -d ' ')
  [[ $files_with_spaces -eq 0 ]] && return 0

  find "$font_dir" -type f -name "* *" 2>/dev/null | while read -r file; do
    local dir base new_name
    dir=$(dirname "$file")
    base=$(basename "$file")
    new_name="${base// /-}"
    mv "$file" "$dir/$new_name" 2>/dev/null || true
  done

  log_success "Standardized $files_with_spaces filenames"
}

install_font_files() {
  local source_dir="$1"
  local target_dir="$2"
  local platform="$3"

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

  if [[ $installed -gt 0 ]] && [[ $skipped -gt 0 ]]; then
    log_success "Installed $installed new fonts ($skipped already present)"
  elif [[ $installed -gt 0 ]]; then
    log_success "Installed $installed fonts"
  elif [[ $skipped -gt 0 ]]; then
    log_success "All $skipped fonts already installed"
  fi
}

refresh_font_cache() {
  local platform="$1"
  local target_dir="$2"

  case "$platform" in
    linux|arch)
      if command -v fc-cache &> /dev/null; then
        fc-cache -f "$target_dir" 2>/dev/null || true
      fi
      ;;
    macos|wsl)
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
