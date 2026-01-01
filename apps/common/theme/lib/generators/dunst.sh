#!/usr/bin/env bash
# Generate dunst notification color config from theme.yml
# Usage: dunst.sh <theme.yml> [output-file]
#
# Enhanced generator using FULL color palette:
# - Semantic colors for urgency levels
# - Distinct frame colors using base16 accents
# - Highlight colors for emphasis
#
# Applied via drop-in: ~/.config/dunst/dunstrc.d/99-theme.conf

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <theme.yml> [output-file]"
  exit 1
fi

input_file="$1"
output_file="${2:-}"

eval "$(load_colors "$input_file")"

generate() {
  cat << EOF
# ${THEME_NAME} - Dunst notification colors
# Generated from theme.yml
# Author: ${THEME_AUTHOR}

[global]
    # Separator between notifications
    separator_color = "${BASE02}"

    # Progress bar colors
    highlight = "${BASE0D}"

[urgency_low]
    background = "${BASE00}"
    foreground = "${BASE04}"
    frame_color = "${BASE0C}"
    highlight = "${BASE0C}"
    timeout = 5

[urgency_normal]
    background = "${BASE00}"
    foreground = "${BASE05}"
    frame_color = "${BASE0D}"
    highlight = "${BASE0D}"
    timeout = 10

[urgency_critical]
    background = "${BASE01}"
    foreground = "${BASE07}"
    frame_color = "${BASE08}"
    highlight = "${BASE08}"
    timeout = 0
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
