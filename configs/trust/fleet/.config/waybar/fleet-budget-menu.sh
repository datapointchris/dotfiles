#!/usr/bin/env bash
# Opens the model budget in a rofi panel under the pointer. A second click on the
# module closes it. Choosing a row does nothing, because the panel only reads.
pkill -x rofi && exit 0

budget=$("$(dirname "$(readlink -f "$0")")/fleet-budget.sh")
rows=$(jq -r '.rows[]' <<<"$budget")
widest=$(wc -L <<<"$rows")
row_count=$(wc -l <<<"$rows")
pointer_x=$(hyprctl cursorpos -j | jq '.x')

rofi -dmenu -no-custom -mesg "$(jq -r '.heading' <<<"$budget")" -theme-str "
  configuration { font: \"JetBrainsMono Nerd Font 22\"; }
  window { location: north west; anchor: north west; x-offset: ${pointer_x}px; y-offset: 4px; width: $((widest < 60 ? 66 : widest + 6))ch; }
  mainbox { children: [message, listview]; }
  message { padding: 0 0 12px 0; }
  textbox { text-color: @fg; background-color: transparent; }
  listview { lines: ${row_count}; scrollbar: false; spacing: 0; }
  element { padding: 1px 8px; }
  element selected.normal { background-color: transparent; }
  element-text selected.normal { text-color: inherit; }
" <<<"$rows" >/dev/null
