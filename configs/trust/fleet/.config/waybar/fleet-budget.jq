# Formats a budget reading as waybar's {text, class}, and as the heading and rows
# fleet-budget-menu.sh opens. $palette maps the active theme's color names to hex.

# Escapes a piece of text for Pango, in the named theme color where one is given.
def paint($color):
  @html as $text
  | ($palette[$color // ""] // null) as $hex
  | if $hex then "<span color=\"\($hex)\">\($text)</span>" else $text end;
def level_color: {"0": "red", "1": "red", "2": "yellow", "3": "green", "4": "cyan"}[tostring] // null;
def epoch: sub("\\.[0-9]+"; "") | fromdateiso8601;
def duration:
  if . >= 86400 then "\(. / 86400 | floor)d \(. % 86400 / 3600 | floor)h"
  elif . >= 3600 then "\(. / 3600 | floor)h \(. % 3600 / 60 | floor)m"
  else "\([. / 60 | floor, 0] | max)m" end;
# A time as the status line prints it: the clock today, the weekday within six days, else the date.
def clock:
  epoch
  | if strflocaltime("%F") == (now | strflocaltime("%F")) then strflocaltime("%H:%M")
    elif (. - now | fabs) < 518400 then strflocaltime("%a %H:%M")
    else strflocaltime("%b %-d %H:%M") end;
def from_now: epoch - now | duration;
# A rate at two decimals. Null, an unread reading, prints as a dash.
def rate:
  if . == null then "-"
  else (. * 100 | round) as $hundredths
    | ($hundredths | fabs) as $whole
    | (if $hundredths < 0 then "-" else "" end)
      + "\($whole / 100 | floor)." + ("0\($whole % 100)" | .[-2:]) + "%/h"
  end;
# A token count as abtop prints it: 950, 182.3k, 1.2M. Null prints as a dash.
def tokens:
  def tenths($unit; $suffix):
    (. / $unit * 10 | round / 10) as $v
    | if $v == ($v | floor) then "\($v | floor)\($suffix)" else "\($v)\($suffix)" end;
  if . == null then "-"
  elif . >= 1000000 then tenths(1000000; "M")
  elif . >= 1000 then tenths(1000; "k")
  else tostring end;
def pad($width): . + (" " * ([$width - length, 0] | max));
def pad_left($width): (" " * ([$width - length, 0] | max)) + .;
def row($name): "\($name | pad(11)) \(.)";
def out_text:
  if . == "refused" then "refused" elif . == "on_reserve" then "on reserve" else "out" end;
def account: .account_name // (.pool // "?" | .[:8]);
# A dial's position, and who set it until when, where a setting stands.
def position:
  .position
  + (if .setting then
       ", set by \(.setting.by)" + (if .setting.until then " until \(.setting.until | clock)" else "" end)
     else " (default)" end);

.timeline.whole_budget as $whole
| ($whole.combined.last_6_hours // null) as $six
| ($whole.combined.last_hour // null) as $one
| ($whole.combined.last_minute // null) as $minute
| [.timeline.weeks // [] | .[] | select(.current)] as $weeks
| ($weeks | map(select(.ends_at != null)) | min_by(.ends_at) // null) as $refilling
| ($whole.first_shortage_at != null
   and ($whole.next_refill_at == null or ($whole.first_shortage_at | epoch) < ($whole.next_refill_at | epoch))) as $out_before_refill
| ([$weeks[] | account | length] | max // 0) as $name_width
| ($weeks | map(
    "\(account | pad($name_width))  \(.left_pct | round | tostring | pad_left(3))% left"
    + "  ↻ \(.ends_at | from_now | pad(7))"
    + (if .level == 0 then "  out, \(.out_reason | out_text)"
       elif .label then "  \(.label)"
       else "" end))) as $plans
| ([.held.jobs[]? | select(.waiting) | .name]) as $waiting
| (if $whole.combined.window_hours then "over \($whole.combined.window_hours)h" else "lately" end) as $lately
| (if $minute == null then "unread: the daemon predates the reading"
   elif $minute.active_tokens == null then "unread: \($minute.unread // "the warehouse did not answer")"
   else "\($minute.active_tokens | tokens) a minute to \($minute.until | epoch | strflocaltime("%H:%M:%S"))"
     + (if $minute.tokens then
          " · \($minute.tokens.input | tokens) input · \($minute.tokens.output | tokens) output"
          + " · \($minute.tokens.cache_write | tokens) cache writes"
          + " · \($minute.tokens.cache_read | tokens) cache reads left out"
        else "" end)
     + (if $minute.messages != null then " · \($minute.messages) messages" else "" end)
   end) as $tokens_row
| (if .workers then .workers
     | position + " · " + (if .rate_pct_per_hour == null then "no cap" else (.rate_pct_per_hour | rate) end)
       + " · \(.running) running · \(.held) held"
       + (if .next_opens_at then " · next opens \(.next_opens_at | clock)" else "" end)
   else "unread: \(.workers_error // "the reading has no workers dial")" end) as $workers_row
| (if .scheduled then .scheduled
     | position + " · " + (if .rate_pct_per_hour == null then "no cap" else (.rate_pct_per_hour | rate) end)
       + (if .lifted then ", lifted from \(.position_rate_pct_per_hour | rate) by the surplus" else "" end)
       + (if .jobs_per_hour then " · about \(.jobs_per_hour | round) jobs an hour" else "" end)
       + " · \(.running) running · \(.held) held"
       + (if .next_opens_at then " · next opens \(.next_opens_at | clock)" else "" end)
   else "unread: \(.scheduled_error // "the reading has no scheduled dial")" end) as $scheduled_row
| (if .use then .use
     | "\(account) first" + (if .until then " until \(.until | clock)" else "" end) + ", set by \(.by)"
       + (if .takes_runs then "" else " · takes no run now, so queue work routes by the usual order" end)
   elif .use_error then "unread: \(.use_error)"
   else "the usual order: credits, then the plan whose week ends soonest" end) as $account_row
| (if $whole.first_shortage_at == null then "not in the week ahead"
   else "\($whole.first_shortage_at | clock) (in \($whole.first_shortage_at | from_now))"
     + (if $out_before_refill then ", before the refill" else ", after the refill" end)
     + " · \($whole.short_pct | round)% short over the week ahead"
   end) as $runs_out_row
| ((if .paused then
     [("by \(.paused.by)"
       + (if .paused.until then " until \(.paused.until | clock)" else "" end)
       + (if .paused.reason then ": \(.paused.reason)" else "" end) | row("paused")), ""]
   else [] end)
  + [
    ("\($six.pct_per_hour | rate) over 6h · \($one.pct_per_hour | rate) over 1h"
     + " · against \($whole.combined.supply_pct_per_hour | rate) the plans supply" | row("burn")),
    ("\($lately), sessions \($whole.attended.actual_pct_per_hour | rate) against \($whole.attended.forecast_pct_per_hour | rate) forecast"
     + " · queue \($whole.unattended.actual_pct_per_hour | rate) against \($whole.unattended.sustainable_pct_per_hour | rate) sustainable"
     | row("")),
    ($tokens_row | row("tokens")),
    ($runs_out_row | row("runs out")),
    (if $whole.sessions_first_shortage_at then
       "sessions alone \($whole.sessions_short_pct | round)% short from \($whole.sessions_first_shortage_at | clock)" | row("")
     else empty end),
    (if $whole.next_refill_at then
       "\(if $refilling then ($refilling | account) + " " else "" end)\($whole.next_refill_at | clock) (in \($whole.next_refill_at | from_now))"
     else "no week reads" end | row("refill")),
    "",
    ($workers_row | row("workers")),
    ($scheduled_row | row("scheduled")),
    ($account_row | row("account")),
    ""
  ] + $plans
  + (if ($waiting | length) > 0 then ["", "waiting on the budget"] + ($waiting | map("  \(.)")) else [] end)
  ) as $rows
| ([
    ("budget \($whole.label)"
     + (if $out_before_refill then ", runs out \($whole.first_shortage_at | clock)" else "" end)
     | paint($whole.level | level_color)),
    (if .paused then
       "paused" + (if .paused.until then " until \(.paused.until | clock)" else "" end) | paint("magenta")
     else empty end),
    ("burn 6h \($six.pct_per_hour | rate), 1h \($one.pct_per_hour | rate)" | paint(null)),
    ("\($minute.active_tokens | tokens) tok/min" | paint(null)),
    (.scheduled // empty
     | (if .setting then "magenta" elif .lifted then "cyan" else null end) as $color
     | "scheduled \(.position)" + (if .lifted then ", lifted" else "" end) | paint($color)),
    (.workers // empty
     | (if .setting or .held > 0 then "magenta" else null end) as $color
     | "workers \(.position)" + (if .held > 0 then ", \(.held) held" else "" end) | paint($color)),
    (if .use then
       "use \(.use | account)" + (if .use.takes_runs then "" else ", refused" end) | paint("magenta")
     else empty end)
  ] | join(" · ")) as $text
| {
    text: $text,
    heading: ("\($whole.label): \($whole.why)" | @html),
    rows: $rows,
    class: ([$whole.label | gsub(" "; "-")] + (if .paused then ["paused"] else [] end))
  }
