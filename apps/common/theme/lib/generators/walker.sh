#!/usr/bin/env bash
# Generate walker app launcher theme from palette.yml
# Usage: walker.sh <palette.yml> [output-file]
#
# Walker uses GTK CSS @define-color syntax

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
/* ${THEME_NAME} - Walker colors */
/* Generated from palette.yml */

@define-color selected-text ${BASE0C};
@define-color text ${SPECIAL_FG};
@define-color base ${SPECIAL_BG};
@define-color border ${SPECIAL_FG};
@define-color foreground ${SPECIAL_FG};
@define-color background ${SPECIAL_BG};
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
