#!/usr/bin/env bash
# Generate hyprlock theme from theme.yml
# Usage: hyprlock.sh <theme.yml> [output-file]
#
# Enhanced generator using FULL color palette:
# - All base16 colors as rgba variables
# - Semantic colors for lock screen states
# - Success/fail colors for authentication
#
# Hyprlock uses rgba format for colors with Hyprland variable syntax

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

hex_to_rgba() {
  local hex="$1"
  local alpha="${2:-1.0}"
  hex="${hex#\#}"
  local r=$((16#${hex:0:2}))
  local g=$((16#${hex:2:2}))
  local b=$((16#${hex:4:2}))
  echo "rgba($r,$g,$b,$alpha)"
}

generate() {
  cat << EOF
# ${THEME_NAME} - Hyprlock colors
# Generated from theme.yml
# Author: ${THEME_AUTHOR}

# =============================================================================
# BASE16 PALETTE (as rgba)
# =============================================================================

\$base00 = $(hex_to_rgba "$BASE00" "1.0")
\$base01 = $(hex_to_rgba "$BASE01" "1.0")
\$base02 = $(hex_to_rgba "$BASE02" "1.0")
\$base03 = $(hex_to_rgba "$BASE03" "1.0")
\$base04 = $(hex_to_rgba "$BASE04" "1.0")
\$base05 = $(hex_to_rgba "$BASE05" "1.0")
\$base06 = $(hex_to_rgba "$BASE06" "1.0")
\$base07 = $(hex_to_rgba "$BASE07" "1.0")
\$base08 = $(hex_to_rgba "$BASE08" "1.0")
\$base09 = $(hex_to_rgba "$BASE09" "1.0")
\$base0A = $(hex_to_rgba "$BASE0A" "1.0")
\$base0B = $(hex_to_rgba "$BASE0B" "1.0")
\$base0C = $(hex_to_rgba "$BASE0C" "1.0")
\$base0D = $(hex_to_rgba "$BASE0D" "1.0")
\$base0E = $(hex_to_rgba "$BASE0E" "1.0")
\$base0F = $(hex_to_rgba "$BASE0F" "1.0")

# =============================================================================
# LOCK SCREEN COLORS
# =============================================================================

# Main background color (used for lock screen background tint)
\$color = $(hex_to_rgba "$BASE00" "1.0")

# Input field colors
\$inner_color = $(hex_to_rgba "$BASE01" "0.9")
\$outer_color = $(hex_to_rgba "$BASE02" "1.0")

# Text colors
\$font_color = $(hex_to_rgba "$BASE05" "1.0")
\$font_color_dim = $(hex_to_rgba "$BASE04" "1.0")

# Authentication state colors
\$check_color = $(hex_to_rgba "$BASE0D" "1.0")
\$fail_color = $(hex_to_rgba "$BASE08" "1.0")
\$success_color = $(hex_to_rgba "$BASE0B" "1.0")
\$caps_lock_color = $(hex_to_rgba "$BASE09" "1.0")
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
