#!/usr/bin/env bash
# Generate theme preview PNG image using ImageMagick
# Usage: preview.sh <theme-directory> <output.png>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <theme-directory> <output.png>"
  exit 1
fi

theme_dir="$1"
output_file="$2"
theme_file="$theme_dir/theme.yml"

if [[ ! -f "$theme_file" ]]; then
  echo "Error: theme.yml not found in $theme_dir" >&2
  exit 1
fi

if ! command -v magick &>/dev/null; then
  echo "Error: ImageMagick not found" >&2
  exit 1
fi

# Load all colors from theme
eval "$(load_colors "$theme_file")"

# Read metadata
name=$(yq '.meta.display_name // "Unknown"' "$theme_file")
author=$(yq '.meta.author // "Unknown"' "$theme_file")
variant=$(yq '.meta.variant // "dark"' "$theme_file")
nvim_cs=$(yq '.meta.neovim_colorscheme_name // .meta.id // "unknown"' "$theme_file")

# Get extended colors with fallbacks
syntax_comment="${EXTENDED_SYNTAX_COMMENT:-$ANSI_BRIGHT_BLACK}"
syntax_keyword="${EXTENDED_SYNTAX_KEYWORD:-$ANSI_MAGENTA}"
syntax_function="${EXTENDED_SYNTAX_FUNCTION:-$ANSI_BLUE}"
syntax_string="${EXTENDED_SYNTAX_STRING:-$ANSI_GREEN}"
syntax_number="${EXTENDED_SYNTAX_NUMBER:-$ANSI_CYAN}"
syntax_type="${EXTENDED_SYNTAX_TYPE:-$ANSI_YELLOW}"
syntax_operator="${EXTENDED_SYNTAX_OPERATOR:-$ANSI_YELLOW}"

# Diagnostic colors
diag_error="${EXTENDED_DIAGNOSTIC_ERROR:-$ANSI_RED}"
diag_warning="${EXTENDED_DIAGNOSTIC_WARNING:-$ANSI_YELLOW}"
diag_info="${EXTENDED_DIAGNOSTIC_INFO:-$ANSI_BLUE}"
diag_hint="${EXTENDED_DIAGNOSTIC_HINT:-$ANSI_CYAN}"

# Git colors
git_add="${EXTENDED_GIT_ADD:-$ANSI_GREEN}"
git_change="${EXTENDED_GIT_CHANGE:-$ANSI_YELLOW}"
git_delete="${EXTENDED_GIT_DELETE:-$ANSI_RED}"

# Find font file (same approach as font preview)
get_font_file() {
  local font_name="$1"
  fc-list : family file | grep -i "$font_name" | head -1 | cut -d: -f1
}

FONT_FILE=$(get_font_file "ComicShannsMono Nerd Font")
if [[ -z "$FONT_FILE" ]]; then
  FONT_FILE=$(get_font_file "JetBrainsMono Nerd Font")
fi
if [[ -z "$FONT_FILE" ]]; then
  FONT_FILE=$(get_font_file "Menlo")
fi
if [[ -z "$FONT_FILE" ]]; then
  FONT_FILE=$(get_font_file "Courier")
fi

if [[ -z "$FONT_FILE" ]]; then
  echo "Error: No suitable monospace font found" >&2
  exit 1
fi

# Image dimensions (matching font preview: 1200x1600)
WIDTH=1200
HEIGHT=1600

# Generate the preview image
if ! magick -size ${WIDTH}x${HEIGHT} "xc:${SPECIAL_BG}" \
  -font "$FONT_FILE" -pointsize 18 \
  \
  `# Theme name (large)` \
  -pointsize 28 -fill "${SPECIAL_FG}" -annotate +40+45 "$name" \
  \
  `# Author and variant` \
  -pointsize 14 -fill "${BASE04}" -annotate +40+75 "by $author | $variant | nvim: $nvim_cs" \
  \
  `# Special colors section` \
  -pointsize 18 -fill "${SPECIAL_FG}" -annotate +40+130 "Special Colors" \
  -fill "${SPECIAL_BG}" -stroke "${BASE03}" -strokewidth 2 -draw "rectangle 40,145 90,195" \
  -fill "${SPECIAL_FG}" -draw "rectangle 100,145 150,195" \
  -fill "${SPECIAL_CURSOR}" -draw "rectangle 160,145 210,195" \
  -fill "${SPECIAL_SELECTION_BG}" -draw "rectangle 220,145 270,195" \
  -fill "${SPECIAL_BORDER}" -draw "rectangle 280,145 330,195" \
  -stroke none \
  -pointsize 12 -fill "${BASE04}" \
  -annotate +52+215 "bg" \
  -annotate +112+215 "fg" \
  -annotate +168+215 "cursor" \
  -annotate +228+215 "sel" \
  -annotate +288+215 "border" \
  \
  `# ANSI Normal colors` \
  -pointsize 18 -fill "${SPECIAL_FG}" -annotate +40+270 "ANSI Normal (0-7)" \
  -fill "${ANSI_BLACK}" -draw "rectangle 40,285 90,335" \
  -fill "${ANSI_RED}" -draw "rectangle 100,285 150,335" \
  -fill "${ANSI_GREEN}" -draw "rectangle 160,285 210,335" \
  -fill "${ANSI_YELLOW}" -draw "rectangle 220,285 270,335" \
  -fill "${ANSI_BLUE}" -draw "rectangle 280,285 330,335" \
  -fill "${ANSI_MAGENTA}" -draw "rectangle 340,285 390,335" \
  -fill "${ANSI_CYAN}" -draw "rectangle 400,285 450,335" \
  -fill "${ANSI_WHITE}" -draw "rectangle 460,285 510,335" \
  -pointsize 12 -fill "${BASE04}" \
  -annotate +58+355 "0" -annotate +118+355 "1" -annotate +178+355 "2" -annotate +238+355 "3" \
  -annotate +298+355 "4" -annotate +358+355 "5" -annotate +418+355 "6" -annotate +478+355 "7" \
  \
  `# ANSI Bright colors` \
  -pointsize 18 -fill "${SPECIAL_FG}" -annotate +40+400 "ANSI Bright (8-15)" \
  -fill "${ANSI_BRIGHT_BLACK}" -draw "rectangle 40,415 90,465" \
  -fill "${ANSI_BRIGHT_RED}" -draw "rectangle 100,415 150,465" \
  -fill "${ANSI_BRIGHT_GREEN}" -draw "rectangle 160,415 210,465" \
  -fill "${ANSI_BRIGHT_YELLOW}" -draw "rectangle 220,415 270,465" \
  -fill "${ANSI_BRIGHT_BLUE}" -draw "rectangle 280,415 330,465" \
  -fill "${ANSI_BRIGHT_MAGENTA}" -draw "rectangle 340,415 390,465" \
  -fill "${ANSI_BRIGHT_CYAN}" -draw "rectangle 400,415 450,465" \
  -fill "${ANSI_BRIGHT_WHITE}" -draw "rectangle 460,415 510,465" \
  -pointsize 12 -fill "${BASE04}" \
  -annotate +58+485 "8" -annotate +118+485 "9" -annotate +173+485 "10" -annotate +233+485 "11" \
  -annotate +293+485 "12" -annotate +353+485 "13" -annotate +413+485 "14" -annotate +473+485 "15" \
  \
  `# Base16 row 1` \
  -pointsize 18 -fill "${SPECIAL_FG}" -annotate +40+540 "Base16 (00-07)" \
  -fill "${BASE00}" -draw "rectangle 40,555 90,605" \
  -fill "${BASE01}" -draw "rectangle 100,555 150,605" \
  -fill "${BASE02}" -draw "rectangle 160,555 210,605" \
  -fill "${BASE03}" -draw "rectangle 220,555 270,605" \
  -fill "${BASE04}" -draw "rectangle 280,555 330,605" \
  -fill "${BASE05}" -draw "rectangle 340,555 390,605" \
  -fill "${BASE06}" -draw "rectangle 400,555 450,605" \
  -fill "${BASE07}" -draw "rectangle 460,555 510,605" \
  -pointsize 12 -fill "${BASE04}" \
  -annotate +53+625 "00" -annotate +113+625 "01" -annotate +173+625 "02" -annotate +233+625 "03" \
  -annotate +293+625 "04" -annotate +353+625 "05" -annotate +413+625 "06" -annotate +473+625 "07" \
  \
  `# Base16 row 2` \
  -pointsize 18 -fill "${SPECIAL_FG}" -annotate +40+670 "Base16 (08-0F)" \
  -fill "${BASE08}" -draw "rectangle 40,685 90,735" \
  -fill "${BASE09}" -draw "rectangle 100,685 150,735" \
  -fill "${BASE0A}" -draw "rectangle 160,685 210,735" \
  -fill "${BASE0B}" -draw "rectangle 220,685 270,735" \
  -fill "${BASE0C}" -draw "rectangle 280,685 330,735" \
  -fill "${BASE0D}" -draw "rectangle 340,685 390,735" \
  -fill "${BASE0E}" -draw "rectangle 400,685 450,735" \
  -fill "${BASE0F}" -draw "rectangle 460,685 510,735" \
  -pointsize 12 -fill "${BASE04}" \
  -annotate +53+755 "08" -annotate +113+755 "09" -annotate +173+755 "0A" -annotate +233+755 "0B" \
  -annotate +293+755 "0C" -annotate +353+755 "0D" -annotate +413+755 "0E" -annotate +473+755 "0F" \
  \
  `# Syntax colors` \
  -pointsize 18 -fill "${SPECIAL_FG}" -annotate +40+810 "Syntax Highlighting" \
  -pointsize 16 \
  -fill "$syntax_keyword" -annotate +40+845 "keyword" \
  -fill "$syntax_function" -annotate +140+845 "function" \
  -fill "$syntax_type" -annotate +260+845 "Type" \
  -fill "$syntax_string" -annotate +340+845 '"string"' \
  -fill "$syntax_number" -annotate +460+845 "42" \
  -fill "$syntax_comment" -annotate +520+845 "# comment" \
  \
  `# Diagnostics and Git` \
  -pointsize 18 -fill "${SPECIAL_FG}" -annotate +40+900 "Diagnostics" \
  -pointsize 16 \
  -fill "$diag_error" -annotate +180+900 "error" \
  -fill "$diag_warning" -annotate +260+900 "warning" \
  -fill "$diag_info" -annotate +380+900 "info" \
  -fill "$diag_hint" -annotate +450+900 "hint" \
  \
  -pointsize 18 -fill "${SPECIAL_FG}" -annotate +40+950 "Git" \
  -pointsize 16 \
  -fill "$git_add" -annotate +100+950 "+added" \
  -fill "$git_change" -annotate +200+950 "~changed" \
  -fill "$git_delete" -annotate +330+950 "-deleted" \
  \
  `# Code sample box` \
  -pointsize 18 -fill "${SPECIAL_FG}" -annotate +40+1010 "Code Sample" \
  -fill "${BASE00}" -draw "rectangle 40,1025 1160,1560" \
  -stroke "${BASE02}" -strokewidth 2 -draw "rectangle 40,1025 1160,1560" \
  -stroke none \
  \
  `# Code sample content - Python` \
  -pointsize 16 \
  -fill "$syntax_comment" -annotate +60+1060 "# Configuration module for application settings" \
  -fill "$syntax_keyword" -annotate +60+1095 "from" \
  -fill "$syntax_type" -annotate +120+1095 "typing" \
  -fill "$syntax_keyword" -annotate +195+1095 "import" \
  -fill "$syntax_type" -annotate +270+1095 "Dict, List, Optional" \
  \
  -fill "$syntax_keyword" -annotate +60+1145 "class" \
  -fill "$syntax_type" -annotate +120+1145 "Config" \
  -fill "${SPECIAL_FG}" -annotate +190+1145 ":" \
  -fill "$syntax_string" -annotate +80+1180 '"""Application configuration manager."""' \
  \
  -fill "${SPECIAL_FG}" -annotate +80+1230 "VERSION" \
  -fill "$syntax_operator" -annotate +175+1230 "=" \
  -fill "$syntax_string" -annotate +200+1230 '"1.0.0"' \
  \
  -fill "$syntax_keyword" -annotate +80+1280 "def" \
  -fill "$syntax_function" -annotate +130+1280 "__init__" \
  -fill "${SPECIAL_FG}" -annotate +230+1280 "(self, name:" \
  -fill "$syntax_type" -annotate +370+1280 "str" \
  -fill "${SPECIAL_FG}" -annotate +410+1280 ", debug:" \
  -fill "$syntax_type" -annotate +500+1280 "bool" \
  -fill "$syntax_operator" -annotate +555+1280 "=" \
  -fill "$syntax_keyword" -annotate +575+1280 "False" \
  -fill "${SPECIAL_FG}" -annotate +640+1280 "):" \
  \
  -fill "${SPECIAL_FG}" -annotate +100+1315 "self.name" \
  -fill "$syntax_operator" -annotate +200+1315 "=" \
  -fill "${SPECIAL_FG}" -annotate +220+1315 "name" \
  -fill "${SPECIAL_FG}" -annotate +100+1350 "self.debug" \
  -fill "$syntax_operator" -annotate +210+1350 "=" \
  -fill "${SPECIAL_FG}" -annotate +230+1350 "debug" \
  -fill "${SPECIAL_FG}" -annotate +100+1385 "self.count" \
  -fill "$syntax_operator" -annotate +210+1385 "=" \
  -fill "$syntax_number" -annotate +230+1385 "42" \
  \
  -fill "$syntax_keyword" -annotate +80+1435 "def" \
  -fill "$syntax_function" -annotate +130+1435 "validate" \
  -fill "${SPECIAL_FG}" -annotate +230+1435 "(self)" \
  -fill "$syntax_operator" -annotate +300+1435 "->" \
  -fill "$syntax_type" -annotate +330+1435 "bool" \
  -fill "${SPECIAL_FG}" -annotate +380+1435 ":" \
  -fill "$syntax_keyword" -annotate +100+1470 "return" \
  -fill "${SPECIAL_FG}" -annotate +170+1470 "self.count" \
  -fill "$syntax_operator" -annotate +285+1470 ">" \
  -fill "$syntax_number" -annotate +305+1470 "0" \
  -fill "$syntax_keyword" -annotate +330+1470 "and" \
  -fill "$syntax_function" -annotate +385+1470 "len" \
  -fill "${SPECIAL_FG}" -annotate +425+1470 "(self.name)" \
  -fill "$syntax_operator" -annotate +545+1470 ">" \
  -fill "$syntax_number" -annotate +565+1470 "0" \
  \
  -fill "$syntax_comment" -annotate +60+1520 "# End of configuration module" \
  \
  -quality 100 \
  "$output_file"; then
  echo "Error: ImageMagick failed to generate preview" >&2
  exit 1
fi
