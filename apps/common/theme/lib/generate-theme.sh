#!/usr/bin/env bash
# Generate all app configs for a theme directory
# Usage: generate-theme.sh <theme-dir>
#
# Expects theme-dir to contain theme.yml
# Generates: ghostty.conf, alacritty.toml, kitty.conf, tmux.conf, btop.theme

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENERATORS_DIR="$SCRIPT_DIR/generators"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <theme-dir>"
  echo "  theme-dir: Directory containing theme.yml"
  exit 1
fi

theme_dir="$1"
theme_file="$theme_dir/theme.yml"

if [[ ! -f "$theme_file" ]]; then
  echo "Error: theme.yml not found in $theme_dir"
  exit 1
fi

echo "Generating configs for: $theme_dir"

# Generate each config
declare -A generators=(
  ["ghostty.conf"]="ghostty.sh"
  ["alacritty.toml"]="alacritty.sh"
  ["kitty.conf"]="kitty.sh"
  ["tmux.conf"]="tmux.sh"
  ["btop.theme"]="btop.sh"
)

for output in "${!generators[@]}"; do
  generator="${generators[$output]}"
  generator_path="$GENERATORS_DIR/$generator"
  output_path="$theme_dir/$output"

  if [[ -x "$generator_path" ]]; then
    bash "$generator_path" "$theme_file" "$output_path"
  else
    echo "  Skipped: $output (generator not found)"
  fi
done

echo "Done!"
