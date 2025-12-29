#!/usr/bin/env bash
# Generate tmux config from palette.yml
# Usage: tmux.sh <palette.yml> [output-file]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../palette.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <palette.yml> [output-file]"
  exit 1
fi

palette_file="$1"
output_file="${2:-}"

# Load palette into variables
eval "$(load_palette "$palette_file")"

generate() {
  cat << EOF
# ${THEME_NAME} - tmux theme
# Generated from palette.yml
# Author: ${THEME_AUTHOR}

# Default statusbar colors
# base01 = lighter background (perfect for status bar)
# base04 = dark foreground (status bar text)
set-option -g status-style "fg=${BASE04},bg=${BASE01}"

# Default window title colors
set-window-option -g window-status-style "fg=${BASE04},bg=${BASE01}"

# Active window title colors
# base0A = yellow accent for current window
set-window-option -g window-status-current-style "fg=${BASE0A},bg=${BASE01}"

# Pane border colors
# base01 = subtle border, base04 = visible active border
set-option -g pane-border-style "fg=${BASE01}"
set-option -g pane-active-border-style "fg=${BASE04}"

# Message text colors
# base06 = light foreground, base02 = selection background
set-option -g message-style "fg=${BASE06},bg=${BASE02}"

# Pane number display colors
set-option -g display-panes-active-colour "${BASE04}"
set-option -g display-panes-colour "${BASE01}"

# Clock color
# base0D = blue
set-window-option -g clock-mode-colour "${BASE0D}"

# Copy mode highlight
# base04 = dark foreground, base02 = selection background
set-window-option -g mode-style "fg=${BASE04},bg=${BASE02}"

# Bell style
# base08 = red for alerts
set-window-option -g window-status-bell-style "fg=${BASE00},bg=${BASE08}"

# Activity style
set-window-option -g window-status-activity-style "fg=${BASE05},bg=${BASE01}"

# Command message style
set-option -g message-command-style "fg=${BASE06},bg=${BASE02}"

# vim: set ft=tmux tw=0:
EOF
}

if [[ -n "$output_file" ]]; then
  generate > "$output_file"
  echo "Generated: $output_file"
else
  generate
fi
