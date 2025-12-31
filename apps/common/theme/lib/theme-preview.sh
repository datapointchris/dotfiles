#!/usr/bin/env bash
# Theme preview for fzf - displays colors using ANSI 24-bit escape codes
# Usage: theme-preview.sh <theme-directory>

set -euo pipefail

theme_dir="$1"
theme_file="$theme_dir/theme.yml"

if [[ ! -f "$theme_file" ]]; then
  echo "Theme file not found: $theme_file"
  exit 1
fi

# Preview width (characters)
WIDTH=56

# Read metadata
name=$(yq '.meta.display_name // "Unknown"' "$theme_file")
author=$(yq '.meta.author // "Unknown"' "$theme_file")
variant=$(yq '.meta.variant // "dark"' "$theme_file")
neovim_cs=$(yq '.meta.neovim_colorscheme_name // .meta.id // "unknown"' "$theme_file")

# Read special colors
theme_bg=$(yq '.special.background // "#1a1a1a"' "$theme_file")
theme_fg=$(yq '.special.foreground // "#ffffff"' "$theme_file")
theme_cursor=$(yq '.special.cursor // "#ffffff"' "$theme_file")
theme_selection_bg=$(yq '.special.selection_bg // "#444444"' "$theme_file")
theme_border=$(yq '.special.border // "#555555"' "$theme_file")

# Read ANSI colors
black=$(yq '.ansi.black // "#000000"' "$theme_file")
red=$(yq '.ansi.red // "#ff0000"' "$theme_file")
green=$(yq '.ansi.green // "#00ff00"' "$theme_file")
yellow=$(yq '.ansi.yellow // "#ffff00"' "$theme_file")
blue=$(yq '.ansi.blue // "#0000ff"' "$theme_file")
magenta=$(yq '.ansi.magenta // "#ff00ff"' "$theme_file")
cyan=$(yq '.ansi.cyan // "#00ffff"' "$theme_file")
white=$(yq '.ansi.white // "#ffffff"' "$theme_file")

bright_black=$(yq '.ansi.bright_black // "#808080"' "$theme_file")
bright_red=$(yq '.ansi.bright_red // "#ff8080"' "$theme_file")
bright_green=$(yq '.ansi.bright_green // "#80ff80"' "$theme_file")
bright_yellow=$(yq '.ansi.bright_yellow // "#ffff80"' "$theme_file")
bright_blue=$(yq '.ansi.bright_blue // "#8080ff"' "$theme_file")
bright_magenta=$(yq '.ansi.bright_magenta // "#ff80ff"' "$theme_file")
bright_cyan=$(yq '.ansi.bright_cyan // "#80ffff"' "$theme_file")
bright_white=$(yq '.ansi.bright_white // "#ffffff"' "$theme_file")

# Read base16 colors
base00=$(yq '.base16.base00 // "#000000"' "$theme_file")
base01=$(yq '.base16.base01 // "#111111"' "$theme_file")
base02=$(yq '.base16.base02 // "#222222"' "$theme_file")
base03=$(yq '.base16.base03 // "#333333"' "$theme_file")
base04=$(yq '.base16.base04 // "#444444"' "$theme_file")
base05=$(yq '.base16.base05 // "#555555"' "$theme_file")
base06=$(yq '.base16.base06 // "#666666"' "$theme_file")
base07=$(yq '.base16.base07 // "#777777"' "$theme_file")
base08=$(yq '.base16.base08 // "#ff0000"' "$theme_file")
base09=$(yq '.base16.base09 // "#ff8000"' "$theme_file")
base0A=$(yq '.base16.base0A // "#ffff00"' "$theme_file")
base0B=$(yq '.base16.base0B // "#00ff00"' "$theme_file")
base0C=$(yq '.base16.base0C // "#00ffff"' "$theme_file")
base0D=$(yq '.base16.base0D // "#0080ff"' "$theme_file")
base0E=$(yq '.base16.base0E // "#ff00ff"' "$theme_file")
base0F=$(yq '.base16.base0F // "#804000"' "$theme_file")

# Read extended/semantic colors with fallbacks
syntax_comment=$(yq '.extended.syntax_comment // .ansi.bright_black // "#808080"' "$theme_file")
syntax_string=$(yq '.extended.syntax_string // .ansi.green // "#00ff00"' "$theme_file")
syntax_keyword=$(yq '.extended.syntax_keyword // .ansi.magenta // "#ff00ff"' "$theme_file")
syntax_function=$(yq '.extended.syntax_function // .ansi.blue // "#0000ff"' "$theme_file")
syntax_number=$(yq '.extended.syntax_number // .ansi.cyan // "#00ffff"' "$theme_file")
syntax_type=$(yq '.extended.syntax_type // .ansi.yellow // "#ffff00"' "$theme_file")
syntax_operator=$(yq '.extended.syntax_operator // .ansi.yellow // "#ffff00"' "$theme_file")

# Git/diagnostic colors
git_add=$(yq '.extended.git_add // .ansi.green // "#00ff00"' "$theme_file")
git_change=$(yq '.extended.git_change // .ansi.yellow // "#ffff00"' "$theme_file")
git_delete=$(yq '.extended.git_delete // .ansi.red // "#ff0000"' "$theme_file")
diag_error=$(yq '.extended.diagnostic_error // .ansi.red // "#ff0000"' "$theme_file")
diag_warning=$(yq '.extended.diagnostic_warning // .ansi.yellow // "#ffff00"' "$theme_file")
diag_info=$(yq '.extended.diagnostic_info // .ansi.blue // "#0000ff"' "$theme_file")
diag_hint=$(yq '.extended.diagnostic_hint // .ansi.cyan // "#00ffff"' "$theme_file")

# ANSI escape helpers
reset=$'\033[0m'
bold=$'\033[1m'

# Convert hex to ANSI - fg with theme bg
c() {
  local hex="${1#\#}"
  local bg_hex="${theme_bg#\#}"
  printf '\033[38;2;%d;%d;%d;48;2;%d;%d;%dm' \
    "0x${hex:0:2}" "0x${hex:2:2}" "0x${hex:4:2}" \
    "0x${bg_hex:0:2}" "0x${bg_hex:2:2}" "0x${bg_hex:4:2}"
}

# Background only
bg() {
  local hex="${1#\#}"
  printf '\033[48;2;%d;%d;%dm' "0x${hex:0:2}" "0x${hex:2:2}" "0x${hex:4:2}"
}

# Pre-compute common color combos (fg color on theme bg)
C_FG="$(c "$theme_fg")"
C_DIM="$(c "$base03")"
C_KW="$(c "$syntax_keyword")"
C_FN="$(c "$syntax_function")"
C_TY="$(c "$syntax_type")"
C_ST="$(c "$syntax_string")"
C_NU="$(c "$syntax_number")"
C_CM="$(c "$syntax_comment")"
C_OP="$(c "$syntax_operator")"
C_ERR="$(c "$diag_error")"
C_WRN="$(c "$diag_warning")"
C_INF="$(c "$diag_info")"
C_HNT="$(c "$diag_hint")"
C_ADD="$(c "$git_add")"
C_CHG="$(c "$git_change")"
C_DEL="$(c "$git_delete")"
BG="$(bg "$theme_bg")"

# Print line with theme background, padded to WIDTH
p() {
  local text="$1"
  # Print: bg + text + padding + reset
  printf '%s' "$BG"
  printf '%s' "$text"
  # Pad with spaces (crude but works - just print extra spaces)
  printf '%*s' $((WIDTH - ${#text} + 40)) ""
  printf '%s\n' "$reset"
}

# Print a color swatch block
s() {
  printf '%s  %s' "$(bg "$1")" "$BG"
}

# Output all lines
p ""
p "${C_FG}${bold} $name${reset}${BG}"
p "${C_DIM} Author: $author"
p "${C_DIM} Variant: $variant | Neovim: $neovim_cs"
p ""
p "${C_FG}${bold} Special${reset}${BG}"
p " $(s "$theme_bg")${C_DIM}bg $(s "$theme_fg")${C_DIM}fg $(s "$theme_cursor")${C_DIM}cur $(s "$theme_selection_bg")${C_DIM}sel $(s "$theme_border")${C_DIM}bdr"
p ""
p "${C_FG}${bold} ANSI Normal${reset}${BG}"
p " $(s "$black")$(s "$red")$(s "$green")$(s "$yellow")$(s "$blue")$(s "$magenta")$(s "$cyan")$(s "$white")${C_DIM} 0-7"
p ""
p "${C_FG}${bold} ANSI Bright${reset}${BG}"
p " $(s "$bright_black")$(s "$bright_red")$(s "$bright_green")$(s "$bright_yellow")$(s "$bright_blue")$(s "$bright_magenta")$(s "$bright_cyan")$(s "$bright_white")${C_DIM} 8-15"
p ""
p "${C_FG}${bold} Base16${reset}${BG}"
p " $(s "$base00")$(s "$base01")$(s "$base02")$(s "$base03")$(s "$base04")$(s "$base05")$(s "$base06")$(s "$base07")${C_DIM} 00-07"
p " $(s "$base08")$(s "$base09")$(s "$base0A")$(s "$base0B")$(s "$base0C")$(s "$base0D")$(s "$base0E")$(s "$base0F")${C_DIM} 08-0F"
p ""
p "${C_FG}${bold} Syntax${reset}${BG}"
p " ${C_KW}keyword ${C_FN}func ${C_TY}Type ${C_ST}\"str\" ${C_NU}42 ${C_CM}# comment"
p ""
p "${C_FG}${bold} Diagnostics${reset}${BG} ${C_ERR}err ${C_WRN}warn ${C_INF}info ${C_HNT}hint"
p "${C_FG}${bold} Git${reset}${BG}         ${C_ADD}+add ${C_CHG}~chg ${C_DEL}-del"
p ""
p "${C_FG}${bold} Code Sample${reset}${BG}"
p "${C_CM}  # Configuration module"
p "${C_KW}  from ${C_TY}typing ${C_KW}import ${C_TY}Dict"
p ""
p "${C_KW}  class ${C_TY}Config${C_FG}:"
p "${C_ST}      \"\"\"App config.\"\"\""
p "${C_FG}      VERSION ${C_OP}= ${C_ST}\"1.0\""
p ""
p "${C_KW}      def ${C_FN}__init__${C_FG}(self, name):"
p "${C_FG}          self.name ${C_OP}= ${C_FG}name"
p "${C_FG}          self.count ${C_OP}= ${C_NU}42"
p ""
p "${C_KW}      def ${C_FN}validate${C_FG}(self):"
p "${C_KW}          return ${C_FG}self.count ${C_OP}> ${C_NU}0"
p ""
