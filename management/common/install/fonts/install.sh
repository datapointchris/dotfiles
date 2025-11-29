#!/usr/bin/env bash
# Install fonts from ~/fonts to system font directory
# Platform-aware installation for macOS, Linux, and WSL

set -euo pipefail

# Source structured logging library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# ================================================================
# Configuration & Global Variables
# ================================================================

FONTS_SOURCE="${FONTS_SOURCE:-$HOME/fonts}"
INSTALL_FAMILY=""
FORCE=false
DRY_RUN=false

# Exclude list - fonts to never install
# These fonts are excluded because they are not liked/useful:
# - IosevkaTermSlab: Too dim/faint, looks like Iosevka Term but worse
EXCLUDED_FONTS=(
  "IosevkaTermSlab"
)

# Platform detection
PLATFORM=""
FONTS_TARGET=""

# ================================================================
# Usage & Help
# ================================================================

usage() {
  cat <<EOF
Install fonts from ~/fonts to system font directory

Usage: font-install [OPTIONS]

Options:
  -h, --help            Show this help message
  -f, --family FAMILY   Install only specified font family
  -n, --dry-run         Show what would be installed without installing
  --force               Overwrite existing fonts
  -s, --source DIR      Source directory (default: ~/fonts)

Examples:
  font-install                          # Install all fonts
  font-install -f jetbrains             # Install only JetBrains Mono
  font-install -n                       # Dry run to see what would be installed
  font-install --force                  # Reinstall/overwrite existing fonts

Platform-specific install locations:
  macOS:     ~/Library/Fonts/
  Linux:     ~/.local/share/fonts/
  WSL:       Manual install to Windows required

Available families:
  $(find "$FONTS_SOURCE" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | tr '\n' ' ' || echo "No fonts found in $FONTS_SOURCE")
EOF
}

# ================================================================
# Argument Parsing
# ================================================================

parse_args() {
  while [[ $# -gt 0 ]]; do
    case $1 in
      -h|--help)
        usage
        exit 0
        ;;
      -f|--family)
        INSTALL_FAMILY="$2"
        shift 2
        ;;
      -n|--dry-run)
        DRY_RUN=true
        shift
        ;;
      --force)
        FORCE=true
        shift
        ;;
      -s|--source)
        FONTS_SOURCE="$2"
        shift 2
        ;;
      *)
        print_error "Unknown option: $1"
        usage
        exit 1
        ;;
    esac
  done
}

# ================================================================
# Platform Detection
# ================================================================

detect_platform() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
    FONTS_TARGET="$HOME/Library/Fonts"
  elif [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    PLATFORM="wsl"
    FONTS_TARGET="/mnt/c/Windows/Fonts"
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"
    FONTS_TARGET="$HOME/.local/share/fonts"
  else
    print_error "Unsupported platform: $OSTYPE"
    exit 1
  fi
}

# ================================================================
# Helper Functions
# ================================================================

count_fonts() {
  local dir="$1"
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) 2>/dev/null | wc -l | tr -d ' '
}

# ================================================================
# Installation Functions
# ================================================================

install_family() {
  local family="$1"
  local source_dir="$FONTS_SOURCE/$family"

  if [[ ! -d "$source_dir" ]]; then
    print_error "Font family not found: $family"
    return 1
  fi

  local font_count=$(count_fonts "$source_dir")

  if [[ $font_count -eq 0 ]]; then
    print_warning "No fonts found in $family"
    return 0
  fi

  print_info "Installing $family ($font_count files)..."

  if [[ "$DRY_RUN" == "true" ]]; then
    print_info "[DRY RUN] Would install $font_count fonts from $family"
    return 0
  fi

  # Install based on platform
  case "$PLATFORM" in
    macos|linux)
      mkdir -p "$FONTS_TARGET"
      local installed=0
      local skipped=0
      while IFS= read -r -d '' font_file; do
        local filename=$(basename "$font_file")
        local target_file="$FONTS_TARGET/$filename"

        # Check if font is in exclusion list
        local excluded=false
        for excluded_pattern in "${EXCLUDED_FONTS[@]}"; do
          if [[ "$filename" =~ $excluded_pattern ]]; then
            excluded=true
            break
          fi
        done

        if [[ "$excluded" == "true" ]]; then
          skipped=$((skipped + 1))
          continue
        fi

        if [[ -f "$target_file" ]] && [[ "$FORCE" != "true" ]]; then
          skipped=$((skipped + 1))
          continue
        fi

        cp "$font_file" "$FONTS_TARGET/"
        installed=$((installed + 1))
      done < <(find "$source_dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) -print0)

      if [[ $installed -gt 0 ]] && [[ $skipped -gt 0 ]]; then
        print_success "Installed $installed new fonts from $family ($skipped already present)"
      elif [[ $installed -gt 0 ]]; then
        print_success "Installed $installed fonts from $family"
      else
        print_success "All $skipped fonts from $family already installed"
      fi
      ;;
    wsl)
      print_info "WSL detected - attempting to install to Windows..."

      # Try to copy to Windows Fonts directory
      if [[ -d "$FONTS_TARGET" ]]; then
        local installed=0
        local skipped=0
        local failed=0

        while IFS= read -r -d '' font_file; do
          local filename=$(basename "$font_file")
          local target_file="$FONTS_TARGET/$filename"

          if [[ -f "$target_file" ]] && [[ "$FORCE" != "true" ]]; then
            skipped=$((skipped + 1))
            continue
          fi

          if cp "$font_file" "$FONTS_TARGET/" 2>/dev/null; then
            installed=$((installed + 1))
          else
            failed=$((failed + 1))
          fi
        done < <(find "$source_dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) -print0)

        if [[ $installed -gt 0 ]] && [[ $skipped -gt 0 ]]; then
          print_success "Installed $installed new fonts to Windows ($skipped already present)"
        elif [[ $installed -gt 0 ]]; then
          print_success "Installed $installed fonts to Windows"
        elif [[ $skipped -gt 0 ]]; then
          print_success "All $skipped fonts already installed to Windows"
        fi

        if [[ $failed -gt 0 ]]; then
          print_warning "Failed to install $failed fonts (permission denied)"
          print_info "Manually install from: $source_dir"
          print_info "To: C:\\Windows\\Fonts (right-click → Install)"
        fi
      else
        print_warning "Windows Fonts directory not accessible: $FONTS_TARGET"
        print_info "Manually install fonts from: $source_dir"
        print_info "To: C:\\Windows\\Fonts (right-click → Install)"
      fi
      ;;
  esac
}

install_all_families() {
  local families=()

  while IFS= read -r -d '' dir; do
    families+=("$(basename "$dir")")
  done < <(find "$FONTS_SOURCE" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

  if [[ ${#families[@]} -eq 0 ]]; then
    print_error "No font families found in $FONTS_SOURCE"
    return 1
  fi

  for family in "${families[@]}"; do
    install_family "$family"
  done
}

refresh_font_cache() {
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi

  case "$PLATFORM" in
    linux)
      if command -v fc-cache &> /dev/null; then
        print_info "Refreshing font cache..."
        fc-cache -f "$FONTS_TARGET" 2>/dev/null || true
        print_success "Font cache refreshed"
      fi
      ;;
    macos)
      print_info "macOS will automatically refresh font cache"
      ;;
    wsl)
      print_info "Font cache refresh not applicable for WSL"
      ;;
  esac
}

# ================================================================
# Main Execution
# ================================================================

main() {
  parse_args "$@"

  # Detect platform
  detect_platform

  # Print header
  print_header "Font Installation" "cyan"
  echo ""

  # Verify source directory
  if [[ ! -d "$FONTS_SOURCE" ]]; then
    print_error "Source directory not found: $FONTS_SOURCE"
    echo "Run 'font-download' to download fonts first"
    exit 1
  fi

  # Platform info
  print_info "Platform: $PLATFORM"
  print_info "Source: $FONTS_SOURCE"
  print_info "Target: $FONTS_TARGET"

  if [[ "$DRY_RUN" == "true" ]]; then
    print_warning "DRY RUN MODE - No files will be installed"
  fi

  if [[ "$FORCE" == "true" ]]; then
    print_warning "Force mode enabled - Will overwrite existing fonts"
  fi

  echo ""

  # Install fonts
  if [[ -n "$INSTALL_FAMILY" ]]; then
    print_header "Installing family: $INSTALL_FAMILY" "cyan"
    echo ""
    install_family "$INSTALL_FAMILY"
  else
    install_all_families
  fi

  echo ""

  # Refresh cache
  refresh_font_cache

  # Summary
  echo ""
  print_header_success "Font Installation Complete"

  if [[ "$DRY_RUN" != "true" ]]; then
    local total_fonts=$(count_fonts "$FONTS_TARGET")
    local total_families=$(find "$FONTS_SOURCE" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
    echo "  Families: $total_families"
    echo "  Files: $total_fonts"
    echo "  Location: $FONTS_TARGET"
  fi

  echo ""
}

main "$@"
