#!/usr/bin/env bash
# The desk nudge pill's click: open doit tui on its now tab in a floating Ghostty, or close the one
# already open. windowrules.lua floats, centers and sizes the window by its class.
set -euo pipefail

class=doit.tui
if hyprctl clients -j | jq -e --arg class "$class" 'any(.[]; .class == $class)' >/dev/null; then
  exec hyprctl dispatch 'hl.dsp.window.close({ window = "class:^(doit\\.tui)$" })'
fi
exec ghostty --class="$class" -e doit tui --tab now
