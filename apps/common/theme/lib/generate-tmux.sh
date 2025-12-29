#!/usr/bin/env bash
# Generate tmux.conf from Ghostty theme colors
# Usage: generate-tmux.sh <ghostty-theme-name> [output-file]

set -euo pipefail

GHOSTTY_THEMES="/Applications/Ghostty.app/Contents/Resources/ghostty/themes"

usage() {
  echo "Usage: $0 <ghostty-theme-name> [output-file]"
  echo ""
  echo "Examples:"
  echo "  $0 Smyck                    # Print to stdout"
  echo "  $0 Smyck tmux.conf          # Write to file"
  echo ""
  echo "Available themes in: $GHOSTTY_THEMES"
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

theme_name="$1"
output_file="${2:-}"
theme_path="$GHOSTTY_THEMES/$theme_name"

if [[ ! -f "$theme_path" ]]; then
  echo "Error: Theme not found: $theme_path" >&2
  exit 1
fi

# Extract colors from Ghostty theme
get_color() {
  local key="$1"
  grep "^${key} = " "$theme_path" | cut -d= -f2 | xargs
}

get_palette() {
  local index="$1"
  grep "^palette = ${index}=#" "$theme_path" | cut -d= -f3
}

# Extract base colors
bg=$(get_color "background")
fg=$(get_color "foreground")

# Palette colors (base16-style mapping)
# shellcheck disable=SC2034  # Some colors extracted but not used in current tmux config
color0=$(get_palette 0)   # black
color1=$(get_palette 1)   # red
_color2=$(get_palette 2)   # green # shellcheck disable=SC2034
color3=$(get_palette 3)   # yellow
color4=$(get_palette 4)   # blue
_color5=$(get_palette 5)   # magenta # shellcheck disable=SC2034
_color6=$(get_palette 6)   # cyan # shellcheck disable=SC2034
color7=$(get_palette 7)   # white
color8=$(get_palette 8)   # bright black
_color9=$(get_palette 9)   # bright red # shellcheck disable=SC2034
_color10=$(get_palette 10) # bright green # shellcheck disable=SC2034
_color11=$(get_palette 11) # bright yellow # shellcheck disable=SC2034
_color12=$(get_palette 12) # bright blue # shellcheck disable=SC2034
_color13=$(get_palette 13) # bright magenta # shellcheck disable=SC2034
_color14=$(get_palette 14) # bright cyan # shellcheck disable=SC2034
color15=$(get_palette 15) # bright white

# Use darker color for status bar background (color8 or color0)
status_bg="${color8:-$color0}"
# Use lighter color for active elements
status_fg="${color7:-$fg}"
# Accent color for highlights (yellow or blue)
accent="${color3:-$color4}"

generate_tmux() {
  cat << EOF
# ${theme_name} tmux theme
# Generated from Ghostty theme

# default statusbar colors
set-option -g status-style "fg=${status_fg},bg=${status_bg}"

# default window title colors
set-window-option -g window-status-style "fg=${status_fg},bg=${status_bg}"

# active window title colors
set-window-option -g window-status-current-style "fg=${accent},bg=${status_bg}"

# pane border
set-option -g pane-border-style "fg=${status_bg}"
set-option -g pane-active-border-style "fg=${status_fg}"

# message text
set-option -g message-style "fg=${color15:-$fg},bg=${color0:-$bg}"

# pane number display
set-option -g display-panes-active-colour "${status_fg}"
set-option -g display-panes-colour "${status_bg}"

# clock
set-window-option -g clock-mode-colour "${color4}"

# copy mode highlight
set-window-option -g mode-style "fg=${status_fg},bg=${color0:-$bg}"

# bell
set-window-option -g window-status-bell-style "fg=${bg},bg=${color1}"

# style for window titles with activity
set-window-option -g window-status-activity-style "fg=${fg},bg=${status_bg}"

# style for command messages
set-option -g message-command-style "fg=${color15:-$fg},bg=${color0:-$bg}"

# vim: set ft=tmux tw=0:
EOF
}

if [[ -n "$output_file" ]]; then
  generate_tmux > "$output_file"
  echo "Generated: $output_file"
else
  generate_tmux
fi
