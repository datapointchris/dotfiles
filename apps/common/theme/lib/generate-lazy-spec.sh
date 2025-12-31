#!/usr/bin/env bash
# Generate Lazy.nvim plugin spec for all themes
# Usage: generate-lazy-spec.sh [themes-dir] [output-file]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THEME_DIR="${1:-$SCRIPT_DIR/../themes}"
OUTPUT_FILE="${2:-$THEME_DIR/lazy-colorschemes.lua}"

source "$SCRIPT_DIR/theme.sh"

cat > "$OUTPUT_FILE" << 'HEADER'
-- Generated colorschemes from theme system
-- Add this to your Lazy.nvim plugins or require it from your plugin config
--
-- Usage in your Neovim config:
--   require("lazy").setup({
--     { import = "plugins" },
--     require("path.to.lazy-colorschemes"),  -- Add generated themes
--   })
--
-- Or copy individual entries to your colorscheme config

local themes_dir = vim.fn.expand("~/dotfiles/apps/common/theme/themes")

return {
HEADER

# Find all themes with neovim directories
for theme_dir in "$THEME_DIR"/*/; do
  theme_name=$(basename "$theme_dir")
  theme_file="$theme_dir/theme.yml"
  neovim_dir="$theme_dir/neovim"

  # Skip if no neovim colorscheme
  if [[ ! -d "$neovim_dir" ]]; then
    continue
  fi

  # Get metadata from theme.yml
  if [[ -f "$theme_file" ]]; then
    name=$(yq -r '.meta.display_name // ""' "$theme_file")
    source=$(yq -r '.meta.derived_from // ""' "$theme_file")
  else
    name="$theme_name"
    source="unknown"
  fi

  # Generate entry
  cat >> "$OUTPUT_FILE" << EOF
  -- ${name} - ${source} variant
  {
    dir = themes_dir .. "/${theme_name}/neovim",
    name = "${theme_name}",
    lazy = true,
    priority = 1000,
  },

EOF
done

# Close the return table
echo "}" >> "$OUTPUT_FILE"

echo "Generated: $OUTPUT_FILE"
