#!/usr/bin/env bash
# Generate themed wallpapers from theme.yml
# Usage: wallpaper.sh <theme.yml> <output-file> [style] [width] [height]
#
# Styles:
#   plasma     - Fractal plasma with theme colors (default)
#   geometric  - Random geometric shapes
#   hexagons   - Honeycomb pattern
#   circles    - Overlapping circles
#   noise      - Subtle noise texture
#   gradient   - Simple diagonal gradient
#
# Requires: ImageMagick (magick command)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <theme.yml> <output-file> [style] [width] [height]"
  echo ""
  echo "Styles: plasma, geometric, hexagons, circles, noise, gradient"
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
  local dark
  dark=$(darken_color "$BASE00" 30)

  # Generate plasma with theme colors, then tint to match palette
  magick -size "${width}x${height}" \
    plasma:"${dark}-${BASE01}" \
    -blur 0x2 \
    -modulate 100,50,100 \
    +level-colors "${dark},${BASE02}" \
    "$output_file"
}

generate_geometric() {
  local dark
  dark=$(darken_color "$BASE00" 20)

  # Create base image
  magick -size "${width}x${height}" xc:"${dark}" /tmp/geo_base_$$.png

  # Add random shapes using theme colors with transparency via hex alpha
  local colors=("$BASE01" "$BASE02" "$BASE03" "$BASE0D" "$BASE0E")

  for _ in {1..30}; do
    local color="${colors[$((RANDOM % ${#colors[@]}))]}"
    # Add alpha channel to color (20% opacity = 33 in hex)
    local color_alpha="${color}33"
    local x1=$((RANDOM % width))
    local y1=$((RANDOM % height))
    local size=$((RANDOM % 400 + 100))

    # Random shape: rectangle, circle, or triangle
    local shape=$((RANDOM % 3))
    case $shape in
      0) # Rectangle
        local x2=$((x1 + size))
        local y2=$((y1 + size / 2))
        magick /tmp/geo_base_$$.png -fill "${color_alpha}" \
          -draw "rectangle $x1,$y1 $x2,$y2" /tmp/geo_base_$$.png
        ;;
      1) # Circle
        magick /tmp/geo_base_$$.png -fill "${color_alpha}" \
          -draw "circle $x1,$y1 $((x1 + size/2)),$y1" /tmp/geo_base_$$.png
        ;;
      2) # Polygon (triangle)
        local x2=$((x1 + size))
        local y2=$((y1 + size))
        local x3=$((x1 - size/2))
        magick /tmp/geo_base_$$.png -fill "${color_alpha}" \
          -draw "polygon $x1,$y1 $x2,$y2 $x3,$y2" /tmp/geo_base_$$.png
        ;;
    esac
  done

  magick /tmp/geo_base_$$.png -blur 0x3 "$output_file"
  rm -f /tmp/geo_base_$$.png
}

generate_hexagons() {
  local dark
  dark=$(darken_color "$BASE00" 15)
  local hex_size=80

  # Create a hexagon tile
  local tile_file="/tmp/hex_tile_$$.png"

  magick -size "$((hex_size * 3))x$((hex_size * 3))" xc:"$dark" \
    -fill "$BASE01" -stroke "$BASE02" -strokewidth 1 \
    -draw "polygon $((hex_size)),$((hex_size/4)) $((hex_size*2)),$((hex_size/4)) $((hex_size*5/2)),$((hex_size)) $((hex_size*2)),$((hex_size*7/4)) $((hex_size)),$((hex_size*7/4)) $((hex_size/2)),$((hex_size))" \
    "$tile_file"

  # Tile it across the wallpaper
  magick -size "${width}x${height}" "tile:${tile_file}" \
    -blur 0x1 \
    "$output_file"

  rm -f "$tile_file"
}

generate_circles() {
  local dark
  dark=$(darken_color "$BASE00" 25)

  # Create base image
  magick -size "${width}x${height}" xc:"${dark}" /tmp/circles_base_$$.png

  local colors=("$BASE0D" "$BASE0E" "$BASE0C" "$BASE09" "$BASE0B")

  # Add overlapping circles with transparency via hex alpha
  for _ in {1..20}; do
    local color="${colors[$((RANDOM % ${#colors[@]}))]}"
    # Add alpha channel (15% opacity = 26 in hex)
    local color_alpha="${color}26"
    local x=$((RANDOM % width))
    local y=$((RANDOM % height))
    local radius=$((RANDOM % 300 + 50))

    magick /tmp/circles_base_$$.png -fill "${color_alpha}" \
      -draw "circle $x,$y $((x + radius)),$y" /tmp/circles_base_$$.png
  done

  magick /tmp/circles_base_$$.png -blur 0x5 "$output_file"
  rm -f /tmp/circles_base_$$.png
}

generate_noise() {
  local dark
  dark=$(darken_color "$BASE00" 10)

  # Subtle noise pattern
  magick -size "${width}x${height}" xc:"$dark" \
    +noise gaussian \
    -blur 0x1 \
    -modulate 100,20,100 \
    +level-colors "${dark},${BASE01}" \
    "$output_file"
}

generate_gradient() {
  local dark
  dark=$(darken_color "$BASE00" 30)

  magick -size "${width}x${height}" \
    -define gradient:angle=135 \
    gradient:"${dark}-${BASE00}" \
    "$output_file"
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
  noise)
    generate_noise
    ;;
  gradient)
    generate_gradient
    ;;
  *)
    echo "Unknown style: $style"
    echo "Valid styles: plasma, geometric, hexagons, circles, noise, gradient"
    exit 1
    ;;
esac

echo "Generated: $output_file (${width}x${height}, style: $style)"
