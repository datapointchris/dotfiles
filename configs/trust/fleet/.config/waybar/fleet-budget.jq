# Formats a budget reading as waybar's {text, class}, and as the heading and rows
# fleet-budget-menu.sh opens. $status_line is the status line's budget text, in its
# terminal colors, and $palette maps the active theme's color names to their hex values.

# Turns terminal color codes into Pango spans, which is the markup waybar draws.
def terminal_colors_as_spans:
  {"31": "red", "32": "green", "33": "yellow", "34": "blue", "35": "magenta", "36": "cyan"} as $names
  | @html
  | gsub("\u001b\\[(?<code>[0-9]+)m";
      if .code == "0" then "</span>"
      else $palette[$names[.code] // "fg"] as $hex
        | if $hex then "<span color=\"\($hex)\">" else "<span>" end
      end);
def epoch: sub("\\.[0-9]+"; "") | fromdateiso8601;
def clock: epoch | strflocaltime("%a %H:%M");
def duration:
  if . >= 86400 then "\(. / 86400 | floor)d \(. % 86400 / 3600 | floor)h"
  elif . >= 3600 then "\(. / 3600 | floor)h \(. % 3600 / 60 | floor)m"
  else "\([. / 60 | floor, 0] | max)m" end;
def span: epoch - now | duration;
# A rate at two decimals. Null reads as a dash.
def rate:
  if . == null then "-"
  else (. * 100 | round) as $hundredths
    | ($hundredths | fabs) as $whole
    | (if $hundredths < 0 then "-" else "" end)
      + "\($whole / 100 | floor)." + ("0\($whole % 100)" | .[-2:]) + "%/h"
  end;
def pad($width): . + (" " * ([$width - length, 0] | max));
def pad_left($width): (" " * ([$width - length, 0] | max)) + .;
def out_text:
  if . == "refused" then "refused" elif . == "on_reserve" then "on reserve" else "out" end;

.timeline.whole_budget as $whole
| [.timeline.weeks[] | select(.current)] as $weeks
| ([$weeks[].account_name | length] | max // 0) as $name_width
| ($weeks | map(
    "\(.account_name | pad($name_width))  \(.left_pct | round | tostring | pad_left(3))% left"
    + "  ↻ \(.ends_at | span | pad(7))"
    + (if .level == 0 then "  \(.out_reason | out_text)"
       elif .level == null then ""
       else "  \(.label), queue \(.pace.rate_pct_per_hour | rate)" end)
    + (if .lapse_pct >= 1 then ", lapses \(.lapse_pct | round)%" else "" end))) as $plans
| ([.held.jobs[]? | select(.waiting) | .name]) as $waiting
| (if $whole.combined.window_hours then "over \($whole.combined.window_hours)h" else "lately" end) as $lately
| ([
    "attended    \($whole.attended.actual_pct_per_hour | rate) \($lately), \($whole.attended.forecast_pct_per_hour | rate) forecast",
    "unattended  \($whole.unattended.actual_pct_per_hour | rate) \($lately), \($whole.unattended.allowed_pct_per_hour | rate) allowed, \($whole.unattended.sustainable_pct_per_hour | rate) sustainable",
    "combined    \($whole.combined.actual_pct_per_hour | rate) \($lately), \($whole.combined.supply_pct_per_hour | rate) supplied",
    ""
  ] + $plans + [
    "",
    "next refill \($whole.next_refill_at | clock)" + (if $whole.lapse_pct >= 1 then ", \($whole.lapse_pct | round)% lapses at the resets" else "" end)
  ]
  + (if $whole.first_shortage_at then ["sessions run \($whole.short_pct | round)% short from \($whole.first_shortage_at | clock)"] else [] end)
  + (if .paused then ["paused by \(.paused.by): \(.paused.reason)"] else [] end)
  + (if ($waiting | length) > 0 then ["", "waiting on the budget"] + ($waiting | map("  \(.)")) else [] end)
  ) as $rows
| {
    text: (if $status_line == "" then "Fleet Budget ?" else $status_line | terminal_colors_as_spans end),
    heading: ("\($whole.label): \($whole.why)" | @html),
    rows: $rows,
    class: ([$whole.label | gsub(" "; "-")] + (if .paused then ["paused"] else [] end))
  }
