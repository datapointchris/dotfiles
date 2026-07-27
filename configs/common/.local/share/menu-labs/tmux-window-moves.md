---
tags: [tmux, session, window, multiplexer, keybindings]
cadence: 1mo
---

# Move windows between tmux sessions

> A session is a unit of work and its windows are the places you touch to do it,
> so windows get reclassified constantly — work starts wherever you were and
> belongs somewhere else. This Lab drills the moves that make that cheap:
> `prefix .`, `prefix T`, `prefix w`, and the break/join pair. Scratch sessions
> only; your real ones are untouched.

## Setup

Copy this into your other pane. It builds three throwaway sessions, detached, so
they appear on the top status line without stealing focus:

```bash
tmux new-session -d -s lab-alpha -n 'audit packages'
tmux new-window  -d -t lab-alpha -n 'apply'
tmux new-session -d -s lab-beta  -n 'ci'
tmux new-session -d -s lab-inbox -n 'scratch'
tmux new-window  -d -t lab-inbox -n 'stray task'
```

## Steps

1. **See every window at once.** `prefix w`
   - Expect: an fzf list of every window in every session, session name on the
     left, live pane content previewed on the right.
   - Why: the status line only ever shows the *focused* session's windows, so
     this is the only view that answers "where did I leave that". Note the
     session column — with one repo open in several sessions it is the thing
     that tells two identically-named windows apart.

2. **Walk both axes.** `M-,` and `M-.` for sessions, `M-n` and `M-p` for windows
   - Expect: the top line's highlight moves for the first pair, the second line's
     for the second.
   - Why: four single-modifier keys on one hand. Direction is physical — `n` is
     left of `p`, `,` is left of `.` — so `M-n` goes *left* even though "n" reads
     as next. That inverts tmux's own `prefix n` / `prefix p`, which still mean
     next / previous.

3. **File a stray window into the right session.** Focus `lab-inbox:stray task`,
   then `prefix .` and type `lab-alpha`
   - Expect: the window leaves `lab-inbox` and lands at the end of `lab-alpha`.
   - Why: this is the routine move under a work-session model and the one that
     never existed under repo-sessions, where a window's session was fixed by its
     directory. It is what makes a catch-all inbox safe — start anywhere, file it
     once you know where it belongs.
   - Alternative: `move-window -t lab-alpha` at `prefix :` does the same thing
     and takes a `-b` to land it at the front instead.

4. **Promote a window that outgrew its session.** Focus any window in
   `lab-alpha`, then `prefix T` and accept the prefilled name
   - Expect: the window becomes a session of its own, named after itself.
   - Why: `prefix .` moves into an *existing* session, `prefix T` makes a *new*
     one. A session holding a single window is renamed in place rather than
     moved, since moving its only window would leave an empty session behind for
     tmux to destroy.

5. **Name things, because nothing else will.** `prefix ,` on a window, `prefix $`
   on a session
   - Expect: the prompt is prefilled with the current name; edit and confirm.
   - Why: the model only pays off if a window says `apply` rather than `zsh`.
     `allow-rename` is off so a program cannot overwrite your name, but
     `automatic-rename` still tracks the running command until a window is named
     explicitly — so an unnamed window drifts and a named one never does.

6. **Collapse two windows into one.** From the target window, `prefix j` and pick
   another window
   - Expect: that window's pane is pulled in beside the current one.
   - Why: `prefix j` / `prefix J` join side-by-side or stacked, and `prefix !`
     breaks a pane back out into its own window. Between them, "two windows" and
     "one window, two panes" are the same content in different shapes — grouping
     is a display decision you can change at any time, not something to get right
     when you create it.
   - Alternative: `prefix v` / `e` / `g` reshape the panes you already have into
     main-vertical, even, or tiled.

7. **Reach a directory that has no session yet.** `prefix s`
   - Expect: the sesh picker, a couple of hundred rows deep. `Ctrl-t` filters to
     running sessions, `Ctrl-g` to the three configured in `sesh.toml`, `Ctrl-x`
     to zoxide directories, `Ctrl-f` to an `fd` search, `Ctrl-a` back to
     everything.
   - Why: most rows are not sessions — they are places sesh can *make* one from.
     Selecting one creates a session, so when you want the directory inside the
     session you are already in, open a window instead (`prefix c`, then
     `prefix ,`).
   - Alternative: `Ctrl-d` kills the highlighted session without leaving the
     picker, which is the fastest way to prune several at once.

8. **Kill at the right scale.** `prefix x` a pane, `prefix k` a window, `prefix K`
   a session
   - Expect: the pane goes without asking; the window and session name their
     target and confirm first.
   - Why: only the pane is usually still visible somewhere else. A window carries
     scrollback and whatever its panes are running, which no name can restore, so
     it asks. `detach-on-destroy` is off, so killing the session you are in drops
     you into another rather than ending the client.

## Cleanup

Step 4 renamed one of them, so list first and kill what is left:

```bash
tmux list-sessions -F '#{session_name}' | grep -E '^lab-|^(audit packages|apply|ci|stray task)$'
tmux kill-session -t '=lab-alpha'; tmux kill-session -t '=lab-beta'; tmux kill-session -t '=lab-inbox'
```

## Notes

- Killing a session does not remove it from the last resurrect save, and restore
  is all-or-nothing. Anything killed inside the current 15-minute save window
  comes back the next time the `sesh` wrapper restores on a cold start.
- `prefix t` shows the full keybinding reference in a popup, and `menu` searches
  the same card by binding or by description.
