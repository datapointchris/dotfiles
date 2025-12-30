#!/usr/bin/env bash
# Generate dunst notification color config from theme.yml
# Usage: dunst.sh <theme.yml> [output-file]
#
# Outputs [urgency_*] sections for dunst.
# Note: Dunst doesn't support includes, so apply function will
# need to update dunstrc directly or replace these sections.

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
# ${THEME_NAME} - Dunst notification colors
# Generated from theme.yml

[urgency_low]
    background = "${SPECIAL_BG}"
    foreground = "${SPECIAL_FG}"
    frame_color = "${ANSI_BLUE}"
    timeout = 5

[urgency_normal]
    background = "${SPECIAL_BG}"
    foreground = "${SPECIAL_FG}"
    frame_color = "${ANSI_BLUE}"
    timeout = 10

[urgency_critical]
    background = "${SPECIAL_BG}"
    foreground = "${SPECIAL_FG}"
    frame_color = "${ANSI_RED}"
    timeout = 0
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
