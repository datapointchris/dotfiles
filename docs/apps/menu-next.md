---
icon: material/dice-multiple
---

# Menu Next

Answer "what should I do right now?" from a weighted list of the things that matter, rather than from
whichever list happens to be open. `menu next` draws a handful of **pursuits**, resolves each one to
a concrete item through whichever CLI owns that domain, and `menu log` records what actually
happened — writing through to that CLI where it can.

## Quick Start

```bash
menu next                       # What to do now (cached 15 minutes)
menu next --explain             # The same draw with every number behind it
menu log read-library "ch 4"    # Record it, with a note
menu log chores --minutes 20    # Record how long it took
menu next skip chores           # Pass; suppressed for a while, weight untouched
menu next list                  # Every pursuit, its weight, its implied share
menu next drift                 # What you said mattered vs what you did
menu next edit                  # Edit the pursuits file
```

## Why this exists alongside the dashboard

`menu dashboard` deliberately refuses to rank across its lanes: an ordering it invented over unlike
things — a book, a habit, a chore — would be arbitrary dressed up as advice. That reasoning is
exactly why this tool is allowed to rank. It does not invent the ordering. You declare it, one weight
per pursuit, and everything else is arithmetic on top of numbers you wrote.

So the two are complements, not rivals. The dashboard is the read of everything outstanding; next is
the decision about what to spend the next hour on. Neither should grow into the other.

## Pursuits

A pursuit is a strand of life you want to spend attention on, and it lives in
`$XDG_CONFIG_HOME/menu/pursuits.yml` — hand-edited, only ever read by the tool. Not in this repo:
a register of personal intentions is stewarded data, and this repo is public.

```yaml
pursuits:
  chores:
    description: The maintenance list nobody else is going to do
    weight: 25
    cadence: 1w
    resolve: icb tasks todo --limit 3 --json
    label: name
    id: id
    on_log: icb tasks complete {id}

  visit-new-places:
    description: Go somewhere new
    weight: 70
    until: 2027-08-01
```

| Field | Meaning |
| --- | --- |
| `weight` | Required. A **relative magnitude**, not a percentage — nothing has to add up to 100 |
| `description` | Shown when nothing more specific resolved |
| `cadence` | Optional hard schedule (`10d` / `2w` / `1mo`); overdue **pins** it above the draw |
| `until` | Optional end date; after it the pursuit pauses itself and says so |
| `paused` | Keeps it in the file and out of the draw |
| `alpha` | Per-pursuit override for how sharply urgency climbs |
| `resolve` | Command answering "specifically what?" |
| `items` / `label` / `id` | Which fields of the resolver's JSON to read |
| `on_log` | Command run after logging — the write-through |

Weights stay relative because that is how the decision actually gets made: travel matters more than
reading *this year* is a comparison, not an allocation. `menu next list` prints the share each weight
implies, which is where a number that dominates more than you meant becomes visible.

## How the draw works

Four steps, all inspectable with `--explain`.

**The interval is derived, not declared.** A pursuit's share of the total weight, against how many
things you actually log per day, gives how often it would come up if you were living the way you said.
The rate is measured from your own journal — log more and every interval tightens; log less and they
all stretch. That is the only place the tool tunes itself, and it tunes to observed behaviour rather
than to a setting.

**Urgency multiplies the weight.** Zero inside a cooldown of the first fifth of the interval, 1.0 at
exactly the interval, climbing superlinearly past it, capped at eight so nothing dormant can own the
screen forever. Never done counts as maximally urgent.

**Overdue cadences are pinned, not sampled.** A weighted draw makes an overdue chore *likely*, and
likely is not enough for the case this tool exists for. Anything with a declared cadence that is past
due appears above the draw every time until it is done.

**The rest is drawn.** Weighted sampling without replacement by the Efraimidis–Spirakis key trick, so
the list changes between sessions and a heavy pursuit is probable rather than guaranteed. Re-running
inside 15 minutes returns the same draw — glance, get interrupted, glance again, and the answer must
not have changed underneath you. `--reroll` forces a new one.

## Logging, and writing through

`menu log <pursuit>` is the fast path and completes from a flat cache file, so Tab is instant. It
accepts `--ago 3h` for something you did earlier and `--minutes 45` for how long it took.

Logging is the **only** source of last-done, on purpose. Deriving it from the backend was considered
and rejected: an hour of studying is a real log even though the resource will not be finished for two
weeks, so a backend-derived date would report the pursuit as cold while it is the thing you do most.

Where a pursuit declares `on_log`, logging also acts. The 15-minute cache already knows which concrete
item was on screen, so `menu log chores` can complete exactly the task it offered — no second lookup,
no chance of closing something else. It asks first, because that cache can be a quarter-hour old and
a wrong completion in another app is expensive to notice. `-y` skips the prompt, `--no-write` logs
only.

## Drift

`menu next drift` is what the journal is for: stated weight against realized share over a window, in
both count and recorded time, with how often each pursuit was offered and how often it was passed.

It never adjusts a weight. Stated and revealed preference are different signals and blending them
destroys the only honest comparison available — the point is to *see* that you said 35% and did 8%,
and then decide whether the weight was wrong or the week was. The offered count is there to separate
the two failures that otherwise look identical: a pursuit that never comes up, and one that comes up
constantly and gets ignored.

`menu next dormant` is the same signal from the other end — pursuits gone colder than their own weight
implies.

## Storage

| What | Where | Why |
| --- | --- | --- |
| Pursuits register | `$XDG_CONFIG_HOME/menu/pursuits.yml` | Hand-edited, so config. Personal, so not in this repo |
| Journal | `$XDG_STATE_HOME/menu/next-log-<host>.jsonl` | Append-only, **one file per machine** |
| Offered counts | `$XDG_STATE_HOME/menu/next-offers-<host>.json` | Same per-machine rule |
| Draw cache, name cache | `$XDG_CACHE_HOME/menu/` | Regenerable at no cost but a redraw |

The per-machine split is not fussiness. Syncthing resolves conflicts per *file* — it mirrors, it does
not merge text the way git does — so when two machines each hold a version of one file the other has
not seen, the loser is set aside whole as a `.sync-conflict` copy that nothing ever reads. For an
append-only log that divergence is the ordinary shape of a day: log on the laptop, close the lid
before it syncs, log at the desktop, reopen the laptop. One writer per file removes the condition
entirely, and reads take the union.

Every record carries the full weight vector at that moment, so `drift` stays honest about a past week
after the weights have changed, along with which draw it came from and whether it had been offered at
all. That is deliberate over-recording: none of it can be backfilled later.
