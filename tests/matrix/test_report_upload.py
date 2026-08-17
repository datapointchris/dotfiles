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
def test_this_box_s_record_and_its_log_both_reach_the_shelf(
    sandbox: Sandbox, server: Path, named: str, cli: Callable[..., Invocation]
) -> None:
    """Both files, because each answers half of a failure — the record carries a
    run's scope and the log carries its cause."""
    a_record(sandbox, named)

    ran = cli('report', 'upload')

    assert ran.exit_code == ExitCode.CONVERGED
    assert sorted(path.name for path in shelf(server).iterdir()) == [
        f'20260817T120000Z-{named}-check.json',
        f'20260817T120000Z-{named}-check.jsonl',
    ]


@pytest.mark.parametrize('named', HOSTNAMES, indirect=True)
def test_a_peer_s_record_stays_on_the_machine_that_wrote_it(
    sandbox: Sandbox, server: Path, named: str, cli: Callable[..., Invocation]
) -> None:
    """`$XDG_STATE_HOME` is a Syncthing folder on the fleet, so the runs directory
    holds every box's records and this shelf is one box's."""
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


@pytest.mark.parametrize('named', HOSTNAMES, indirect=True)
def test_a_refused_listing_is_reported_rather_than_read_as_an_empty_shelf(
    sandbox: Sandbox, server: Path, named: str, cli: Callable[..., Invocation]
) -> None:
    """A shelf that cannot be listed and a shelf with nothing on it are opposite
    findings. Collapsing them re-uploads every record on every run."""
    a_record(sandbox, named)
    deny_listing(server)

    ran = cli('report', 'upload', catch_exceptions=True)

    assert ran.exit_code != ExitCode.CONVERGED
