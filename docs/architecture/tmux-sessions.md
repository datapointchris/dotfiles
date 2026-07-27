# tmux Sessions

How the tmux workspace is organised: a session is a task, and windows are the roles inside it.

## The Model

A session is a **task**, not a repository. Sessions are named `repo·task` —
`dotfiles·tmux-sessions`, `learning·api` — and the first status line lists them all. Inside a
session, windows are the roles that task needs: an editor, a shell, an agent, a log tail.

This inverts the more common arrangement, where a session is a repo and windows are whatever came
up while working in it. That arrangement fails in a specific way: tasks do not map onto repos one
to one, so a task gets started in whichever session happens to be focused, and finding it again
means remembering where it was put. Naming the task as the session removes the question — the task
*is* the session, and the status line shows all of them at once.

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
| `M-o` | Last session |
| `M-t` | New session (a bare name inherits the current repo prefix) |
| `prefix T` | Promote the focused window into its own session |
| `prefix s` | sesh picker — open a session, or make one from a directory |
| `prefix w` | Find a window in any session |

These are unprefixed because switching sessions is the most frequent move of the day. Alt is free
on both platforms: Hyprland binds SUPER, and AeroSpace's Alt bindings are letters and arrows that
none of these collide with. `M-[` is avoided because Alt+`[` emits the CSI prefix, which terminals
mis-parse.

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

The two naming schemes compose rather than collide, and `sesh` needs no configuration change.

sesh names a session after the **basename** of its path (`dir_length` defaults to 1), or after the
explicit `name` in a `[[session]]` block in `~/.config/sesh/sesh.toml`. It then sanitises the
result, replacing `.`, `:`, and runs of whitespace with `_`. It does **not** touch `·`, so
`repo·task` names survive sesh untouched and appear normally under `sesh list -t`.

That splits the work cleanly:

- **sesh opens a repo.** `prefix s` on `~/dotfiles` gives a session named `dotfiles` — no `·`, so
  the status line lists it as a plain `dotfiles`. That is the repo's home session.
- **`M-t` branches a task off it.** `tmux-sessions new` takes the current name up to the first `·`,
  which for a sesh-created session is the whole name, so `M-t voice` from `dotfiles` yields
  `dotfiles·voice`.

sesh has no way to create a `repo·task` session and does not need one — that is what `M-t` and
`prefix T` are for. A long-lived task session can still be given its own `[[session]]` block if it
is worth a fixed entry in the picker.

`prefix s` and `prefix w` are not two versions of the same picker. They sit at different levels,
and the split mirrors the two status lines: `prefix s` is line 1, `prefix w` is line 2 for every
session at once. sesh's own `sesh window` only lists windows **in the current session**, so it
cannot answer "which session is that window in" — the gap `prefix w` exists to fill. sesh in turn
does something `prefix w` cannot: it creates sessions from zoxide directories, config entries, and
`fd` results, so it reaches places that have no running session at all.

One pre-existing sesh behaviour is worth knowing, because it shows up in the status line: since
names come from the basename, two repos sharing one (`~/homelab` and `~/code/refs/homelab`)
produce the same session name. Setting `dir_length = 2` in `sesh.toml` disambiguates them.

## Migrating an Existing Window

`prefix T` moves the focused window out into a session of its own, prefilled with the window name.
This is the escape hatch for a task that got started inside whatever session happened to be
focused. A session holding a single window is renamed in place instead of being moved, since
moving its only window would leave an empty session for tmux to destroy.

## Files

| File | Role |
|------|------|
| `apps/common/tmux-sessions` | Switching, creation, promotion, status relocation |
| `configs/common/.config/tmux/tmux.conf` | Two-line status, keybindings, relocation call |
| `~/tools/theme/lib/generators/tmux.sh` | Generates line 1's format and colours |
