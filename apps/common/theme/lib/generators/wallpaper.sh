#!/usr/bin/env bash
# Generate themed wallpapers from theme.yml
# Usage: wallpaper.sh <theme.yml> <output-file> [style] [width] [height]
#
# Styles:
#   plasma     - Fractal plasma with theme colors (default)
#   geometric  - Random geometric shapes
#   hexagons   - Honeycomb pattern
#   circles    - Overlapping circles
#   demo       - All styles in a 2x2 grid with labels
#
# Requires: ImageMagick (magick command)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <theme.yml> <output-file> [style] [width] [height]"
  echo ""
  echo "Styles: plasma, geometric, hexagons, circles, demo"
  echo "Default: plasma at 3840x2160"
  exit 1
fi

input_file="$1"
output_file="$2"
style="${3:-plasma}"
width="${4:-3840}"
height="${5:-2160}"

eval "$(load_colors "$input_file")"

# Darken a hex color by a percentage
darken_color() {
  local hex="$1"
  local percent="${2:-20}"
  hex="${hex#\#}"
  local r=$((16#${hex:0:2}))
  local g=$((16#${hex:2:2}))
  local b=$((16#${hex:4:2}))
  r=$((r * (100 - percent) / 100))
  g=$((g * (100 - percent) / 100))
  b=$((b * (100 - percent) / 100))
  printf "#%02x%02x%02x" "$r" "$g" "$b"
}

generate_plasma() {
  # Multi-colored nebula clouds using accent palette
  local colors=("$BASE0D" "$BASE0E" "$BASE0C" "$BASE09" "$BASE0B")

  # Generate base with first plasma
  magick -size "${width}x${height}" -seed $RANDOM plasma:fractal \
    -grayscale Rec709Luminance \
    -sigmoidal-contrast 12x50% \
    -solarize 50% \
    -blur 0x2 \
    +level-colors "${BASE00},${colors[0]}" \
    /tmp/plasma_base_$$.png

  # Layer additional plasma clouds with different seeds and colors
  for i in {1..4}; do
    local color="${colors[$i]}"
    local contrast=$((10 + RANDOM % 8))
    local solarize=$((35 + RANDOM % 35))

    magick -size "${width}x${height}" -seed $RANDOM plasma:fractal \
      -grayscale Rec709Luminance \
      -sigmoidal-contrast "${contrast}x50%" \
      -solarize "${solarize}%" \
      -blur 0x2 \
      +level-colors "${BASE00},${color}" \
      /tmp/plasma_layer_$$.png

    magick /tmp/plasma_base_$$.png /tmp/plasma_layer_$$.png \
      -compose lighten -composite /tmp/plasma_base_$$.png
  done

  mv /tmp/plasma_base_$$.png "$output_file"
  rm -f /tmp/plasma_layer_$$.png
}

generate_geometric() {
  # Rotated shapes with accent colors (same palette as circles)
  local colors=("$BASE0D" "$BASE0E" "$BASE0C" "$BASE09" "$BASE0B")
  local draw_commands=""

  for _ in {1..60}; do
    local color="${colors[$((RANDOM % ${#colors[@]}))]}"
    local color_alpha="${color}45"  # 27% opacity
    local cx=$((RANDOM % width))
    local cy=$((RANDOM % height))
    local size=$((RANDOM % 150 + 50))
    local angle=$((RANDOM % 360))

    local shape=$((RANDOM % 3))
    case $shape in
      0) # Rotated rectangle
        local hw=$((size / 2))
        local hh=$((size / 4))
        draw_commands+=" -fill '${color_alpha}' -draw 'translate $cx,$cy rotate $angle rectangle $((- hw)),$((- hh)) $hw,$hh'"
        ;;
      1) # Circle (rotation doesn't matter)
        draw_commands+=" -fill '${color_alpha}' -draw 'circle $cx,$cy $((cx + size/2)),$cy'"
        ;;
      2) # Rotated triangle
        local s=$((size / 2))
        draw_commands+=" -fill '${color_alpha}' -draw 'translate $cx,$cy rotate $angle polygon 0,$((- s)) $((s)),$s $((-s)),$s'"
        ;;
    esac
  done

  # Single magick call with all draws
  eval "magick -size '${width}x${height}' xc:'${BASE00}' $draw_commands '$output_file'"
}

generate_hexagons() {
  # Scattered hexagons of varying sizes and accent colors
  local colors=("$BASE0D" "$BASE0E" "$BASE0C" "$BASE09" "$BASE0B")
  local draw_commands=""

  for _ in {1..45}; do
    local color="${colors[$((RANDOM % ${#colors[@]}))]}"
    local color_alpha="${color}40"
    local cx=$((RANDOM % width))
    local cy=$((RANDOM % height))
    local size=$((RANDOM % 80 + 30))
    local angle=$((RANDOM % 60))

    # Hexagon points relative to center
    local s=$size
    local h=$((s * 866 / 1000))  # sqrt(3)/2 approximation
    draw_commands+=" -fill '${color_alpha}' -draw 'translate $cx,$cy rotate $angle polygon 0,$((-s)) $h,$((-s/2)) $h,$((s/2)) 0,$s $((-h)),$((s/2)) $((-h)),$((-s/2))'"
  done

  eval "magick -size '${width}x${height}' xc:'${BASE00}' $draw_commands '$output_file'"
}

generate_circles() {
  # Build all draw commands at once
  local colors=("$BASE0D" "$BASE0E" "$BASE0C" "$BASE09" "$BASE0B")
  local draw_commands=""

  for _ in {1..50}; do
    local color="${colors[$((RANDOM % ${#colors[@]}))]}"
    local color_alpha="${color}35"  # 21% opacity
    local x=$((RANDOM % width))
    local y=$((RANDOM % height))
    local radius=$((RANDOM % 100 + 30))
    draw_commands+=" -fill '${color_alpha}' -draw 'circle $x,$y $((x + radius)),$y'"
  done

  # Single magick call with all circles
  eval "magick -size '${width}x${height}' xc:'${BASE00}' $draw_commands '$output_file'"
}

generate_demo() {
  # Generate all styles in a 2x2 grid with labels
  local tmp_dir="/tmp/wallpaper_demo_$$"
  local final_output="$output_file"
  mkdir -p "$tmp_dir"

  # Calculate tile size (2 columns, 2 rows)
  local tile_w=$((width / 2))
  local tile_h=$((height / 2))

  # Save original dimensions and generate each style at tile size
  local orig_width="$width"
  local orig_height="$height"
  width="$tile_w"
  height="$tile_h"

  local styles=("plasma" "geometric" "hexagons" "circles")

  for style_name in "${styles[@]}"; do
    local tile_file="$tmp_dir/${style_name}.png"
    output_file="$tile_file"
    "generate_${style_name}"

    # Add label to tile
    magick "$tile_file" \
      -gravity South \
      -fill "$BASE05" -font "Helvetica-Bold" -pointsize 48 \
      -annotate +0+20 "$style_name" \
      "$tile_file"
  done

  # Restore original dimensions and output file
  width="$orig_width"
  height="$orig_height"
  output_file="$final_output"

  # Combine into 2x2 grid
  magick montage \
    "$tmp_dir/plasma.png" "$tmp_dir/geometric.png" \
    "$tmp_dir/hexagons.png" "$tmp_dir/circles.png" \
    -tile 2x2 -geometry "${tile_w}x${tile_h}+0+0" \
    "$output_file"

  rm -rf "$tmp_dir"
}

# Generate based on style
case "$style" in
  plasma)
    generate_plasma
    ;;
  geometric)
    generate_geometric
    ;;
  hexagons)
    generate_hexagons
    ;;
  circles)
    generate_circles
    ;;
  demo)
    generate_demo
    ;;
  *)
    echo "Unknown style: $style"
    echo "Valid styles: plasma, geometric, hexagons, circles, demo"
    exit 1
    ;;
esac

echo "Generated: $output_file (${width}x${height}, style: $style)"
