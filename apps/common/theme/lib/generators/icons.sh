#!/usr/bin/env bash
# Generate icon theme file from theme.yml
# Usage: icons.sh <theme.yml> [output-file]
#
# Reads meta.icon_theme from theme.yml and outputs the icon theme name.
# Falls back to "Yaru-blue" if not specified.

set -euo pipefail



if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <theme.yml> [output-file]"
  exit 1
fi

input_file="$1"
output_file="${2:-}"

icon_theme=$(yq -r '.meta.icon_theme // "Yaru-blue"' "$input_file")

generate() {
  echo "$icon_theme"
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
