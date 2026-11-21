# tmux Sessions

How the tmux workspace is organized: a session is a unit of work, and its windows are the places you
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
for. It was abandoned because it carried no information: a session named after a directory
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
are separated by whitespace alone, and the current entry is marked by color and weight — green on
line 1 for the session you are in, yellow on line 2 for the window.

Those two choices come out of visual-perception research rather than taste. Color is the strongest
[preattentive channel](https://link.springer.com/article/10.3758/s13423-020-01859-9) — it is
processed in parallel across the visual field before you focus on anything, which is what makes
"where am I" answerable at a glance instead of by reading. And
[proximity](https://www.nngroup.com/articles/gestalt-proximity/) groups on *relative* distance, so
the gap between entries being wider than the gaps inside a name is the entire mechanism.

Dividers were tried and dropped. Padding plus a bar is two separators doing one job: it flattens
the spacing so proximity carries no information, and the extra marks only make the line busier.
Accenting the dividers was also tried — a tmux format loop has no lookahead, so an entry can color
the bar on one side of itself but not the one on its other side, which belongs to its neighbor.
That leaves all bars accented or none, and the current entry's color already carries the signal.

tmux draws `status-format[0]` topmost and ships its own window row there, so the window row has to
move down before the theme can claim line 1. `tmux-sessions install-status` does that relocation,
and `tmux.conf` runs it immediately **before** sourcing the theme, while the window row is still at
its stock value. The command is idempotent — on a config reload line 2 already holds the window row
and the copy is skipped.

Line 1's format is generated per-theme by the `theme` CLI (`lib/generators/tmux.sh`), which owns
status bar color the same way it owns `pane-border-format`.

## Switching

| Key | Action |
| --- | --- |
| `M-n` / `M-p` | Previous / next window |
| `M-,` / `M-.` | Previous / next session |
| `prefix <` / `prefix >` | Move the focused session left / right |
| `prefix {` / `prefix }` | Swap the focused window left / right |
| `M-{` / `M-}` | Swap the focused pane back / forward |
| `prefix A` / `prefix E` | Move the focused session to the front / end |
| `M-o` | Last session |
| `M-t` | New session |
| `prefix K` | Kill the session, after confirming |
| `prefix T` | Promote the focused window into its own session |
| `prefix s` | Choose a session from tmux's tree (tmux default) |
| `prefix w` | Find a window in any session |
| `prefix n` | The pane that has needed you longest, in any session |
| `prefix .` | Move the focused window into another session (tmux default) |
| `prefix p` | The `prs-board` session, or back to the session you left it from |

Both pairs repeat by holding Alt rather than re-arming a leader, and both are unprefixed because
moving around is the most frequent action of the day.

**Direction comes from where the keyboard's TMUX layer puts each key, not from the letter.** The
layer places `M-n` left of `M-p` and `M-,` left of `M-.`, and the left key of each pair goes back.
So `M-n` is *previous* even though `n` reads as "next", the reverse of tmux's own `prefix n` /
`prefix p`. Where the letters sit on a base layout plays no part, which is why the pairs keep their
direction across QWERTY and Colemak.

Every switching key takes one modifier. An earlier arrangement put sessions on the shifted `M-<` /
`M->` so the two axes were one gesture apart, and it was dropped because holding Alt and Shift
together is unreliable on the Corne. Not for the reason it first appears — the positional gate is
satisfied, since `COMMA` and `DOT` are keys 32 and 33 inside `KEYS_R` and `hold-trigger-on-release`
is set on every home-row mod, which is exactly what lets two same-hand mods chord. What breaks it is
`require-prior-idle-ms` (150 on `hml`, 100 on `hmls`): whichever mod is pressed second sees the
first as a prior keypress inside that window and resolves as a tap, emitting a letter. Pressing them
a beat apart works.

**Reordering is ranked by how often each level moves, and the ranking decides which table each pair
lands in.** Panes get swapped most, so `swap-pane` takes the root chord `M-{` / `M-}`. Windows take
the prefix braces that stock tmux gave `swap-pane`. Sessions move least and take `prefix <` / `>`,
which window swap vacated. Nothing here is on a bare Alt letter, which is what freed `M-h` and `M-l`.

That ranking is the whole justification, and it inverts the usual instinct that the prefix is for
rare things because it is safer. It is not a safety argument — none of these three destroys
anything. It is a keystroke-count argument, and it only holds while the frequency order does.

Alt is the only modifier available *to a letter*. tmux's key parser accepts `C-`, `M-` and `S-` and
rejects everything else, so a chord containing GUI — which the keyboards' `HYPER` does — cannot be
bound at any level, whatever the keyboard sends. Ctrl is spent on the terminal's own control codes,
which leaves Alt. Arrows are the exception and carry every modifier bit in their `CSI 1;<mod>`
encoding, which is how pane resize reaches `C-S-arrow`. `M-[` is avoided because Alt+`[` emits the
CSI prefix, leaving tmux to disambiguate it on the `escape-time` timer.

**AeroSpace no longer takes any of these.** It used to take four: `alt-h` and `alt-l` are window
focus, `alt-a` and `alt-e` are workspaces A and E. Moving every reorder key onto the prefix table
retired all four at once, because AeroSpace can only claim a root chord. Front and end kept their
letters and changed only their modifier. Watch `aerospace.toml` for what is left: `alt-comma` and
`alt-period` are commented out there, and uncommenting either silently takes the session switching
keys, which are still root chords.

`M-{` and `M-}` are clear of AeroSpace, which binds no braces. They are also close to unreachable by
hand on the Corne — `{` is the `S`+`F` combo and `}` is `J`+`L`, so each brace is built from its own
hand's Alt and Ctrl keys. The TMUX layer is how they get pressed.

On macOS this all rests on Ghostty delivering Option as Alt, which it does by default only for U.S.
keyboard layouts. Setting `macos-option-as-alt` explicitly would pin it; it is deliberately left
unset.

## Why Switching Needs a Helper

The status line and tmux's own `switch-client -n`/`-p` disagree about what "next" means, so
`tmux-sessions` re-derives the line's order before stepping. Its header comment carries why, and
`shift_session` beside it carries how the reordering keys get around there being no
`swap-session`. Windows need no helper at all, which is why the two pairs are bound differently:
`next-window`/`previous-window` already walk windows in the order line 2 draws them.

Creation order was chosen for the display because it is stable, and that stability is what makes
the line fast to read. Stable is not fixed — the four reorder keys move a session within a
server's life.

What the code cannot say is what happens across one. tmux-resurrect saves by session **name** and
its file lists them alphabetically, so a restore recreates them in that order and hands out ids to
match. A deliberate order lasts as long as the server does; a name is what orders sessions across
restarts.

Because the order only matters at keypress time, line 1 stays a pure tmux format rather than a
`#(shell-command)`. Formats re-evaluate on tmux's own redraw events, so the list updates the moment
a session is created, renamed, or killed; a shell command would inherit the 15-second
`status-interval` lag and need refresh hooks to compensate.

## Finding a Window in Another Session

`prefix w` opens a fuzzy picker over every window in every session. It replaced `choose-tree` on
that key: both list the same thing, but this one is typed at rather than navigated with arrows, and
recognition beats recall.

Deliberately a picker and not more status bar. The bar answers "where am I" and the picker answers
"where did I leave that", and `find_window` in `apps/common/tmux-sessions` gives the layout reason
those two want opposite shapes, resting on
[the vertical-list finding](https://www.nngroup.com/articles/vertical-nav/) that measures it.

What belongs here is the alternative that was rejected. A bar carrying every window would answer
"where did I leave that" no better and "where am I" worse, and it is the documented failure mode
of tab bars at scale. The
[CHI 2010 study of tabbed browsing](https://dubroy.com/blog/my-chi2010-talk-a-study-of-tabbed-browsing/)
found heavy users' bars scrolling with titles too small to read.

## Surviving a Reboot

A reboot brings back every session, window name and layout, the programs in each pane, and each
Claude conversation, and the cold start is a bare `tmux`. Three plugins and two scripts share the
work:

- **tmux-resurrect** writes a snapshot of the layout and each pane's command line, and replays it.
- **tmux-continuum** saves every minute from the status line, and restores when the server starts.
  A bare `tmux` creates session `0`, which the restore kills once the saved sessions exist.
- **tmux-restore** rewrites each pane's saved command into whatever restarts it: an agent's resume
  command with that pane's own flags, a program `@resurrect-processes` names, or, for anything else,
  the command typed on the zsh prompt and waiting for Enter. ssh comes back typed, because a saved
  `ssh host command` would run its command again.
- **`tmux-shutdown-save`** saves at shutdown.
- **`tmux-snapshots`** keeps `last` pointing at a whole snapshot, and thins the rest.

**A program comes back only when a shell started it.** resurrect records the pane's child process,
so a pane whose own process is the program saves an empty command and returns as a shell.
`tmux-monitor-layout` starts abtop and btop under the shell for that reason. An agent is the
exception, because tmux-restore checks the pane's own process for one too, so a Claude worker pane
`tmuxctl` opens comes back.

**A conversation a board opens in its own terminal comes back through an adapter.** tmux-restore
looks no deeper than the pane's child, where the board sits. An adapter in
`~/.config/tmux-restore/agents/` saves such a pane as the conversation's resume command followed by
the board's own, so quitting the conversation lands back in the board, as it did before.

**The save at shutdown runs before anything is stopped.** `tmux-shutdown-save`, run by its user
unit, holds a logind delay lock and saves on `PrepareForShutdown`. logind waits up to
`InhibitDelayMaxSec`, 5 s by default. The save, its hooks and the prune after it have to finish
inside that delay. One that does not leaves a cut-off snapshot, which `tmux-snapshots list` shows.
It is also the only save a detached server gets, since continuum's trigger is the status line a
detached server does not draw. The unit is on Wayland boxes only, so a Mac relies on continuum's
minute.

**`last` is checked before every restore.** resurrect relinks `last` to each new save without
looking at it, so one cut-off save hides every whole one before it. `tmux-snapshots repair-last`
runs as the pre-restore hook and points `last` at the newest whole snapshot first, which covers a
power cut in the middle of a save as well as a shutdown.

**Snapshots thin as they age**: every one for a day, the newest whole one in each hour for a week,
and one a day after that, until resurrect deletes it at `@resurrect-delete-backup-after`. The
thinning is for reading the list rather than for space. `tmux-snapshots list` and
`tmux-snapshots restore <stamp>` reach an older one.

**The resurrect fork runs one restore at a time.** Upstream starts a second restore when something
runs a short-lived server first, and the two split the same windows and squash the panes. The fork
is `andrewboldi/tmux-resurrect` on its `fix-concurrent-restore` branch, proposed upstream as #600.

**The two young plugins are pinned to a commit.** Each `@plugin` line carries the commit that was
tested after `#`. TPM hands that text to `git clone -b`, which takes a branch or a tag and no
commit. So pluginsync clones a pinned plugin at its commit before TPM runs, and TPM then finds it
installed. `dotfiles check` reports a checkout at another commit, and `dotfiles plugins apply` moves
it. TPM also counts a plugin installed by its directory alone. So pluginsync sets aside a checkout
cloned from another repository or branch than the line names, and puts it back if the new clone
does not arrive.

*Rejected:* saving on `client-detached`. Ghostty exits at a reboot while systemd is stopping the
session, so that save runs on a server being torn down. The snapshot it leaves holds pane lines and
nothing else — no windows, no names, every pane a shell because Claude has already died — and
resurrect points `last` at it, so the next restore brings back a fraction of the sessions.

*Rejected:* writing the command rewriting and the shutdown save here. tmux-restore's tests take
real agents through save, kill and restore, and its edge cases — two panes on one conversation, a
program that renames itself, a Python venv — would all be relearned. If it goes unmaintained, its
ideas move here.

*Rejected:* a true snapshot of the processes. CRIU restores each process under its original PID,
needs root, and cannot reopen a network connection, and hibernation resumes only under the kernel it
left, which the update a reboot installs replaces.

*Rejected:* sesh. It names a session after a directory, where the model names it after the work.
Its other duty was a shell wrapper that ran the restore before attaching, which existed only because
continuum's restore raced sesh's own attach, and which covered no other way of starting the server.
`prefix s` is tmux's `choose-tree -Zs`, `prefix w` finds a window, and `monitor` comes back from the
snapshot like any other session, with `prefix W` to rebuild its layout.

## Killing Sessions

Kill them freely. An initiative genuinely ends, which is the sense in which this is truer now than
it was under repo-sessions — a repo is never finished. `M-t` and a name rebuild one in a
keystroke. Keep one alive only when it holds something that cannot be cheaply rebuilt — a running
process, scrollback still being referenced, a pane layout that took setting up. A session sitting at
an idle shell is pure clutter in the list.

One caveat: a killed session stays in the snapshots until the next save, within a minute, so a cold
start inside that minute brings it back.

This matters because the status line has no automatic answer to "which of these am I still using".
Ordering and fading were both tried and reverted (see above), so pruning by hand with `prefix K` is
what keeps the list short.

Killing scales with case: `prefix x` a pane, `prefix k` a window, `prefix K` the session. The window
and session both confirm first and name their target in the prompt, since each takes something that
cannot be reconstructed from a name — a window carries its scrollback and whatever its panes are
running. `detach-on-destroy` is off, so killing the session you are in drops you into another rather
than ending the client. In `prefix s`'s tree, `x` kills the highlighted session, and `t` then `X`
kills every tagged one, which is better for pruning several at once.

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
version, and its module docstring says what it does and how the work is split between the model and
the local code. Three decisions behind it are not in there.

**Which panes it may touch is an argument, and the narrow reading of an absent one won.** Two
readings were available and the deciding question was which is safe to do by accident. A second
guard sits above the argument, because one argument cannot report that it was mistyped — an agent's
workspace only relocates where the argument named the window holding it. `tmux-rearrange --help`
carries the forms.

**The six-pane cap is imposed on the answer rather than requested of it.** A limit the model is
merely told about is honored most of the time. A limit applied afterwards is honored always.

**A new window opens with one pane, so any split at all was made by hand.** An even 188|188 is as
deliberate as a dragged 183|193, and treating only the uneven case as intentional is what once
collapsed six windows to a single pane.

What it cannot do is worth knowing before trusting it. Two-across versus three is undetectable —
both are default-shaped for their pane count — so that is a preference, not an observation. A
hand-tuned window whose panes get split across sessions loses its layout permanently, since the
layout string encodes pane ids and the old geometry; only the per-pane fraction transfers, and only
where the group stays together. It sees content, never intent: it can tell that two conversations
cite the same item, not that you want them apart.

## A Pane That Needs You Lights Its Window, Its Session and a Count

A Claude session that stops on a question or a permission prompt stamps its pane's
`@claude_needs_you` with the epoch seconds, and typing in that pane clears it. The bar draws the
stamp the way X11 draws an urgency hint, and the way i3 and sway draw an urgent workspace: a
window holding a flagged pane, and a session holding one, draw in the theme's alert style, and
`status-right` opens with `2 need you`. `prefix n` is i3's `[urgent=oldest] focus`.

**`tmux.conf` says what counts, and the theme draws it.** `tmux.conf` sets four user options, each
a format holding one character per flagged pane: `@window_needs_you`, `@session_needs_you`,
`@needs_you_status` and `@window_needs_you_style`. The theme generator expands them with `E:` in
the alert branches of line 1, the window format and `status-right`. The split follows ownership:
the theme owns every status color, so a theme apply rewrites those three formats. An option it
only reads survives that, and a theme loaded with no options set draws nothing extra.

**The oldest stamp goes first, because its prompt cache expires first.** The windows do not sort
by it. They keep their order and numbers so `prefix <n>` stays where it was, and the key gives the
order instead. A flag lasts until you type, so `prefix n` passes over the pane you are on and
pressing it again reaches the next.

**The current session and window keep their current style.** Line 1 already does this for a
bell alert. The count still includes them, and line 2 shows a flagged window beside the current
one.

**Only a terminal that draws blink gets it.** Windows Terminal has drawn SGR 5 since 1.4. Ghostty
parses it and draws nothing, with [ghostty-org/ghostty#11875](https://github.com/ghostty-org/ghostty/pull/11875)
open to change that, so `@window_needs_you_style` checks `client_termtype` and gives a Ghostty
client none.

*Rejected:* a `#(shell-command)` count. Setting a pane option redraws every client at once, so
the formats change within a redraw of the hook firing. A shell command would wait out the
15-second `status-interval`, for the reason line 1 stays a format.

## A Board Session Is Not an Initiative

`prs-board` is a board: a session `prefix p` owns, holding the pull request board, `prs tui`. One
process serves every other session, refreshing while you work elsewhere. It sits on line 1 and in the
`M-,` / `M-.` walk like any session. The comment above the binding in `tmux.conf` says why it is a
session rather than a popup or a window in each session.

The windows prs opens, such as a Claude review from `r`, open beside the board in the same session.
`q` quits prs and closes its window, and the session ends with it once nothing else is open there.
`tmux-rearrange` leaves every pane of a board where it is at session and server scope, and a
tmux-resurrect save leaves the session out. `board` in `apps/common/tmux-sessions` says how the board
is found and restarted.

## A tmux Client Inside a Popup Stalls on Esc

A popup that attaches a client to another tmux server, with `tmux -L <socket> new-session -A`, draws
no nesting refusal. Its Esc stalls unless that server's `clear` is overridden. A tmux client asks its
terminal for colors with OSC 10 and OSC 11, and holds a lone Escape for 500 ms until the answer comes.
A popup answers the device-attribute queries and never those two. So Escape took 507 ms in the nested
client against 15 ms in the popup alone, and merged with the next key into alt+key.

tmux sends the queries only to a terminal whose `clear` opens with `\E[`.
`set -as terminal-overrides ",*:clear=\\E7\\E[H\\E[2J"` opens it with a save-cursor instead, which
brought Escape to 17 ms. Features are learned by the same queries, so that server also has to name
them with `terminal-features`.

## Files

| File | Role |
| --- | --- |
| `apps/common/tmux-sessions` | Switching, creation, promotion, reordering, status relocation, boards |
| `apps/common/tmux-rearrange` | Bulk regroup: scan, propose, render a script |
| `apps/common/tmux-monitor-layout` | Lays a window out as the monitor, for `prefix W` |
| `apps/common/tmux-snapshots` | Lists, restores, repairs and thins the resurrect snapshots |
| `apps/common/claude-resurrect` | Resumes a Claude session here from the warehouse's copy |
| `configs/common/.config/tmux/tmux.conf` | Two-line status, keybindings, relocation call, plugins |
| `configs/trust/fleet/.config/tmux/restored-programs.conf` | Programs to restart that only machines on that trust run |
| `configs/trust/fleet/.config/tmux-restore/agents/fleet.sh` | Reopens a conversation a board opened, ahead of the board |
| `apps/display/wayland/tmux-shutdown-save` | Holds a shutdown delay lock and saves when logind announces one |
| `configs/display/wayland/.config/systemd/user/tmux-shutdown-save.service` | Runs it from login on |
| `lib/generators/tmux.sh` in the `theme` CLI | Generates line 1's format, the colors, and how a pane that needs you draws |
