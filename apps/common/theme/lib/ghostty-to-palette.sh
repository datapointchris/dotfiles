#!/usr/bin/env bash
# Convert Ghostty theme to palette.yml
# Usage: ghostty-to-palette.sh <ghostty-theme-name> <theme-display-name> [output-file]
#
# Extracts colors from Ghostty's built-in theme and creates a palette.yml

set -euo pipefail

GHOSTTY_THEMES="/Applications/Ghostty.app/Contents/Resources/ghostty/themes"

usage() {
  echo "Usage: $0 <ghostty-theme-name> <theme-display-name> [output-file]"
  echo ""
  echo "Convert Ghostty theme to palette.yml format"
  echo ""
  echo "Arguments:"
  echo "  ghostty-theme-name   Name in Ghostty (e.g., 'Smyck', 'Rose Pine')"
  echo "  theme-display-name   Display name for palette (e.g., 'Smyck', 'Rose Pine')"
  echo "  output-file          Output path (default: stdout)"
  echo ""
  echo "Example:"
  echo "  $0 'Smyck' 'Smyck' library/smyck/palette.yml"
  exit 1
}

if [[ $# -lt 2 ]]; then
  usage
fi

theme_name="$1"
display_name="$2"
output_file="${3:-}"
theme_path="$GHOSTTY_THEMES/$theme_name"

if [[ ! -f "$theme_path" ]]; then
  echo "Error: Theme not found: $theme_path" >&2
  exit 1
fi

# Extract colors from Ghostty theme
get_color() {
  local key="$1"
  grep "^${key} = " "$theme_path" | cut -d= -f2 | xargs
}

get_palette() {
  local index="$1"
  grep "^palette = ${index}=#" "$theme_path" | cut -d= -f3
}

# Extract all colors
bg=$(get_color "background")
fg=$(get_color "foreground")
cursor=$(get_color "cursor-color")
cursor_text=$(get_color "cursor-text")
sel_bg=$(get_color "selection-background")
sel_fg=$(get_color "selection-foreground")

# ANSI palette
c0=$(get_palette 0)
c1=$(get_palette 1)
c2=$(get_palette 2)
c3=$(get_palette 3)
c4=$(get_palette 4)
c5=$(get_palette 5)
c6=$(get_palette 6)
c7=$(get_palette 7)
c8=$(get_palette 8)
c9=$(get_palette 9)
c10=$(get_palette 10)
c11=$(get_palette 11)
c12=$(get_palette 12)
c13=$(get_palette 13)
c14=$(get_palette 14)
c15=$(get_palette 15)

# Map ANSI to base16
# This is an approximation - manual tuning may be needed
base00="$bg"
base01="$c8"         # Bright black as lighter bg
base02="${sel_bg:-$c8}"
base03="$c8"         # Comments (bright black)
base04="$c7"         # Dark foreground (white)
base05="$fg"
base06="${c15:-$fg}"
base07="${c15:-$fg}"
base08="$c1"         # Red
base09="${c9:-$c1}"  # Orange (bright red fallback)
base0A="$c3"         # Yellow
base0B="$c2"         # Green
base0C="$c6"         # Cyan
base0D="$c4"         # Blue
base0E="$c5"         # Purple
base0F="${c5:-$c4}"  # Brown (fallback to purple/blue)

generate() {
  cat << EOF
# ${display_name} Theme Palette
# Converted from Ghostty theme: ${theme_name}

name: "${display_name}"
author: "Ghostty"
variant: "dark"
source: "Ghostty built-in theme"

palette:
  # --- Backgrounds ---
  base00: "${base00}"  # Default background
  base01: "${base01}"  # Lighter background (status bars, line numbers)
  base02: "${base02}"  # Selection background
  base03: "${base03}"  # Comments, invisibles, line highlighting

  # --- Foregrounds ---
  base04: "${base04}"  # Dark foreground (status bars)
  base05: "${base05}"  # Default foreground
  base06: "${base06}"  # Light foreground
  base07: "${base07}"  # Lightest foreground

  # --- Accent Colors ---
  base08: "${base08}"  # Red - errors, deletion
  base09: "${base09}"  # Orange - warnings, constants
  base0A: "${base0A}"  # Yellow - classes, search highlight
  base0B: "${base0B}"  # Green - strings, success
  base0C: "${base0C}"  # Cyan - regex, escape chars
  base0D: "${base0D}"  # Blue - functions, info
  base0E: "${base0E}"  # Purple - keywords
  base0F: "${base0F}"  # Brown/accent - deprecated

ansi:
  # Normal colors
  black: "${c0}"
  red: "${c1}"
  green: "${c2}"
  yellow: "${c3}"
  blue: "${c4}"
  magenta: "${c5}"
  cyan: "${c6}"
  white: "${c7}"

  # Bright colors
  bright_black: "${c8}"
  bright_red: "${c9}"
  bright_green: "${c10}"
  bright_yellow: "${c11}"
  bright_blue: "${c12}"
  bright_magenta: "${c13}"
  bright_cyan: "${c14}"
  bright_white: "${c15}"

special:
  background: "${bg}"
  foreground: "${fg}"
  cursor: "${cursor:-$fg}"
  cursor_text: "${cursor_text:-$bg}"
  selection_bg: "${sel_bg:-$c8}"
  selection_fg: "${sel_fg:-$fg}"
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
