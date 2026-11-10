#!/usr/bin/env bash
# Prints the model budget as the JSON a waybar custom module reads: the bar's text in the
# active theme's colors, beside the heading and rows of the panel a click opens.
unreached() {
  jq -nc --arg why "$1" '{text: "budget ?", heading: ($why | @html), rows: [], class: "unreached"}'
}

if ! reading=$(fleet budget now --json 2>/dev/null); then
  unreached 'fleet budget now did not answer'
  exit 0
fi
jq -ce '.timeline.whole_budget // empty | .label' <<<"$reading" >/dev/null || {
  unreached "$(jq -r '.timeline_error // "fleet budget now gave no whole budget"' <<<"$reading")"
  exit 0
}
palette=$(jq -Rn '[inputs | capture("^@define-color (?<name>[a-z-]+) (?<hex>#[0-9a-fA-F]{6});") | {(.name): .hex}] | add // {}' \
  ~/.config/waybar/themes/current.css 2>/dev/null) || palette='{}'
jq -c --argjson palette "$palette" -f "$(dirname "$(readlink -f "$0")")/fleet-budget.jq" <<<"$reading"
