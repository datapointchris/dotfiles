"""Sending a run record to the remote, and what is taken out of it on the way.

A record is read by a person diagnosing a failure, which is what makes masking the
right screen for it rather than the row-withholding a status document gets. These
assert the property that follows: the line survives, the name does not.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dotfiles.commands import report
from dotfiles.coordinates import NetworkTrust

NAMES = {'the Windows account': 'ab12345', 'this machine name': 'wkstn01x'}


def test_a_record_is_masked_without_its_shape_changing(tmp_path: Path) -> None:
    local = tmp_path / '20260817T131536Z-wkstn01x-apply.json'
    local.write_text(
        json.dumps(
            {
                'machine': 'wsl-work-workstation',
                'outcomes': [{'address': 'system/step/windows-fonts', 'message': '/mnt/c/Users/ab12345/AppData'}],
            }
        )
    )

    staged = report._masked_copy(local, NAMES)
    written = json.loads(staged.read_text())

    assert staged.name == local.name, 'the stamp is how a record is addressed on the shelf'
    assert written['outcomes'][0]['address'] == 'system/step/windows-fonts', 'the address says which step failed'
    assert written['outcomes'][0]['message'] == '/mnt/c/Users/<windows-account>/AppData'


def test_a_stream_stays_line_delimited(tmp_path: Path) -> None:
    """Parsed and re-emitted per line rather than as one document, because the
    whole file is not JSON and a raw-text pass breaks on a name JSON escapes."""
    local = tmp_path / '20260817T131536Z-wkstn01x-apply.jsonl'
    local.write_text(
        json.dumps({'argv': ['cmd.exe', '/C', 'echo %USERNAME%'], 'answer': 'ab12345', 'returncode': 0})
        + '\n'
        + json.dumps({'argv': ['systemctl', '--user', 'is-enabled'], 'returncode': 1})
        + '\n'
    )

    staged = report._masked_copy(local, NAMES)
    lines = [json.loads(line) for line in staged.read_text().splitlines()]

    assert len(lines) == 2, 'one line in, one line out'
    assert lines[0]['answer'] == '<windows-account>'
    assert lines[0]['argv'] == ['cmd.exe', '/C', 'echo %USERNAME%'], 'the command that produced it still reads'
    assert lines[0]['returncode'] == 0
    assert lines[1]['returncode'] == 1, 'a line carrying no name is untouched'


def test_a_path_under_this_home_reads_as_a_person_writes_it(tmp_path: Path, monkeypatch) -> None:
    """Rooted before masked. The other order spells the same path
    `/home/<account-this-runs-as>/.local/bin/dotfiles`, which is unreadable and
    throws away a `~` that was available."""
    monkeypatch.setattr(report.Path, 'home', staticmethod(lambda: Path('/home/chris')))
    local = tmp_path / '20260817T131536Z-wkstn01x-apply.jsonl'
    local.write_text(json.dumps({'argv': ['/home/chris/.local/bin/dotfiles', '--version']}) + '\n')

    staged = report._masked_copy(local, {'the account this runs as': 'chris'})
    line = json.loads(staged.read_text())

    assert line['argv'] == ['~/.local/bin/dotfiles', '--version']


def test_a_hyphen_in_the_hostname_still_finds_this_box_its_own_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`runs/` is Syncthing-shared, so the send has to name a box, and the only
    name any record was filed under is the bare hostname. `discriminator` answers
    a different question and hands a hyphenated hostname a blake2b digest — which
    matched no filename, sent nothing, and named a box appearing nowhere in
    `report list`."""
    directory = tmp_path / 'runs'
    directory.mkdir()
    mine = '20260817T195934Z-scheduler-lxc-check.json'
    for name in (mine, '20260817T200117Z-macmini-check.json'):
        (directory / name).write_text(json.dumps({'machine': 'linux-lxc-server', 'outcomes': []}))

    monkeypatch.setattr('dotfiles.paths.RUNS_DIR', directory)
    monkeypatch.setattr('dotfiles.paths.MACHINE_ID', 'scheduler-lxc')
    monkeypatch.setattr(
        report,
        'resolved',
        lambda _: SimpleNamespace(
            machine=SimpleNamespace(coordinates=SimpleNamespace(network_trust=NetworkTrust.FLEET)),
            machine_name='linux-lxc-server',
        ),
    )
    pushed: list[str] = []
    monkeypatch.setattr(report.transport, 'reachable', lambda: SimpleNamespace())
    monkeypatch.setattr(report.transport, 'reports_for', lambda where, machine: '/shelf/reports')
    monkeypatch.setattr(report.transport, 'listed', lambda where, shelf: ())
    monkeypatch.setattr(report.transport, 'push', lambda where, local, shelf: pushed.append(local.name))

    shelf, sent = report._send(None)

    assert sent == 1
    assert pushed == [mine], "a peer's record is not this box's to publish"
    assert shelf == '/shelf/reports'


def test_the_record_on_this_machine_is_not_rewritten(tmp_path: Path) -> None:
    """The local copy is the account of what happened here, and this box is the one
    entitled to it. Masking in place would take that away to protect it from
    itself."""
    local = tmp_path / '20260817T131536Z-wkstn01x-apply.json'
    original = json.dumps({'outcomes': [{'message': '/mnt/c/Users/ab12345'}]})
    local.write_text(original)

    staged = report._masked_copy(local, NAMES)

    assert local.read_text() == original
    assert staged != local
