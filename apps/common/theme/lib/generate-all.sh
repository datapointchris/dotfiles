#!/usr/bin/env bash
# Generate all app configs from a theme.yml file
# Usage: generate-all.sh <theme-dir>
#
# Expects theme-dir to contain theme.yml
# Generates configs for: terminals, TUI apps, Hyprland desktop environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENERATORS_DIR="$SCRIPT_DIR/generators"

usage() {
  echo "Usage: $0 <theme-dir>"
  echo ""
  echo "Generate all app configs from theme.yml"
  echo ""
  echo "Arguments:"
  echo "  theme-dir    Directory containing theme.yml"
  echo ""
  echo "Example:"
  echo "  $0 themes/kanagawa"
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

theme_dir="$1"
theme_file="$theme_dir/theme.yml"

if [[ ! -f "$theme_file" ]]; then
  echo "Error: theme.yml not found in $theme_dir" >&2
  exit 1
fi

theme_name=$(yq -r '.meta.display_name' "$theme_file")
echo "Generating configs for: $theme_name"
echo ""

# Generate each app config
generate_app() {
  local app="$1"
  local ext="$2"
  local generator="$GENERATORS_DIR/${app}.sh"
  local output="$theme_dir/${app}.${ext}"

  if [[ -f "$generator" ]]; then
    "$generator" "$theme_file" "$output"
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
generate_app "rofi" "rasi"
generate_app "dunst" "conf"
generate_app "mako" "ini"
generate_app "walker" "css"
generate_app "swayosd" "css"

echo ""
echo "Done! Generated configs in: $theme_dir"
