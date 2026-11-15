#!/usr/bin/env bash
# Prints the unread rows of `fleet notifications list` as the JSON a waybar custom module reads:
# the count as the bar's text, the loudest unread level as its class, and the titles as its
# tooltip. Prints nothing where that command fails or answers with anything but a JSON array,
# so waybar hides the module. An install older than the command is one such case.
listed=$(fleet notifications list --unread --json 2>/dev/null) || exit 0
jq -c '
  def loudness: {passive: 0, low: 1, default: 2, high: 3}[.level // ""] // 2;
  def shown: 10;
  select(type == "array")
  | if length == 0 then {text: "0 unread", class: "none"}
    else {
      text: "\(length) unread",
      class: (max_by(loudness) | .level),
      tooltip: ([.[:shown][] | .title // .key | @html]
                + (if length > shown then ["and \(length - shown) more"] else [] end)
                | join("\n"))
    } end
' <<<"$listed" 2>/dev/null
exit 0
