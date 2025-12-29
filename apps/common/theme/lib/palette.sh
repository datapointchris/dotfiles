#!/usr/bin/env bash
# palette.sh - Common functions for reading palette.yml files
# Sources palette colors into shell variables for use by generators

set -euo pipefail

# Read a value from palette.yml using yq
# Usage: palette_get <key> <palette_file>
palette_get() {
  local key="$1"
  local file="$2"
  yq -r "$key // \"\"" "$file"
}

# Load all palette colors into shell variables
# Usage: source <(load_palette palette.yml)
load_palette() {
  local file="$1"

  if [[ ! -f "$file" ]]; then
    echo "Error: Palette file not found: $file" >&2
    return 1
  fi

  # Metadata
  echo "THEME_NAME=\"$(palette_get '.name' "$file")\""
  echo "THEME_AUTHOR=\"$(palette_get '.author' "$file")\""
  echo "THEME_VARIANT=\"$(palette_get '.variant' "$file")\""

  # Base16 palette
  echo "BASE00=\"$(palette_get '.palette.base00' "$file")\""
  echo "BASE01=\"$(palette_get '.palette.base01' "$file")\""
  echo "BASE02=\"$(palette_get '.palette.base02' "$file")\""
  echo "BASE03=\"$(palette_get '.palette.base03' "$file")\""
  echo "BASE04=\"$(palette_get '.palette.base04' "$file")\""
  echo "BASE05=\"$(palette_get '.palette.base05' "$file")\""
  echo "BASE06=\"$(palette_get '.palette.base06' "$file")\""
  echo "BASE07=\"$(palette_get '.palette.base07' "$file")\""
  echo "BASE08=\"$(palette_get '.palette.base08' "$file")\""
  echo "BASE09=\"$(palette_get '.palette.base09' "$file")\""
  echo "BASE0A=\"$(palette_get '.palette.base0A' "$file")\""
  echo "BASE0B=\"$(palette_get '.palette.base0B' "$file")\""
  echo "BASE0C=\"$(palette_get '.palette.base0C' "$file")\""
  echo "BASE0D=\"$(palette_get '.palette.base0D' "$file")\""
  echo "BASE0E=\"$(palette_get '.palette.base0E' "$file")\""
  echo "BASE0F=\"$(palette_get '.palette.base0F' "$file")\""

  # ANSI colors (with fallbacks to base16)
  local ansi_black ansi_red ansi_green ansi_yellow ansi_blue ansi_magenta ansi_cyan ansi_white
  ansi_black=$(palette_get '.ansi.black' "$file")
  ansi_red=$(palette_get '.ansi.red' "$file")
  ansi_green=$(palette_get '.ansi.green' "$file")
  ansi_yellow=$(palette_get '.ansi.yellow' "$file")
  ansi_blue=$(palette_get '.ansi.blue' "$file")
  ansi_magenta=$(palette_get '.ansi.magenta' "$file")
  ansi_cyan=$(palette_get '.ansi.cyan' "$file")
  ansi_white=$(palette_get '.ansi.white' "$file")

  echo "ANSI_BLACK=\"${ansi_black:-\$BASE00}\""
  echo "ANSI_RED=\"${ansi_red:-\$BASE08}\""
  echo "ANSI_GREEN=\"${ansi_green:-\$BASE0B}\""
  echo "ANSI_YELLOW=\"${ansi_yellow:-\$BASE0A}\""
  echo "ANSI_BLUE=\"${ansi_blue:-\$BASE0D}\""
  echo "ANSI_MAGENTA=\"${ansi_magenta:-\$BASE0E}\""
  echo "ANSI_CYAN=\"${ansi_cyan:-\$BASE0C}\""
  echo "ANSI_WHITE=\"${ansi_white:-\$BASE05}\""

  # Bright ANSI colors
  local bright_black bright_red bright_green bright_yellow bright_blue bright_magenta bright_cyan bright_white
  bright_black=$(palette_get '.ansi.bright_black' "$file")
  bright_red=$(palette_get '.ansi.bright_red' "$file")
  bright_green=$(palette_get '.ansi.bright_green' "$file")
  bright_yellow=$(palette_get '.ansi.bright_yellow' "$file")
  bright_blue=$(palette_get '.ansi.bright_blue' "$file")
  bright_magenta=$(palette_get '.ansi.bright_magenta' "$file")
  bright_cyan=$(palette_get '.ansi.bright_cyan' "$file")
  bright_white=$(palette_get '.ansi.bright_white' "$file")

  echo "ANSI_BRIGHT_BLACK=\"${bright_black:-\$BASE03}\""
  echo "ANSI_BRIGHT_RED=\"${bright_red:-\$BASE08}\""
  echo "ANSI_BRIGHT_GREEN=\"${bright_green:-\$BASE0B}\""
  echo "ANSI_BRIGHT_YELLOW=\"${bright_yellow:-\$BASE0A}\""
  echo "ANSI_BRIGHT_BLUE=\"${bright_blue:-\$BASE0D}\""
  echo "ANSI_BRIGHT_MAGENTA=\"${bright_magenta:-\$BASE0E}\""
  echo "ANSI_BRIGHT_CYAN=\"${bright_cyan:-\$BASE0C}\""
  echo "ANSI_BRIGHT_WHITE=\"${bright_white:-\$BASE07}\""

  # Special colors (with fallbacks)
  local bg fg cursor cursor_text sel_bg sel_fg
  bg=$(palette_get '.special.background' "$file")
  fg=$(palette_get '.special.foreground' "$file")
  cursor=$(palette_get '.special.cursor' "$file")
  cursor_text=$(palette_get '.special.cursor_text' "$file")
  sel_bg=$(palette_get '.special.selection_bg' "$file")
  sel_fg=$(palette_get '.special.selection_fg' "$file")

  echo "SPECIAL_BG=\"${bg:-\$BASE00}\""
  echo "SPECIAL_FG=\"${fg:-\$BASE05}\""
  echo "SPECIAL_CURSOR=\"${cursor:-\$BASE05}\""
  echo "SPECIAL_CURSOR_TEXT=\"${cursor_text:-\$BASE00}\""
  echo "SPECIAL_SELECTION_BG=\"${sel_bg:-\$BASE02}\""
  echo "SPECIAL_SELECTION_FG=\"${sel_fg:-\$BASE05}\""
}

# Convert color to uppercase (for btop)
to_upper() {
  echo "$1" | tr '[:lower:]' '[:upper:]'
}
