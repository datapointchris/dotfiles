"""`report upload` driven through the front door, against the fake transport.

The verb its two siblings already had. `status upload` and `bundle upload` are
each driven end to end here against a relay on PATH; `report upload` shipped with
four tests, all of them on `_masked_copy`, and none of them reaching the function
that decides which records go. That function selected on the wrong identity for
its whole life and every one of those tests stayed green.

**Identity is a parameter, not the runner's hostname.** `paths.MACHINE_ID` is the
real hostname of whatever box runs the suite, and whether the defect reproduces
depends on whether that name carries a hyphen — so a test taking the ambient
answer passes here and fails on a runner, or the reverse. The rows below name
both shapes and neither is the machine this runs on.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest
from relay import declare
from relay import deny_listing
from relay import install_relay

from dotfiles import paths
from dotfiles.vocabulary import ExitCode
from matrix.harness import Invocation
from matrix.harness import Sandbox

MACHINE = 'box'

HOSTNAMES = [
    pytest.param('workstation', id='plain-hostname'),
    # `publishing.discriminator` sends a hyphenated name down its digest branch,
    # which is the name no record was ever filed under.
    pytest.param('scheduler-lxc', id='hyphenated-hostname'),
]


@pytest.fixture
def server(sandbox: Sandbox) -> Path:
    root = sandbox.root / 'server'
    (root / 'artefacts').mkdir(parents=True)
    install_relay(sandbox.bin, root)
    declare(sandbox.config)
    return root


def shelf(server: Path) -> Path:
    return server / 'artefacts' / 'reports' / MACHINE


@pytest.fixture
def scratch(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The directory a send stages into, pointed inside this test's own sandbox.

    `tempfile.tempdir` and not `TMPDIR`. The environment variable is read once
    per process and cached, so by the time a test sets it something else has
    already resolved the answer and the assertion below counts an empty
    directory whatever the code does.
    """
    made = sandbox.root / 'scratch'
    made.mkdir()
    monkeypatch.setattr(tempfile, 'tempdir', str(made))
    return made


@pytest.fixture
def named(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """This box's hostname, replacing the runner's on both spellings of it.

    Two, because the package reads the identity two ways and the split is load
    bearing. `runs.begin` stamps filenames from the `MACHINE_ID` constant, and
    `publishing.discriminator` calls the `machine_id` function. Patching one
    leaves the other answering for the real machine, which is a state no box is
    ever in and a green test that proves nothing.
    """
    hostname = getattr(request, 'param', 'workstation')
    monkeypatch.setattr(paths, 'MACHINE_ID', hostname)
    monkeypatch.setattr(paths, 'machine_id', lambda: hostname)
    return hostname


def a_record(sandbox: Sandbox, host: str, stamp: str = '20260817T120000Z', verb: str = 'check') -> Path:
    """One run filed under `host`, with the event log every run writes beside it."""
    record = sandbox.runs / f'{stamp}-{host}-{verb}.json'
    record.write_text('{"id": "abc123abc123", "machine": "box", "verb": "check", "outcomes": [], "issues": []}')
    record.with_suffix('.jsonl').write_text('{"event": "ran", "argv": ["true"], "seconds": 0.1}\n')
    return record


@pytest.mark.parametrize('named', HOSTNAMES, indirect=True)
def test_a_peer_s_record_stays_on_the_machine_that_wrote_it(
    sandbox: Sandbox, server: Path, named: str, cli: Callable[..., Invocation]
) -> None:
    """`$XDG_STATE_HOME` is a Syncthing folder on the fleet, so the runs directory
    holds every box's records and this shelf is one box's. Both of this box's
    files go and neither of the peer's does — the record carries a failure's
    scope and the log carries its cause, so sending one is the shape that makes
    somebody ask for the other."""
    a_record(sandbox, named)
    a_record(sandbox, 'a-peer-box', stamp='20260817T130000Z')

    ran = cli('report', 'upload')

    assert ran.exit_code == ExitCode.CONVERGED
    landed = sorted(path.name for path in shelf(server).iterdir())
    assert landed == [f'20260817T120000Z-{named}-check.json', f'20260817T120000Z-{named}-check.jsonl']
    assert not any('a-peer-box' in name for name in landed)


@pytest.mark.parametrize('named', HOSTNAMES, indirect=True)
def test_a_second_upload_sends_nothing_and_still_converges(
    sandbox: Sandbox, server: Path, named: str, cli: Callable[..., Invocation]
) -> None:
    """Bare it is a reconcile rather than a push, which is why there is no second
    verb for keeping the shelf in sync."""
    a_record(sandbox, named)
    cli('report', 'upload')
    before = sorted(path.name for path in shelf(server).iterdir())

    ran = cli('report', 'upload')

    assert ran.exit_code == ExitCode.CONVERGED
    assert sorted(path.name for path in shelf(server).iterdir()) == before


@pytest.mark.parametrize('named', HOSTNAMES, indirect=True)
def test_a_named_run_uploads_that_run(sandbox: Sandbox, server: Path, named: str, cli: Callable[..., Invocation]) -> None:
    """The id path resolves a stem and never consults the box identity, which is
    why it kept working while the bare verb found nothing."""
    a_record(sandbox, named)
    wanted = a_record(sandbox, named, stamp='20260817T140000Z', verb='apply')

    ran = cli('report', 'upload', wanted.stem)

    assert ran.exit_code == ExitCode.CONVERGED
    assert sorted(path.name for path in shelf(server).iterdir()) == [f'{wanted.stem}.json', f'{wanted.stem}.jsonl']


@pytest.mark.parametrize('named', HOSTNAMES, indirect=True)
def test_a_box_with_no_records_of_its_own_refuses_and_writes_nothing(
    sandbox: Sandbox, server: Path, named: str, cli: Callable[..., Invocation]
) -> None:
    """The refusal is paired with the shelf, because an empty directory alone is
    equally satisfied by a crash before the first push."""
    a_record(sandbox, 'a-peer-box')

    ran = cli('report', 'upload', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert not shelf(server).exists() or list(shelf(server).iterdir()) == []


@pytest.fixture
def publishing_server(sandbox: Sandbox) -> Path:
    """A remote this machine has asked to publish to after every apply."""
    root = sandbox.root / 'server'
    (root / 'artefacts').mkdir(parents=True)
    install_relay(sandbox.bin, root)
    declare(sandbox.config, extra='publish_reports_after_apply = true\n')
    return root


def test_an_apply_publishes_its_own_record_where_the_machine_asked_for_that(
    sandbox: Sandbox, publishing_server: Path, named: str, cli: Callable[..., Invocation]
) -> None:
    """The automatic half of the verb, and the half nothing drove. A record
    describes what a run did, so the run that failed is the one worth reading —
    which is why this publishes whatever the verdict, unlike the status."""
    cli('apply')

    landed = sorted(path.name for path in shelf(publishing_server).iterdir())
    assert landed, 'the apply filed a record and the machine asked for it to be sent'
    assert all(named in name for name in landed)


def test_an_apply_publishes_nothing_unless_the_machine_asked(
    sandbox: Sandbox, server: Path, named: str, cli: Callable[..., Invocation]
) -> None:
    """Off by default. A converge that reaches a server unasked is a change in
    posture on an employer network, so the flag is the whole permission."""
    ran = cli('apply')

    assert ran.exit_code in {ExitCode.CONVERGED, ExitCode.DRIFT}
    assert sandbox.filed_records, 'the apply did file a record, so there was something to publish'
    assert not shelf(server).exists() or list(shelf(server).iterdir()) == []


def test_a_remote_that_cannot_be_reached_does_not_fail_the_apply(sandbox: Sandbox, named: str, cli: Callable[..., Invocation]) -> None:
    """The apply's verdict is about the machine. Failing it because a server did
    not answer would report a converged box as broken."""
    declare(sandbox.config, program='no-such-transport', extra='publish_reports_after_apply = true\n')

    ran = cli('apply', catch_exceptions=True)

    assert ran.exit_code in {ExitCode.CONVERGED, ExitCode.DRIFT}
    assert sandbox.filed_records, 'the run still recorded what it did on this machine'


@pytest.mark.parametrize('named', HOSTNAMES, indirect=True)
def test_a_refused_listing_is_reported_rather_than_read_as_an_empty_shelf(
    sandbox: Sandbox, server: Path, named: str, cli: Callable[..., Invocation]
) -> None:
    """A shelf that cannot be listed and a shelf with nothing on it are opposite
    findings. Collapsing them re-uploads every record on every run."""
    a_record(sandbox, named)
    deny_listing(server)

    ran = cli('report', 'upload', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE, 'the refusal `remote.listed` raises, not whatever a traceback exits with'
    assert not shelf(server).exists() or list(shelf(server).iterdir()) == []


def test_a_send_leaves_nothing_behind_in_the_temporary_directory(
    sandbox: Sandbox, server: Path, scratch: Path, named: str, cli: Callable[..., Invocation]
) -> None:
    """The masked copy is a copy, so a send makes files that are nobody's account
    of anything once it ends. Left behind they are unbounded: `/tmp` is a tmpfs on
    a workstation, so a scheduled check uploading twice a day fills memory on a
    timer, and 8044 of them is what took this desk down.

    Counted rather than reasoned about. The whole point is that a reverted fix
    stays green under every other assertion in this file.
    """
    a_record(sandbox, named)

    ran = cli('report', 'upload')

    assert ran.exit_code == ExitCode.CONVERGED
    assert sorted(path.name for path in shelf(server).iterdir()), 'the send did happen'
    assert list(scratch.iterdir()) == [], 'and staged nothing that outlived it'
