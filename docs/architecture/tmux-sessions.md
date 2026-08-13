# tmux Sessions

How the tmux workspace is organised: a session is a unit of work, and its windows are the places you
touch to do it.

## The Model

A session is an **initiative** — `standardize installs`, `repos` — and its windows are the places
the work happens, named for the activity rather than the directory: `audit packages`, `apply`, `ci`.
One initiative usually spans several repos, so the same repo can hold a window in more than one
session at once, under different names and for different purposes. The first status line lists
every session; the second lists the focused session's windows.

The unit of work is the **window**, not the session. Several are open at once and moving between
them is the most frequent action of the day, which is why they hold the unshifted key pair.

A session being a repo is the degenerate case of this, and it is what the layer was originally used
for. It was abandoned because it carried no information: `sesh` names a session after a directory
basename, work in flight is usually one task per repo, and the result was five sessions one window
deep — the first status line and the second showing the same list at two granularities, with a
session switch standing between you and every window. Naming sessions after the work restores the
distinction the two lines are drawing.

Because a repo now appears in several sessions, the **session name is what disambiguates** two
windows sitting in the same directory. That makes `prefix w`'s session column load-bearing rather
than a restatement of the window name.

> Two attempts at this have been built and reverted. Do not rebuild either without reading why.
>
> A `repo·task` session naming scheme made each task its own session. Tasks are one window each, so
> it left every session one window deep, the second status line vestigial, and the first full of
> near-identical `repo·` rows — and the separator was untypeable, an internal encoding leaking into
> a name you have to enter by hand.
>
> Sorting the session list by recency, with untouched sessions faded, replaced the `#{S:}` loop with
> a script that emitted the whole line. It worked and was still wrong to use: a recency order puts
> the session you just left next to the one you are in, so the "previous session" key degrades into
> a two-session toggle and "next session" only ever reaches the least-used one, while every switch
> reshuffles the line. Where a session landed after a re-sort was unpredictable in practice.
> Ordering is therefore creation order, which never reshuffles, and sessions are pruned by hand
> with `prefix K` instead.

Terminal tabs are deliberately not used for this. On macOS, Ghostty uses native `NSWindow` tabs,
which the Accessibility API reports as separate windows, so AeroSpace tiles each one; [Ghostty's
own guidance](https://ghostty.org/docs/help/macos-tiling-wms) is to use a multiplexer instead.
Keeping everything in tmux also keeps the model identical on Arch, where Hyprland and Ghostty tabs
would otherwise compete with tmux for the same job.

## Two Status Lines

The status bar runs two lines, set in `configs/common/.config/tmux/tmux.conf`:

| Line | Shows |
| --- | --- |
| 1 | Every session |
| 2 | The focused session's windows |

Both lines share one shape, so they read as a single bar rather than two competing designs. Entries
are separated by whitespace alone, and the current entry is marked by colour and weight — green on
line 1 for the session you are in, yellow on line 2 for the window.

Those two choices come out of visual-perception research rather than taste. Colour is the strongest
[preattentive channel](https://link.springer.com/article/10.3758/s13423-020-01859-9) — it is
processed in parallel across the visual field before you focus on anything, which is what makes
"where am I" answerable at a glance instead of by reading. And
[proximity](https://www.nngroup.com/articles/gestalt-proximity/) groups on *relative* distance, so
the gap between entries being wider than the gaps inside a name is the entire mechanism.

Dividers were tried and dropped. Padding plus a bar is two separators doing one job: it flattens
the spacing so proximity carries no information, and the extra marks only make the line busier.
Accenting the dividers was also tried — a tmux format loop has no lookahead, so an entry can colour
the bar on one side of itself but not the one on its other side, which belongs to its neighbour.
That leaves all bars accented or none, and the current entry's colour already carries the signal.

tmux draws `status-format[0]` topmost and ships its own window row there, so the window row has to
move down before the theme can claim line 1. `tmux-sessions install-status` does that relocation,
and `tmux.conf` runs it immediately **before** sourcing the theme, while the window row is still at
its stock value. The command is idempotent — on a config reload line 2 already holds the window row
and the copy is skipped.

Line 1's format is generated per-theme by the `theme` CLI (`lib/generators/tmux.sh`), which owns
status bar colour the same way it owns `pane-border-format`.

## Switching

| Key | Action |
| --- | --- |
| `M-n` / `M-p` | Previous / next window |
| `M-,` / `M-.` | Previous / next session |
| `M-h` / `M-l` | Move the focused session left / right — Linux only |
| `M-a` / `M-e` | Move the focused session to the front / end — Linux only |
| `M-o` | Last session |
| `M-t` | New session |
| `prefix K` | Kill the session, after confirming |
| `prefix T` | Promote the focused window into its own session |
| `prefix s` | sesh picker — open a session, or make one from a directory |
| `prefix w` | Find a window in any session |
| `prefix .` | Move the focused window into another session (tmux default) |

Both pairs repeat by holding Alt rather than re-arming a leader, and both are unprefixed because
moving around is the most frequent action of the day.

**Direction is physical, not semantic.** `n` sits left of `p` on the keyboard and `,` left of `.`,
so each pair runs left-to-right where it is typed — which means `M-n` is *previous* even though `n`
reads as "next", inverting tmux's own `prefix n` / `prefix p`. The keyboard direction is the one
that gets used; the mnemonic is not.

Every key here takes one modifier. An earlier arrangement put sessions on the shifted `M-<` / `M->`
so the two axes were one gesture apart, and it was dropped once four single-modifier keys were
available on the same hand: holding Alt and Shift together is unreliable on the Corne. Not for the
reason it first appears — the positional gate is satisfied, since `COMMA` and `DOT` are keys 32 and
33 inside `KEYS_R` and `hold-trigger-on-release` is set on every home-row mod, which is exactly what
lets two same-hand mods chord. What breaks it is `require-prior-idle-ms` (150 on `hml`, 100 on
`hmls`): whichever mod is pressed second sees the first as a prior keypress inside that window and
resolves as a tap, emitting a letter. Pressing them a beat apart works. A ZMK combo would fix it
outright and is deliberately not done — a tmux keybinding has no business reaching into keyboard
firmware.

The prefixed `h` / `l` went at the same time. They existed as a fallback for the chord, and a
fallback for keys that now need no fallback is one more binding to remember.

Alt is the only modifier available *to a letter*. tmux's key parser accepts `C-`, `M-` and `S-` and
rejects everything else, so a chord containing GUI — which the keyboards' `HYPER` does — cannot be
bound at any level, whatever the keyboard sends. Ctrl is spent on the terminal's own control codes,
which leaves Alt. Arrows are the exception and carry every modifier bit in their `CSI 1;<mod>`
encoding, which is how pane resize reaches `C-S-arrow`. `M-[` is avoided because Alt+`[` emits the
CSI prefix, leaving tmux to disambiguate it on the `escape-time` timer.

**AeroSpace takes four of these before tmux sees them, and only on macOS.** `alt-h` and `alt-l` are
window focus; `alt-a` and `alt-e` are workspaces A and E. So the four reordering keys are Linux-only,
and the movement keys were picked from letters AeroSpace leaves alone. Watch `aerospace.toml` for the
rest: `alt-comma` and `alt-period` are commented out there, and uncommenting either silently takes
the session keys.

On macOS this all rests on Ghostty delivering Option as Alt, which it does by default only for U.S.
keyboard layouts. Setting `macos-option-as-alt` explicitly would pin it; it is deliberately left
unset.

## Why Switching Needs a Helper

The status line lists sessions with `#{S:}`, which walks them in **session-id order** — creation
order. tmux's own `switch-client -n`/`-p` walk them **alphabetically**. Using the built-ins would
mean "next" skipping past the session shown next to the current one, so `tmux-sessions` re-derives
the status line's order before stepping. Windows need no such helper, which is why the two pairs are
bound differently: `next-window`/`previous-window` already walk windows in the order line 2 draws
them.

Creation order is the right choice for the display, and the reason is worth keeping: it is stable.
Renaming a session leaves it where it is and a new one is appended at the end. Alphabetical
ordering would reshuffle the list whenever a session was created or renamed, which destroys the
positional memory that makes it fast to read.

Stable is not fixed, though. tmux has no `swap-session` and ids only ever ascend with no way to
renumber, but a session recreated now sorts after every session that was not — so `move-left`,
`move-right`, `move-first` and `move-last` reorder by rebuilding the shortest run of sessions that
produces the order wanted, carrying windows and their processes across with `move-window`. Moving
left leaves the focused session alone and rebuilds the neighbour it jumped; moving right has to
rebuild the focused one, since a rebuild can only send a session later.

The order does not survive a restart. tmux-resurrect saves by session **name** and its file lists
them alphabetically, so a restore recreates them in that order and hands out ids to match. A
deliberate order lasts as long as the server does; a name is what orders sessions across restarts.

Because the order only matters at keypress time, line 1 stays a pure tmux format rather than a
`#(shell-command)`. Formats re-evaluate on tmux's own redraw events, so the list updates the moment
a session is created, renamed, or killed; a shell command would inherit the 15-second
`status-interval` lag and need refresh hooks to compensate.

## Finding a Window in Another Session

`prefix w` opens a fuzzy picker over every window in every session, session column left-justified,
window name after it, previewing the window's live pane content. It replaced `choose-tree` on that
key: both list the same thing, but this one is typed at rather than navigated with arrows, and
recognition beats recall.

Deliberately, this is a picker and not more status bar. [Visual search is measurably faster down a
left-justified vertical list than along a horizontal one](https://www.nngroup.com/articles/vertical-nav/)
— fewer fixations, because each one takes in more candidates — so the two questions want opposite
layouts. The status line answers "where am I", which colour resolves in a glance; the picker
answers "where did I leave that", which needs a list. Widening the bar until every window fit would
make the second question no easier and the first one harder, and it is the documented failure mode
of tab bars at scale: the [CHI 2010 study of tabbed browsing](https://dubroy.com/blog/my-chi2010-talk-a-study-of-tabbed-browsing/)
found heavy users' bars scrolling with titles too small to read.

The preview shows pane content rather than a directory listing because two windows of the same task
usually share a directory — what is running in them is the only thing that distinguishes them.

## Interaction with sesh

sesh names a session after the **basename** of its path (`dir_length` defaults to 1), or after the
explicit `name` in a `[[session]]` block in `~/.config/sesh/sesh.toml`, sanitising the result by
replacing `.`, `:`, and runs of whitespace with `_`.

That naming is the one place sesh and the work-session model pull against each other, since a
basename is a repo name and an initiative needs one you type. So the model splits sesh's job in
two. Its **candidate discovery** — zoxide frecency, config entries, `fd` — is model-agnostic and
still what `prefix s` is for; it emits paths, and what you do with a path is your choice. Its
**session creation** is the model-bound half, and `M-t` is the road for a named initiative instead.

`sesh.toml` therefore lists long-lived contexts rather than every repo — `sesh list -c` enumerates
them. Declaring initiative templates would mean handing off to tmuxinator via `sesh connect -T`,
which is heavier than typing a name for work that lasts a few days.

The exception is `monitor`, which is not an initiative: btop over oxker, every pane a read, safe to
kill and rebuild because nothing in it holds work. That is exactly what a config block describes
well. sesh has no pane key — `[[window]]` carries only `name`, `startup_script` and `path`, and
issue #198 asking for panes was closed without them — so the split runs inline in
`startup_command` via `tmux split-window`. It replaced a bash app that did the same thing in 150
lines, and the file lives in `configs/trust/fleet/`, so the coordinate keeps it off the work box
without the app's `command -v` probing.

`prefix s` and `prefix w` are not two versions of the same picker. They sit at different levels,
and the split mirrors the two status lines: `prefix s` is line 1, `prefix w` is line 2 for every
session at once. sesh's own `sesh window` takes `-s` to target one session at a time, so it still
cannot answer "which session is that window in" — the gap `prefix w` exists to fill. sesh in turn
does something `prefix w` cannot: it creates sessions from zoxide directories, config entries, and
`fd` results, so it reaches places that have no running session at all.

One pre-existing sesh behaviour is worth knowing, because it shows up in the status line: since
names come from the basename, two repos sharing one (`~/homelab` and `~/code/refs/homelab`)
produce the same session name. Setting `dir_length = 2` in `sesh.toml` disambiguates them.

Note also what `prefix s` lists. Most of its entries are not sessions: alongside the running ones it
offers every `[[session]]` block in `sesh.toml` and every zoxide directory, which is why the picker
runs to a couple of hundred rows while only a handful are live. Those are places sesh knows how to
*make* a session from, created at the moment you pick one, and they never appear in the status bar.

## Killing Sessions

Kill them freely. An initiative genuinely ends, which is the sense in which this is truer now than
it was under repo-sessions — a repo is never finished. The durable record is `sesh.toml` for the
three configured contexts and zoxide for everything else, so `prefix s` rebuilds a session at the
same path in a keystroke either way. Keep one alive only when it holds something that cannot be
cheaply rebuilt — a running process, scrollback still being referenced, a pane layout that took
setting up. A session sitting at an idle shell is pure clutter in the list.

One caveat: killing a session does not remove it from the last resurrect save, and restore is
all-or-nothing, so anything killed inside the current 15-minute window returns on a cold start.

This matters because the status line has no automatic answer to "which of these am I still using".
Ordering and fading were both tried and reverted (see above), so pruning by hand with `prefix K` is
what keeps the list short.

Killing scales with case: `prefix x` a pane, `prefix k` a window, `prefix K` the session. The window
and session both confirm first and name their target in the prompt, since each takes something that
cannot be reconstructed from a name — a window carries its scrollback and whatever its panes are
running. `detach-on-destroy` is off, so killing the session you are in drops you into another rather
than ending the client. `prefix s` also kills the highlighted session with `Ctrl-d` without leaving
the picker, which is better for pruning several at once.

## Moving Windows Between Sessions

Reclassification is normal here, and it is the one operation the repo-per-session model never
needed: a file's repo does not change, but work started in whatever session was focused very often
belongs to a different initiative than the one it was born in. Two commands cover it.

`prefix .` is tmux's own `move-window`, which takes a target session and completes on it. This is
the routine case — pulling a window out of a catch-all session and into the initiative it turned
out to belong to.

`prefix T` moves the focused window out into a **new** session of its own, prefilled with the window
name, for work that has outgrown being one window among several. A session holding a single window
is renamed in place instead of being moved, since moving its only window would leave an empty
session for tmux to destroy.

The name is taken verbatim, as is `M-t`'s. Both once spliced a `repo·` prefix onto a bare name,
which went with the naming scheme and went out with it.

Together these are what make a catch-all session safe. Work can start anywhere without a decision
about where it belongs, and be filed once that is obvious.

## Regrouping the Whole Workspace

Filing a window at a time keeps up only while the drift is small. `tmux-rearrange` is the bulk
version: it reads every pane's scrollback, asks a model which panes belong together, and writes a
script that moves them. `plan` proposes, `apply` runs what plan wrote, `show` prints the scan
without spending a model call.

**The model gets exactly one job — which panes group, and what to call each group.** That is the
half needing judgement over prose, and it is the half nothing else can do: titles alone will not
reveal that two conversations two windows apart both turn on the same issue. Everything geometric
is computed locally and the tmux commands are rendered locally, so the half that can destroy work
never comes back from a model. One invariant is enforced before a single command runs — the set of
pane ids returned must equal the set sent, exactly once each.

Layout intent is read, not guessed. **A new window opens with one pane, so any split at all was made
by hand** — an even 188|188 is as deliberate as a dragged 183|193, and treating only the uneven case
as intentional is what once collapsed six windows to a single pane. Proportion is the finer signal:
past the one-cell remainder tmux leaves when dividing, a border was dragged. The axis comes from the
layout string rather than the numbers, because an even vertical split leaves every pane both the
same width *and* the same height, so nothing in the dimensions distinguishes it from a horizontal
one; `{}` is a row and `[]` is a column.

What it cannot do is worth knowing before trusting it. Two-across versus three is undetectable —
both are default-shaped for their pane count — so that is a preference, not an observation. A
hand-tuned window whose panes get split across sessions loses its layout permanently, since the
layout string encodes pane ids and the old geometry; only the per-pane fraction transfers, and only
where the group stays together. It sees content, never intent: it can tell that two conversations
cite the same item, not that you want them apart. And it proposes rather than applies, because
reading the script is what catches the run where it was wrong.

## Files

| File | Role |
| --- | --- |
| `apps/common/tmux-sessions` | Switching, creation, promotion, reordering, status relocation |
| `apps/common/tmux-rearrange` | Bulk regroup: scan, propose, render a script |
| `configs/common/.config/tmux/tmux.conf` | Two-line status, keybindings, relocation call |
| `~/tools/theme/lib/generators/tmux.sh` | Generates line 1's format and colours |
