#!/usr/bin/env bash
# Generate Chromium DevTools theme color from theme.yml
# Usage: chromium.sh <theme.yml> [output-file]
#
# Outputs RGB values of the background color for Chrome's new tab theme.
# Format: R,G,B (e.g., 40,40,40)

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

# Convert hex to RGB (R,G,B format)
hex_to_rgb() {
  local hex="${1#\#}"
  local r g b
  r=$((16#${hex:0:2}))
  g=$((16#${hex:2:2}))
  b=$((16#${hex:4:2}))
  echo "${r},${g},${b}"
}

generate() {
  hex_to_rgb "$SPECIAL_BG"
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
