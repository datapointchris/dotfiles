#!/usr/bin/env bash
# Generate kitty config from theme.yml or palette.yml
# Usage: kitty.sh <theme.yml|palette.yml> [output-file]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <theme.yml|palette.yml> [output-file]"
  exit 1
fi

input_file="$1"
output_file="${2:-}"

# Load colors (auto-detects format)
eval "$(load_colors "$input_file")"

generate() {
  cat << EOF
# ${THEME_NAME} - kitty theme
# Generated from theme.yml
# Author: ${THEME_AUTHOR}

# Basic colors
foreground ${SPECIAL_FG}
background ${SPECIAL_BG}

# Selection colors
selection_foreground ${SPECIAL_SELECTION_FG}
selection_background ${SPECIAL_SELECTION_BG}

# Cursor colors
cursor ${SPECIAL_CURSOR}
cursor_text_color ${SPECIAL_CURSOR_TEXT}

# URL color
url_color ${BASE0D}

# Tab bar colors
active_tab_foreground ${BASE00}
active_tab_background ${BASE0D}
inactive_tab_foreground ${BASE04}
inactive_tab_background ${BASE01}

# Normal colors (0-7)
color0 ${ANSI_BLACK}
color1 ${ANSI_RED}
color2 ${ANSI_GREEN}
color3 ${ANSI_YELLOW}
color4 ${ANSI_BLUE}
color5 ${ANSI_MAGENTA}
color6 ${ANSI_CYAN}
color7 ${ANSI_WHITE}

# Bright colors (8-15)
color8 ${ANSI_BRIGHT_BLACK}
color9 ${ANSI_BRIGHT_RED}
color10 ${ANSI_BRIGHT_GREEN}
color11 ${ANSI_BRIGHT_YELLOW}
color12 ${ANSI_BRIGHT_BLUE}
color13 ${ANSI_BRIGHT_MAGENTA}
color14 ${ANSI_BRIGHT_CYAN}
color15 ${ANSI_BRIGHT_WHITE}

# Mark colors (for marked text)
mark1_foreground ${BASE00}
mark1_background ${BASE0D}
mark2_foreground ${BASE00}
mark2_background ${BASE0E}
mark3_foreground ${BASE00}
mark3_background ${BASE0C}
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
