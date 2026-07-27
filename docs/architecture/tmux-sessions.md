# tmux Sessions

How the tmux workspace is organised: a session is a repo, and windows are named tasks inside it.

## The Model

A session is a **repo** — `dotfiles`, `learning`, `homelab` — opened by `sesh`, which names it
after the directory. Inside it, windows are the named tasks in flight: `voice`, `comprehension`,
`auto update`. The first status line lists every session; the second lists the focused session's
windows.

The unit of work is the **window**, not the session. Several tasks are typically open at once
across different repos, each one window, and moving between them is the most frequent action of the
day.

That creates one problem this architecture exists to solve: a task started in whichever session
happened to be focused is hard to find later, because the status line only shows the current
session's windows. `prefix w` answers that — see below — rather than the status line growing to
hold everything.

> A `repo·task` session naming scheme was built to make each task its own session and reverted the
> same day. Tasks are one window each, so it left every session one window deep, the second status
> line vestigial, and the first full of near-identical `repo·` rows. The remaining open question —
> sessions accumulate, and nothing shows which are actually live — is tracked in the **dotfiles**
> project in `icb`. Do not rebuild the naming scheme; read the item first.

Terminal tabs are deliberately not used for this. On macOS, Ghostty uses native `NSWindow` tabs,
which the Accessibility API reports as separate windows, so AeroSpace tiles each one; [Ghostty's
own guidance](https://ghostty.org/docs/help/macos-tiling-wms) is to use a multiplexer instead.
Keeping everything in tmux also keeps the model identical on Arch, where Hyprland and Ghostty tabs
would otherwise compete with tmux for the same job.

## Two Status Lines

The status bar runs two lines, set in `configs/common/.config/tmux/tmux.conf`:

| Line | Shows |
|------|-------|
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
|-----|--------|
| `M-.` | Next session |
| `M-,` | Previous session |
| `M-n` | Next window |
| `M-p` | Previous window |
| `M-o` | Last session |
| `M-t` | New session (a bare name inherits the current repo prefix) |
| `prefix T` | Promote the focused window into its own session |
| `prefix s` | sesh picker — open a session, or make one from a directory |
| `prefix w` | Find a window in any session |

All of these repeat by holding Alt rather than re-arming a leader, and they are unprefixed because
moving around is the most frequent action of the day. The prefixed `h` / `l` remain as a fallback
and carry `-r` so they repeat too. `M-n` / `M-p` are the unprefixed twins of tmux's own default
`prefix n` / `prefix p`.

**Every binding is one modifier plus a right-hand key, and that is a hardware constraint rather
than a style choice.** The Corne's home-row mods are positional — `hold-trigger-key-positions =
<KEYS_R ...>` — so a left-hand mod resolves as a *hold* only when the next key is on the right hand.
Press another left-hand key and it resolves as a *tap* and types a letter. `LALT` and `LSHIFT` sit
next to each other on the left home row (the `S` and `D` positions), so `Alt+Shift` chords degrade
silently, and a left-plus-right mod pair fails too because each positional mod then demands the
opposite hand. An `M-<` / `M->` pairing was built on these keys and had to be abandoned for exactly
this. The definitions are in `~/code/zmk/shared/dts/shared_behaviors.dtsi`.

Alt is also the only modifier tmux can take. Its key parser accepts `C-`, `M-`, and `S-` and
rejects everything else, so a chord containing GUI — which the keyboards' `HYPER` does — cannot be
bound at any level, whatever the keyboard sends. The vim-natural `M-h` / `M-l` are unavailable too:
AeroSpace grabs them globally for window focus. `M-[` is avoided because Alt+`[` emits the CSI
prefix, leaving tmux to disambiguate it on the `escape-time` timer.

On macOS this all rests on Ghostty delivering Option as Alt, which it does by default only for U.S.
keyboard layouts. Setting `macos-option-as-alt` explicitly would pin it; it is deliberately left
unset.

## Why Switching Needs a Helper

The status line lists sessions with `#{S:}`, which walks them in **session-id order** — creation
order. tmux's own `switch-client -n`/`-p` walk them **alphabetically**. Using the built-ins would
mean "next" skipping past the session shown next to the current one, so `tmux-sessions` re-derives
the status line's order before stepping.

Creation order is the right choice for the display, and the reason is worth keeping: it is stable.
Renaming a session leaves it where it is and a new one is appended at the end. Alphabetical
ordering would reshuffle the list whenever a session was created or renamed, which destroys the
positional memory that makes it fast to read.

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

sesh owns session creation and naming, and needs no configuration change. It names a session after
the **basename** of its path (`dir_length` defaults to 1), or after the explicit `name` in a
`[[session]]` block in `~/.config/sesh/sesh.toml`, then sanitises the result by replacing `.`, `:`,
and runs of whitespace with `_`. Sessions are therefore never named by hand.

`prefix s` and `prefix w` are not two versions of the same picker. They sit at different levels,
and the split mirrors the two status lines: `prefix s` is line 1, `prefix w` is line 2 for every
session at once. sesh's own `sesh window` only lists windows **in the current session**, so it
cannot answer "which session is that window in" — the gap `prefix w` exists to fill. sesh in turn
does something `prefix w` cannot: it creates sessions from zoxide directories, config entries, and
`fd` results, so it reaches places that have no running session at all.

One pre-existing sesh behaviour is worth knowing, because it shows up in the status line: since
names come from the basename, two repos sharing one (`~/homelab` and `~/code/refs/homelab`)
produce the same session name. Setting `dir_length = 2` in `sesh.toml` disambiguates them.

## Promoting a Window

`prefix T` moves the focused window out into a session of its own, prefilled with the window name —
for a task that has outgrown being one window among several. A session holding a single window is
renamed in place instead of being moved, since moving its only window would leave an empty session
for tmux to destroy.

This is occasional rather than routine. It was written to migrate every window into its own session
under the reverted naming scheme; that use is gone, the command is not.

## Files

| File | Role |
|------|------|
| `apps/common/tmux-sessions` | Switching, creation, promotion, status relocation |
| `configs/common/.config/tmux/tmux.conf` | Two-line status, keybindings, relocation call |
| `~/tools/theme/lib/generators/tmux.sh` | Generates line 1's format and colours |
