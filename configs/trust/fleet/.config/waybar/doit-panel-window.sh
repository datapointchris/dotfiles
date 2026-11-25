#!/usr/bin/env bash
# The desk nudge pill and SUPER+N toggle doit's panel window, which windowrules.lua places by title.
set -euo pipefail

title='doit panel'
if hyprctl clients -j | jq -e --arg title "$title" 'any(.[]; .title == $title)' >/dev/null; then
  exec hyprctl dispatch 'hl.dsp.window.close({ window = "title:^(doit panel)$" })'
fi
exec doit desk-nudge panel open
