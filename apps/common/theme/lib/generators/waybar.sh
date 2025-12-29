#!/usr/bin/env bash
# Generate waybar CSS from palette.yml
# Usage: waybar.sh <palette.yml> [output-file]

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

generate() {
  cat << EOF
/* ${THEME_NAME} - waybar theme */
/* Generated from palette.yml */
/* Author: ${THEME_AUTHOR} */

/* Base colors */
@define-color background ${BASE00};
@define-color background-alt ${BASE01};
@define-color foreground ${BASE05};
@define-color foreground-alt ${BASE04};

/* Selection and highlighting */
@define-color selection ${BASE02};
@define-color comment ${BASE03};

/* Accent colors */
@define-color red ${BASE08};
@define-color orange ${BASE09};
@define-color yellow ${BASE0A};
@define-color green ${BASE0B};
@define-color cyan ${BASE0C};
@define-color blue ${BASE0D};
@define-color purple ${BASE0E};
@define-color brown ${BASE0F};
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
