#!/usr/bin/env bash
# Generate hyprland config from palette.yml
# Usage: hyprland.sh <palette.yml> [output-file]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../palette.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <palette.yml> [output-file]"
  exit 1
fi

palette_file="$1"
output_file="${2:-}"

# Load palette into variables
eval "$(load_palette "$palette_file")"

# Convert #RRGGBB to RRGGBB for hyprland rgb() format
strip_hash() {
  echo "${1#\#}"
}

generate() {
  local active_border inactive_border
  active_border=$(strip_hash "$BASE04")
  inactive_border=$(strip_hash "$BASE01")

  cat << EOF
# ${THEME_NAME} - hyprland theme
# Generated from palette.yml
# Author: ${THEME_AUTHOR}

\$activeBorderColor = rgb(${active_border})
\$inactiveBorderColor = rgb(${inactive_border})

general {
    col.active_border = \$activeBorderColor
    col.inactive_border = \$inactiveBorderColor
}

group {
    col.border_active = \$activeBorderColor
    col.border_inactive = \$inactiveBorderColor
}
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
