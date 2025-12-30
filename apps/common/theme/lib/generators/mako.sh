#!/usr/bin/env bash
# Generate mako notification daemon theme from palette.yml
# Usage: mako.sh <palette.yml> [output-file]
#
# Mako uses INI format with hex colors

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
# ${THEME_NAME} - Mako notification colors
# Generated from palette.yml

text-color=${SPECIAL_FG}
border-color=${SPECIAL_FG}
background-color=${SPECIAL_BG}
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
