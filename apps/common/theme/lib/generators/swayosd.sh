#!/usr/bin/env bash
# Generate swayosd on-screen display theme from palette.yml
# Usage: swayosd.sh <palette.yml> [output-file]
#
# SwayOSD uses GTK CSS @define-color syntax

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

generate() {
  cat << EOF
/* ${THEME_NAME} - SwayOSD colors */
/* Generated from palette.yml */

@define-color background-color ${SPECIAL_BG};
@define-color border-color ${SPECIAL_FG};
@define-color label ${SPECIAL_FG};
@define-color image ${SPECIAL_FG};
@define-color progress ${SPECIAL_FG};
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
