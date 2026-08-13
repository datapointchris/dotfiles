"""The three verbs that read rather than converge: `report`, `bundle` and `network`.

None of them is a resource, so none is reached through the engine — which is why
they are one module. `report` reads the records `sinks.keep` left behind, `bundle`
handles an archive on disk, and `network` asks whether this box can reach what it
installs from. Each is measured through a real seam: a record written by
`runs.write`, a tarball built by `tarfile`, and a shadowed `curl` and `git` on the
sandbox `PATH`.

**`network check` shells out, so the httpx guard is not what holds it.** Its
probes are `curl` and `git ls-remote` through `effects.run`, and `git` is not among
the binaries the sandbox shadows by default — an unshadowed run reaches
github.com over a socket the autouse guard never sees. Every test here that runs it
shadows both, and `test_a_network_check_asks_only_the_shadowed_binaries` records
the argv to prove it.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import tarfile
from collections.abc import Callable
from pathlib import Path

import pytest

from dotfiles import runs
from dotfiles.commands import staging
from dotfiles.vocabulary import ExitCode
from matrix.harness import ANSWERS
from matrix.harness import DECLARES_LAZYGIT
from matrix.harness import LAZYGIT
from matrix.harness import REFUSED
from matrix.harness import Invocation
from matrix.harness import Sandbox

# ─────────────────────────────────────────────────────────────────────────────
# Records on disk, written by the function every verb writes through
# ─────────────────────────────────────────────────────────────────────────────


def record(
    sandbox: Sandbox,
    *,
    identifier: str,
    verb: str = 'apply',
    host: str = 'box',
    when: str = '20260101T000000Z',
    done: tuple[str, ...] = (),
    absent: tuple[str, ...] = (),
    failed: tuple[str, ...] = (),
    issues: tuple[str, ...] = (),
) -> Path:
    """One run record, through `runs.write` — the call `sinks.keep` makes.

    Written rather than produced by running a verb, because every axis below is a
    property of the *store*: which machine a run happened on, which verb it was,
    how long ago, and whether it converged. A real invocation decides all four for
    itself, and three of them from the box running the suite.
    """
    started = dt.datetime.strptime(when, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.UTC)
    identity = runs.Identity(id=identifier, machine=sandbox.machine, verb=verb, started=started, host=host)
    written = runs.start(identity)
    for address in done:
        written.record_outcome(address, 'drifted', 'done', runs.Timing(started_at='x', duration_seconds=1.0))
    for address in absent:
        written.record_outcome(address, 'drifted', 'absent', runs.Timing(started_at='x', duration_seconds=1.0))
    for address in failed:
        written.record_outcome(address, 'drifted', 'failed', runs.Timing(started_at='x', duration_seconds=1.0), 'the world said no')
    for address in issues:
        written.record_issue(address, 'refused', 'could not be examined')
    runs.finish(written)
    return runs.write(written, sandbox.runs)


def three_runs(sandbox: Sandbox) -> None:
    """Two boxes, three verbs, three days. The store every filter row reads."""
    record(sandbox, identifier='aaaaaaaaaaaa', verb='plan', host='box', when='20260101T000000Z')
    record(sandbox, identifier='bbbbbbbbbbbb', verb='apply', host='mbp', when='20260102T000000Z')
    record(sandbox, identifier='cccccccccccc', verb='check', host='box', when='20260103T000000Z')


BOX_PLAN = '20260101T000000Z-box-plan'
MBP_APPLY = '20260102T000000Z-mbp-apply'
BOX_CHECK = '20260103T000000Z-box-check'


def unlink_the_latest_link(sandbox: Sandbox) -> None:
    """Drop the pointer `runs.write` maintains, so `latest` falls back to the newest.

    A real state: the link is deliberately not synced, so a machine reading a
    fleet-shared `runs/` it has never written to has records and no link.
    """
    from dotfiles import paths

    link = sandbox.runs.parent / paths.LATEST_RUN.name
    link.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# report: an empty store
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('argv', 'exit_code', 'message'),
    [
        (('report', 'latest'), ExitCode.ISSUE, 'no runs recorded yet'),
        (('report', 'path'), ExitCode.ISSUE, 'no runs recorded yet'),
        (('report', 'stats'), ExitCode.ISSUE, 'no runs recorded yet'),
        (('report', 'show', 'anything'), ExitCode.USAGE, "no run matching 'anything'"),
    ],
    ids=['latest', 'path', 'stats', 'show'],
)
def test_a_verb_that_needs_a_run_says_so_when_the_store_is_empty(
    argv: tuple[str, ...], exit_code: ExitCode, message: str, cli: Callable[..., Invocation]
) -> None:
    """A machine that has never run is not a machine with a problem, and the
    distinction is the exit code: `show` was given an identifier that resolves to
    nothing, which is a usage error, and the other three were asked a question the
    store cannot answer."""
    ran = cli(*argv, catch_exceptions=True)

    assert ran.exit_code == exit_code
    assert message in ran.stderr


def test_an_empty_store_lists_nothing_rather_than_refusing(cli: Callable[..., Invocation]) -> None:
    """`list` is the one verb an empty store is a real answer for."""
    ran = cli('report', 'list')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.stdout == ''


def test_an_empty_store_still_puts_a_document_on_stdout(cli: Callable[..., Invocation]) -> None:
    """The machine contract does not lapse because there is nothing to say. A
    consumer piping this into `jq` gets an empty array, not an empty file."""
    ran = cli('report', 'list', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document == []


# ─────────────────────────────────────────────────────────────────────────────
# report list: the filters
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('flags', 'expected'),
    [
        ((), [BOX_CHECK, MBP_APPLY, BOX_PLAN]),
        (('--machine', 'box'), [BOX_CHECK, BOX_PLAN]),
        (('--machine', 'mbp'), [MBP_APPLY]),
        (('--machine', 'nosuch'), []),
        (('--verb', 'apply'), [MBP_APPLY]),
        (('--verb', 'plan'), [BOX_PLAN]),
        (('--verb', 'nosuch'), []),
        (('--limit', '2'), [BOX_CHECK, MBP_APPLY]),
        (('--limit', '1'), [BOX_CHECK]),
        (('--limit', '9'), [BOX_CHECK, MBP_APPLY, BOX_PLAN]),
        (('--machine', 'box', '--verb', 'plan'), [BOX_PLAN]),
        (('--machine', 'box', '--verb', 'apply'), []),
    ],
    ids=[
        'unfiltered',
        'machine-box',
        'machine-mbp',
        'machine-absent',
        'verb-apply',
        'verb-plan',
        'verb-absent',
        'limit-under',
        'limit-one',
        'limit-over',
        'machine-and-verb',
        'machine-and-verb-disjoint',
    ],
)
def test_the_listing_filters_narrow_by_what_the_filename_carries(
    flags: tuple[str, ...], expected: list[str], sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Newest first, and read off the names rather than the records — which is why
    `--machine` matches the *host* a record was written on and not the manifest
    both Macs share."""
    three_runs(sandbox)

    ran = cli('report', 'list', *flags, '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document == expected


def test_a_limit_of_zero_lists_every_run_there_is(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Current behaviour, pinned so the fix below is a change rather than a
    discovery. `runs.list_runs` ends `found[:limit] if limit else found`, and zero
    is falsy — so the one value that asks for nothing is read as no limit at all."""
    three_runs(sandbox)

    ran = cli('report', 'list', '--limit', '0', '--json')

    assert ran.document == [BOX_CHECK, MBP_APPLY, BOX_PLAN]


@pytest.mark.xfail(strict=True, reason='list_runs tests `if limit` rather than `if limit is not None`, so 0 means unlimited')
def test_a_limit_of_zero_lists_nothing(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`--limit 0` asks for no runs and is answered with all of them.

    The fault is a falsy-versus-absent conflation in `runs.list_runs`: `limit` is
    typed `int | None` and only `None` means unlimited, but the guard is `if
    limit`. Nothing else in the CLI is bounded this way, so a caller that computes
    its limit — `--limit "$(remaining)"` — gets the whole shared fleet directory at
    the moment it asked for none of it.
    """
    three_runs(sandbox)

    ran = cli('report', 'list', '--limit', '0', '--json')

    assert ran.document == []


# ─────────────────────────────────────────────────────────────────────────────
# report list: what the outcome column says
# ─────────────────────────────────────────────────────────────────────────────


def test_a_run_that_converged_is_marked_ok(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    record(sandbox, identifier='aaaaaaaaaaaa', done=('packages:ruff',))

    ran = cli('report', 'list')

    assert 'ok' in ran.stdout


@pytest.mark.parametrize(
    ('issues', 'failed', 'expected'),
    [
        (('packages',), (), '1 unconverged: packages'),
        ((), ('packages:ruff',), '1 unconverged: packages:ruff'),
        (('a', 'b'), ('c', 'd'), '4 unconverged: a, b, c, …'),
    ],
    ids=['refused-resource', 'failed-item', 'more-than-three'],
)
def test_the_listing_names_what_kept_a_run_from_converging(
    issues: tuple[str, ...], failed: tuple[str, ...], expected: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Both halves of the record answer this — an issue is a resource that could
    not be examined, a failed outcome is an item the world refused — and the column
    exists so finding the bad run does not mean opening every record in turn."""
    record(sandbox, identifier='aaaaaaaaaaaa', issues=issues, failed=failed)

    ran = cli('report', 'list')

    assert expected in ran.stdout


def test_an_install_that_left_the_item_absent_is_marked_ok(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Current behaviour, pinned. `UNSUCCESSFUL` holds FAILED and REFUSED, and an
    ABSENT outcome is neither — so the run renders green."""
    record(sandbox, identifier='aaaaaaaaaaaa', absent=('packages:pkg-config',))

    ran = cli('report', 'list')

    assert 'ok' in ran.stdout
    assert 'pkg-config' not in ran.stdout


@pytest.mark.xfail(strict=True, reason='report._unsuccessful omits OutcomeStatus.ABSENT, so a succeeded-but-absent install lists as ok')
def test_an_install_that_left_the_item_absent_is_named_in_the_listing(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """ABSENT is the exact failure the run history was shared to make visible, and
    it is the one unsuccessful action the listing calls `ok`.

    `OutcomeStatus.ABSENT` means the install command exited 0 and the thing is
    still not there — `brew install pkg-config` landing a formula renamed to
    `pkgconf`, thirteen times. `_never_converged` says that case is now caught on
    the first run rather than the third, because `_transact` re-observes and
    records `absent`. The listing is where a reader goes to find which run went
    wrong, and it is the one reader that does not count it.
    """
    record(sandbox, identifier='aaaaaaaaaaaa', absent=('packages:pkg-config',))

    ran = cli('report', 'list')

    assert 'packages:pkg-config' in ran.stdout


# ─────────────────────────────────────────────────────────────────────────────
# report latest / show / path
# ─────────────────────────────────────────────────────────────────────────────


def test_latest_follows_this_box_link_rather_than_the_newest_record(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`runs/` is shared by the whole fleet, so the newest record in it is whichever
    machine ran most recently. The link is what makes `latest` a statement about
    this box — asserted by writing the older record last, which is what a Mac's
    record arriving over Syncthing looks like from here."""
    record(sandbox, identifier='newerbyname1', verb='plan', when='20260202T000000Z')
    record(sandbox, identifier='writtenlast1', verb='check', when='20260101T000000Z')

    listed = cli('report', 'list', '--json')
    latest = cli('report', 'latest')

    assert listed.document[0] == '20260202T000000Z-box-plan'
    assert latest.stdout.startswith('writtenlast1')


def test_latest_falls_back_to_the_newest_record_when_the_link_is_gone(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The link is not synced, so a machine reading a shared directory it has never
    written to has records and no pointer. Answering approximately beats answering
    nothing."""
    record(sandbox, identifier='newerbyname1', verb='plan', when='20260202T000000Z')
    record(sandbox, identifier='writtenlast1', verb='check', when='20260101T000000Z')
    unlink_the_latest_link(sandbox)

    ran = cli('report', 'latest')

    assert ran.stdout.startswith('newerbyname1')


@pytest.mark.parametrize(
    'identifier',
    ['abcdef012345', 'abcdef', '20260101T000000Z-box-apply', '20260101'],
    ids=['whole-id', 'id-prefix', 'whole-stem', 'stem-prefix'],
)
def test_a_run_resolves_from_either_identifier_it_is_known_by(identifier: str, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The id every rendering leads with appears nowhere in the filename, so the
    one identifier a reader has in front of them is the one the stem match cannot
    resolve. Both are accepted, and the stem is tried first because it reads no
    files."""
    record(sandbox, identifier='abcdef012345', when='20260101T000000Z')

    ran = cli('report', 'show', identifier, '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document['id'] == 'abcdef012345'


@pytest.mark.parametrize(
    ('identifier', 'message'),
    [('2026', 'matches 2 runs; give more of the id'), ('nothing', "no run matching 'nothing'")],
    ids=['ambiguous', 'unknown'],
)
def test_an_identifier_that_does_not_name_one_run_is_a_usage_error(
    identifier: str, message: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Neither is a finding about the machine, so neither is exit 3."""
    record(sandbox, identifier='aaaaaaaaaaaa', when='20260101T000000Z')
    record(sandbox, identifier='bbbbbbbbbbbb', when='20260102T000000Z')

    ran = cli('report', 'show', identifier, catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert message in ran.stderr


def test_show_renders_the_record_and_names_the_file_it_came_from(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The path is in the rendering because sending the record somewhere is what a
    reader usually wants it for, and asking for it separately is a verb nobody
    knows about."""
    written = record(sandbox, identifier='abcdef012345', done=('packages:ruff',), issues=('symlinks',))

    ran = cli('report', 'show', 'abcdef')

    assert str(written) in ran.stdout
    assert 'packages:ruff' in ran.stdout
    assert 'refused symlinks: could not be examined' in ran.stdout


def test_show_json_is_the_record_and_carries_no_derived_field(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A piped `apply` and a later `report show --json` are the same bytes for one
    run, which is what `reconcile.apply_machine` reading its own file back exists
    to keep. The slowest commands appear only in the rendering because they are
    derived from a second file."""
    written = record(sandbox, identifier='abcdef012345', done=('packages:ruff',))
    written.with_suffix('.jsonl').write_text(json.dumps({'event': 'ran', 'argv': ['brew', 'list'], 'seconds': 9.0}) + '\n')

    ran = cli('report', 'show', 'abcdef', '--json')

    assert ran.document == json.loads(written.read_text())
    assert 'brew' not in ran.stdout


@pytest.mark.parametrize(
    ('log', 'shown'),
    [
        ('{"event": "ran", "argv": ["brew", "install", "ruff"], "seconds": 12.5}\n', True),
        ('{"event": "ran", "argv": ["brew", "install", "ruff"], "seconds": 12.5}\nnot json at all\n', True),
        ('', False),
        (None, False),
    ],
    ids=['well-formed', 'one-unparseable-line', 'empty', 'no-log-at-all'],
)
def test_the_slowest_commands_come_from_the_event_log_beside_the_record(
    log: str | None, shown: bool, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """The log is written best-effort onto a machine whose state directory may be
    read-only, so a run whose optional companion is absent or half-written must
    still render. A record that refused would be trading the answer for the
    footnote."""
    written = record(sandbox, identifier='abcdef012345', done=('packages:ruff',))
    if log is not None:
        written.with_suffix('.jsonl').write_text(log)

    ran = cli('report', 'show', 'abcdef')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ('brew install ruff' in ran.stdout) is shown


def test_path_prints_a_bare_path_on_stdout_and_nothing_else(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`ifiles upload "$(dotfiles report path)"` is the whole reason this verb
    exists, and a single stray character on stdout breaks it."""
    written = record(sandbox, identifier='abcdef012345')

    ran = cli('report', 'path')

    assert ran.stdout == f'{written}\n'
    assert ran.stderr == ''


# ─────────────────────────────────────────────────────────────────────────────
# report stats
# ─────────────────────────────────────────────────────────────────────────────


def test_stats_totals_one_address_across_every_recorded_run(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The question no single run can answer, which is why `stats` is a verb rather
    than a flag on `show`."""
    record(sandbox, identifier='aaaaaaaaaaaa', when='20260101T000000Z', done=('packages:ruff',))
    record(sandbox, identifier='bbbbbbbbbbbb', when='20260102T000000Z', done=('packages:ruff', 'symlinks'))

    ran = cli('report', 'stats', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document['durations']['packages:ruff'] == {'runs': 2, 'total': 2.0, 'median': 1.0, 'slowest': 1.0}
    assert ran.document['durations']['symlinks']['runs'] == 1


@pytest.mark.parametrize('applies', [1, 2, 3, 4], ids=['one', 'two', 'three', 'four'])
def test_an_item_every_apply_acts_on_is_called_unconverged_at_three(applies: int, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Two consecutive applies is legitimate — a release lands between them, or the
    first was the machine's first. Three says that installing it does not make it
    installed, which is never a fact about the world."""
    for day in range(applies):
        record(sandbox, identifier=f'aaaaaaaaaa{day:02d}', when=f'2026010{day + 1}T000000Z', done=('packages:pkg-config',))

    ran = cli('report', 'stats', '--json')

    expected = [{'address': 'packages:pkg-config', 'machine': 'box', 'applies': applies}] if applies >= 3 else []
    assert ran.document['unconverged'] == expected


def test_a_streak_ends_at_the_run_that_left_the_item_alone(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A converged item is absent from a record rather than present with no action,
    so absence is what ends a streak. Counting through it reported two long-fixed
    faults as current, both streaks made entirely of history."""
    record(sandbox, identifier='aaaaaaaaaa01', when='20260101T000000Z', done=('packages:pkg-config',))
    record(sandbox, identifier='aaaaaaaaaa02', when='20260102T000000Z', done=('packages:pkg-config',))
    record(sandbox, identifier='aaaaaaaaaa03', when='20260103T000000Z', done=('symlinks',))
    record(sandbox, identifier='aaaaaaaaaa04', when='20260104T000000Z', done=('packages:pkg-config',))

    ran = cli('report', 'stats', '--json')

    assert ran.document['unconverged'] == []


def test_a_streak_is_counted_per_box_rather_than_per_manifest(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """macmini and mbp share a manifest. Keyed on it, either Mac leaving an item
    alone ended the other's streak and a real fault on one read as settled."""
    for day in range(3):
        record(sandbox, identifier=f'aaaaaaaaaa{day:02d}', host='mbp', when=f'2026010{day + 1}T000000Z', done=('packages:pkg-config',))
        record(sandbox, identifier=f'bbbbbbbbbb{day:02d}', host='macmini', when=f'2026010{day + 1}T000100Z', done=('symlinks',))

    ran = cli('report', 'stats', '--json')

    found = [(entry['address'], entry['machine']) for entry in ran.document['unconverged']]
    assert found == [('packages:pkg-config', 'mbp'), ('symlinks', 'macmini')]


@pytest.mark.parametrize('verb', ['plan', 'check'], ids=['plan', 'check'])
def test_only_an_apply_can_contribute_to_a_streak(verb: str, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A plan that keeps reporting the same drift is a machine nobody has applied,
    which is not the fault this counts."""
    for day in range(4):
        record(sandbox, identifier=f'aaaaaaaaaa{day:02d}', verb=verb, when=f'2026010{day + 1}T000000Z', done=('packages:pkg-config',))

    ran = cli('report', 'stats', '--json')

    assert ran.document['unconverged'] == []


# ─────────────────────────────────────────────────────────────────────────────
# report: a record it cannot read
# ─────────────────────────────────────────────────────────────────────────────


def corrupt_store(sandbox: Sandbox) -> None:
    """One readable record and one truncated one, with the link out of the way.

    Zero bytes is what an interrupted or out-of-space `write_text` leaves, and
    `sinks.keep` catches the OSError so the run itself reports nothing. The link is
    removed so the corrupt record is the one `latest` selects, which is the state a
    machine reading a fleet-shared directory is already in.
    """
    record(sandbox, identifier='aaaaaaaaaaaa', verb='plan', when='20260101T000000Z')
    (sandbox.runs / '20260103T000000Z-box-check.json').write_text('')
    unlink_the_latest_link(sandbox)


@pytest.mark.parametrize(
    'argv',
    [('report', 'list'), ('report', 'stats'), ('report', 'latest'), ('report', 'show', '20260103')],
    ids=['list', 'stats', 'latest', 'show'],
)
def test_one_unreadable_record_takes_down_every_verb_that_opens_a_record(
    argv: tuple[str, ...], sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Current behaviour, pinned. `runs.read` calls `json.loads` on whatever is
    there and nothing above it catches a parse error."""
    corrupt_store(sandbox)

    with pytest.raises(json.JSONDecodeError):
        cli(*argv)


@pytest.mark.parametrize(
    ('argv', 'expected'),
    [
        (('report', 'list', '--json'), ['20260103T000000Z-box-check', '20260101T000000Z-box-plan']),
        (('report', 'path'), None),
    ],
    ids=['list-json', 'path'],
)
def test_a_verb_that_only_names_a_record_survives_an_unreadable_one(
    argv: tuple[str, ...], expected: list[str] | None, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """The two verbs that answer from the filename alone. `list --json` emits stems
    and `path` prints one, so neither opens the file — which is the same property
    that makes the filter matrix above read no records."""
    corrupt_store(sandbox)

    ran = cli(*argv)

    assert ran.exit_code == ExitCode.CONVERGED
    if expected is not None:
        assert ran.document == expected


@pytest.mark.xfail(strict=True, reason='runs.read lets json.JSONDecodeError out, so one truncated record ends the whole listing')
def test_the_listing_reports_the_runs_it_can_read(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """One unreadable record makes the entire run history unreadable.

    `runs/` is a Syncthing folder shared by the whole fleet, and a record is
    written with a plain `write_text` — so an interrupted process or a full disk
    leaves a truncated file that every reading verb then dies on. The companion
    event log is already tolerated exactly this way: `_slow_commands` catches its
    own parse errors line by line and says so, on the grounds that a run must not
    refuse to render because an optional file is malformed. The record's own reader
    has no such guard, and the blast radius is larger — `list`, `stats`, `latest`
    and `show` all stop answering about the runs that are fine.
    """
    corrupt_store(sandbox)

    ran = cli('report', 'list')

    assert '20260101T000000Z-box-plan' in ran.stdout


def test_a_file_that_is_not_a_run_record_breaks_the_machine_filter(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Current behaviour, pinned. `--machine` splits the stem on the hyphens it
    expects and indexes the result without checking that they were there."""
    record(sandbox, identifier='aaaaaaaaaaaa', verb='plan', when='20260101T000000Z')
    (sandbox.runs / 'notes.json').write_text('{}')

    with pytest.raises(IndexError):
        cli('report', 'list', '--machine', 'box', '--json')


@pytest.mark.xfail(strict=True, reason='list_runs indexes stem.split("-", 1)[1] without checking the name has the shape it assumes')
def test_the_machine_filter_ignores_a_file_it_cannot_name(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Any `.json` in `runs/` that is not named like a run crashes `--machine`.

    The unfiltered listing tolerates it and so does `--verb`, which uses `rsplit`
    and cannot raise. Only `--machine` indexes into a split that may have one
    element. A filter's job is to decide whether a row matches, and a row it cannot
    parse does not match — raising `IndexError` out of the CLI is the one answer
    that is neither.
    """
    record(sandbox, identifier='aaaaaaaaaaaa', verb='plan', when='20260101T000000Z')
    (sandbox.runs / 'notes.json').write_text('{}')

    ran = cli('report', 'list', '--machine', 'box', '--json')

    assert ran.document == ['20260101T000000Z-box-plan']


# ─────────────────────────────────────────────────────────────────────────────
# report reads what a verb wrote
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('verb', ['plan', 'check', 'apply'], ids=['plan', 'check', 'apply'])
def test_a_reconcile_verb_files_a_record_report_can_read_back(verb: str, cli: Callable[..., Invocation]) -> None:
    """The join between the two halves of this module. Everything above builds its
    store with `runs.write`; this proves the CLI writes one the same reader
    resolves, without the test choosing the machine, the verb or the timestamp."""
    cli(verb)

    ran = cli('report', 'latest', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document['verb'] == verb
    assert ran.document['machine'] == 'box'
    assert ran.document['schema'] == runs.SCHEMA


# ─────────────────────────────────────────────────────────────────────────────
# bundle: the verbs that are not built
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('verb', ['prune'], ids=['prune'])
def test_an_unbuilt_bundle_verb_refuses_rather_than_answering_nothing(verb: str, cli: Callable[..., Invocation]) -> None:
    """Exit 3 and a sentence saying what it would do, which is the only honest
    answer a stub can give — exiting 0 would report a machine as checked by a verb
    that checked nothing.

    `check` and `show` were stubs when this was written and are implemented on this
    branch, so they moved to the case below. `prune` is the one still owed.
    """
    ran = cli('bundle', verb, catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert f'bundle {verb} is not built' in ran.stderr


@pytest.mark.parametrize('verb', ['check', 'show'], ids=['check', 'show'])
def test_a_built_bundle_verb_with_nothing_staged_names_the_path_and_the_fix(verb: str, cli: Callable[..., Invocation]) -> None:
    """Now that these are implemented, an absent bundle is a finding about the
    machine rather than about the verb.

    The distinction the previous case protected still holds — exit 3 rather than 0,
    because a verb that found nothing to read has not checked anything. What
    changed is that the sentence is about the bundle instead of about the stub.
    """
    ran = cli('bundle', verb, catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert 'no readable bundle at' in ran.stderr
    assert 'dotfiles bundle stage' in ran.stderr


# ─────────────────────────────────────────────────────────────────────────────
# bundle create
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('platform', staging.PLATFORMS)
def test_every_offered_platform_is_accepted_and_stops_at_the_manifest(
    platform: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Read off `staging.PLATFORMS` rather than written down, so a platform added
    there is measured here without an edit.

    Each gets past validation and dies resolving the manifest, which is what proves
    the platform itself was accepted — the sandbox declares only `box`, and the
    error names the manifest the leaf asked for.
    """
    ran = cli('bundle', 'create', '--platform', platform, catch_exceptions=True)

    assert 'has no manifest' in ran.stderr
    assert 'Available: box' in ran.stderr


def test_an_unknown_platform_is_a_usage_error_naming_the_ones_that_exist(cli: Callable[..., Invocation]) -> None:
    ran = cli('bundle', 'create', '--platform', 'sunos-sparc', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert "unknown platform 'sunos-sparc'" in ran.stderr


def test_bundle_create_always_builds_for_the_work_box_manifest(cli: Callable[..., Invocation]) -> None:
    """`create_bundle.main` takes `--manifest` and the leaf never passes it, so the
    manifest is fixed at `wsl-work-workstation` whatever machine runs the command.

    Pinned rather than corrected: which manifests the front door should offer is an
    interface question. What this asserts is only that the manifest is not the
    running machine's — the sandbox is `box` and the failure names the other one.
    """
    ran = cli('bundle', 'create', catch_exceptions=True)

    assert 'wsl-work-workstation: has no manifest' in ran.stderr


def test_a_bundle_that_cannot_be_built_exits_one(cli: Callable[..., Invocation]) -> None:
    """Current behaviour, pinned. `create_bundle.main` returns 1 for a `BundleError`
    and the leaf raises `typer.Exit` on that return value directly."""
    ran = cli('bundle', 'create', catch_exceptions=True)

    assert ran.exit_code == ExitCode.DRIFT


@pytest.mark.xfail(strict=True, reason='bundle create returns create_bundle.main verbatim, so a build failure exits DRIFT')
def test_a_bundle_that_cannot_be_built_exits_issue(cli: Callable[..., Invocation]) -> None:
    """A failed build reports itself as drift, which in the machine contract means
    the opposite of a problem.

    Exit 1 is DRIFT: the machine differs from its declaration, which is what apply
    is for and is not worth reporting as wrong. A bundle that could not be built is
    an Issue by the same vocabulary, and `windows create` — the sibling verb in this
    same file, failing the same way on a `BundleError` — exits `ExitCode.ISSUE`. The
    two disagree because this one passes `create_bundle.main`'s argparse-era return
    value straight through to `typer.Exit`.
    """
    ran = cli('bundle', 'create', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE


# ─────────────────────────────────────────────────────────────────────────────
# bundle stage
# ─────────────────────────────────────────────────────────────────────────────


def bundled(directory: Path, name: str, *, manifest: bool = True, member: str = 'installers') -> Path:
    """A tarball shaped like one `bundle create` writes, named so `newest` finds it."""
    staged = directory / 'build' / member
    staged.mkdir(parents=True, exist_ok=True)
    if manifest:
        (staged / 'manifest.txt').write_text('# Format: category|name|version|filename\nbinary|lazygit|0.45.0|lazygit\n')
    else:
        (staged / 'README.txt').write_text('nothing a provider reads\n')

    archive = directory / name
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(staged, arcname=member)
    return archive


def test_staging_with_no_archive_anywhere_says_where_it_looked(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The two directories searched are the two a tarball is ever copied to, and
    naming them is what turns "no bundle" into something a reader can act on."""
    ran = cli('bundle', 'stage', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert 'no bundle archive in' in ran.stderr
    assert 'dotfiles bundle create' in ran.stderr


@pytest.mark.parametrize('directory', ['root', 'home'], ids=['beside-the-checkout', 'in-home'])
def test_an_unnamed_stage_finds_the_bundle_in_either_searched_directory(
    directory: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """The default is right often enough that naming the archive is the exception:
    a machine has one bundle and its name carries a date nobody types."""
    bundled(getattr(sandbox, directory), 'dotfiles-offline-v20260101-box-linux-x86_64.tar.gz')

    ran = cli('bundle', 'stage')

    assert ran.exit_code == ExitCode.CONVERGED
    assert (sandbox.bundle / 'manifest.txt').is_file()


def test_a_bundle_beside_the_checkout_wins_over_an_older_one_in_home(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Directories are tried in order rather than the newest taken across both: a
    tarball just copied next to the checkout is the one meant, even where a stale
    one is still sitting in `$HOME`."""
    bundled(sandbox.root, 'dotfiles-offline-v20260101-box-linux-x86_64.tar.gz')
    bundled(sandbox.home, 'dotfiles-offline-v20260909-box-linux-x86_64.tar.gz')

    ran = cli('bundle', 'stage')

    assert 'dotfiles-offline-v20260101' in ran.stderr


def test_a_named_archive_is_staged_wherever_it_sits(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Named only where the default is wrong, so the argument has to reach past the
    two searched directories."""
    archive = bundled(sandbox.root / 'elsewhere', 'anything-at-all.tar.gz')

    ran = cli('bundle', 'stage', str(archive))

    assert ran.exit_code == ExitCode.CONVERGED
    assert (sandbox.bundle / 'manifest.txt').is_file()


@pytest.mark.parametrize(
    ('build', 'message'),
    [
        ('unreadable', 'is not a readable archive'),
        ('no-manifest', 'carries no manifest.txt, so it is not a dotfiles bundle'),
    ],
    ids=['unreadable', 'no-manifest'],
)
def test_an_archive_that_is_not_a_bundle_is_refused_before_anything_is_staged(
    build: str, message: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """The manifest decides, not the member's name: the name is what the bundler
    happened to call its staging directory, whereas the manifest is the agreement
    the providers read. Staging the wrong tarball otherwise fails much later, as
    every tool in the plan missing at once."""
    if build == 'unreadable':
        archive = sandbox.root / 'broken.tar.gz'
        archive.write_text('not a tarball at all')
    else:
        archive = bundled(sandbox.root, 'shaped-wrong.tar.gz', manifest=False)

    ran = cli('bundle', 'stage', str(archive), catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert message in ran.stderr
    assert not sandbox.bundle.exists()


def test_a_newer_bundle_refreshes_what_it_carries_and_leaves_the_rest(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Merged into rather than replaced, which is what `tar -x` over the top does
    and what the bundle's own README describes. Replacing would delete the wheels an
    interrupted run still needs."""
    first = bundled(sandbox.root / 'one', 'dotfiles-offline-v20260101-box-linux-x86_64.tar.gz')
    cli('bundle', 'stage', str(first))
    (sandbox.bundle / 'wheels').mkdir()
    (sandbox.bundle / 'wheels' / 'pyyaml.whl').write_text('bytes an interrupted run still needs')

    second = bundled(sandbox.root / 'two', 'dotfiles-offline-v20260202-box-linux-x86_64.tar.gz')
    ran = cli('bundle', 'stage', str(second))

    assert ran.exit_code == ExitCode.CONVERGED
    assert (sandbox.bundle / 'wheels' / 'pyyaml.whl').is_file()


# ─────────────────────────────────────────────────────────────────────────────
# network check
# ─────────────────────────────────────────────────────────────────────────────

REFUSES = REFUSED

BASELINE_PROBES = 4
"""What a machine declaring nothing still reaches for: this repo, and three runtimes.

Not written down as a list of URLs — `network.derive` builds them from
`toolchain`'s own constants and from `DOTFILES_REPO`, and a URL written into a test
is true only on the day it is written.
"""


@pytest.mark.parametrize(
    ('curl', 'git', 'reachable', 'exit_code'),
    [
        (REFUSES, REFUSES, 0, ExitCode.ISSUE),
        (ANSWERS, REFUSES, 3, ExitCode.ISSUE),
        (REFUSES, ANSWERS, 1, ExitCode.ISSUE),
        (ANSWERS, ANSWERS, 4, ExitCode.CONVERGED),
    ],
    ids=['nothing-answers', 'downloads-only', 'clones-only', 'everything-answers'],
)
def test_a_blocked_source_is_a_finding_however_few_there_are(
    curl: str, git: str, reachable: int, exit_code: ExitCode, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Downloads and clones are measured by different binaries, which is why the
    two are separate rows even where both name github.com: at the work firewall the
    clone path is reachable while parts of the release path are not.

    Exit 3 on a block rather than 0, so a scheduled run or a container assertion
    does not have to parse the output to learn the answer.
    """
    sandbox.shadow('curl', curl)
    sandbox.shadow('git', git)

    ran = cli('network', 'check', '--json', catch_exceptions=True)

    assert ran.exit_code == exit_code
    assert ran.document['reachable'] == reachable
    assert ran.document['blocked'] == BASELINE_PROBES - reachable


def test_the_probes_are_derived_from_the_declaration_rather_than_listed(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A declared release adds its own row, the API row that tells a blocked web UI
    apart from a blocked `api.github.com`, and nothing else — the registry rows come
    from the sections that reach one, and `github_releases` reaches neither."""
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
    sandbox.shadow('curl', REFUSES)
    sandbox.shadow('git', REFUSES)

    ran = cli('network', 'check', '--json', catch_exceptions=True)

    sections = [probe['section'] for probe in ran.document['probes']]
    assert sections == ['github_release', 'github_api', 'git_clone', 'language_manager', 'language_manager', 'language_manager']


def test_a_machine_that_declares_no_release_has_no_asset_row_and_no_reason(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The asset probe is discovered from the API rather than synthesized, so a
    machine with no releases has nothing to discover — and that is not a gap worth
    reporting."""
    sandbox.shadow('curl', REFUSES)
    sandbox.shadow('git', REFUSES)

    ran = cli('network', 'check', '--json', catch_exceptions=True)

    assert ran.document['unprobed'] == []
    assert len(ran.document['probes']) == BASELINE_PROBES


@pytest.mark.parametrize(
    ('curl', 'reason'),
    [
        (REFUSES, 'did not answer, so no asset URL could be resolved'),
        (ANSWERS, 'answered with something that is not JSON'),
    ],
    ids=['api-blocked', 'api-answered-with-nothing'],
)
def test_an_asset_row_that_could_not_be_built_is_carried_as_a_reason(
    curl: str, reason: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Never a NO when it cannot be built: a blocked API already has its own row, so
    inferring a second failure from it reports one block as two. The reason is
    carried as data rather than warned about in passing, because a row's absence
    cannot say whether nothing needed probing or the probe could not be made."""
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
    sandbox.shadow('curl', curl)
    sandbox.shadow('git', REFUSES)

    ran = cli('network', 'check', '--json', catch_exceptions=True)

    assert ran.document['unprobed'] == [f'release asset delivery: jesseduffield/lazygit {reason}']


def test_the_human_rendering_names_only_what_is_blocked(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Every reachable row printed would bury the three that matter, and the count
    at the end is what says how many were asked.

    Asserted per stream rather than on the two joined. The tally is the answer and
    belongs on stdout; the rows are the evidence behind it and belong on stderr,
    per `standards/cli-design.md` § "stdout is data, stderr is everything else".
    An assertion over both at once cannot tell a row on the wrong stream from a row
    on the right one, which is how an empty stdout goes unnoticed.
    """
    sandbox.shadow('curl', ANSWERS)
    sandbox.shadow('git', REFUSES)

    ran = cli('network', 'check', catch_exceptions=True)

    assert re.search(r'blocked\s+git_clone/dotfiles', ran.stderr)
    assert '1 blocked' in ran.stdout
    assert 'astral.sh' not in ran.stdout
    assert f'3 reachable, {BASELINE_PROBES - 3} blocked' in ran.stdout


def test_an_unknown_machine_is_reported_rather_than_probed(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`--machine` measures what a manifest would install, so a name that resolves
    to nothing is answered before a single request is made.

    Exit 2 rather than 3: the name is retryable, and nothing has been learnt about
    the machine to report as an Issue.
    """
    ran = cli('network', 'check', '--machine', 'nosuch', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'nosuch: has no manifest' in ran.stderr


def test_no_results_file_is_written_unless_output_names_one(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The default is a pure read, and that is a safety property rather than a
    convention: the committed results file is the work box's measurement, and a run
    on any unfirewalled machine would replace the only record of what work blocks."""
    sandbox.shadow('curl', REFUSES)
    sandbox.shadow('git', REFUSES)

    cli('network', 'check', catch_exceptions=True)

    assert sorted(path.name for path in sandbox.root.iterdir() if path.is_file()) == []


def test_the_results_file_carries_the_columns_the_firewalled_containers_parse(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The layout is load-bearing rather than decorative: `tests/e2e/harness.py`
    splits these rows on the pipes to decide which hosts to blackhole, and the
    header word is what says whether a file carries the LANDED column at all."""
    from dotfiles import network

    sandbox.shadow('curl', REFUSES)
    sandbox.shadow('git', REFUSES)
    destination = sandbox.root / 'measured' / 'connectivity-results.txt'

    ran = cli('network', 'check', '--output', str(destination), catch_exceptions=True)

    written = destination.read_text()
    assert ran.exit_code == ExitCode.ISSUE
    assert network.RESULTS_HEADER in written
    assert network.LANDED_COLUMN in written
    assert 'Manifest: box' in written
    assert f'Summary: 0 reachable, {BASELINE_PROBES} blocked' in written
    assert 'NO  | git_clone' in written


def test_a_network_check_records_nothing_about_the_machine(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A measurement, not a reconciliation. There is no desired state to converge
    on, so there is no run to file — which is what keeps it out of `report`."""
    sandbox.shadow('curl', REFUSES)
    sandbox.shadow('git', REFUSES)

    cli('network', 'check', catch_exceptions=True)

    assert sandbox.run_files == []


def test_a_network_check_asks_only_the_shadowed_binaries(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The autouse guard sits at httpx, and `network.measure` never goes near it —
    every probe is `curl` or `git ls-remote` through `effects.run`, which is a
    subprocess and a socket the guard cannot see.

    Recording the argv is what proves the shadows answered rather than the real
    binaries: a run that reached the machine's own `curl` would leave this file
    empty and still report the same verdicts.
    """
    asked = sandbox.root / 'asked.txt'
    recorder = f'#!/bin/sh\nprintf "%s\\n" "$*" >> {asked}\nexit 1\n'
    sandbox.shadow('curl', recorder)
    sandbox.shadow('git', recorder)

    cli('network', 'check', catch_exceptions=True)

    requested = asked.read_text()
    assert 'ls-remote --quiet https://github.com/datapointchris/dotfiles.git HEAD' in requested
    assert requested.count('\n') >= BASELINE_PROBES
