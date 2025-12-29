#!/usr/bin/env bash
# Generate Ghostty config from palette.yml
# Usage: ghostty.sh <palette.yml> [output-file]
#
# If palette has builtin.ghostty, outputs a theme reference.
# Otherwise, outputs full color definitions.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../palette.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <palette.yml> [output-file]"
  exit 1
fi

palette_file="$1"
output_file="${2:-}"

# Check for built-in theme reference
builtin_theme=$(yq -r '.builtin.ghostty // ""' "$palette_file")

# Load palette into variables
eval "$(load_palette "$palette_file")"

generate_reference() {
  cat << EOF
# ${THEME_NAME} - Ghostty theme
# Uses Ghostty built-in theme
theme = ${builtin_theme}
EOF
}

generate_full() {
  cat << EOF
# ${THEME_NAME} - Ghostty theme
# Generated from palette.yml
# Author: ${THEME_AUTHOR}

background = ${SPECIAL_BG}
foreground = ${SPECIAL_FG}
cursor-color = ${SPECIAL_CURSOR}
cursor-text = ${SPECIAL_CURSOR_TEXT}
selection-background = ${SPECIAL_SELECTION_BG}
selection-foreground = ${SPECIAL_SELECTION_FG}

# ANSI colors
palette = 0=${ANSI_BLACK}
palette = 1=${ANSI_RED}
palette = 2=${ANSI_GREEN}
palette = 3=${ANSI_YELLOW}
palette = 4=${ANSI_BLUE}
palette = 5=${ANSI_MAGENTA}
palette = 6=${ANSI_CYAN}
palette = 7=${ANSI_WHITE}
palette = 8=${ANSI_BRIGHT_BLACK}
palette = 9=${ANSI_BRIGHT_RED}
palette = 10=${ANSI_BRIGHT_GREEN}
palette = 11=${ANSI_BRIGHT_YELLOW}
palette = 12=${ANSI_BRIGHT_BLUE}
palette = 13=${ANSI_BRIGHT_MAGENTA}
palette = 14=${ANSI_BRIGHT_CYAN}
palette = 15=${ANSI_BRIGHT_WHITE}
EOF
}

generate() {
  if [[ -n "$builtin_theme" ]]; then
    generate_reference
  else
    generate_full
  fi
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
