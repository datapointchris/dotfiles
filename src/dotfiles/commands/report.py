"""Reading the run records.

Nothing here shells out — `sinks.keep` wrote the records on the way past, so this
reads them off disk and does not change when the resources move underneath it.

`path` exists to be substituted into another command: `ifiles upload "$(dotfiles
report path)"` is the whole fleet-analysis loop, which is why it prints a bare
path to stdout and nothing else. It is not the only place a path appears, though,
because a verb that makes you go and ask for one is a verb nobody knows about:
`latest` and `show` render it too, and a failed `apply` prints it unasked.
"""

from __future__ import annotations

import dataclasses
import dataclasses as dc
import json
import statistics
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from pathlib import Path

import typer
from rich.table import Table

from dotfiles import paths
from dotfiles import publishing
from dotfiles import remote as transport
from dotfiles import runs
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import resolved
from dotfiles.commands import verbosity
from dotfiles.output import VERDICT_COLOURS
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import error
from dotfiles.output import render_note
from dotfiles.output import warn
from dotfiles.resources import UNCONVERGED
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='What past runs did, and what they cost')

UNSUCCESSFUL = {str(status) for status in UNCONVERGED}
"""`UNCONVERGED` as `RunOutcome.action` spells it.

An action is a bare string, and `sinks.intention` writes values that are
deliberately not `OutcomeStatus` members at all, so the comparison is against
text. Derived rather than written out a second time — written out, this half said
`{FAILED, REFUSED}` and silently disagreed with `Outcome.ok` in both directions.
"""

JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')


def _unsuccessful(record: runs.RunRecord) -> str:
    """What kept a run from converging, in the words `apply` used at the time.

    Not `RunRecord.converged`, which is true only where every item MATCHED — that
    is the right answer for `show`, whose reader is looking at one run, and the
    wrong one for a list, where it marks a healthy apply that repaired something
    the same as the run that could not examine a resource at all.
    """
    refused = [issue.address for issue in record.issues]
    failed = [outcome.address for outcome in record.outcomes if outcome.action in UNSUCCESSFUL]
    named = sorted(set(refused + failed))
    if not named:
        return ''
    shown = ', '.join(named[:3])
    return f'{len(named)} unconverged: {shown}' + (', …' if len(named) > 3 else '')


def _readable(found: Iterable[Path]) -> Iterator[tuple[Path, runs.RunRecord]]:
    """Every record in a set that parses, saying on stderr which ones did not.

    The split `runs.Unreadable` exists for. A verb answering about the whole
    directory has an answer left when one file will not open — the runs that are
    fine — so it skips that file and names it. A verb answering about one record
    has nothing left, so it lets the refusal reach the boundary and exits ISSUE:
    the broken file is the question it was asked.

    Stderr rather than a row, because `--json` on this stream is a contract and a
    skipped record is not part of the answer.
    """
    for path in found:
        try:
            yield path, runs.read(path)
        except runs.Unreadable as unreadable:
            warn(str(unreadable))


def _listed(path: Path) -> dict[str, str]:
    """One listing row: what the filename says, plus what the record concluded.

    A record that will not parse still gets its row. The alternative drops a run
    out of a listing over a truncated file, which is the answer least useful to
    whoever is looking for the run that went wrong.
    """
    try:
        record = runs.read(path)
    except runs.Unreadable:
        return {'run': path.stem, 'machine': '', 'verb': '', 'outcome': 'unreadable'}
    return {'run': path.stem, 'machine': record.machine, 'verb': record.verb, 'outcome': _unsuccessful(record) or 'ok'}


def _find(identifier: str | None) -> Path:
    """Resolve a run id to its record, or the newest run when none is given."""
    if identifier is None:
        if found := runs.latest():
            return found
        error('no runs recorded yet')
        raise typer.Exit(ExitCode.ISSUE)

    matches = [path for path in runs.list_runs() if path.stem.startswith(identifier)]
    if not matches:
        # The id every rendering leads with is the record's, and it appears nowhere
        # in the filename the stem match reads — so the one identifier a reader has
        # in front of them was the only one that did not resolve. Second, because
        # this reads every record and the stem match reads none.
        matches = [path for path, record in _readable(runs.list_runs()) if record.id.startswith(identifier)]
    if not matches:
        raise typer.BadParameter(f'no run matching {identifier!r}')
    if len(matches) > 1:
        raise typer.BadParameter(f'{identifier!r} matches {len(matches)} runs; give more of the id')
    return matches[0]


SLOW_COMMANDS_SHOWN = 10
"""How many of a run's slowest commands `show` names.

A cap rather than a threshold, because the question this answers is "where did
the time go" and the answer is always the top of a sorted list. A threshold would
print nothing at all on the run that was merely slower than usual, which is the
one worth comparing against the run that was not.
"""


def _slow_commands(record_path: Path) -> list[tuple[float, str]]:
    """The commands a run spent longest in, from the event log beside its record.

    Read here rather than accumulated into the record, because it already exists:
    `effects.run` writes one `ran` line per command with its duration, and has for
    as long as there has been a debug stream. What was missing was any reader —
    the file answered "which command took the five minutes" perfectly and only
    for somebody who already suspected a command was the answer.

    Silent about a missing or malformed log. The stream is written best-effort on
    a machine whose `$XDG_STATE_HOME` may be read-only, and a run record that
    refused to render because its optional companion was absent would be trading
    the answer for the footnote.
    """
    log = record_path.with_suffix('.jsonl')
    found: list[tuple[float, str]] = []
    try:
        for line in log.read_text().splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get('event') == 'ran' and (argv := entry.get('argv')):
                found.append((float(entry.get('seconds', 0.0)), ' '.join(str(word) for word in argv)))
    except OSError:
        return []
    return sorted(found, reverse=True)[:SLOW_COMMANDS_SHOWN]


def _render(path: Path, record: runs.RunRecord) -> None:
    # `[{verdict}]` reads as a Rich style tag, so the word this line exists to say
    # was parsed as markup and dropped — every header printed a trailing blank.
    verdict = 'converged' if record.converged else 'drift'
    colour = VERDICT_COLOURS[verdict]
    console.print(f'[bold]{record.id}[/]  {record.box}  {record.verb}  [{colour}]{verdict}[/]')
    console.print(f'{record.started_at} · {record.duration_seconds:.1f}s')
    # What the reader wants the record *for* is usually to send it somewhere, and
    # the rendering that answers every other question about a run was the one place
    # its own location did not appear. Unwrapped and unparsed: this is meant to be
    # copied whole, and a path is not markup however many brackets it contains.
    console.print(str(path), soft_wrap=True, markup=False)

    if record.outcomes:
        table = Table(box=None, pad_edge=False)
        table.add_column('address')
        table.add_column('verdict')
        table.add_column('action')
        table.add_column('seconds', justify='right')
        for outcome in record.outcomes:
            table.add_row(outcome.address, outcome.verdict, outcome.action, f'{outcome.timing.duration_seconds:.2f}')
        console.print(table)

    if slow := _slow_commands(path):
        console.print()
        console.print('[bold]slowest commands[/]')
        commands = Table(box=None, pad_edge=False)
        commands.add_column('seconds', justify='right')
        commands.add_column('command')
        for seconds, command in slow:
            commands.add_row(f'{seconds:.2f}', command)
        console.print(commands)

    # The one place the two artefacts meet, so the one place worth naming the
    # other command: the table above is read *out of* the stream, and a reader
    # who wants the rest of it would otherwise have to know that a separate noun
    # exists. `logs show` resolves a run id, which is what this rendering leads with.
    if path.with_suffix('.jsonl').is_file():
        console.print()
        console.print(f'[blue]dotfiles logs show {record.id}[/] for everything this run logged')

    # Only where it went wrong: a provider hands back a detail line for a success
    # too, and 112 of "installed zk" buries the four that say why nothing was.
    for outcome in record.outcomes:
        if outcome.message and outcome.action in UNSUCCESSFUL:
            console.print(f'[red]{outcome.action}[/] {outcome.address}: {outcome.message}')

    for issue in record.issues:
        console.print(f'[red]{issue.kind}[/] {issue.address}: {issue.message}')


def _emit(path: Path, record: runs.RunRecord, as_json: bool) -> None:
    """The record itself for a machine, and a reading of it for a person.

    **`--json` is the record and nothing else**, which is why the slowest
    commands appear only in the rendering. `reconcile.apply_machine` emits its
    `--json` by reading back the file it just wrote, precisely so that a piped
    apply and a later `report show --json` are the same bytes for one run.
    Synthesising a field into one of them ends that, and the field would be
    derived rather than recorded — a second document assembled from two sources,
    which is the arrangement that property exists to refuse.

    The asymmetry is between a derived view and its source rather than between a
    person and a machine. What `_slow_commands` reads is the run's own `.jsonl`,
    which is machine-readable, sits beside this file, and holds one line per
    command with its duration. `dotfiles logs` is the noun that owns it:

        dotfiles logs show --json | jq -r 'select(.event == "ran")
          | "\\(.seconds)\\t\\(.argv | join(" "))"' | sort -rn | head
    """
    if as_json:
        emit_json(dataclasses.asdict(record))
    else:
        _render(path, record)


@app.command('latest')
def latest(as_json: bool = JsonOption) -> None:
    """Show the most recent run."""
    found = _find(None)
    _emit(found, runs.read(found), as_json)


@app.command('list')
def list_runs(
    machine: str = typer.Option(None, '--machine', help='Only runs on this machine'),
    verb: str = typer.Option(None, '--verb', help='Only runs of this verb'),
    limit: int = typer.Option(20, '--limit', min=0, help='How many to show'),
    as_json: bool = JsonOption,
) -> None:
    """List recorded runs, newest first."""
    found = runs.list_runs(machine=machine, verb=verb, limit=limit)
    if as_json:
        # Identifiers alone made this stream answer a narrower question than the
        # table beside it: a caller asking which machine is unhealthy got filenames
        # and had to open each record to find out, which is the fan-out the table
        # stopped doing. `outcome` is the same string the table prints, so the two
        # cannot drift into disagreeing about what a run concluded.
        #
        # Every record gets a row, including one that will not parse — which is why
        # this reads each path itself rather than through `_readable`, whose whole
        # job is to drop those. A listing is the answer to "what is here", and a
        # fleet-shared `runs/` is where a truncated file is least surprising and
        # least acceptable to silently omit. The unreadable row carries the run and
        # says so, and the fields it cannot know are empty rather than guessed.
        emit_json([_listed(path) for path in found])
        return
    if not found:
        return
    # Names alone made this a directory listing with a filter: finding which run
    # failed meant opening each record in turn, and the fleet shares `runs/`, so
    # "which one went wrong" is the question the list is reached for.
    table = Table(box=None, pad_edge=False)
    table.add_column('run')
    table.add_column('outcome')
    for path, record in _readable(found):
        wrong = _unsuccessful(record)
        colour = 'red' if wrong else 'green'
        table.add_row(path.stem, f'[{colour}]{wrong or "ok"}[/]')
    console.print(table)


@app.command('show')
def show(identifier: str = typer.Argument(..., help='Run id, or a unique prefix'), as_json: bool = JsonOption) -> None:
    """Show one run in full."""
    found = _find(identifier)
    _emit(found, runs.read(found), as_json)


@app.command('path')
def path(identifier: str = typer.Argument(None, help='Run id (default: the newest)')) -> None:
    """Print a run record's path, for piping into another command."""
    print(_find(identifier))


@app.command('upload')
def upload(
    identifier: str = typer.Argument(None, help='Run id (default: every record the remote does not have)'),
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Send this machine's run records to the remote, masked.

    Bare it is a reconcile rather than a push: the shelf is listed, and only the
    records missing from it are sent. So it is idempotent, it is the whole answer
    to "keep these in sync", and it needs no second verb — running it twice sends
    nothing the second time. `standards/cli-design.md` § "One closed verb
    vocabulary across every resource" is why this is `upload` beside `status
    upload` and `bundle upload` rather than a `sync` that means the same act under
    a third name.

    **Both files, always.** A run writes a `.json` of what it decided and a
    `.jsonl` of what it ran, and each answers half of a failure — the first its
    scope, the second its cause. Sending one is the shape that makes somebody ask
    for the other.

    Only this box's own records. `$XDG_STATE_HOME` is a Syncthing folder on the
    fleet, so the runs directory holds every machine's, and a bare "upload
    everything" would put a peer's records on this machine's shelf.
    """
    verbosity(verbose, quiet)
    directory, sent = _send(identifier)
    if not sent:
        render_note(f'{directory} already has every record for this machine')
        raise typer.Exit(ExitCode.CONVERGED)
    render_note(f'sent {sent} file(s) to {directory}')


def _send(identifier: str | None) -> tuple[str, int]:
    """The shelf written to, and how many files reached it.

    Its own function because `publish_after_apply` needs the same act without the
    verb's verbosity handling or its exit codes — a command function calling
    another command function inherits both, and typer's argument defaults are not
    the same thing as Python's.

    **`MACHINE_ID` selects, and the trust coordinate only screens.** `runs.begin`
    stamps every filename with the bare hostname on every box, so that is the one
    name `list_runs` can match. `publishing.discriminator` answers a different
    question — which name may *leave* here — and gives a blake2b digest to a
    hostname carrying a hyphen or a box off the fleet. Selecting on it matched no
    file at all and reported the digest, which appears in nothing the reader can
    see.
    """
    where = transport.reachable()
    session = resolved(None)
    trust = session.machine.coordinates.network_trust

    directory = transport.reports_for(where, session.machine_name)
    chosen = [_find(identifier)] if identifier else runs.list_runs(machine=paths.MACHINE_ID)
    if not chosen:
        error(f'no runs recorded for {paths.MACHINE_ID}')
        raise typer.Exit(ExitCode.ISSUE)

    already = frozenset(transport.listed(where, directory) or ())
    identities = publishing.identifying(trust)
    sent = 0
    # One directory for the whole send, removed when it ends. A record and its
    # log share a stem and differ by suffix, and two runs cannot share a
    # filename, so nothing staged here collides.
    with tempfile.TemporaryDirectory(prefix='dotfiles-report-') as staging:
        for record in chosen:
            for local in (record, record.with_suffix('.jsonl')):
                if not local.is_file() or local.name in already:
                    continue
                transport.push(where, _masked_copy(local, identities, Path(staging)), directory)
                sent += 1
    return directory, sent


def _screened(payload: object, identities: Mapping[str, str]) -> object:
    """Rooted first, then masked, and the order is what keeps the file readable.

    `rooted` turns every path under this home into `~/…`, which is both how a
    person writes one and how the account name leaves most of the document. What
    masking then finds is the handful that are not paths — an answer a command
    printed, a domain in an argument — and those become a placeholder because
    there is no shorter true form of them.

    Masking first would reach the same names and spell them
    `/home/<account-this-runs-as>/.local/bin/dotfiles`, which is a path nobody can
    read and a `~` that was available the whole time.
    """
    return publishing.masked(publishing.rooted(payload, str(Path.home())), identities)


def _masked_copy(local: Path, identities: Mapping[str, str], into: Path) -> Path:
    """The same file with every identifying name taken out, written into `into`.

    A copy rather than a rewrite, because the record on this machine is the
    account of what happened here and screening it in place would take that away
    from the one box entitled to it.

    **The caller owns the directory, and that is what makes it disposable.** A
    `mkdtemp` here answers to nobody: every file sent leaves a directory that
    nothing removes, and where `/tmp` is a tmpfs those are resident pages. A
    scheduled check that uploads twice a day then fills memory on a timer.

    `.jsonl` is handled line by line so the file stays line-delimited JSON: the
    whole file is not one document, and a raw-text pass would hold until a name
    contained a character JSON escapes.
    """
    if into.resolve() == local.parent.resolve():
        # The copy keeps the record's filename, so staging into its own directory
        # screens it in place — and the account of what happened on this box is
        # then gone, which is the one thing the copy exists to prevent. Narrowing
        # the signature made this unreachable; taking a destination gives it back.
        raise ValueError(f'{into} is where the record already lives, so staging there would overwrite it')
    staged = into / local.name
    if local.suffix == '.jsonl':
        lines = (_screened(json.loads(line), identities) for line in local.read_text().splitlines() if line.strip())
        staged.write_text(''.join(json.dumps(line) + '\n' for line in lines))
        return staged
    staged.write_text(json.dumps(_screened(json.loads(local.read_text()), identities), indent=2) + '\n')
    return staged


def publish_after_apply() -> None:
    """Publish this run's record, where the machine asked for that to be automatic.

    Off unless `remote.publish_reports_after_apply` says otherwise, for the reason
    `status.publish_after_apply` gives: a converge that reaches a server unasked is
    a change in posture on an employer network.

    **Unlike the status, this publishes a failed run too.** A status describes what
    the machine *is*, and one composed from a half-finished apply describes a
    machine part way through being something else. A record describes what a run
    *did*, and the run that failed is the one worth reading.

    Every failure is a warning rather than an exit code. The apply's verdict is
    about the machine, and failing it because a server did not answer would report
    a converged box as broken.
    """
    found = transport.read()
    if found.remote is None or not found.remote.publish_reports_after_apply:
        return
    try:
        directory, sent = _send(None)
    except typer.Exit:
        return
    except Exception as failed:
        warn(f'this run finished and its record was not published: {failed}')
        return
    if sent:
        render_note(f'published {sent} file(s) to {directory}')


@app.command('stats')
def stats(as_json: bool = JsonOption) -> None:
    """Aggregate time per address across every recorded run.

    The question this answers is what is slow and whether it is getting slower,
    which no single run can say — which is why `stats` is its own verb rather
    than a flag on `show`.
    """
    durations: defaultdict[str, list[float]] = defaultdict(list)
    records = [record for _, record in _readable(runs.list_runs())]
    for record in records:
        for outcome in record.outcomes:
            durations[outcome.address].append(outcome.timing.duration_seconds)

    if not durations:
        error('no runs recorded yet')
        raise typer.Exit(ExitCode.ISSUE)

    summary = {
        address: {
            'runs': len(seconds),
            'total': round(sum(seconds), 2),
            'median': round(statistics.median(seconds), 2),
            'slowest': round(max(seconds), 2),
        }
        for address, seconds in sorted(durations.items(), key=lambda item: -sum(item[1]))
    }

    unconverged = _never_converged(records)

    if as_json:
        emit_json({'durations': summary, 'unconverged': [dc.asdict(entry) for entry in unconverged]})
        return

    table = Table(box=None, pad_edge=False)
    table.add_column('address')
    for heading in ('runs', 'total', 'median', 'slowest'):
        table.add_column(heading, justify='right')
    for address, row in summary.items():
        table.add_row(address, *(str(row[key]) for key in ('runs', 'total', 'median', 'slowest')))
    console.print(table)

    if unconverged:
        console.print()
        console.print('[bold yellow]never converged[/]  installed again on every recent apply')
        churn = Table(box=None, pad_edge=False)
        churn.add_column('address')
        churn.add_column('machine')
        churn.add_column('applies', justify='right')
        for entry in unconverged:
            churn.add_row(entry.address, entry.machine, str(entry.applies))
        console.print(churn)


CHURN_THRESHOLD = 3
"""Consecutive applies acting on one item before it is called unconverged.

Three rather than two because an item legitimately installs on two runs in a row
— a release lands between them, or the first apply was the machine's first. What
three consecutive says is that installing it does not make it installed, which is
never a fact about the world.
"""


@dc.dataclass(frozen=True, slots=True)
class Unconverged:
    """One item an apply keeps acting on, and how many runs deep it goes."""

    address: str
    machine: str
    applies: int


def _never_converged(records: list[runs.RunRecord]) -> list[Unconverged]:
    """Items an apply acts on every time, which no amount of applying settles.

    The failure mode this exists to name: `brew install pkg-config` succeeds,
    `brew list` reports `pkgconf` because the formula was renamed, and the
    evidence check looks for the declared name and finds nothing. The install
    reports success, the run reports converged, and the item is reinstalled
    forever. Nothing sees the repetition until the fleet shares its run history.

    A registry package does not reach here at all. `_transact` re-observes what it
    installed and records `absent` rather than `done`, so the streak this counts
    never starts and the first run says it outright instead of the third. What
    reaches here is everything that cannot be re-measured that cheaply, which is
    what three consecutive applies is the fallback for.

    Counted per machine, from the newest apply backwards, stopping at the first
    run that left the item alone. A total count would rank a tool that drifted
    monthly for a year above one that has not converged since Tuesday, and only
    the second is broken.

    A converged item is *absent* from a record rather than present with no
    action — only changes get outcomes — so absence is what ends a streak. Making
    absence transparent instead kept counting through the runs that proved the
    item fine, which reported two long-fixed faults as current: the App Store
    rename and the awscli branch both showed six-deep streaks made entirely of
    history.
    """
    applies = [record for record in records if record.verb == 'apply']
    by_machine: defaultdict[str, list[runs.RunRecord]] = defaultdict(list)
    for record in applies:
        # By box, not by manifest. Keyed on the manifest, macmini's and mbp's
        # applies interleaved into one history, so either Mac leaving an item
        # alone ended the other's streak and a real fault on one of them read as
        # settled.
        by_machine[record.box].append(record)

    found: list[Unconverged] = []
    for machine, history in by_machine.items():
        ordered = sorted(history, key=lambda record: record.started_at, reverse=True)
        streaks: dict[str, int] = {}
        alive: set[str] | None = None
        for record in ordered:
            acted = {outcome.address for outcome in record.outcomes if outcome.action == 'done'}
            # The newest apply seeds the set: an item it left alone converged
            # there, whatever it did before, and this names what is wrong *now*.
            alive = acted if alive is None else alive & acted
            if not alive:
                break
            for address in alive:
                streaks[address] = streaks.get(address, 0) + 1
        found.extend(Unconverged(address, machine, count) for address, count in streaks.items() if count >= CHURN_THRESHOLD)
    return sorted(found, key=lambda entry: (-entry.applies, entry.address))
