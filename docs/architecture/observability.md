# Observability

What a run leaves behind, who reads it, and why the pieces are separate files
rather than one.

Every module named here documents its own job. This page is the arrangement —
the thing none of them can state, because each only knows its own end.

## Four artefacts, three readers

Four things live under `$XDG_STATE_HOME/dotfiles/`, and they are separate because
their readers are:

| Artefact | Written by | Read by |
| --- | --- | --- |
| `runs/<id>.json` | a run — **not yet wired**, see below | `dotfiles report`, days later |
| `runs/<id>.jsonl` | the logging file sink | a person debugging one failure |
| `status.json` | every `check` | another machine, and the bundle builder |
| `nudge` | every `check` | zsh, at every prompt |

The split that matters most is the last one. `status.json` is the document a
caller reasons about; `nudge` is one line of human text. Deriving the line from
the document at prompt time would mean parsing JSON in zsh, which means `jq`,
which means a subprocess per shell — the exact cost `.zshrc`'s completion caching
exists to avoid. A file holding exactly the sentence to print is `$(<file)`, with
no fork at all.

## The run record

Two files per run: a JSON record of what happened, and the full debug event
stream beside it.

**The recorder is built and nothing drives it.** `runs.py` has the record, the
stopwatch and the writer, all tested, and `dotfiles report` reads them — but no
command calls `start`/`finish`/`write`, so `report latest` correctly answers "no
runs recorded yet". The design below is what it will record; what is live today is
the event stream, which the logging file sink writes on every run regardless.

**Timing is a field, not something grepped back out of the log.** A statistic
that has to parse a log stream is a statistic nobody computes, so every outcome
carries its own phase breakdown and the recorder will not accept one without it.
The split earns its place because "the install was slow" and "the *downloads*
were slow" are different findings, and only a per-phase number tells them apart.

The event stream exists because the questions asked after a failed install —
what did it actually download, which step was slow — are answerable only if the
detail was recorded while nobody wanted it. So everything is emitted at debug and
the file sink keeps all of it, whatever `LOG_LEVEL` says; the console threshold is
the only thing that variable moves.

`dotfiles report` is how the records are asked about, and `--help` lists the
verbs. The one that shaped the format is `stats`: it totals time per address
across every record, which is the question that made timing a field. `path` exists
so a record can be piped somewhere else in one word — `ifiles put "$(dotfiles
report path)"` is the intended fleet-analysis loop, and it is waiting on the same
wiring.

**Records are kept indefinitely.** There is no retention bound and no prune verb:
the value of the history is that it goes back, and "is this getting slower" cannot
be answered by a window that has already dropped the comparison. A record is a few
kilobytes of JSON. The state directory is its own Syncthing folder, so the fleet
shares one history and the work box keeps its own by construction rather than by a
rule, since it is not on Syncthing.

## The nudge fires on Issues, never on drift

Drift is the *normal* state of a machine between applies — it is exactly what
`apply` is for. Nudging about it at every prompt would train the nudge away inside
a week. An Issue is something wrong: a checker that could not run, a declaration
that will not parse. Those are rare enough to be worth interrupting for, which is
what makes the line worth reading when it does appear.

Two consequences follow, and both are deliberate:

**Every check writes it, not only the scheduled one.** An interactive check
refreshes what the next shell reports, which is what stops a nudge outliving the
problem it describes.

**The shell ignores a nudge older than a day.** A stopped timer would otherwise
leave a week-old warning on screen with nothing to say it had stopped being true.
The age check uses zsh's builtin `stat` and `datetime` modules, so the whole
snippet costs no subprocess — a startup nudge has to be invisible when there is
nothing to say, and a fork per prompt is not invisible.

`dotfiles shell-init <shell>` prints the snippet; `.zshrc` caches it behind the
`DOTFILES_NUDGE` flag.

## `status.json` crosses machines, so it is versioned

`check --json` emits the same document the file holds — version, machine, when it
was measured, the worst verdict, and every resource's row. Not a bare array of
rows: both forms cross machines, and a reader cannot tell two shapes apart without
a version to test.

That is the point of the document. The work box is git-only and off Syncthing, so
the way its needs reach the fleet is its check output travelling as a file. What
it says is missing or outdated is what the fleet builds into the next offline
bundle for it.

**The loop that consumes it is not built.** `bundle create --since <status.json>`
would diff the document to carry only what that machine is missing, and
`bundle check <status.json>` would answer whether it needs a new bundle at all.
Both are stubs today and error out saying so, which is why nothing here silently
returns a wrong answer. The document exists ahead of them on purpose: it is
written by every check already, so by the time the loop is built it will have a
history to diff against rather than starting from the day it ships.

## Related

- [Management Interface](management-interface.md) — the two front doors and the verbs
- [System Configuration](system-configuration.md) — what the scheduled check measures
- [Testing](../development/testing.md) — the tiers, and what each may touch
