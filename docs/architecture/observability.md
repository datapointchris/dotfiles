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
| `runs/<id>.jsonl` | every `plan`, `check` and `apply` | `dotfiles logs`, during the run or after |
| `status.json` | every `check` | a caller asking where this machine stands |
| `nudge` | every `check` | zsh, at every prompt |

The split that matters most is the last one. `status.json` is a document a caller
reasons about; `nudge` is one line of human text. Deriving the line from the
document at prompt time would mean parsing JSON in zsh, which means `jq`, which
means a subprocess per shell — the exact cost `.zshrc`'s completion caching exists
to avoid. A file holding exactly the sentence to print is `$(<file)`, with no fork
at all.

The interchange document `plan --json` and `check --json` emit is a fifth thing
and is deliberately not in the table, because nothing here writes it: it goes to
stdout, and where it lands is the caller's business.

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
`host` is the bare lowercased hostname, per `standards/data.md` § "Machine
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

**The timing breakdown is `steps`, and a rename is the schema change a default
cannot absorb.** `Stage` already names the ordering across a run, so `phase`
meaning the breakdown inside one provider's `perform` left two ordering words in
one codebase; at schema 4 the constant is `runs.STEPS` and the stored key is
`steps`. Unlike `host` at schema 3, no default could carry this: an absent field
takes its default, while a renamed key reaches the constructor and raises, so
every record written before 4 would have become unreadable. `Timing.from_record`
accepts either spelling, which keeps what the type used to look like on the type
rather than in `read` — and is the pattern to copy for the next one.

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
`LOG_LEVEL` and the verbosity flags say. Those move the console threshold and
nothing else, which is the property that lets a run be quiet and still be
answerable afterwards.

**Every line carries the resource that provoked it.** `effects` sits below the
walk and cannot name the resource it is serving, so the walk binds the address
into contextvars around `observe` and around each `perform` — the same mechanism
`bind_run` already uses for the run id. It attributes lines that exist rather than
adding any, which is why it does not reopen the argument above against logging the
walk: an address on a `ran` line says which section spent the time, and the record
still owns every verdict. What stays unattributed is honest — the stray-branch
probe runs before the walk and belongs to no resource.

## `dotfiles logs` is its own noun, not a verb under `report`

The two artefacts have different authors and different lifetimes. A record is
**composed**: `sinks.record` walks the events and builds a typed `RunRecord` with
a schema and a versioned reader, and it is what travels off the machine. A stream
is **emitted**: whatever any module logged, at debug, in whatever shape that module
chose, and it is what stays behind. Filing the stream under a group whose help
reads "What past runs did" would also put a live follow under a past tense.

`show` rather than `read`, per `standards/cli-design.md` § "One word per job":
`read` earns its place only where something is left over for `show` to say, and
everything knowable *about* a stream is already on the record beside it. Nothing
installed spells it `read` either — `docker logs`, `kubectl logs`, `gh run view
--log`.

The one place the two nouns meet is `report show`, which reads the stream to name
a run's slowest commands. That rendering names `dotfiles logs show <id>`, because
a reader who wants the rest of what it summarised would otherwise have to know a
separate noun exists.

**`--follow` switches files, and that is the whole reason it is a command.** A
stream is named for the moment its run started, so following one file ends at the
next invocation — the exact thing that makes a second pane worth having is a
reader that survives the run boundary. A stable symlink cannot stand in:
`tail -F` pins to the resolved inode and does not notice a repoint, measured
both ways — repointing a symlink lost every line of the second file, while
replacing a real file by rename followed correctly. Owning the switch in the
reader needs no second copy of every byte, and it compares by *name* rather than
mtime because `Identity.stem` leads with a UTC timestamp for exactly that reason.

Discovery goes through the `.jsonl` files rather than the records, and it has to:
a run opens its stream first and writes its record last, so for the whole duration
of a run the stream exists and the record does not. Routed through the records,
the live run would be the single thing this could not find. It filters to this box
for the same reason `report latest` does — `runs/` is shared over Syncthing, so
another machine's check arriving mid-run is otherwise the newest file in the
directory.

## `-v`, `-vv` and `-q` on every reconciling leaf

A counted `-v` with a `-q` beside it, because that is what the neighbours on the
same machine take — uv, ruff, cargo, rsync and curl all ship that pair, and none
of them takes a `--verbosity` naming a log level. Passing both is a usage error
rather than a precedence rule: either order of resolution is defensible, which is
the tell that a caller passing both meant neither.

The second `-v` un-silences the HTTP client rather than moving the level again.
Debug is already the bottom, and the only detail still withheld there is the
per-request line `_quiet_the_http_client` pins to WARNING — one line per declared
tool on a refresh, between the rows a person is actually reading. Measured on a
refreshing `plan`: 1240 lines at `-v` with none of them HTTP, and 69 request
lines on top at `-vv`.

**`-q` suppresses the evidence, never the verdict.** The per-item rows go through
Rich rather than through a logger, so a flag that only moved the log threshold
changed nothing a reader could see. The resource verdict stays on stdout because
it is the answer to the question asked, and a `check` reporting by exit code alone
would be a worse command, not a quieter one.

The flags bind on the leaves rather than on the groups, for the reason `--machine`
does and which `main.py` records: Click parses group options before the subcommand
name, so a flag declared on the group turns `dotfiles apply -v` into
`No such option`. `tests/cli/test_conformance.py` walks the tree and fails when a
`plan`, `check` or `apply` is missing either one, which is what stops the
asymmetry `--dry-run` and `--force` each had.

**Every one of them takes the pair, with no exceptions.** The first cut spared
`network check` and `bundle check`, on the grounds that they answer a question
about a network or an archive rather than converging the machine, and so emit
nothing worth turning up. Measuring that afterwards showed it was false —
`network.py` goes through `effects` six times and `offline_bundle.py` twice.
`machines check` is the only one that really does
not emit, and `-q` still earns its place there because the finding rows it
suppresses are rendered the same way as everything else. The rule is the verb
rather than the subject, so learning `-v` on one `check` teaches it everywhere.

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
through `effects` and writes about 25KB. The scheduled check runs every ten
minutes (`schedule.INTERVAL_SECONDS`), and the state directory is its own
Syncthing folder, so the fleet keeps the history and no verb here prunes it.

That cadence is what makes the records a series rather than a sample, and it is
also what makes their volume worth stating: at roughly 36KB a run measured across
the last thirty, a machine writes about 5MB and 288 files a day, and nothing
prunes them.

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

## The interchange document crosses machines, so it is versioned

`plan --json` and `check --json` emit it — version, verb, machine, when it was
measured, the worst verdict, and every resource's row. Not a bare array of rows:
it crosses machines, and a reader cannot tell two shapes apart without a version
to test.

That is the point of it. The work box is git-only and off Syncthing, so the way
its needs reach the fleet is its check output travelling as a file. What it says
is missing or outdated is what the fleet builds into the next offline bundle
for it.

**Each resource's row names its items, and does not merely count them.** A row
carries the findings this verb kept, the ones the other verb keeps, everything
that was examined and matched, and any declaration problem — beside the counts
that summarise all four. Counts alone answered *how many*, and every question a
bundle builder or a caller actually has is *which*, so the only way to reach an
item was to parse the terminal rendering. The rows travel whatever `-v` says,
because a document is not a rendering and a verbosity flag must not decide what a
machine is told.

That is the version 2 shape, and the number moved for it. Nothing was removed, so
a version 1 reader still works — but a version 1 document has no `findings` key at
all, which is indistinguishable from a version 2 resource that found nothing, and
a builder acting on the first stages an empty bundle for a machine that named
twelve missing tools.

The resource-scoped read verbs emit this document too, and that is the other half
of the bump. `dotfiles packages plan --json` answered a bare resource row, and an
array of them whenever the walk turned out to be two resources wide — which
`--source` makes it whenever the section's runtime is declared `needed_by`, a fact
about the declaration that no caller of that door holds. One shape now, for one
resource and for nine.

## `status.json` is the state, not that document

The file a `check` writes carries the same header and every resource's verdict,
detail and counts — and none of the rows. It has its own version, still 1, because
it is its own artifact and has not changed: what moved to 2 was the document, and
a shared number could not have said which of the two.

**The difference is who asked.** The document is composed because a caller asked
for it and is kept by that caller, so carrying every item is exactly what it is
for. This file is written unasked by every check, several times a day, into a
directory the fleet syncs — and the question it exists to answer is whether this
machine is converged. Written as the document it measured 127 KB against 2.8 KB
for the same walk, of which 33 KB was 252 rows naming things that were fine.

So a caller wanting the items redirects the door that composes them —
`dotfiles check --json > wherever` — rather than reading a file that happens to be
lying around. `standards/cli-design.md` § "A fact on screen is reachable through
some machine door" is satisfied by that door and asks nothing of this file.

**`apply --json` is not this document, and deliberately so.** The two answer
different questions and unifying them would cost the bundle loop its input. `plan`
and `check` emit the versioned interchange document above — what a machine *needs*,
which is what travels to a machine that can reach the network and build a bundle
from it. `apply --json` is the run record: what a run actually *did*, for piping
into whatever wants it. It is emitted by reading back the record just written, so
it and `dotfiles report show --json` cannot give different answers about one run,
which building the same document twice would allow. Everything a run narrates goes
to stderr, so stdout stays a stream.

**Half the loop that consumes it is built.** `bundle check` answers whether a
staged bundle covers what a machine's plan asks for, resolved locally rather than
from a document. What is missing is the other direction: a `bundle create` that
takes a machine's own `plan --json` and carries only what that machine lacks,
instead of every installer the repo declares. The document is ready for it — a
row names its items, which is what a diff needs — and so is the history, because
every `plan` and `check` already files a run record carrying the same changes.

## Related

- [Management Interface](management-interface.md) — the two front doors and the verbs
- [System Configuration](system-configuration.md) — what the scheduled check measures
- [Testing](../development/testing.md) — the tiers, and what each may touch
