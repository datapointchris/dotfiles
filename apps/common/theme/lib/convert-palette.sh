#!/usr/bin/env bash
# Convert palette.yml to theme.yml format
# Usage: convert-palette.sh <library-theme-dir> <output-theme-dir>

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <library-theme-dir> <output-theme-dir>"
  exit 1
fi

src_dir="$1"
dst_dir="$2"
palette_file="$src_dir/palette.yml"

if [[ ! -f "$palette_file" ]]; then
  echo "Error: $palette_file not found"
  exit 1
fi

mkdir -p "$dst_dir"

# Extract metadata
name=$(yq -r '.name // ""' "$palette_file")
author=$(yq -r '.author // "Unknown"' "$palette_file")
variant=$(yq -r '.variant // "dark"' "$palette_file")
source=$(yq -r '.source // "Ghostty built-in theme"' "$palette_file")
slug=$(basename "$dst_dir")

# For neovim_colorscheme, use slug but check for known mappings
neovim_colorscheme="$slug"

# Generate theme.yml
cat > "$dst_dir/theme.yml" << EOF
meta:
  name: "$name"
  slug: "$slug"
  neovim_colorscheme: "$neovim_colorscheme"
  author: "$author"
  variant: "$variant"
  source: "$source"

base16:
$(yq -r '.palette | to_entries | .[] | "  " + .key + ": \"" + .value + "\""' "$palette_file")

ansi:
$(yq -r '.ansi | to_entries | .[] | "  " + .key + ": \"" + .value + "\""' "$palette_file")

special:
$(yq -r '.special | to_entries | .[] | "  " + .key + ": \"" + .value + "\""' "$palette_file")
EOF

echo "Converted: $dst_dir/theme.yml"
