#!/usr/bin/env bash
# Generate Windows Terminal color scheme from theme.yml
# Usage: windows-terminal.sh <theme.yml> [output-file]
#
# Outputs JSON color scheme for Windows Terminal settings.json "schemes" array.
# Note: Windows Terminal uses "purple" instead of "magenta".

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../theme.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <theme.yml> [output-file]"
  exit 1
fi

input_file="$1"
output_file="${2:-}"

eval "$(load_colors "$input_file")"

generate() {
  cat << EOF
{
  "name": "${THEME_NAME}",
  "background": "${SPECIAL_BG}",
  "foreground": "${SPECIAL_FG}",
  "cursorColor": "${SPECIAL_CURSOR}",
  "selectionBackground": "${SPECIAL_SELECTION_BG}",
  "black": "${ANSI_BLACK}",
  "red": "${ANSI_RED}",
  "green": "${ANSI_GREEN}",
  "yellow": "${ANSI_YELLOW}",
  "blue": "${ANSI_BLUE}",
  "purple": "${ANSI_MAGENTA}",
  "cyan": "${ANSI_CYAN}",
  "white": "${ANSI_WHITE}",
  "brightBlack": "${ANSI_BRIGHT_BLACK}",
  "brightRed": "${ANSI_BRIGHT_RED}",
  "brightGreen": "${ANSI_BRIGHT_GREEN}",
  "brightYellow": "${ANSI_BRIGHT_YELLOW}",
  "brightBlue": "${ANSI_BRIGHT_BLUE}",
  "brightPurple": "${ANSI_BRIGHT_MAGENTA}",
  "brightCyan": "${ANSI_BRIGHT_CYAN}",
  "brightWhite": "${ANSI_BRIGHT_WHITE}"
}
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
