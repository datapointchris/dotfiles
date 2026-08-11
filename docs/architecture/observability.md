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
| `runs/<id>.json` | every `plan`, `check` and `apply` | `dotfiles report`, days later |
| `runs/<id>.jsonl` | every `plan`, `check` and `apply` | a person debugging one failure |
| `status.json` | every `check` | another machine; the bundle builder reads `plan --json` |
| `nudge` | every `check` | zsh, at every prompt |

The split that matters most is the last one. `status.json` is the document a
caller reasons about; `nudge` is one line of human text. Deriving the line from
the document at prompt time would mean parsing JSON in zsh, which means `jq`,
which means a subprocess per shell — the exact cost `.zshrc`'s completion caching
exists to avoid. A file holding exactly the sentence to print is `$(<file)`, with
no fork at all.

## The run record

Two files per run under one stem: a JSON record of what happened, and the full
debug stream beside it.

**A `runs.Identity` is settled before the run starts**, because the two files are
written at opposite ends of it — `sinks.open_log` opens the stream first,
`sinks.keep` assembles the record from the event stream last — and they have to
agree on a filename and an id. Neither end is allowed to mint one. That is what
lets `run_id` in the log select exactly the lines belonging to the record beside
it, and what stopped the record from timing the loop over an already-collected
list and naming its file after the moment the run finished.

**The stem names the box, the record names both.** `machine` is the manifest and
`host` is the bare lowercased hostname, per `~/dev/standards/data.md` § "Machine
identity is a bare lowercased hostname" — two boxes legitimately share a manifest,
and macmini and mbp both declare `macos-personal-workstation`. Keyed on the
manifest alone, as it was through schema 2, their records were one
indistinguishable stream in a directory the whole fleet shares: `report list
--machine` could not separate them, the per-machine streak count in
`_never_converged` pooled both boxes so either Mac leaving an item alone ended the
other's streak, and "check the reports for both Macs" had no answer at all.
`paths.machine_id` had already been introduced for exactly this, and the `status-`,
`nudge-` and `latest-` files were keyed on it — the run records were the one place
it never reached. Readers take `RunRecord.box`, never `host`, because a record
written before schema 3 carries no host and a bare read would pool the entire
earlier history of all four boxes under one empty name.

**Both ends swallow an `OSError` on purpose.** `$XDG_STATE_HOME` is a Syncthing
folder on the fleet, absent on a fresh machine and read-only in more containers
than it should be; a verb that cannot open a log has still been asked a question
it can answer, so it falls back to the console sink and carries on. Same rule as
`status.record`.

**The verb hands over when the run began.** A record assembled from an event
stream is assembled once the last event is in, so a timestamp taken there measures
the walk over an already-collected list rather than the run: a WSL apply that
installed 112 things recorded 0.0003 seconds and named its file after the moment
it finished. Everything finer than the run is measured by the engine, which is the
only thing that knows when observing started and when a write finished.

**`keep` returns the path, and a failed `apply` prints it.** What a person does
with a record of a failed offline install is send it to the fleet, and the line
that used to name `dotfiles report latest` sent them hunting `$XDG_STATE_HOME` for
a file the caller was already holding. For the same reason the rendered record
carries its own path — it answered every other question about a run except where
it was.

**Timing is a field, not something grepped back out of the log.** A statistic
that has to parse a log stream is a statistic nobody computes, so every outcome
carries its own step breakdown and the recorder will not accept one without it.
The split earns its place because "the install was slow" and "the *downloads*
were slow" are different findings, and only a per-step number tells them apart.

**What is measured today is `observe` per resource and `act` per item.** The
engine holds the clock, because it is the only thing that knows when observing
started and when a write finished. A resource's row carries the measuring cost —
an inventory is one query per manager rather than one per package, so splitting it
across the items would be inventing a number — and each item's row carries what
acting on it cost. The finer `fetch`/`verify`/`extract` breakdown is a provider's
to write and no consumer reads it yet.

## The event stream is emitted from `effects` and nowhere else

The questions asked after a failed install — what did it actually download, which
step was slow — are answerable only if the detail was recorded while nobody wanted
it. So everything is emitted at debug and the file sink keeps all of it whatever
`LOG_LEVEL` says; that variable moves the console threshold and nothing else.

**Both are below the record, which is why the walk is not instrumented.**
`effects` is already the one module that touches the world outside the process, so
a line in `run`, `fetch`, `unpack` and `gunzip` covers every subprocess, download
and extraction there is. The record says an item took nine seconds; only these
lines say which of the four commands behind it did. Logging the walk instead would
restate the record — address, verdict, action and per-step timings are already
there — in a second format that then has to agree with the first.

**A command's transcript is kept only when it failed.** A successful `apt-get
install` is thousands of lines nobody will read, and keeping every one is how a
debug stream turns into something people switch off; a failed one is the entire
reason the stream exists. The record still carries the provider's one-line
`Outcome.message`, which is what survives being uploaded off the machine — the
stream is what stays behind and says what the command actually printed.

Measured on a converged Arch workstation: a read-only `check` makes 77 calls
through `effects` and writes about 25KB. The scheduled check runs every six hours
(`schedule.INTERVAL_SECONDS`), and the state directory is its own Syncthing
folder, so the fleet keeps the history and no verb here prunes it.

`dotfiles report` is how the records are asked about, and `--help` lists the
verbs. The one that shaped the format is `stats`: it totals time per address
across every record, which is the question that made timing a field. `path` exists
so a record can be piped somewhere else in one word — `ifiles upload "$(dotfiles
report path)"` is the fleet-analysis loop.

**`apply` records both halves**: a `Change` is what was decided and an `Outcome`
is what was done, so a `plan` record carries verdicts with no action and an
`apply` record carries the pair. It recorded nothing until the phase registry
went, and the reason was the original diagnosis rather than an oversight — a
phase layer returning booleans has no per-item value to keep. The `/tmp` failures
log went with it: `dotfiles report latest` is where a failed install is read.

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
