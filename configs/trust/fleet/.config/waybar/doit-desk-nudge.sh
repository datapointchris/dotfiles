#!/usr/bin/env bash
# Prints the desk nudge's pill as the JSON that a waybar custom module reads: the text and class that
# `doit desk-nudge watch` writes into its state file. Prints `nudge stopped` where no watch has
# ticked before the file's stale_after, which also covers a missing file and one never ticked.
state="${XDG_STATE_HOME:-$HOME/.local/state}/doit/desk-nudge.json"

stopped() {
  jq -nc '{text: "nudge stopped", class: "stopped"}'
  exit 0
}

pill=$(jq -ce '.pill | objects' "$state" 2>/dev/null) || stopped
stale_after=$(jq -r '.stale_after // empty' <<<"$pill")
[[ -n $stale_after ]] || stopped
deadline=$(date -d "$stale_after" +%s 2>/dev/null) || stopped
((EPOCHSECONDS < deadline)) || stopped
jq -c '{text: (.text | @html), class}' <<<"$pill"
