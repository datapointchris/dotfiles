#!/usr/bin/env bash
# Prints the model budget as the JSON a waybar custom module reads: the bar's
# text, a tooltip with every plan and rate, and a class for its color.
unreached() {
  jq -nc --arg why "$1" '{text: "budget ?", tooltip: ($why | @html), class: "unreached"}'
}

if ! reading=$(fleet budget now --json 2>/dev/null); then
  unreached 'fleet budget now did not answer'
  exit 0
fi
jq -ce '.timeline.whole_budget // empty | .label' <<<"$reading" >/dev/null || {
  unreached "$(jq -r '.timeline_error // "fleet budget now gave no whole budget"' <<<"$reading")"
  exit 0
}
jq -c -f "$(dirname "$(readlink -f "$0")")/fleet-budget.jq" <<<"$reading"
