# tmux Session Tabs

How the tmux workspace is organised: sessions are tabs, windows are the roles inside one task.

## The Model

A tab is a **task**, not a repository. Sessions are named `repo·task` — `dotfiles·tmux-tabs`,
`learning·api` — and the first status line renders every session as a tab. Inside a tab, windows
are the roles that task needs: an editor, a shell, an agent, a log tail.

This inverts the more common arrangement, where a session is a repo and windows are whatever came
up while working in it. That arrangement fails in a specific way: tasks do not map onto repos one
to one, so a task gets started in whichever session happens to be focused, and finding it again
means remembering where it was put. Naming the task as the session removes the question — the task
*is* the tab, and the strip shows all of them at once.

Terminal tabs are deliberately not used for this. On macOS, Ghostty uses native `NSWindow` tabs,
which the Accessibility API reports as separate windows, so AeroSpace tiles each tab as its own
window; [Ghostty's own guidance](https://ghostty.org/docs/help/macos-tiling-wms) is to use a
multiplexer instead. Keeping tabs in tmux also keeps the model identical on Arch, where Hyprland
and Ghostty tabs would otherwise compete with tmux for the same job.

## Two Status Lines

The status bar runs two lines, set in `configs/common/.config/tmux/tmux.conf`:

| Line | Shows | Accent |
|------|-------|--------|
| 1 | Every session, as a tab | Green |
| 2 | The focused tab's repo, then its windows | Yellow |

The accents differ on purpose. Two rows of tabs in the same colour read as one long list; distinct
accents make it obvious that the rows are different axes.

Tab labels are split on `·` so the repo is muted and the task carries the emphasis — a glance lands
on the task without reading past the repo it belongs to. A session with no `·` renders once rather
than twice. Both formats are generated per-theme by the `theme` CLI (`lib/generators/tmux.sh`),
which owns status bar colour the same way it owns `pane-border-format`.

tmux draws `status-format[0]` topmost and ships its own window row there, so the window row has to
move down before the theme can claim line 1. `tmux-tabs install-status` does that relocation, and
`tmux.conf` runs it immediately **before** sourcing the theme, while the window row is still at its
stock value. The command is idempotent — on a config reload line 2 already holds the window row and
the copy is skipped.

## Navigation

| Key | Action |
|-----|--------|
| `M-.` | Next tab |
| `M-,` | Previous tab |
| `M-o` | Last tab |
| `M-t` | New tab (a bare name inherits the current repo prefix) |
| `prefix T` | Promote the focused window into its own tab |
| `prefix s` | sesh picker, for tabs not worth a keystroke |

These are unprefixed because switching tabs is the most frequent move of the day. Alt is free on
both platforms: Hyprland binds SUPER, and AeroSpace's Alt bindings are letters and arrows that
none of these collide with. `M-[` is avoided because Alt+`[` emits the CSI prefix, which terminals
mis-parse.

## Why Navigation Needs a Helper

The status bar renders sessions with `#{S:}`, which walks them in **session-id order** — creation
order. tmux's own `switch-client -n`/`-p` walk them **alphabetically**. Using the built-ins would
mean "next tab" landing on a visually random tab, so `tmux-tabs` re-derives the strip's order
before stepping.

Creation order is the right choice for the display, and the reason is worth keeping: it is stable.
Renaming a session leaves it where it is and a new one is appended at the end, exactly how browser
tabs behave. Alphabetical ordering would reshuffle the strip whenever a tab was created or renamed,
which destroys the positional memory that makes a tab bar fast.

Because the order only matters at keypress time, the strip itself stays a pure tmux format rather
than a `#(shell-command)`. Formats re-evaluate on tmux's own redraw events, so the bar updates the
moment a session is created, renamed, or killed; a shell command would inherit the 15-second
`status-interval` lag and need refresh hooks to compensate.

## Migrating an Existing Window

`prefix T` moves the focused window out into a tab of its own, prefilled with the window name. This
is the escape hatch for a task that got started inside whatever tab happened to be focused. A
session holding a single window is renamed in place instead of being moved, since moving its only
window would leave an empty session for tmux to destroy.

## Files

| File | Role |
|------|------|
| `apps/common/tmux-tabs` | Navigation, tab creation, promotion, status relocation |
| `configs/common/.config/tmux/tmux.conf` | Two-line status, keybindings, relocation call |
| `~/tools/theme/lib/generators/tmux.sh` | Generates the tab strip format and its colours |
