#!/usr/bin/env bash
# Generate walker app launcher theme from theme.yml
# Usage: walker.sh <theme.yml> [output-file]
#
# Enhanced generator using FULL color palette:
# - All base16 colors as CSS variables
# - Semantic aliases for app launcher elements
#
# Walker uses GTK CSS @define-color syntax

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
/* ${THEME_NAME} - Walker colors */
/* Generated from theme.yml */
/* Author: ${THEME_AUTHOR} */

/* Base16 palette */
@define-color base00 ${BASE00};
@define-color base01 ${BASE01};
@define-color base02 ${BASE02};
@define-color base03 ${BASE03};
@define-color base04 ${BASE04};
@define-color base05 ${BASE05};
@define-color base06 ${BASE06};
@define-color base07 ${BASE07};
@define-color base08 ${BASE08};
@define-color base09 ${BASE09};
@define-color base0A ${BASE0A};
@define-color base0B ${BASE0B};
@define-color base0C ${BASE0C};
@define-color base0D ${BASE0D};
@define-color base0E ${BASE0E};
@define-color base0F ${BASE0F};

/* Semantic colors */
@define-color background ${SPECIAL_BG};
@define-color foreground ${SPECIAL_FG};
@define-color base ${SPECIAL_BG};
@define-color text ${SPECIAL_FG};
@define-color text-muted ${BASE04};
@define-color border ${SPECIAL_BORDER};

/* Selection and highlight */
@define-color selected-bg ${BASE02};
@define-color selected-text ${BASE0D};
@define-color match ${BASE09};
@define-color accent ${BASE0D};
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
