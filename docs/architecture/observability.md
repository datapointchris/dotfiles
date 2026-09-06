# Observability

What a run leaves behind, who reads it, and why the pieces are separate files
rather than one.

Every module named here documents its own job. This page is the arrangement —
the thing none of them can state, because each knows only its own end.

## Three artifacts, and the reader is what splits them

| Artifact | Written by | Read by |
| --- | --- | --- |
| `runs/<id>.json` | every `plan`, `check` and `apply` | `dotfiles report`, days later |
| `runs/<id>.jsonl` | every `plan`, `check` and `apply` | `dotfiles logs`, during the run or after |
| `status-<box>.json` | every `check` | a caller asking where this machine stands |

All three sit under `$XDG_STATE_HOME/dotfiles/`, which is replicated between
machines as its own unit. The fleet shares one history that way, and a machine
outside that replication keeps its own by construction rather than by a rule.
Every name carries the box because the directory is shared — a run id embeds it
(`20260823T224350Z-archlinux-apply.json`) and `status-<box>.json` spells it out.
What collided before they did is `src/dotfiles/paths.py`.

Every one of the three says the box inside as well, under `host`. The name is what
keeps two writes apart and the field is what a reader matches on, and two boxes
legitimately share a manifest — so a document naming only that has nothing to fold
the fleet's files by. `machine` is the manifest in all three, which is why the box
needed a second word rather than the same one: one Mac's stream grouped under the
box and its record under the manifest is one box in two rows of any fold across
the directory. `status.state`, `runs.Identity` and `logging.bind_run` each argue
their own end.

Nothing here is pushed at a person. Every one of the three is read by asking for
it, and the schedule that refreshes the status file is a `steps` row declared in
`architecture/system-configuration.md` § "`steps` is the name for no shared
mechanism". A machine reports what is wrong when `dotfiles check` is run, which
is the only place it says so.

The record and the stream divide one level down, on the same question. A record
is composed and travels off the machine. A stream is emitted and stays behind.
That is why the stream gets its own noun instead of a verb under `report`, which
`src/dotfiles/commands/logs.py` argues in full.

## The artifacts grade the walk; a verb grades the question it was asked

Both answers use one vocabulary — `converged`, `drift`, `issue`, which is what
`reconcile.worst` grades a whole machine with — because two words for one scale
are a disagreement waiting for a reader to find. What differs is the *question*,
and three of them are live at once.

A **verb** answers under one lens and exits on it. `plan` keeps what `apply` can
repair, so a plan over a box with three values only a person can set closes
`converged` and exits 0. That is `cli-design.md` § "A verb that measures returns
what it found, and drift is not a failure", and it is why `check` exists.

The **run record** is a transcript of the walk rather than a verb's answer.
`sinks.record` keeps every `Change` the engine yielded, under both lenses, so
`RunRecord.verdict` grades what was found — `issue` for that same plan. Graded
under the verb's lens instead, a box would report clean whenever its last run
happened to be a `plan`, because a fold across the directory takes the newest
record per box and cannot choose which verb wrote it. `report show` prints the
word as `found <verdict>` for that reason.

**`status-<box>.json` is the narrowest**, written under the check lens alone. Its
verdict says whether anything is *wrong* and never `drift`, and its per-resource
`pending` counts carry what `apply` would change. So a machine with items waiting
for an apply reads `converged` there and `drift` in the record of the same walk.

**The verdict travels through `dotfiles report`, never by reading the state file.**
An aggregator is a different tool on the same box — `doit dashboard` is the one —
and the thing it reads has to be a door rather than a file, or the naming
convention and the box-selection key become its problem to get right. `report
list --json` carries the verdict, and both buckets of addresses behind it, for
every run in the shared directory — which is the whole fleet from any machine in
it. The `outcome` sentence beside them is a rendering and names three.

## Nothing here prunes anything

Records accumulate, and the scheduled check runs on the interval
`src/dotfiles/providers/schedule.py` names, so the history is a series rather
than a sample. Why there is no retention bound is `src/dotfiles/runs.py`. What
happens to the directory afterwards belongs to the replication, which makes it
the fleet's question rather than this tool's.

## The interchange document is a fourth thing, and nothing here writes it

`plan --json` and `check --json` compose it and hand it to stdout, so where it
lands is the caller's business. It is the one artifact of the four with no reader
on this machine. A nonfleet box is git-only and outside the sync, so the way its
needs reach the fleet is its check output traveling as a file, and what that file
says is missing is what the fleet builds into the next offline bundle for it. Why it
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
