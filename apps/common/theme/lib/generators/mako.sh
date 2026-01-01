#!/usr/bin/env bash
# Generate mako notification daemon theme from theme.yml
# Usage: mako.sh <theme.yml> [output-file]
#
# Enhanced generator using FULL color palette:
# - Urgency-based colors using base16 accents
# - Progress bar colors
# - Border colors per urgency level
#
# Mako uses INI format with hex colors

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
# ${THEME_NAME} - Mako notification colors
# Generated from theme.yml
# Author: ${THEME_AUTHOR}

# Default colors
text-color=${BASE05}
background-color=${BASE00}
border-color=${BASE0D}
progress-color=over ${BASE0D}

# Low urgency - subtle cyan
[urgency=low]
text-color=${BASE04}
background-color=${BASE00}
border-color=${BASE0C}

# Normal urgency - blue accent
[urgency=normal]
text-color=${BASE05}
background-color=${BASE00}
border-color=${BASE0D}

# Critical urgency - red alert
[urgency=critical]
text-color=${BASE07}
background-color=${BASE01}
border-color=${BASE08}
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
