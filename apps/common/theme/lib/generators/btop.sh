#!/usr/bin/env bash
# Generate btop theme from theme.yml or palette.yml
# Usage: btop.sh <theme.yml|palette.yml> [output-file]
#
# Enhanced generator using FULL color palette:
# - All 16 base16 colors utilized
# - Semantic color choices for meters and graphs

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

# btop needs uppercase hex colors
generate() {
  cat << EOF
# ${THEME_NAME} - btop theme
# Generated from theme.yml
# Author: ${THEME_AUTHOR}

# Main background, empty for terminal default
theme[main_bg]="$(to_upper "$BASE00")"

# Main text color
theme[main_fg]="$(to_upper "$BASE05")"

# Title color for boxes
# base0C = cyan for titles
theme[title]="$(to_upper "$BASE0C")"

# Highlight color for keyboard shortcuts
# base0D = blue for highlights
theme[hi_fg]="$(to_upper "$BASE0D")"

# Background color of selected item in processes box
# base02 = selection background
theme[selected_bg]="$(to_upper "$BASE02")"

# Foreground color of selected item in processes box
# base06 = light foreground
theme[selected_fg]="$(to_upper "$BASE06")"

# Color of inactive/disabled text
# base03 = comments/muted
theme[inactive_fg]="$(to_upper "$BASE03")"

# Misc colors for processes box
theme[proc_misc]="$(to_upper "$BASE0D")"

# Box outline colors
# base01 = lighter background for subtle borders
theme[cpu_box]="$(to_upper "$BASE01")"
theme[mem_box]="$(to_upper "$BASE01")"
theme[net_box]="$(to_upper "$BASE01")"
theme[proc_box]="$(to_upper "$BASE01")"
theme[div_line]="$(to_upper "$BASE01")"

# Temperature graph colors (gradient: blue -> cyan -> white)
theme[temp_start]="$(to_upper "$BASE0D")"
theme[temp_mid]="$(to_upper "$BASE0C")"
theme[temp_end]="$(to_upper "$BASE06")"

# CPU graph colors
theme[cpu_start]="$(to_upper "$BASE0D")"
theme[cpu_mid]="$(to_upper "$BASE0C")"
theme[cpu_end]="$(to_upper "$BASE06")"

# Memory free meter
theme[free_start]="$(to_upper "$BASE0B")"
theme[free_mid]="$(to_upper "$BASE0C")"
theme[free_end]="$(to_upper "$BASE06")"

# Memory cached meter
theme[cached_start]="$(to_upper "$BASE0A")"
theme[cached_mid]="$(to_upper "$BASE09")"
theme[cached_end]="$(to_upper "$BASE06")"

# Memory available meter
theme[available_start]="$(to_upper "$BASE0D")"
theme[available_mid]="$(to_upper "$BASE0C")"
theme[available_end]="$(to_upper "$BASE06")"

# Memory used meter
theme[used_start]="$(to_upper "$BASE08")"
theme[used_mid]="$(to_upper "$BASE09")"
theme[used_end]="$(to_upper "$BASE0A")"

# Download graph colors
theme[download_start]="$(to_upper "$BASE0B")"
theme[download_mid]="$(to_upper "$BASE0C")"
theme[download_end]="$(to_upper "$BASE06")"

# Upload graph colors
theme[upload_start]="$(to_upper "$BASE0E")"
theme[upload_mid]="$(to_upper "$BASE0D")"
theme[upload_end]="$(to_upper "$BASE06")"

# Process tree colors
# base0F = brown/secondary for tree structure
theme[process_start]="$(to_upper "$BASE0D")"
theme[process_mid]="$(to_upper "$BASE0F")"
theme[process_end]="$(to_upper "$BASE08")"

# Meter background
# base04 = dark foreground for subtle meter backgrounds
theme[meter_bg]="$(to_upper "$BASE04")"

# Graph text (brightest for readability)
# base07 = brightest foreground
theme[graph_text]="$(to_upper "$BASE07")"
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
