# Reloading a Running fzf From Outside

## Problem

A picker left open goes stale, so something outside fzf has to replace its rows. Sent over
fzf's `--listen` socket, this chain answers `HTTP/1.1 200 OK` and reloads the rows, and then
the header and footer never change:

```text
reload-sync(cat rows)+change-header(new header)+change-footer:new footer
```

fzf reports no error. Whatever follows `reload-sync` in the chain is lost. This was measured
on fzf 0.74.5 with `--track --id-nth=1`, and the cause inside fzf was not traced.

## Solution

Put the reload last. `change-footer:` has to end a chain as well, because its colon form is
the only one safe for text holding a parenthesis, so the footer goes in a request of its own:

```text
change-footer:updated 14:02   gh could not list PRs (check 'gh auth status')
change-header(new header)+reload-sync(cat rows)
```

`--track --id-nth=1` keeps the cursor on its item across the reload, provided the first field
names the item and not its position. fzf needs 0.71 for `--id-nth`. Index-based `--track` does
not survive a reload.

## Key Learnings

- `--listen=<path>.sock` needs the suffix to be read as a socket. A Unix socket accepts
  `reload` without `--listen-unsafe`.
- A reload that blanks the list is the failure to design against. `pull-requests` answers `[]`
  and exit 0 with a warning on stderr when a provider is unreachable, so an empty listing with
  a warning has to keep the old rows. A laptop losing its network reaches that path.
- A choice can arrive for a row fzf has not replaced yet, so resolve rows against every PR seen
  this run, keyed by `slug#number`, never against the latest list by index.
- *Rejected:* fzf 0.73's `every(N)` event with `bg-transform`. It removes the thread and the
  socket, and it needs a private subcommand that prints fzf actions, plus a state file the
  parent reads to resolve the choice. The thread keeps all of that in one process.
