# Observability

What a run leaves behind, who reads it, and why the pieces are separate files
rather than one.

Every module named here documents its own job. This page is the arrangement —
the thing none of them can state, because each knows only its own end.

## Four artefacts, and the reader is what splits them

| Artefact | Written by | Read by |
| --- | --- | --- |
| `runs/<id>.json` | every `plan`, `check` and `apply` | `dotfiles report`, days later |
| `runs/<id>.jsonl` | every `plan`, `check` and `apply` | `dotfiles logs`, during the run or after |
| `status-<box>.json` | every `check` | a caller asking where this machine stands |
| `nudge-<box>` | every `check` | zsh, at every prompt |

All four sit under `$XDG_STATE_HOME/dotfiles/`, which is its own Syncthing
folder. The fleet shares one history that way, and the work box keeps its own by
construction rather than by a rule, because it is not on Syncthing. Three of the
names carry the box because the directory is shared; what collided before they
did is `src/dotfiles/paths.py`.

The split that matters most is the last row. The status file is a document a
caller reasons about. The nudge is one line of human text. Deriving that line
from the document at prompt time would mean parsing JSON in zsh, which means
`jq`, which means a subprocess per shell — the exact cost `.zshrc`'s completion
caching exists to avoid. A file holding exactly the sentence to print is
`$(<file)`, with no fork at all. What makes it fire, and how old it may be
before the shell stops reading it, are the module docstring and
`MAX_AGE_SECONDS` in `src/dotfiles/status.py`. The schedule that writes it is a
`steps` row, declared in `architecture/system-configuration.md` § "`steps` is
the name for no shared mechanism".

The record and the stream divide one level down, on the same question. A record
is composed and travels off the machine. A stream is emitted and stays behind.
That is why the stream gets its own noun instead of a verb under `report`, which
`src/dotfiles/commands/logs.py` argues in full.

## Nothing here prunes anything

Records accumulate, and the scheduled check runs on the interval
`src/dotfiles/providers/schedule.py` names, so the history is a series rather
than a sample. Why there is no retention bound is `src/dotfiles/runs.py`. What
happens to the directory afterwards is Syncthing's, which makes it the fleet's
question rather than this tool's.

## The interchange document is a fifth thing, and nothing here writes it

`plan --json` and `check --json` compose it and hand it to stdout, so where it
lands is the caller's business. It is the one artefact of the five with no reader
on this machine. The work box is git-only and off Syncthing, so the way its needs
reach the fleet is its check output travelling as a file, and what that file says
is missing is what the fleet builds into the next offline bundle for it. Why it
carries a version, and what each generation holds, are `VERSION` in
`src/dotfiles/status.py`.

The status file is deliberately not that document, and the same module says why:
the difference is who asked. A caller wanting the items therefore redirects the
door that composes them — `dotfiles check --json > wherever` — rather than
reading a file that happens to be lying around.

## `apply --json` is the run record, not that document

The two answer different questions, and unifying them would cost the offline loop
its input, which `apply` in `src/dotfiles/main.py` states from the other end. The
record is emitted by reading back the file just written, so it and `report show
--json` cannot give different answers about one run — which composing the same
document twice would allow. Everything a run narrates goes to stderr, so stdout
stays a stream.

That loop is closed. `bundle check` answers whether a staged bundle covers what a
machine's plan asks for, and `bundle create --against` takes a published status
document and carries only what that machine lacks. What made it possible was a
row naming its items rather than counting them, which is what a diff needs.
`architecture/offline-bundles.md` is the whole of it.

## Related

- [Management Interface](management-interface.md) — the two front doors and the verbs
- [System Configuration](system-configuration.md) — what the scheduled check measures
- [Testing](../development/testing.md) — the tiers, and what each may touch
