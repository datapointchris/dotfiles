#!/usr/bin/env bash
# Generate alacritty config from theme.yml or palette.yml
# Usage: alacritty.sh <theme.yml|palette.yml> [output-file]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <theme.yml|palette.yml> [output-file]"
  exit 1
fi

input_file="$1"
output_file="${2:-}"

# Load colors (auto-detects format)
eval "$(load_colors "$input_file")"

# Remove # from hex color for alacritty TOML format
strip_hash() {
  echo "${1#\#}"
}

generate() {
  cat << EOF
# ${THEME_NAME} - alacritty theme
# Generated from theme.yml
# Author: ${THEME_AUTHOR}

[colors.primary]
background = "${SPECIAL_BG}"
foreground = "${SPECIAL_FG}"

[colors.cursor]
text = "${SPECIAL_CURSOR_TEXT}"
cursor = "${SPECIAL_CURSOR}"

[colors.selection]
text = "${SPECIAL_SELECTION_FG}"
background = "${SPECIAL_SELECTION_BG}"

[colors.normal]
black = "${ANSI_BLACK}"
red = "${ANSI_RED}"
green = "${ANSI_GREEN}"
yellow = "${ANSI_YELLOW}"
blue = "${ANSI_BLUE}"
magenta = "${ANSI_MAGENTA}"
cyan = "${ANSI_CYAN}"
white = "${ANSI_WHITE}"

[colors.bright]
black = "${ANSI_BRIGHT_BLACK}"
red = "${ANSI_BRIGHT_RED}"
green = "${ANSI_BRIGHT_GREEN}"
yellow = "${ANSI_BRIGHT_YELLOW}"
blue = "${ANSI_BRIGHT_BLUE}"
magenta = "${ANSI_BRIGHT_MAGENTA}"
cyan = "${ANSI_BRIGHT_CYAN}"
white = "${ANSI_BRIGHT_WHITE}"
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
