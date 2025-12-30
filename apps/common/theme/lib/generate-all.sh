#!/usr/bin/env bash
# Generate all app configs from a palette.yml file
# Usage: generate-all.sh <theme-dir>
#
# Expects theme-dir to contain palette.yml
# Generates: ghostty.conf, kitty.conf, tmux.conf, btop.theme,
#            alacritty.toml, hyprland.conf, waybar.css

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENERATORS_DIR="$SCRIPT_DIR/generators"

usage() {
  echo "Usage: $0 <theme-dir>"
  echo ""
  echo "Generate all app configs from palette.yml"
  echo ""
  echo "Arguments:"
  echo "  theme-dir    Directory containing palette.yml"
  echo ""
  echo "Example:"
  echo "  $0 library/nord"
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

theme_dir="$1"
palette_file="$theme_dir/palette.yml"

if [[ ! -f "$palette_file" ]]; then
  echo "Error: palette.yml not found in $theme_dir" >&2
  exit 1
fi

theme_name=$(yq -r '.name' "$palette_file")
echo "Generating configs for: $theme_name"
echo ""

# Generate each app config
generate_app() {
  local app="$1"
  local ext="$2"
  local generator="$GENERATORS_DIR/${app}.sh"
  local output="$theme_dir/${app}.${ext}"

  if [[ -f "$generator" ]]; then
    "$generator" "$palette_file" "$output"
  else
    echo "  Skipping $app (no generator)"
  fi
}

# Terminal emulators
generate_app "ghostty" "conf"
generate_app "kitty" "conf"
generate_app "alacritty" "toml"

# TUI apps
generate_app "tmux" "conf"
generate_app "btop" "theme"

# Desktop environment (Arch/Hyprland)
generate_app "hyprland" "conf"
generate_app "waybar" "css"
generate_app "hyprlock" "conf"
generate_app "mako" "ini"
generate_app "walker" "css"
generate_app "swayosd" "css"

echo ""
echo "Done! Generated configs in: $theme_dir"
