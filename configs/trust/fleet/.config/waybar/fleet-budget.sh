#!/usr/bin/env bash
# Prints the model budget as the JSON a waybar custom module reads: the budget line
# Claude Code's status line prints, from that status line's own filter, and a class
# for its color, beside the heading and rows of the panel a click opens.
unreached() {
  jq -nc --arg why "$1" '{text: "Fleet Budget ?", heading: ($why | @html), rows: [], class: "unreached"}'
}

if ! reading=$(fleet budget now --json 2>/dev/null); then
  unreached 'fleet budget now did not answer'
  exit 0
fi
jq -ce '.timeline.whole_budget // empty | .label' <<<"$reading" >/dev/null || {
  unreached "$(jq -r '.timeline_error // "fleet budget now gave no whole budget"' <<<"$reading")"
  exit 0
}
kept=$(jq -c '{pool, paused, timeline: (.timeline | {plans, weeks, whole_budget})}' <<<"$reading")
login=$(jq -c '[{oauthAccount: {accountUuid: .pool}}]' <<<"$kept")
status_line=$(jq -r --argjson login "$login" --argjson cache "$kept" --argjson width 0 \
  -f ~/.claude/statusline-weekly-budget.jq <<<'{}' 2>/dev/null)
jq -c --arg status_line "$status_line" -f "$(dirname "$(readlink -f "$0")")/fleet-budget.jq" <<<"$reading"
