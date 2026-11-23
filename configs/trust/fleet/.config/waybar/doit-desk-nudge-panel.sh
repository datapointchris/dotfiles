#!/usr/bin/env bash
# The desk nudge's panel: rofi draws each step that `doit desk-nudge panel` prints, and a pick
# hands that row's key back to it. doit computes every row and completes every pick, so this loop
# holds no rule. A row with no key is a note, which rofi shows and will not pick. The loop ends on
# a `done` step, when rofi closes, and on any failed pick, which doit has already announced.
step=$(doit desk-nudge panel show --json) || exit 0
until [[ $(jq -r .step <<<"$step") == "done" ]]; do
  row=$(jq -j '.rows[] | .text, (if .key == null then "\u0000nonselectable\u001ftrue" else "" end), "\n"' <<<"$step" \
    | rofi -dmenu -i -no-custom -format i -p 'desk nudge') || exit 0
  [[ $row =~ ^[0-9]+$ ]] || exit 0
  key=$(jq -r --argjson row "$row" '.rows[$row].key // empty' <<<"$step")
  [[ -n $key ]] || continue
  step=$(doit desk-nudge panel pick "$key" --json) || exit 0
done
