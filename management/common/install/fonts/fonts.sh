#!/usr/bin/env bash
# ================================================================
# Font Management - Download, Process, and Install Coding Fonts
# ================================================================
# Unified font management script combining download and installation
# Supports 22 curated font families with 4-phase workflow
# Part of dotfiles install.sh Phase 3
# ================================================================

set -euo pipefail

# ================================================================
# Library Sources
# ================================================================

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/lib/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

enable_error_traps

# ================================================================
# Configuration & Constants
# ================================================================

FONTS_DIR="${FONTS_DIR:-$HOME/fonts}"
TEMP_DIR="/tmp/font-downloads-$$"
VERBOSE=false
DOWNLOAD_FAMILY=""

# Phase control flags
DOWNLOAD_ONLY=false
PRUNE_ONLY=false
STANDARDIZE_ONLY=false
INSTALL_ONLY=false
SKIP_INSTALL=false
FULL=false
DRY_RUN=false
FORCE=false
SKIP_FILTER=false  # Legacy compatibility

# Progress tracking
TOTAL=22
CURRENT=0

# Exclude list - fonts to never install
# These fonts are excluded because they are not liked/useful:
# - IosevkaTermSlab: Too dim/faint, looks like Iosevka Term but worse
EXCLUDED_FONTS=(
  "IosevkaTermSlab"
)

# ================================================================
# Usage & Help
# ================================================================

usage() {
  cat <<EOF
Font Management - Download, process, and install coding fonts

Usage: bash management/common/install/fonts/fonts.sh [OPTIONS]

From dotfiles root:
  bash management/common/install/fonts/fonts.sh --full

Called automatically by install.sh (Phase 3):
  ./install.sh                    # Includes font download/install
  SKIP_FONTS=1 ./install.sh       # Skip fonts entirely

Phase Control Options:
  --download-only        Download fonts only (no pruning/standardization/install)
  --prune-only           Prune existing fonts only (no downloading/standardization/install)
  --standardize-only     Standardize names only (no downloading/pruning/install)
  --install-only         Install fonts only (no downloading/pruning/standardization)
  --skip-install         Download + Prune + Standardize (no install)
  --full                 All phases: Download + Prune + Standardize + Install (default)

Standard Options:
  -h, --help             Show this help message
  -f, --family FAMILY    Process only specified font family
  -l, --list             List available font families
  -n, --dry-run          Show what would be done without making changes (prune/standardize/install)
  -s, --skip-filter      Keep all variants (no pruning)
  -v, --verbose          Show detailed output
  --force                Overwrite existing fonts during install

Examples:
  # Full workflow (download + prune + standardize + install)
  bash management/common/install/fonts/fonts.sh --full

  # Download all fonts only (no processing)
  bash management/common/install/fonts/fonts.sh --download-only

  # Test pruning logic without deleting
  bash management/common/install/fonts/fonts.sh --prune-only --dry-run

  # Install only (fonts already downloaded)
  bash management/common/install/fonts/fonts.sh --install-only

  # Download and process, but don't install
  bash management/common/install/fonts/fonts.sh --skip-install

  # Single family workflow
  bash management/common/install/fonts/fonts.sh -f jetbrains --full

Platform-specific install locations:
  macOS:     ~/Library/Fonts/
  Linux:     ~/.local/share/fonts/
  WSL:       /mnt/c/Windows/Fonts/

Available Families (22 total):
  jetbrains, cascadia, meslo, monaspace, iosevka, iosevka-base,
  sgr-iosevka, victor, firacode, firacodescript, droid,
  commitmono, comicmono, seriousshanns, sourcecode, terminess,
  hack, 3270, robotomono, spacemono, intelone

Workflow Phases:
  1. Download: Fetch fonts from GitHub/sources to ~/fonts
  2. Prune: Remove unwanted weight/spacing variants (Regular, Bold, Italic, BoldItalic only)
  3. Standardize: Remove spaces from filenames for ImageMagick compatibility
  4. Install: Copy fonts to system font directory
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
  local has_phase_mode=false

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
        has_phase_mode=true
        shift
        ;;
      --prune-only)
        PRUNE_ONLY=true
        has_phase_mode=true
        shift
        ;;
      --standardize-only)
        STANDARDIZE_ONLY=true
        has_phase_mode=true
        shift
        ;;
      --install-only)
        INSTALL_ONLY=true
        has_phase_mode=true
        shift
        ;;
      --skip-install)
        SKIP_INSTALL=true
        has_phase_mode=true
        shift
        ;;
      --full)
        FULL=true
        has_phase_mode=true
        shift
        ;;
      -n|--dry-run)
        DRY_RUN=true
        shift
        ;;
      --force)
        FORCE=true
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
        log_error "Unknown option: $1"
        usage
        exit 1
        ;;
      *)
        FONTS_DIR="$1"
        shift
        ;;
    esac
  done

  # Default to --full if no phase mode specified
  if [[ "$has_phase_mode" == "false" ]]; then
    FULL=true
  fi
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
  local name="$1"
  CURRENT=$((CURRENT + 1))
  print_section "[$CURRENT/$TOTAL] $name" "blue"
}

count_font_files() {
  local dir="$1"
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) 2>/dev/null | wc -l | tr -d ' '
}

find_font_files() {
  local dir="$1"
  shift
  find "$dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) "$@"
}

get_font_target_dir() {
  local platform="$1"
  case "$platform" in
    macos) echo "$HOME/Library/Fonts" ;;
    wsl)   echo "/mnt/c/Windows/Fonts" ;;
    linux|arch) echo "$HOME/.local/share/fonts" ;;
    *)     echo "" ;;
  esac
}

get_family_dir_name() {
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

fetch_github_release_asset() {
  local repo="$1"
  local pattern="$2"
  local release_json

  release_json=$(curl -fsSL "https://api.github.com/repos/$repo/releases/latest")
  echo "$release_json" | grep -o "\"browser_download_url\": *\"[^\"]*$pattern\"" | head -1 | sed 's/.*": *"//' | sed 's/"$//'
}

# ================================================================
# Phase 1: Download Functions
# ================================================================

# Generic Nerd Fonts
download_nerd_font() {
  local name="$1"
  local package="$2"
  local dir_name="$3"
  local extension="${4:-ttf}"

  download_progress "$name"

  mkdir -p "$FONTS_DIR/$dir_name"
  log_verbose "Downloading $package.tar.xz..."

  curl -fsSL "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${package}.tar.xz" -o "${package}.tar.xz"
  tar -xf "${package}.tar.xz"

  log_verbose "Extracting fonts to $FONTS_DIR/$dir_name..."
  find . -maxdepth 1 -name "*NerdFont*.$extension" -exec mv {} "$FONTS_DIR/$dir_name/" \; 2>/dev/null || true

  local downloaded
  downloaded=$(count_font_files "$FONTS_DIR/$dir_name")
  log_success "Downloaded $downloaded files"
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

download_droid() {
  download_nerd_font "DroidSansMono Nerd Font" "DroidSansMono" "DroidSansM-Nerd-Font" "otf"
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

# Complex Downloads

download_sgr_iosevka() {
  download_progress "SGr-Iosevka variants (4 families)"

  log_verbose "Fetching latest Iosevka release info..."
  local release_json
  release_json=$(curl -fsSL https://api.github.com/repos/be5invis/Iosevka/releases/latest)

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

  log_success "Downloaded 4 variants (TTC collections contain all weights)"
}

download_victor() {
  download_progress "Victor Mono"

  mkdir -p "$FONTS_DIR/VictorMono"

  log_verbose "Fetching Victor Mono version..."
  local victor_version
  victor_version=$(curl -s https://api.github.com/repos/rubjo/victor-mono/releases/latest | grep '"tag_name"' | cut -d '"' -f 4)

  log_verbose "Downloading Victor Mono source ($victor_version)..."
  curl -fsSL "https://api.github.com/repos/rubjo/victor-mono/zipball/$victor_version" -o victor-source.zip
  unzip -qo victor-source.zip

  local victor_dir
  victor_dir=$(find . -maxdepth 1 -type d -name "rubjo-victor-mono-*" | head -1)

  if [[ -f "$victor_dir/public/VictorMonoAll.zip" ]]; then
    log_verbose "Extracting VictorMonoAll.zip from source..."
    unzip -qo "$victor_dir/public/VictorMonoAll.zip"
    find . -type f -name "*.ttf" -path "*/TTF/*" -exec mv {} "$FONTS_DIR/VictorMono/" \; 2>/dev/null || true

    local downloaded
    downloaded=$(count_font_files "$FONTS_DIR/VictorMono")
    log_success "Downloaded $downloaded files"
  else
    log_warning "VictorMonoAll.zip not found in source, skipping"
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

  local downloaded
  downloaded=$(count_font_files "$FONTS_DIR/FiraCodeiScript")
  log_success "Downloaded $downloaded files"
}

download_commitmono() {
  download_progress "Commit Mono"

  mkdir -p "$FONTS_DIR/CommitMono"

  log_verbose "Fetching CommitMono latest release..."
  local commit_url
  commit_url=$(fetch_github_release_asset "eigilnikolajsen/commit-mono" "\.zip")

  if [[ -n "$commit_url" ]]; then
    log_verbose "Downloading CommitMono from $commit_url..."
    curl -fsSL "$commit_url" -o CommitMono.zip
    unzip -qo CommitMono.zip
    find . -type f -name "*.otf" -exec mv {} "$FONTS_DIR/CommitMono/" \; 2>/dev/null || true

    local downloaded
    downloaded=$(count_font_files "$FONTS_DIR/CommitMono")
    log_success "Downloaded $downloaded files"
  else
    log_warning "CommitMono download URL not found, skipping"
  fi
}

download_firacode() {
  download_progress "Fira Code"

  mkdir -p "$FONTS_DIR/FiraCode"

  log_verbose "Downloading Fira Code from latest release..."
  curl -fsSL https://github.com/tonsky/FiraCode/releases/download/6.2/Fira_Code_v6.2.zip -o FiraCode.zip
  unzip -qo FiraCode.zip
  mv ttf/*.ttf "$FONTS_DIR/FiraCode/" 2>/dev/null || true

  local downloaded
  downloaded=$(count_font_files "$FONTS_DIR/FiraCode")
  log_success "Downloaded $downloaded files"
}

download_iosevka_base() {
  download_progress "Iosevka base (.ttc files)"

  mkdir -p "$FONTS_DIR/Iosevka"

  log_verbose "Fetching Iosevka latest release..."
  local iosevka_url
  iosevka_url=$(fetch_github_release_asset "be5invis/Iosevka" "PkgTTC-Iosevka-[0-9.]*\.zip")

  if [[ -n "$iosevka_url" ]]; then
    log_verbose "Downloading Iosevka base from $iosevka_url..."
    curl -fsSL "$iosevka_url" -o Iosevka-base.zip
    unzip -qo Iosevka-base.zip
    find . -maxdepth 1 -name "*.ttc" -exec mv {} "$FONTS_DIR/Iosevka/" \; 2>/dev/null || true

    local downloaded
    downloaded=$(count_font_files "$FONTS_DIR/Iosevka")
    log_success "Downloaded $downloaded TTC files"
  else
    log_warning "Iosevka base download URL not found, skipping"
  fi
}

download_comicmono() {
  download_progress "Comic Mono"

  mkdir -p "$FONTS_DIR/ComicMono"

  log_verbose "Downloading Comic Mono Regular..."
  curl -fsSL https://dtinth.github.io/comic-mono-font/ComicMono.ttf -o "$FONTS_DIR/ComicMono/ComicMono.ttf"

  log_verbose "Downloading Comic Mono Bold..."
  curl -fsSL https://dtinth.github.io/comic-mono-font/ComicMono-Bold.ttf -o "$FONTS_DIR/ComicMono/ComicMono-Bold.ttf"

  local downloaded
  downloaded=$(count_font_files "$FONTS_DIR/ComicMono")
  log_success "Downloaded $downloaded files"
}

download_intelone() {
  download_progress "Intel One Mono"

  mkdir -p "$FONTS_DIR/IntelOneMono"

  log_verbose "Fetching Intel One Mono latest release..."
  local intel_url
  intel_url=$(fetch_github_release_asset "intel/intel-one-mono" "ttf\.zip")

  if [[ -n "$intel_url" ]]; then
    log_verbose "Downloading Intel One Mono from $intel_url..."
    curl -fsSL "$intel_url" -o IntelOneMono.zip
    unzip -qo IntelOneMono.zip
    find ./ttf -type f -name "*.ttf" -exec mv {} "$FONTS_DIR/IntelOneMono/" \; 2>/dev/null || true

    local downloaded
    downloaded=$(count_font_files "$FONTS_DIR/IntelOneMono")
    log_success "Downloaded $downloaded files"
  else
    log_warning "Intel One Mono download URL not found, skipping"
  fi
}

# ================================================================
# Phase 2: Pruning Functions
# ================================================================

prune_font_family() {
  local font_dir="$1"
  local family_name
  family_name=$(basename "$font_dir")

  if [[ "$SKIP_FILTER" == "true" ]]; then
    log_verbose "Skipping prune (--skip-filter enabled)"
    return 0
  fi

  if [[ ! -d "$font_dir" ]]; then
    log_warning "Font directory not found: $font_dir"
    return 1
  fi

  local before_count
  before_count=$(count_font_files "$font_dir")

  if [[ $before_count -eq 0 ]]; then
    log_verbose "No files to prune in $family_name"
    return 0
  fi

  print_section "Pruning $family_name" "blue"
  log_verbose "Files before pruning: $before_count"

  # Step 1: Remove unwanted weight variants
  log_verbose "Removing unwanted weights (ExtraLight, Light, Thin, Medium, SemiBold, ExtraBold, Black, Retina)..."

  if [[ "$DRY_RUN" == "true" ]]; then
    local weight_files
    weight_files=$(find "$font_dir" -type f \( \
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
    local spacing_files
    spacing_files=$(find "$font_dir" -type f -name "*NerdFontPropo-*" 2>/dev/null)

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
    after_count=$(count_font_files "$font_dir")
    pruned=$((before_count - after_count))
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    log_info "[DRY RUN] Would prune $pruned files (keeping $after_count)"
  else
    log_success "Pruned $pruned files (kept $after_count essential variants)"
  fi
}

prune_all_fonts() {
  if [[ ! -d "$FONTS_DIR" ]]; then
    log_error "Fonts directory not found: $FONTS_DIR"
    return 1
  fi

  print_header "Pruning Font Families" "cyan"
  echo ""

  local families=()
  while IFS= read -r -d '' dir; do
    families+=("$(basename "$dir")")
  done < <(find "$FONTS_DIR" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

  if [[ ${#families[@]} -eq 0 ]]; then
    log_warning "No font families found in $FONTS_DIR"
    return 0
  fi

  for family in "${families[@]}"; do
    prune_font_family "$FONTS_DIR/$family"
  done

  echo ""
  print_header_success "Pruning Complete"
}

# ================================================================
# Phase 3: Standardization Functions
# ================================================================

standardize_font_family() {
  local font_dir="$1"
  local family_name
  family_name=$(basename "$font_dir")

  if [[ ! -d "$font_dir" ]]; then
    log_warning "Font directory not found: $font_dir"
    return 1
  fi

  local files_with_spaces
  files_with_spaces=$(find "$font_dir" -type f -name "* *" 2>/dev/null | wc -l | tr -d ' ')

  if [[ $files_with_spaces -eq 0 ]]; then
    log_verbose "No files with spaces in $family_name"
    return 0
  fi

  print_section "Standardizing $family_name" "blue"
  log_verbose "Files with spaces: $files_with_spaces"

  if [[ "$DRY_RUN" == "true" ]]; then
    find "$font_dir" -type f -name "* *" 2>/dev/null | while read -r file; do
      local base
      local new_name
      base=$(basename "$file")
      new_name="${base// /-}"
      echo "  Would rename: $base → $new_name"
    done
  else
    find "$font_dir" -type f -name "* *" 2>/dev/null | while read -r file; do
      local dir
      local base
      local new_name
      dir=$(dirname "$file")
      base=$(basename "$file")
      new_name="${base// /-}"
      mv "$file" "$dir/$new_name" 2>/dev/null || true
    done
    log_success "Standardized $files_with_spaces filenames"
  fi
}

standardize_all_fonts() {
  if [[ ! -d "$FONTS_DIR" ]]; then
    log_error "Fonts directory not found: $FONTS_DIR"
    return 1
  fi

  print_header "Standardizing Font Names" "cyan"
  echo ""

  local families=()
  while IFS= read -r -d '' dir; do
    families+=("$(basename "$dir")")
  done < <(find "$FONTS_DIR" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

  if [[ ${#families[@]} -eq 0 ]]; then
    log_warning "No font families found in $FONTS_DIR"
    return 0
  fi

  for family in "${families[@]}"; do
    standardize_font_family "$FONTS_DIR/$family"
  done

  echo ""
  print_header_success "Standardization Complete"
}

# ================================================================
# Phase 4: Installation Functions
# ================================================================

install_font_files() {
  local source_dir="$1"
  local target_dir="$2"
  local platform="$3"
  local family_name
  family_name=$(basename "$source_dir")

  local installed=0
  local skipped=0
  local failed=0

  while IFS= read -r -d '' font_file; do
    local filename
    filename=$(basename "$font_file")
    local target_file="$target_dir/$filename"

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

    if [[ "$platform" == "wsl" ]]; then
      # WSL: Allow failures for permission issues
      if cp "$font_file" "$target_dir/" 2>/dev/null; then
        installed=$((installed + 1))
      else
        failed=$((failed + 1))
      fi
    else
      # macOS/Linux: Expect success
      cp "$font_file" "$target_dir/"
      installed=$((installed + 1))
    fi
  done < <(find_font_files "$source_dir" -print0)

  # Log results
  if [[ $installed -gt 0 ]] && [[ $skipped -gt 0 ]]; then
    log_success "Installed $installed new fonts from $family_name ($skipped already present)"
  elif [[ $installed -gt 0 ]]; then
    log_success "Installed $installed fonts from $family_name"
  elif [[ $skipped -gt 0 ]]; then
    log_success "All $skipped fonts from $family_name already installed"
  fi

  if [[ $failed -gt 0 ]]; then
    log_warning "Failed to install $failed fonts from $family_name (permission denied)"
  fi

  return 0
}

install_family() {
  local family="$1"
  local source_dir="$FONTS_SOURCE/$family"
  local platform="$2"
  local target_dir="$3"

  if [[ ! -d "$source_dir" ]]; then
    log_error "Font family not found: $family"
    return 1
  fi

  local font_count
  font_count=$(count_font_files "$source_dir")

  if [[ $font_count -eq 0 ]]; then
    log_warning "No fonts found in $family"
    return 0
  fi

  log_info "Installing $family ($font_count files)..."

  if [[ "$DRY_RUN" == "true" ]]; then
    log_info "[DRY RUN] Would install $font_count fonts from $family"
    return 0
  fi

  mkdir -p "$target_dir"
  install_font_files "$source_dir" "$target_dir" "$platform"
}

install_all_families() {
  local platform="$1"
  local target_dir="$2"
  local families=()

  while IFS= read -r -d '' dir; do
    families+=("$(basename "$dir")")
  done < <(find "$FONTS_SOURCE" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

  if [[ ${#families[@]} -eq 0 ]]; then
    log_error "No font families found in $FONTS_SOURCE"
    return 1
  fi

  for family in "${families[@]}"; do
    install_family "$family" "$platform" "$target_dir"
  done
}

refresh_font_cache() {
  local platform="$1"
  local target_dir="$2"

  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi

  case "$platform" in
    linux|arch)
      if command -v fc-cache &> /dev/null; then
        log_info "Refreshing font cache..."
        fc-cache -f "$target_dir" 2>/dev/null || true
        log_success "Font cache refreshed"
      fi
      ;;
    macos)
      log_info "macOS will automatically refresh font cache"
      ;;
    wsl)
      log_info "Font cache refresh not applicable for WSL"
      ;;
  esac
}

# ================================================================
# Phase Runners
# ================================================================

run_download_phase() {
  # Skip if fonts already exist (unless forcing)
  if [[ -d "$FONTS_DIR" ]] && [[ $(count_font_files "$FONTS_DIR") -gt 0 ]] && [[ "${FORCE_INSTALL:-false}" != "true" ]]; then
    local existing_count
    local family_count
    existing_count=$(count_font_files "$FONTS_DIR")
    family_count=$(find "$FONTS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
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
    print_header "Font Download (22 families)" "cyan"
  fi

  echo "Target directory: $FONTS_DIR"
  echo "Temporary directory: $TEMP_DIR"
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

  echo ""
  print_header_success "Download Complete"
}

run_prune_phase() {
  if [[ "$DRY_RUN" == "true" ]]; then
    print_header "Font Pruning (DRY RUN)" "cyan"
  else
    print_header "Font Pruning" "cyan"
  fi
  echo "Target directory: $FONTS_DIR"
  echo ""

  if [[ -n "$DOWNLOAD_FAMILY" ]]; then
    local family_dir
    family_dir=$(get_family_dir_name "$DOWNLOAD_FAMILY")
    prune_font_family "$FONTS_DIR/$family_dir"
  else
    prune_all_fonts
  fi

  echo ""
  local total
  total=$(count_font_files "$FONTS_DIR")
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "Current total: $total font files"
  else
    echo "Total after pruning: $total font files"
  fi
  echo ""
}

run_standardize_phase() {
  if [[ "$DRY_RUN" == "true" ]]; then
    print_header "Font Name Standardization (DRY RUN)" "cyan"
  else
    print_header "Font Name Standardization" "cyan"
  fi
  echo "Target directory: $FONTS_DIR"
  echo ""

  if [[ -n "$DOWNLOAD_FAMILY" ]]; then
    local family_dir
    family_dir=$(get_family_dir_name "$DOWNLOAD_FAMILY")
    standardize_font_family "$FONTS_DIR/$family_dir"
  else
    standardize_all_fonts
  fi

  echo ""
}

run_install_phase() {
  # Set FONTS_SOURCE to FONTS_DIR for installation
  FONTS_SOURCE="$FONTS_DIR"

  # Detect platform
  local platform
  platform=$(detect_distro)

  local target_dir
  target_dir=$(get_font_target_dir "$platform")

  # Print header
  print_header "Font Installation" "cyan"
  echo ""

  # Verify source directory
  if [[ ! -d "$FONTS_SOURCE" ]]; then
    log_error "Source directory not found: $FONTS_SOURCE"
    echo "Run with --download-only or --full to download fonts first"
    exit 1
  fi

  # Platform info
  log_info "Platform: $platform"
  log_info "Source: $FONTS_SOURCE"
  log_info "Target: $target_dir"

  if [[ "$DRY_RUN" == "true" ]]; then
    log_warning "DRY RUN MODE - No files will be installed"
  fi

  if [[ "$FORCE" == "true" ]]; then
    log_warning "Force mode enabled - Will overwrite existing fonts"
  fi

  echo ""

  # Install fonts
  if [[ -n "$DOWNLOAD_FAMILY" ]]; then
    local family_dir
    family_dir=$(get_family_dir_name "$DOWNLOAD_FAMILY")
    install_family "$family_dir" "$platform" "$target_dir"
  else
    install_all_families "$platform" "$target_dir"
  fi

  echo ""

  # Refresh cache
  refresh_font_cache "$platform" "$target_dir"

  # Summary
  echo ""
  print_header_success "Font Installation Complete"

  if [[ "$DRY_RUN" != "true" ]]; then
    local total_fonts
    local total_families
    total_fonts=$(count_font_files "$target_dir")
    total_families=$(find "$FONTS_SOURCE" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
    echo "  Families: $total_families"
    echo "  Files: $total_fonts"
    echo "  Location: $target_dir"
  fi

  echo ""
}

# ================================================================
# Download Orchestration
# ================================================================

# Wrapper function to run font downloads with failure handling
# Allows download to continue even if individual fonts fail
# Usage: run_font_download <function_name> <font_name>
run_font_download() {
    local download_func="$1"
    local font_name="$2"

    # Run download function - if it fails, check if failure was reported
    if $download_func; then
        return 0
    else
        local exit_code=$?

        # Check if failure was reported to registry
        if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]] && \
           compgen -G "$DOTFILES_FAILURE_REGISTRY/*-${font_name}.txt" > /dev/null 2>&1; then
            # Failure was reported - good, just log it
            log_warning "$font_name download failed (details in summary)"
        else
            # Unreported failure - create generic entry
            report_failure "$font_name" "unknown" "latest" \
                "Try downloading manually from nerdfonts.com or the font's GitHub repository" \
                "Download failed"
            log_warning "$font_name download failed (see summary)"
        fi

        return 1
    fi
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
      log_error "Unknown font family: $family"
      echo "Run with --list to see available families"
      exit 1
      ;;
  esac
}

download_all_families() {
  run_font_download download_jetbrains "jetbrains" || true
  run_font_download download_cascadia "cascadia" || true
  run_font_download download_meslo "meslo" || true
  run_font_download download_monaspace "monaspace" || true
  run_font_download download_iosevka "iosevka" || true
  run_font_download download_iosevka_base "iosevka-base" || true
  run_font_download download_sgr_iosevka "sgr-iosevka" || true
  run_font_download download_victor "victor" || true
  run_font_download download_firacode "firacode" || true
  run_font_download download_firacodescript "firacodescript" || true
  run_font_download download_droid "droid" || true
  run_font_download download_commitmono "commitmono" || true
  run_font_download download_comicmono "comicmono" || true
  run_font_download download_seriousshanns "seriousshanns" || true
  run_font_download download_sourcecode "sourcecode" || true
  run_font_download download_terminess "terminess" || true
  run_font_download download_hack "hack" || true
  run_font_download download_3270 "3270" || true
  run_font_download download_robotomono "robotomono" || true
  run_font_download download_spacemono "spacemono" || true
  run_font_download download_intelone "intelone" || true
}

# ================================================================
# Main Execution
# ================================================================

cleanup_temp_files() {
  if [[ -n "${TEMP_DIR:-}" ]] && [[ -d "$TEMP_DIR" ]]; then
    rm -rf "$TEMP_DIR"
  fi
}

validate_phase_modes() {
  # Count how many phase modes are enabled
  local phase_count=0
  [[ "$DOWNLOAD_ONLY" == "true" ]] && phase_count=$((phase_count + 1))
  [[ "$PRUNE_ONLY" == "true" ]] && phase_count=$((phase_count + 1))
  [[ "$STANDARDIZE_ONLY" == "true" ]] && phase_count=$((phase_count + 1))
  [[ "$INSTALL_ONLY" == "true" ]] && phase_count=$((phase_count + 1))
  [[ "$SKIP_INSTALL" == "true" ]] && phase_count=$((phase_count + 1))
  [[ "$FULL" == "true" ]] && phase_count=$((phase_count + 1))

  if [[ $phase_count -gt 1 ]]; then
    log_error "Cannot combine multiple phase modes"
    echo "Choose only one: --download-only, --prune-only, --standardize-only, --install-only, --skip-install, or --full"
    exit 1
  fi

  # Validate --dry-run usage
  if [[ "$DRY_RUN" == "true" ]]; then
    if [[ "$DOWNLOAD_ONLY" == "true" ]]; then
      log_error "--dry-run not compatible with --download-only"
      exit 1
    fi
  fi
}

main() {
  parse_args "$@"

  # Validate phase modes
  validate_phase_modes

  # Create directories
  mkdir -p "$FONTS_DIR"

  # Route to appropriate phase handler
  if [[ "$DOWNLOAD_ONLY" == "true" ]]; then
    run_download_phase
  elif [[ "$PRUNE_ONLY" == "true" ]]; then
    run_prune_phase
  elif [[ "$STANDARDIZE_ONLY" == "true" ]]; then
    run_standardize_phase
  elif [[ "$INSTALL_ONLY" == "true" ]]; then
    run_install_phase
  elif [[ "$SKIP_INSTALL" == "true" ]]; then
    run_download_phase
    run_prune_phase
    run_standardize_phase
  else
    # Default: full workflow
    run_download_phase
    if [[ "$SKIP_FILTER" != "true" ]]; then
      run_prune_phase
    fi
    run_standardize_phase
    run_install_phase
  fi
}

main "$@"
