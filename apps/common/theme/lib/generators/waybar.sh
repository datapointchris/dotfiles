#!/usr/bin/env bash
# Generate waybar CSS from palette.yml
# Usage: waybar.sh <palette.yml> [output-file]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <palette.yml> [output-file]"
  exit 1
fi

input_file="$1"
output_file="${2:-}"

# Load palette into variables
eval "$(load_colors "$input_file")"

generate() {
  cat << EOF
/* ${THEME_NAME} - waybar theme */
/* Generated from theme.yml */

/* Base colors */
@define-color bg ${SPECIAL_BG};
@define-color bg-dark ${BASE01};
@define-color bg-highlight ${BASE02};
@define-color fg ${SPECIAL_FG};
@define-color fg-dark ${BASE04};

/* Accent colors */
@define-color blue ${ANSI_BLUE};
@define-color cyan ${ANSI_CYAN};
@define-color green ${ANSI_GREEN};
@define-color magenta ${ANSI_MAGENTA};
@define-color red ${ANSI_RED};
@define-color yellow ${ANSI_YELLOW};
@define-color orange ${BASE09};
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
