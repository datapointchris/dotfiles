"""What is taken out of a run record on the way to the remote.

A record is read by a person diagnosing a failure, which is what makes masking the
right screen for it rather than the row-withholding a status document gets. These
assert the property that follows: the line survives, the name does not.

**Only the transformation.** Which records are chosen and where they land are
visible through the verb, so they are rows in `tests/matrix/test_report_upload.py`
against a real fake transport. Asserting them here as well meant faking
`transport.reachable`, `reports_for`, `listed` and `push` — the four functions the
selection defect lived between, which is the seam that hid it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dotfiles.commands import report

NAMES = {'the Windows account': 'ab12345', 'this machine name': 'wkstn01x'}


@pytest.fixture
def staging(tmp_path: Path) -> Path:
    """Where the masked copy lands, which is never where the record lives.

    `_send` owns a directory for the whole send and removes it afterwards. The
    copy keeps the record's filename, so a staging directory that is also the
    record's directory would write the screened copy over the original.
    """
    made = tmp_path / 'staging'
    made.mkdir()
    return made


def test_a_record_is_masked_without_its_shape_changing(tmp_path: Path, staging: Path) -> None:
    local = tmp_path / '20260817T131536Z-wkstn01x-apply.json'
    local.write_text(
        json.dumps(
            {
                'machine': 'wsl-work-workstation',
                'outcomes': [{'address': 'system/step/windows-fonts', 'message': '/mnt/c/Users/ab12345/AppData'}],
            }
        )
    )

    staged = report._masked_copy(local, NAMES, staging)
    written = json.loads(staged.read_text())

    assert staged.parent == staging, 'the caller chooses where a copy lands, and this asserts it rather than assuming it'
    assert staged.name == local.name, 'the stamp is how a record is addressed on the shelf'
    assert written['outcomes'][0]['address'] == 'system/step/windows-fonts', 'the address says which step failed'
    assert written['outcomes'][0]['message'] == '/mnt/c/Users/<windows-account>/AppData'


def test_a_stream_stays_line_delimited(tmp_path: Path, staging: Path) -> None:
    """Parsed and re-emitted per line rather than as one document, because the
    whole file is not JSON and a raw-text pass breaks on a name JSON escapes."""
    local = tmp_path / '20260817T131536Z-wkstn01x-apply.jsonl'
    local.write_text(
        json.dumps({'argv': ['cmd.exe', '/C', 'echo %USERNAME%'], 'answer': 'ab12345', 'returncode': 0})
        + '\n'
        + json.dumps({'argv': ['systemctl', '--user', 'is-enabled'], 'returncode': 1})
        + '\n'
    )

    staged = report._masked_copy(local, NAMES, staging)
    lines = [json.loads(line) for line in staged.read_text().splitlines()]

    assert len(lines) == 2, 'one line in, one line out'
    assert lines[0]['answer'] == '<windows-account>'
    assert lines[0]['argv'] == ['cmd.exe', '/C', 'echo %USERNAME%'], 'the command that produced it still reads'
    assert lines[0]['returncode'] == 0
    assert lines[1]['returncode'] == 1, 'a line carrying no name is untouched'


def test_a_path_under_this_home_reads_as_a_person_writes_it(tmp_path: Path, staging: Path, monkeypatch) -> None:
    """Rooted before masked. The other order spells the same path
    `/home/<account-this-runs-as>/.local/bin/dotfiles`, which is unreadable and
    throws away a `~` that was available."""
    monkeypatch.setattr(report.Path, 'home', staticmethod(lambda: Path('/home/chris')))
    local = tmp_path / '20260817T131536Z-wkstn01x-apply.jsonl'
    local.write_text(json.dumps({'argv': ['/home/chris/.local/bin/dotfiles', '--version']}) + '\n')

    staged = report._masked_copy(local, {'the account this runs as': 'chris'}, staging)
    line = json.loads(staged.read_text())

    assert line['argv'] == ['~/.local/bin/dotfiles', '--version']


def test_the_record_on_this_machine_is_not_rewritten(tmp_path: Path, staging: Path) -> None:
    """The local copy is the account of what happened here, and this box is the one
    entitled to it. Masking in place would take that away to protect it from
    itself, and it is unrecoverable because the original is gone.

    Asked of the function rather than of the fixture. A staging directory that
    happens to differ proves only that today's caller behaves, so the second half
    names the record's own directory and requires the refusal.
    """
    local = tmp_path / '20260817T131536Z-wkstn01x-apply.json'
    original = json.dumps({'outcomes': [{'message': '/mnt/c/Users/ab12345'}]})
    local.write_text(original)

    staged = report._masked_copy(local, NAMES, staging)

    assert local.read_text() == original
    assert staged != local

    with pytest.raises(ValueError, match='already lives'):
        report._masked_copy(local, NAMES, local.parent)
    assert local.read_text() == original, 'and the refusal left the record alone'
