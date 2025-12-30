#!/usr/bin/env bash
# Generate hyprlock theme from palette.yml
# Usage: hyprlock.sh <palette.yml> [output-file]
#
# Hyprlock uses rgba format for colors with Hyprland variable syntax

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <palette.yml> [output-file]"
  exit 1
fi

input_file="$1"
output_file="${2:-}"

eval "$(load_colors "$input_file")"

hex_to_rgba() {
  local hex="$1"
  local alpha="${2:-1.0}"
  hex="${hex#\#}"
  local r=$((16#${hex:0:2}))
  local g=$((16#${hex:2:2}))
  local b=$((16#${hex:4:2}))
  echo "rgba($r,$g,$b,$alpha)"
}

generate() {
  cat << EOF
# ${THEME_NAME} - Hyprlock colors
# Generated from palette.yml

# Main background color (used for lock screen background tint)
\$color = $(hex_to_rgba "$SPECIAL_BG" "1.0")

# Input field inner background (slightly transparent)
\$inner_color = $(hex_to_rgba "$SPECIAL_BG" "0.8")

# Input field outer border
\$outer_color = $(hex_to_rgba "$SPECIAL_FG" "1.0")

# Text color for password input
\$font_color = $(hex_to_rgba "$SPECIAL_FG" "1.0")

# Color when password is being verified
\$check_color = $(hex_to_rgba "$BASE0D" "1.0")
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
