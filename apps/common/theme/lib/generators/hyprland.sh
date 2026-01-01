#!/usr/bin/env bash
# Generate hyprland config from theme.yml
# Usage: hyprland.sh <theme.yml> [output-file]
#
# Enhanced generator using FULL color palette:
# - Active borders use accent color (base0D blue)
# - Inactive borders use subtle color (base02)
# - Group colors use distinct accents
# - All base16 colors available as variables

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <theme.yml> [output-file]"
  exit 1
fi

input_file="$1"
output_file="${2:-}"

# Load palette into variables
eval "$(load_colors "$input_file")"

# Convert #RRGGBB to RRGGBB for hyprland rgb() format
strip_hash() {
  echo "${1#\#}"
}

generate() {
  cat << EOF
# ${THEME_NAME} - hyprland theme
# Generated from theme.yml
# Author: ${THEME_AUTHOR}

# =============================================================================
# COLOR VARIABLES (Base16)
# =============================================================================

\$base00 = rgb($(strip_hash "$BASE00"))  # Main background
\$base01 = rgb($(strip_hash "$BASE01"))  # Lighter background
\$base02 = rgb($(strip_hash "$BASE02"))  # Selection
\$base03 = rgb($(strip_hash "$BASE03"))  # Comments
\$base04 = rgb($(strip_hash "$BASE04"))  # Dark foreground
\$base05 = rgb($(strip_hash "$BASE05"))  # Foreground
\$base06 = rgb($(strip_hash "$BASE06"))  # Light foreground
\$base07 = rgb($(strip_hash "$BASE07"))  # Brightest
\$base08 = rgb($(strip_hash "$BASE08"))  # Red
\$base09 = rgb($(strip_hash "$BASE09"))  # Orange
\$base0A = rgb($(strip_hash "$BASE0A"))  # Yellow
\$base0B = rgb($(strip_hash "$BASE0B"))  # Green
\$base0C = rgb($(strip_hash "$BASE0C"))  # Cyan
\$base0D = rgb($(strip_hash "$BASE0D"))  # Blue
\$base0E = rgb($(strip_hash "$BASE0E"))  # Magenta
\$base0F = rgb($(strip_hash "$BASE0F"))  # Brown

# =============================================================================
# SEMANTIC COLORS
# =============================================================================

\$activeBorderColor = \$base0D
\$inactiveBorderColor = \$base02
\$groupActiveBorderColor = \$base0E
\$groupInactiveBorderColor = \$base03
\$groupLockedActiveBorderColor = \$base09
\$groupLockedInactiveBorderColor = \$base01

# =============================================================================
# WINDOW BORDERS
# =============================================================================

general {
    col.active_border = \$activeBorderColor
    col.inactive_border = \$inactiveBorderColor
}

# =============================================================================
# GROUP BORDERS
# =============================================================================

group {
    col.border_active = \$groupActiveBorderColor
    col.border_inactive = \$groupInactiveBorderColor
    col.border_locked_active = \$groupLockedActiveBorderColor
    col.border_locked_inactive = \$groupLockedInactiveBorderColor
}
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
