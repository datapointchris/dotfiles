#!/usr/bin/env bash
# Generate rofi color theme from theme.yml
# Usage: rofi.sh <theme.yml> [output-file]
#
# Outputs a rasi theme file with color variables.
# Import in rofi config with: @import "themes/current.rasi"

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
/* ${THEME_NAME} - Rofi colors */
/* Generated from theme.yml */

* {
    bg: ${SPECIAL_BG};
    bg-alt: ${BASE01};
    bg-selected: ${SPECIAL_SELECTION_BG};
    fg: ${SPECIAL_FG};
    fg-alt: ${BASE04};
    blue: ${ANSI_BLUE};
    magenta: ${ANSI_MAGENTA};
    red: ${ANSI_RED};
    green: ${ANSI_GREEN};
    yellow: ${ANSI_YELLOW};
    cyan: ${ANSI_CYAN};
}
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
