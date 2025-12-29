#!/usr/bin/env bash
# Generate btop.theme from Ghostty theme colors
# Usage: generate-btop.sh <ghostty-theme-name> [output-file]

set -euo pipefail

GHOSTTY_THEMES="/Applications/Ghostty.app/Contents/Resources/ghostty/themes"

usage() {
  echo "Usage: $0 <ghostty-theme-name> [output-file]"
  echo ""
  echo "Examples:"
  echo "  $0 Smyck                    # Print to stdout"
  echo "  $0 Smyck btop.theme         # Write to file"
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

theme_name="$1"
output_file="${2:-}"
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

# Extract base colors
bg=$(get_color "background")
fg=$(get_color "foreground")

# Palette colors (prefix unused with _)
color0=$(get_palette 0)   # black
_color1=$(get_palette 1)   # red (unused)
_color2=$(get_palette 2)   # green (unused)
_color3=$(get_palette 3)   # yellow (unused)
color4=$(get_palette 4)   # blue
_color5=$(get_palette 5)   # magenta (unused)
color6=$(get_palette 6)   # cyan
_color7=$(get_palette 7)   # white (unused)
color8=$(get_palette 8)   # bright black
color12=$(get_palette 12) # bright blue
color14=$(get_palette 14) # bright cyan
color15=$(get_palette 15) # bright white

# Convert to uppercase for btop
to_upper() {
  echo "$1" | tr '[:lower:]' '[:upper:]'
}

main_bg=$(to_upper "$bg")
main_fg=$(to_upper "$fg")
box_color=$(to_upper "${color8:-$color0}")
accent=$(to_upper "${color4:-$color6}")
_accent_light=$(to_upper "${color12:-$color14}")  # unused
_highlight=$(to_upper "${color6:-$color4}")  # unused
selected_bg=$(to_upper "${color8:-$color0}")
selected_fg=$(to_upper "${color15:-$fg}")
inactive=$(to_upper "${color8:-$color0}")
title=$(to_upper "${color6:-$color4}")
graph_start=$(to_upper "${color4:-$color6}")
graph_mid=$(to_upper "${color6:-$color14}")
graph_end=$(to_upper "${color15:-$fg}")

generate_btop() {
  cat << EOFINNER
# ${theme_name} btop theme
# Generated from Ghostty theme

# Main background, empty for terminal default
theme[main_bg]="${main_bg}"

# Main text color
theme[main_fg]="${main_fg}"

# Title color for boxes
theme[title]="${title}"

# Highlight color for keyboard shortcuts
theme[hi_fg]="${accent}"

# Background color of selected item in processes box
theme[selected_bg]="${selected_bg}"

# Foreground color of selected item in processes box
theme[selected_fg]="${selected_fg}"

# Color of inactive/disabled text
theme[inactive_fg]="${inactive}"

# Misc colors for processes box including mini cpu graphs, details memory graph and details status text
theme[proc_misc]="${accent}"

# Cpu box outline color
theme[cpu_box]="${box_color}"

# Memory/disks box outline color
theme[mem_box]="${box_color}"

# Net up/down box outline color
theme[net_box]="${box_color}"

# Processes box outline color
theme[proc_box]="${box_color}"

# Box divider line and small boxes line color
theme[div_line]="${box_color}"

# Temperature graph colors
theme[temp_start]="${graph_start}"
theme[temp_mid]="${graph_mid}"
theme[temp_end]="${graph_end}"

# CPU graph colors
theme[cpu_start]="${graph_start}"
theme[cpu_mid]="${graph_mid}"
theme[cpu_end]="${graph_end}"

# Mem/Disk free meter
theme[free_start]="${graph_start}"
theme[free_mid]="${graph_mid}"
theme[free_end]="${graph_end}"

# Mem/Disk cached meter
theme[cached_start]="${graph_start}"
theme[cached_mid]="${graph_mid}"
theme[cached_end]="${graph_end}"

# Mem/Disk available meter
theme[available_start]="${graph_start}"
theme[available_mid]="${graph_mid}"
theme[available_end]="${graph_end}"

# Mem/Disk used meter
theme[used_start]="${graph_start}"
theme[used_mid]="${graph_mid}"
theme[used_end]="${graph_end}"

# Download graph colors
theme[download_start]="${graph_start}"
theme[download_mid]="${graph_mid}"
theme[download_end]="${graph_end}"

# Upload graph colors
theme[upload_start]="${graph_start}"
theme[upload_mid]="${graph_mid}"
theme[upload_end]="${graph_end}"
EOFINNER
}

if [[ -n "$output_file" ]]; then
  generate_btop > "$output_file"
  echo "Generated: $output_file"
else
  generate_btop
fi
