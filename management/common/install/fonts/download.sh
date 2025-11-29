#!/usr/bin/env bash
# Download all curated coding fonts
# Organizes fonts by family with separated download/prune/standardize phases

set -euo pipefail

# Source structured logging library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/structured-logging.sh"

# ================================================================
# Configuration & Global Variables
# ================================================================

FONTS_DIR="${FONTS_DIR:-$HOME/fonts}"
TEMP_DIR="/tmp/font-downloads-$$"
VERBOSE=false
DOWNLOAD_FAMILY=""

# Phase control flags
DOWNLOAD_ONLY=false
PRUNE_ONLY=false
STANDARDIZE_ONLY=false
DRY_RUN=false
SKIP_FILTER=false  # Legacy compatibility

# Progress tracking
TOTAL=23
CURRENT=0

# ================================================================
# Usage & Help
# ================================================================

usage() {
  cat <<EOF
Download and organize curated coding fonts

Usage: font-download [OPTIONS] [directory]

Arguments:
  directory              Target directory for fonts (default: ~/fonts)

Phase Control Options:
  --download-only        Download fonts only (no pruning or standardization)
  --prune-only           Prune existing fonts only (no downloading)
  --standardize-only     Standardize names only (no downloading)
  --dry-run              Show what would be pruned without deleting (use with --prune-only)

Standard Options:
  -h, --help             Show this help message
  -f, --family FAMILY    Process only specified font family
  -l, --list             List available font families
  -s, --skip-filter      Keep all variants (no pruning)
  -v, --verbose          Show detailed output

Examples:
  # Download all fonts (all phases)
  font-download

  # Download only (no pruning/standardization)
  font-download --download-only

  # Test pruning logic without deleting
  font-download --prune-only --dry-run

  # Prune downloaded fonts
  font-download --prune-only

  # Standardize font names
  font-download --standardize-only

  # Download single family
  font-download -f jetbrains --download-only

Workflow:
  1. Download: font-download --download-only
  2. Test prune: font-download --prune-only --dry-run
  3. Actually prune: font-download --prune-only
  4. Standardize: font-download --standardize-only

Available Families:
  jetbrains, cascadia, meslo, monaspace, iosevka, iosevka-base,
  sgr-iosevka, victor, firacode, firacodescript, nimbus, droid,
  commitmono, comicmono, seriousshanns, sourcecode, terminess,
  hack, 3270, robotomono, spacemono, intelone

Downloads 23 font families with pruning to essential coding variants:
  - Regular, Bold, Italic, BoldItalic only (when pruning enabled)
  - NerdFontMono spacing only (when pruning enabled)
  - ~70-80 files instead of 260+ (when pruning enabled)
EOF
}

list_families() {
  print_header "Available Font Families" "cyan"
  echo "  jetbrains       - JetBrains Mono Nerd Font"
  echo "  cascadia        - Cascadia Code Nerd Font"
  echo "  meslo           - Meslo Nerd Font"
  echo "  monaspace       - Monaspace Nerd Font (5 families)"
  echo "  iosevka         - Iosevka Nerd Font"
  echo "  iosevka-base    - Iosevka base (.ttc files)"
  echo "  sgr-iosevka     - SGr-Iosevka variants (4 families)"
  echo "  victor          - Victor Mono"
  echo "  firacode        - Fira Code"
  echo "  firacodescript  - FiraCodeiScript"
  echo "  nimbus          - Nimbus Mono"
  echo "  droid           - DroidSansMono Nerd Font"
  echo "  commitmono      - Commit Mono"
  echo "  comicmono       - Comic Mono"
  echo "  seriousshanns   - SeriousShanns Nerd Font"
  echo "  sourcecode      - Source Code Pro Nerd Font"
  echo "  terminess       - Terminess Nerd Font"
  echo "  hack            - Hack Nerd Font"
  echo "  3270            - 3270 Nerd Font"
  echo "  robotomono      - RobotoMono Nerd Font"
  echo "  spacemono       - SpaceMono Nerd Font"
  echo "  intelone        - Intel One Mono"
  echo ""
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
      -l|--list)
        list_families
        exit 0
        ;;
      -f|--family)
        DOWNLOAD_FAMILY="$2"
        shift 2
        ;;
      --download-only)
        DOWNLOAD_ONLY=true
        shift
        ;;
      --prune-only)
        PRUNE_ONLY=true
        shift
        ;;
      --standardize-only)
        STANDARDIZE_ONLY=true
        shift
        ;;
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      -s|--skip-filter)
        SKIP_FILTER=true
        shift
        ;;
      -v|--verbose)
        VERBOSE=true
        shift
        ;;
      -*)
        echo "Unknown option: $1"
        usage
        exit 1
        ;;
      *)
        FONTS_DIR="$1"
        shift
        ;;
    esac
  done
}

# ================================================================
# Helper Functions
# ================================================================

log_verbose() {
  if [[ "$VERBOSE" == "true" ]]; then
    echo "  $*"
  fi
}

download_progress() {
  CURRENT=$((CURRENT + 1))
  print_section "[$CURRENT/$TOTAL] $1" "blue"
}

count_files() {
  local dir="$1"
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) 2>/dev/null | wc -l | tr -d ' '
}

# ================================================================
# Phase 1: Download Functions (NO filtering or standardization)
# ================================================================

# Generic download helper for Nerd Fonts
# Downloads and extracts ONLY - no filtering or name standardization
download_nerd_font() {
  local name="$1"           # Display name
  local package="$2"        # Package name for download URL
  local dir_name="$3"       # Directory name in FONTS_DIR
  local extension="${4:-ttf}" # File extension (ttf or otf)

  download_progress "$name"

  mkdir -p "$FONTS_DIR/$dir_name"
  log_verbose "Downloading $package.tar.xz..."

  curl -fsSL "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${package}.tar.xz" -o "${package}.tar.xz"
  tar -xf "${package}.tar.xz"

  log_verbose "Extracting fonts to $FONTS_DIR/$dir_name..."
  find . -maxdepth 1 -name "*NerdFont*.$extension" -exec mv {} "$FONTS_DIR/$dir_name/" \; 2>/dev/null || true

  local downloaded=$(count_files "$FONTS_DIR/$dir_name")
  print_success "Downloaded $downloaded files"
}

download_jetbrains() {
  download_nerd_font "JetBrains Mono Nerd Font" "JetBrainsMono" "JetBrainsMono" "ttf"
}

download_cascadia() {
  download_nerd_font "Cascadia Code Nerd Font" "CascadiaCode" "CascadiaCode" "ttf"
}

download_meslo() {
  download_nerd_font "Meslo Nerd Font" "Meslo" "Meslo" "ttf"
}

download_monaspace() {
  download_nerd_font "Monaspace Nerd Font (5 families)" "Monaspace" "Monaspace" "otf"
}

download_iosevka() {
  download_nerd_font "Iosevka Nerd Font" "Iosevka" "Iosevka-Nerd-Font" "ttf"
}

download_sgr_iosevka() {
  download_progress "SGr-Iosevka variants (4 families)"

  log_verbose "Fetching latest Iosevka release info..."
  local release_json=$(curl -fsSL https://api.github.com/repos/be5invis/Iosevka/releases/latest)

  # Extract download URLs for SGr variants
  local sgr_iosevka_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*SuperTTC-SGr-Iosevka-[0-9.]*\.zip"' | grep -v "Term\|Slab" | head -1 | sed 's/.*": *"//' | sed 's/"$//')
  local sgr_term_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*SuperTTC-SGr-IosevkaTerm-[0-9.]*\.zip"' | grep -v "Slab" | head -1 | sed 's/.*": *"//' | sed 's/"$//')
  local sgr_slab_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*SuperTTC-SGr-IosevkaSlab-[0-9.]*\.zip"' | grep -v "Term" | head -1 | sed 's/.*": *"//' | sed 's/"$//')
  local sgr_termslab_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*SuperTTC-SGr-IosevkaTermSlab-[0-9.]*\.zip"' | head -1 | sed 's/.*": *"//' | sed 's/"$//')

  # Download and extract each variant
  log_verbose "Downloading SGr-Iosevka..."
  mkdir -p "$FONTS_DIR/SGr-Iosevka"
  curl -fsSL "$sgr_iosevka_url" -o SGr-Iosevka.zip
  unzip -qo SGr-Iosevka.zip
  find . -maxdepth 1 -name "*.ttc" -exec mv {} "$FONTS_DIR/SGr-Iosevka/" \; 2>/dev/null || true

  log_verbose "Downloading SGr-IosevkaTerm..."
  mkdir -p "$FONTS_DIR/SGr-IosevkaTerm"
  curl -fsSL "$sgr_term_url" -o SGr-IosevkaTerm.zip
  unzip -qo SGr-IosevkaTerm.zip
  find . -maxdepth 1 -name "*.ttc" -exec mv {} "$FONTS_DIR/SGr-IosevkaTerm/" \; 2>/dev/null || true

  log_verbose "Downloading SGr-IosevkaSlab..."
  mkdir -p "$FONTS_DIR/SGr-IosevkaSlab"
  curl -fsSL "$sgr_slab_url" -o SGr-IosevkaSlab.zip
  unzip -qo SGr-IosevkaSlab.zip
  find . -maxdepth 1 -name "*.ttc" -exec mv {} "$FONTS_DIR/SGr-IosevkaSlab/" \; 2>/dev/null || true

  log_verbose "Downloading SGr-IosevkaTermSlab..."
  mkdir -p "$FONTS_DIR/SGr-IosevkaTermSlab"
  curl -fsSL "$sgr_termslab_url" -o SGr-IosevkaTermSlab.zip
  unzip -qo SGr-IosevkaTermSlab.zip
  find . -maxdepth 1 -name "*.ttc" -exec mv {} "$FONTS_DIR/SGr-IosevkaTermSlab/" \; 2>/dev/null || true

  print_success "Downloaded 4 variants (TTC collections contain all weights)"
}

download_victor() {
  download_progress "Victor Mono"

  mkdir -p "$FONTS_DIR/VictorMono"

  log_verbose "Fetching Victor Mono version..."
  local victor_version=$(curl -s https://api.github.com/repos/rubjo/victor-mono/releases/latest | grep '"tag_name"' | cut -d '"' -f 4)

  log_verbose "Downloading Victor Mono source ($victor_version)..."
  curl -fsSL "https://api.github.com/repos/rubjo/victor-mono/zipball/$victor_version" -o victor-source.zip
  unzip -qo victor-source.zip

  local victor_dir=$(find . -maxdepth 1 -type d -name "rubjo-victor-mono-*" | head -1)

  if [[ -f "$victor_dir/public/VictorMonoAll.zip" ]]; then
    log_verbose "Extracting VictorMonoAll.zip from source..."
    unzip -qo "$victor_dir/public/VictorMonoAll.zip"
    find . -type f -name "*.ttf" -path "*/TTF/*" -exec mv {} "$FONTS_DIR/VictorMono/" \; 2>/dev/null || true

    local downloaded=$(count_files "$FONTS_DIR/VictorMono")
    print_success "Downloaded $downloaded files"
  else
    print_warning "VictorMonoAll.zip not found in source, skipping"
  fi
}

download_firacodescript() {
  download_progress "FiraCodeiScript"

  mkdir -p "$FONTS_DIR/FiraCodeiScript"

  log_verbose "Downloading FiraCodeiScript Regular..."
  curl -fsSL https://github.com/kencrocken/FiraCodeiScript/raw/master/FiraCodeiScript-Regular.ttf -o "$FONTS_DIR/FiraCodeiScript/FiraCodeiScript-Regular.ttf" 2>/dev/null || true

  log_verbose "Downloading FiraCodeiScript Bold..."
  curl -fsSL https://github.com/kencrocken/FiraCodeiScript/raw/master/FiraCodeiScript-Bold.ttf -o "$FONTS_DIR/FiraCodeiScript/FiraCodeiScript-Bold.ttf" 2>/dev/null || true

  log_verbose "Downloading FiraCodeiScript Italic..."
  curl -fsSL https://github.com/kencrocken/FiraCodeiScript/raw/master/FiraCodeiScript-Italic.ttf -o "$FONTS_DIR/FiraCodeiScript/FiraCodeiScript-Italic.ttf" 2>/dev/null || true

  local downloaded=$(count_files "$FONTS_DIR/FiraCodeiScript")
  print_success "Downloaded $downloaded files"
}

download_nimbus() {
  download_progress "Nimbus Mono"

  mkdir -p "$FONTS_DIR/NimbusMono"

  log_verbose "Downloading Nimbus Mono from Font Squirrel..."
  curl -fsSL https://www.fontsquirrel.com/fonts/download/nimbus-mono -o NimbusMono.zip
  unzip -qo NimbusMono.zip -d nimbus
  find nimbus -name "*.otf" -exec mv {} "$FONTS_DIR/NimbusMono/" \; 2>/dev/null || true

  local downloaded=$(count_files "$FONTS_DIR/NimbusMono")
  print_success "Downloaded $downloaded files"
}

download_droid() {
  download_nerd_font "DroidSansMono Nerd Font" "DroidSansMono" "DroidSansM-Nerd-Font" "otf"
}

download_commitmono() {
  download_progress "Commit Mono"

  mkdir -p "$FONTS_DIR/CommitMono"

  log_verbose "Fetching CommitMono latest release..."
  local release_json=$(curl -fsSL https://api.github.com/repos/eigilnikolajsen/commit-mono/releases/latest)
  local commit_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*\.zip"' | head -1 | sed 's/.*": *"//' | sed 's/"$//')

  if [[ -n "$commit_url" ]]; then
    log_verbose "Downloading CommitMono from $commit_url..."
    curl -fsSL "$commit_url" -o CommitMono.zip
    unzip -qo CommitMono.zip
    find . -type f -name "*.otf" -exec mv {} "$FONTS_DIR/CommitMono/" \; 2>/dev/null || true

    local downloaded=$(count_files "$FONTS_DIR/CommitMono")
    print_success "Downloaded $downloaded files"
  else
    print_warning "CommitMono download URL not found, skipping"
  fi
}

download_firacode() {
  download_progress "Fira Code"

  mkdir -p "$FONTS_DIR/FiraCode"

  log_verbose "Downloading Fira Code from latest release..."
  curl -fsSL https://github.com/tonsky/FiraCode/releases/download/6.2/Fira_Code_v6.2.zip -o FiraCode.zip
  unzip -qo FiraCode.zip
  mv ttf/*.ttf "$FONTS_DIR/FiraCode/" 2>/dev/null || true

  local downloaded=$(count_files "$FONTS_DIR/FiraCode")
  print_success "Downloaded $downloaded files"
}

download_iosevka_base() {
  download_progress "Iosevka base (.ttc files)"

  mkdir -p "$FONTS_DIR/Iosevka"

  log_verbose "Fetching Iosevka latest release..."
  local release_json=$(curl -fsSL https://api.github.com/repos/be5invis/Iosevka/releases/latest)
  local iosevka_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*PkgTTC-Iosevka-[0-9.]*\.zip"' | head -1 | sed 's/.*": *"//' | sed 's/"$//')

  if [[ -n "$iosevka_url" ]]; then
    log_verbose "Downloading Iosevka base from $iosevka_url..."
    curl -fsSL "$iosevka_url" -o Iosevka-base.zip
    unzip -qo Iosevka-base.zip
    find . -maxdepth 1 -name "*.ttc" -exec mv {} "$FONTS_DIR/Iosevka/" \; 2>/dev/null || true

    local downloaded=$(count_files "$FONTS_DIR/Iosevka")
    print_success "Downloaded $downloaded TTC files"
  else
    print_warning "Iosevka base download URL not found, skipping"
  fi
}

download_seriousshanns() {
  download_nerd_font "SeriousShanns Nerd Font" "ComicShannsMono" "SeriousShanns-Nerd-Font" "otf"
}

download_sourcecode() {
  download_nerd_font "Source Code Pro Nerd Font" "SourceCodePro" "SourceCodePro" "ttf"
}

download_terminess() {
  download_nerd_font "Terminess Nerd Font" "Terminus" "Terminess-Nerd-Font" "ttf"
}

download_comicmono() {
  download_progress "Comic Mono"

  mkdir -p "$FONTS_DIR/ComicMono"

  log_verbose "Downloading Comic Mono Regular..."
  curl -fsSL https://dtinth.github.io/comic-mono-font/ComicMono.ttf -o "$FONTS_DIR/ComicMono/ComicMono.ttf"

  log_verbose "Downloading Comic Mono Bold..."
  curl -fsSL https://dtinth.github.io/comic-mono-font/ComicMono-Bold.ttf -o "$FONTS_DIR/ComicMono/ComicMono-Bold.ttf"

  local downloaded=$(count_files "$FONTS_DIR/ComicMono")
  print_success "Downloaded $downloaded files"
}

download_hack() {
  download_nerd_font "Hack Nerd Font" "Hack" "Hack" "ttf"
}

download_3270() {
  download_nerd_font "3270 Nerd Font" "3270" "3270" "ttf"
}

download_robotomono() {
  download_nerd_font "RobotoMono Nerd Font" "RobotoMono" "RobotoMono" "ttf"
}

download_spacemono() {
  download_nerd_font "SpaceMono Nerd Font" "SpaceMono" "SpaceMono" "ttf"
}

download_intelone() {
  download_progress "Intel One Mono"

  mkdir -p "$FONTS_DIR/IntelOneMono"

  log_verbose "Fetching Intel One Mono latest release..."
  local release_json=$(curl -fsSL https://api.github.com/repos/intel/intel-one-mono/releases/latest)
  local intel_url=$(echo "$release_json" | grep -o '"browser_download_url": *"[^"]*ttf\.zip"' | head -1 | sed 's/.*": *"//' | sed 's/"$//')

  if [[ -n "$intel_url" ]]; then
    log_verbose "Downloading Intel One Mono from $intel_url..."
    curl -fsSL "$intel_url" -o IntelOneMono.zip
    unzip -qo IntelOneMono.zip
    find ./ttf -type f -name "*.ttf" -exec mv {} "$FONTS_DIR/IntelOneMono/" \; 2>/dev/null || true

    local downloaded=$(count_files "$FONTS_DIR/IntelOneMono")
    print_success "Downloaded $downloaded files"
  else
    print_warning "Intel One Mono download URL not found, skipping"
  fi
}

# ================================================================
# Phase 2: Pruning Functions (Filter unwanted variants)
# ================================================================

# Prune a single font family directory
# Removes unwanted weight and spacing variants
prune_font_family() {
  local font_dir="$1"
  local family_name=$(basename "$font_dir")

  if [[ "$SKIP_FILTER" == "true" ]]; then
    log_verbose "Skipping prune (--skip-filter enabled)"
    return 0
  fi

  if [[ ! -d "$font_dir" ]]; then
    print_warning "Font directory not found: $font_dir"
    return 1
  fi

  local before_count=$(count_files "$font_dir")

  if [[ $before_count -eq 0 ]]; then
    log_verbose "No files to prune in $family_name"
    return 0
  fi

  print_section "Pruning $family_name" "blue"
  log_verbose "Files before pruning: $before_count"

  # Step 1: Remove unwanted weight variants
  log_verbose "Removing unwanted weights (ExtraLight, Light, Thin, Medium, SemiBold, ExtraBold, Black, Retina)..."

  if [[ "$DRY_RUN" == "true" ]]; then
    local weight_files=$(find "$font_dir" -type f \( \
      -iname "*ExtraLight*" -o \
      -iname "*Light*" -o \
      -iname "*Thin*" -o \
      -iname "*Medium*" -o \
      -iname "*SemiBold*" -o \
      -iname "*ExtraBold*" -o \
      -iname "*Black*" -o \
      -iname "*Retina*" \
    \) 2>/dev/null)

    if [[ -n "$weight_files" ]]; then
      echo "  Would delete weight variants:"
      echo "$weight_files" | while read -r file; do
        echo "    - $(basename "$file")"
      done
    fi
  else
    find "$font_dir" -type f \( \
      -iname "*ExtraLight*" -o \
      -iname "*Light*" -o \
      -iname "*Thin*" -o \
      -iname "*Medium*" -o \
      -iname "*SemiBold*" -o \
      -iname "*ExtraBold*" -o \
      -iname "*Black*" -o \
      -iname "*Retina*" \
    \) -delete 2>/dev/null || true
  fi

  # Step 2: Remove Propo spacing variants (keep both Mono and default)
  log_verbose "Removing Propo spacing variants (keeping both Mono and default)..."

  if [[ "$DRY_RUN" == "true" ]]; then
    local spacing_files=$(find "$font_dir" -type f -name "*NerdFontPropo-*" 2>/dev/null)

    if [[ -n "$spacing_files" ]]; then
      echo "  Would delete Propo spacing variants:"
      echo "$spacing_files" | while read -r file; do
        echo "    - $(basename "$file")"
      done
    fi
  else
    find "$font_dir" -type f -name "*NerdFontPropo-*" -delete 2>/dev/null || true
  fi

  local after_count
  local pruned
  if [[ "$DRY_RUN" == "true" ]]; then
    # Count files that will REMAIN (not match any deletion criteria)
    # Files to keep: Regular, Bold, Italic, BoldItalic weights, excluding unwanted weights and Propo variants
    after_count=$(find "$font_dir" -type f \( \
      -name "*Regular.ttf" -o -name "*Regular.otf" -o \
      -name "*Bold.ttf" -o -name "*Bold.otf" -o \
      -name "*Italic.ttf" -o -name "*Italic.otf" -o \
      -name "*BoldItalic.ttf" -o -name "*BoldItalic.otf" \
    \) ! \( \
      -iname "*ExtraLight*" -o -iname "*Light*" -o -iname "*Thin*" -o \
      -iname "*Medium*" -o -iname "*SemiBold*" -o -iname "*ExtraBold*" -o \
      -iname "*Black*" -o -iname "*Retina*" -o -name "*NerdFontPropo-*" \
    \) 2>/dev/null | wc -l | tr -d ' ')
    pruned=$((before_count - after_count))
  else
    after_count=$(count_files "$font_dir")
    pruned=$((before_count - after_count))
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    print_info "[DRY RUN] Would prune $pruned files (keeping $after_count)"
  else
    print_success "Pruned $pruned files (kept $after_count essential variants)"
  fi
}

# Prune all font families in FONTS_DIR
prune_all_fonts() {
  if [[ ! -d "$FONTS_DIR" ]]; then
    print_error "Fonts directory not found: $FONTS_DIR"
    return 1
  fi

  print_header "Pruning Font Families" "cyan"
  echo ""

  local families=()
  while IFS= read -r -d '' dir; do
    families+=("$(basename "$dir")")
  done < <(find "$FONTS_DIR" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

  if [[ ${#families[@]} -eq 0 ]]; then
    print_warning "No font families found in $FONTS_DIR"
    return 0
  fi

  for family in "${families[@]}"; do
    prune_font_family "$FONTS_DIR/$family"
  done

  echo ""
  print_header_success "Pruning Complete"
}

# ================================================================
# Phase 3: Standardization Functions (Remove spaces from names)
# ================================================================

# Standardize font names for a single family
# Converts spaces to hyphens for ImageMagick compatibility
standardize_font_family() {
  local font_dir="$1"
  local family_name=$(basename "$font_dir")

  if [[ ! -d "$font_dir" ]]; then
    print_warning "Font directory not found: $font_dir"
    return 1
  fi

  local files_with_spaces=$(find "$font_dir" -type f -name "* *" 2>/dev/null | wc -l | tr -d ' ')

  if [[ $files_with_spaces -eq 0 ]]; then
    log_verbose "No files with spaces in $family_name"
    return 0
  fi

  print_section "Standardizing $family_name" "blue"
  log_verbose "Files with spaces: $files_with_spaces"

  if [[ "$DRY_RUN" == "true" ]]; then
    find "$font_dir" -type f -name "* *" 2>/dev/null | while read -r file; do
      local base=$(basename "$file")
      local new_name="${base// /-}"
      echo "  Would rename: $base → $new_name"
    done
  else
    find "$font_dir" -type f -name "* *" 2>/dev/null | while read -r file; do
      local dir=$(dirname "$file")
      local base=$(basename "$file")
      local new_name="${base// /-}"
      mv "$file" "$dir/$new_name" 2>/dev/null || true
    done
    print_success "Standardized $files_with_spaces filenames"
  fi
}

# Standardize all font families in FONTS_DIR
standardize_all_fonts() {
  if [[ ! -d "$FONTS_DIR" ]]; then
    print_error "Fonts directory not found: $FONTS_DIR"
    return 1
  fi

  print_header "Standardizing Font Names" "cyan"
  echo ""

  local families=()
  while IFS= read -r -d '' dir; do
    families+=("$(basename "$dir")")
  done < <(find "$FONTS_DIR" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

  if [[ ${#families[@]} -eq 0 ]]; then
    print_warning "No font families found in $FONTS_DIR"
    return 0
  fi

  for family in "${families[@]}"; do
    standardize_font_family "$FONTS_DIR/$family"
  done

  echo ""
  print_header_success "Standardization Complete"
}

# ================================================================
# Main Download Orchestration
# ================================================================

# Map family name to directory name
get_family_dir() {
  local family="$1"
  case "$family" in
    jetbrains)      echo "JetBrainsMono" ;;
    cascadia)       echo "CascadiaCode" ;;
    meslo)          echo "Meslo" ;;
    monaspace)      echo "Monaspace" ;;
    iosevka)        echo "Iosevka-Nerd-Font" ;;
    iosevka-base)   echo "Iosevka" ;;
    sgr-iosevka)    echo "SGr-Iosevka" ;;
    victor)         echo "VictorMono" ;;
    firacode)       echo "FiraCode" ;;
    firacodescript) echo "FiraCodeiScript" ;;
    nimbus)         echo "NimbusMono" ;;
    droid)          echo "DroidSansM-Nerd-Font" ;;
    commitmono)     echo "CommitMono" ;;
    comicmono)      echo "ComicMono" ;;
    seriousshanns)  echo "SeriousShanns-Nerd-Font" ;;
    sourcecode)     echo "SourceCodePro" ;;
    terminess)      echo "Terminess-Nerd-Font" ;;
    hack)           echo "Hack" ;;
    3270)           echo "3270" ;;
    robotomono)     echo "RobotoMono" ;;
    spacemono)      echo "SpaceMono" ;;
    intelone)       echo "IntelOneMono" ;;
    *)              echo "$family" ;;
  esac
}

download_single_family() {
  local family="$1"

  case "$family" in
    jetbrains)      download_jetbrains ;;
    cascadia)       download_cascadia ;;
    meslo)          download_meslo ;;
    monaspace)      download_monaspace ;;
    iosevka)        download_iosevka ;;
    iosevka-base)   download_iosevka_base ;;
    sgr-iosevka)    download_sgr_iosevka ;;
    victor)         download_victor ;;
    firacode)       download_firacode ;;
    firacodescript) download_firacodescript ;;
    nimbus)         download_nimbus ;;
    droid)          download_droid ;;
    commitmono)     download_commitmono ;;
    comicmono)      download_comicmono ;;
    seriousshanns)  download_seriousshanns ;;
    sourcecode)     download_sourcecode ;;
    terminess)      download_terminess ;;
    hack)           download_hack ;;
    3270)           download_3270 ;;
    robotomono)     download_robotomono ;;
    spacemono)      download_spacemono ;;
    intelone)       download_intelone ;;
    *)
      print_error "Unknown font family: $family"
      echo "Run 'font-download --list' to see available families"
      exit 1
      ;;
  esac
}

download_all_families() {
  download_jetbrains
  download_cascadia
  download_meslo
  download_monaspace
  download_iosevka
  download_iosevka_base
  download_sgr_iosevka
  download_victor
  download_firacode
  download_firacodescript
  download_nimbus
  download_droid
  download_commitmono
  download_comicmono
  download_seriousshanns
  download_sourcecode
  download_terminess
  download_hack
  download_3270
  download_robotomono
  download_spacemono
  download_intelone
}

# ================================================================
# Main Execution
# ================================================================

main() {
  # Parse command line arguments
  parse_args "$@"

  # Validate phase combinations
  local phase_count=0
  [[ "$DOWNLOAD_ONLY" == "true" ]] && phase_count=$((phase_count + 1))
  [[ "$PRUNE_ONLY" == "true" ]] && phase_count=$((phase_count + 1))
  [[ "$STANDARDIZE_ONLY" == "true" ]] && phase_count=$((phase_count + 1))

  if [[ $phase_count -gt 1 ]]; then
    print_error "Cannot combine --download-only, --prune-only, and --standardize-only"
    exit 1
  fi

  if [[ "$DRY_RUN" == "true" ]] && [[ "$PRUNE_ONLY" != "true" ]] && [[ "$STANDARDIZE_ONLY" != "true" ]]; then
    print_error "--dry-run can only be used with --prune-only or --standardize-only"
    exit 1
  fi

  # Create directories
  mkdir -p "$FONTS_DIR"

  # ================================================================
  # PRUNE-ONLY MODE
  # ================================================================
  if [[ "$PRUNE_ONLY" == "true" ]]; then
    if [[ "$DRY_RUN" == "true" ]]; then
      print_header "Font Pruning (DRY RUN)" "cyan"
    else
      print_header "Font Pruning" "cyan"
    fi
    echo "Target directory: $FONTS_DIR"
    echo ""

    if [[ -n "$DOWNLOAD_FAMILY" ]]; then
      local family_dir=$(get_family_dir "$DOWNLOAD_FAMILY")
      prune_font_family "$FONTS_DIR/$family_dir"
    else
      prune_all_fonts
    fi

    echo ""
    local total=$(count_files "$FONTS_DIR")
    if [[ "$DRY_RUN" == "true" ]]; then
      echo "Current total: $total font files"
    else
      echo "Total after pruning: $total font files"
    fi
    echo ""
    return 0
  fi

  # ================================================================
  # STANDARDIZE-ONLY MODE
  # ================================================================
  if [[ "$STANDARDIZE_ONLY" == "true" ]]; then
    if [[ "$DRY_RUN" == "true" ]]; then
      print_header "Font Name Standardization (DRY RUN)" "cyan"
    else
      print_header "Font Name Standardization" "cyan"
    fi
    echo "Target directory: $FONTS_DIR"
    echo ""

    if [[ -n "$DOWNLOAD_FAMILY" ]]; then
      local family_dir=$(get_family_dir "$DOWNLOAD_FAMILY")
      standardize_font_family "$FONTS_DIR/$family_dir"
    else
      standardize_all_fonts
    fi

    echo ""
    return 0
  fi

  # ================================================================
  # DOWNLOAD MODE (with optional auto-prune/standardize)
  # ================================================================

  # Skip if fonts already exist (unless forcing)
  if [[ -d "$FONTS_DIR" ]] && [[ $(count_files "$FONTS_DIR") -gt 0 ]] && [[ "${FORCE_INSTALL:-false}" != "true" ]]; then
    local existing_count=$(count_files "$FONTS_DIR")
    local family_count=$(find "$FONTS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
    print_header "Fonts Already Downloaded" "cyan"
    echo "  Families: $family_count"
    echo "  Files: $existing_count"
    echo "  Location: $FONTS_DIR"
    echo ""
    echo "  Skipping download (set FORCE_INSTALL=true to re-download)"
    echo ""
    return 0
  fi

  mkdir -p "$TEMP_DIR"
  cd "$TEMP_DIR"

  # Print header
  if [[ -n "$DOWNLOAD_FAMILY" ]]; then
    print_header "Font Download: $DOWNLOAD_FAMILY" "cyan"
    TOTAL=1
  else
    print_header "Font Download (23 families)" "cyan"
  fi

  echo "Target directory: $FONTS_DIR"
  echo "Temporary directory: $TEMP_DIR"

  if [[ "$DOWNLOAD_ONLY" == "true" ]]; then
    echo "Mode: Download only (no pruning or standardization)"
  elif [[ "$SKIP_FILTER" == "true" ]]; then
    echo "Mode: Download all variants (no pruning)"
  else
    echo "Mode: Download + Prune + Standardize"
  fi
  echo ""

  # Download fonts
  if [[ -n "$DOWNLOAD_FAMILY" ]]; then
    download_single_family "$DOWNLOAD_FAMILY"
  else
    download_all_families
  fi

  # Cleanup temp directory
  cd ~
  rm -rf "$TEMP_DIR"

  # Post-download processing (unless --download-only)
  if [[ "$DOWNLOAD_ONLY" != "true" ]]; then
    echo ""

    # Prune unwanted variants
    if [[ "$SKIP_FILTER" != "true" ]]; then
      if [[ -n "$DOWNLOAD_FAMILY" ]]; then
        local family_dir=$(get_family_dir "$DOWNLOAD_FAMILY")
        prune_font_family "$FONTS_DIR/$family_dir"
      else
        prune_all_fonts
      fi
      echo ""
    fi

    # Standardize names
    if [[ -n "$DOWNLOAD_FAMILY" ]]; then
      local family_dir=$(get_family_dir "$DOWNLOAD_FAMILY")
      standardize_font_family "$FONTS_DIR/$family_dir"
    else
      standardize_all_fonts
    fi
  fi

  # Summary
  echo ""
  print_header_success "Font Download Complete"

  local font_count=$(count_files "$FONTS_DIR")
  local family_count=$(find "$FONTS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')

  echo "  Families: $family_count"
  echo "  Files: $font_count"
  echo "  Location: $FONTS_DIR"
  echo ""
}

# Run main function
main "$@"
