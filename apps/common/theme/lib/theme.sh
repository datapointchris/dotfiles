#!/usr/bin/env bash
# theme.sh - Functions for reading theme.yml files
# Sources theme colors into shell variables for use by generators

set -euo pipefail

# Read a value from theme.yml using yq
# Usage: theme_get <key> <theme_file>
theme_get() {
  local key="$1"
  local file="$2"
  yq -r "$key // \"\"" "$file"
}

# Load all theme colors into shell variables
# Usage: eval "$(load_theme theme.yml)"
# Outputs same variable names as palette.sh for compatibility with generators
load_theme() {
  local file="$1"

  if [[ ! -f "$file" ]]; then
    echo "Error: Theme file not found: $file" >&2
    return 1
  fi

  # Metadata (from meta section)
  echo "THEME_NAME=\"$(theme_get '.meta.display_name' "$file")\""
  echo "THEME_AUTHOR=\"$(theme_get '.meta.author' "$file")\""
  echo "THEME_VARIANT=\"$(theme_get '.meta.variant' "$file")\""
  echo "THEME_SOURCE=\"$(theme_get '.meta.derived_from' "$file")\""
  echo "THEME_SLUG=\"$(theme_get '.meta.id' "$file")\""

  # Base16 palette (from base16 section, not palette)
  echo "BASE00=\"$(theme_get '.base16.base00' "$file")\""
  echo "BASE01=\"$(theme_get '.base16.base01' "$file")\""
  echo "BASE02=\"$(theme_get '.base16.base02' "$file")\""
  echo "BASE03=\"$(theme_get '.base16.base03' "$file")\""
  echo "BASE04=\"$(theme_get '.base16.base04' "$file")\""
  echo "BASE05=\"$(theme_get '.base16.base05' "$file")\""
  echo "BASE06=\"$(theme_get '.base16.base06' "$file")\""
  echo "BASE07=\"$(theme_get '.base16.base07' "$file")\""
  echo "BASE08=\"$(theme_get '.base16.base08' "$file")\""
  echo "BASE09=\"$(theme_get '.base16.base09' "$file")\""
  echo "BASE0A=\"$(theme_get '.base16.base0A' "$file")\""
  echo "BASE0B=\"$(theme_get '.base16.base0B' "$file")\""
  echo "BASE0C=\"$(theme_get '.base16.base0C' "$file")\""
  echo "BASE0D=\"$(theme_get '.base16.base0D' "$file")\""
  echo "BASE0E=\"$(theme_get '.base16.base0E' "$file")\""
  echo "BASE0F=\"$(theme_get '.base16.base0F' "$file")\""

  # ANSI colors (same structure as palette.yml)
  local ansi_black ansi_red ansi_green ansi_yellow ansi_blue ansi_magenta ansi_cyan ansi_white
  ansi_black=$(theme_get '.ansi.black' "$file")
  ansi_red=$(theme_get '.ansi.red' "$file")
  ansi_green=$(theme_get '.ansi.green' "$file")
  ansi_yellow=$(theme_get '.ansi.yellow' "$file")
  ansi_blue=$(theme_get '.ansi.blue' "$file")
  ansi_magenta=$(theme_get '.ansi.magenta' "$file")
  ansi_cyan=$(theme_get '.ansi.cyan' "$file")
  ansi_white=$(theme_get '.ansi.white' "$file")

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
  bright_black=$(theme_get '.ansi.bright_black' "$file")
  bright_red=$(theme_get '.ansi.bright_red' "$file")
  bright_green=$(theme_get '.ansi.bright_green' "$file")
  bright_yellow=$(theme_get '.ansi.bright_yellow' "$file")
  bright_blue=$(theme_get '.ansi.bright_blue' "$file")
  bright_magenta=$(theme_get '.ansi.bright_magenta' "$file")
  bright_cyan=$(theme_get '.ansi.bright_cyan' "$file")
  bright_white=$(theme_get '.ansi.bright_white' "$file")

  echo "ANSI_BRIGHT_BLACK=\"${bright_black:-\$BASE03}\""
  echo "ANSI_BRIGHT_RED=\"${bright_red:-\$BASE08}\""
  echo "ANSI_BRIGHT_GREEN=\"${bright_green:-\$BASE0B}\""
  echo "ANSI_BRIGHT_YELLOW=\"${bright_yellow:-\$BASE0A}\""
  echo "ANSI_BRIGHT_BLUE=\"${bright_blue:-\$BASE0D}\""
  echo "ANSI_BRIGHT_MAGENTA=\"${bright_magenta:-\$BASE0E}\""
  echo "ANSI_BRIGHT_CYAN=\"${bright_cyan:-\$BASE0C}\""
  echo "ANSI_BRIGHT_WHITE=\"${bright_white:-\$BASE07}\""

  # Special colors (with fallbacks)
  local bg fg cursor cursor_text sel_bg sel_fg border panel
  bg=$(theme_get '.special.background' "$file")
  fg=$(theme_get '.special.foreground' "$file")
  cursor=$(theme_get '.special.cursor' "$file")
  cursor_text=$(theme_get '.special.cursor_text' "$file")
  sel_bg=$(theme_get '.special.selection_bg' "$file")
  sel_fg=$(theme_get '.special.selection_fg' "$file")
  border=$(theme_get '.special.border' "$file")
  panel=$(theme_get '.special.panel' "$file")

  echo "SPECIAL_BG=\"${bg:-\$BASE00}\""
  echo "SPECIAL_FG=\"${fg:-\$BASE05}\""
  echo "SPECIAL_CURSOR=\"${cursor:-\$BASE05}\""
  echo "SPECIAL_CURSOR_TEXT=\"${cursor_text:-\$BASE00}\""
  echo "SPECIAL_SELECTION_BG=\"${sel_bg:-\$BASE02}\""
  echo "SPECIAL_SELECTION_FG=\"${sel_fg:-\$BASE05}\""
  echo "SPECIAL_BORDER=\"${border:-\$BASE03}\""
  echo "SPECIAL_PANEL=\"${panel:-\$BASE01}\""

  # Extended colors (new in theme.yml)
  # These are optional and used by some generators
  local extended_keys
  extended_keys=$(theme_get '.extended | keys | .[]' "$file" 2>/dev/null || echo "")

  for key in $extended_keys; do
    local value
    value=$(theme_get ".extended.${key}" "$file")
    local var_name
    var_name=$(echo "EXTENDED_${key}" | tr '[:lower:]' '[:upper:]')
    echo "${var_name}=\"${value}\""
  done
}

# Load colors from theme.yml (alias for load_theme)
load_colors() {
  load_theme "$1"
}

# Convert color to uppercase (for btop)
to_upper() {
  echo "$1" | tr '[:lower:]' '[:upper:]'
}
