"""`machines requirements` — the register a machine needs supplied by hand.

The register is the one part of a machine `apply` will never converge, so the
only thing standing between a rebuilt box and a broken one is knowing what it
holds. These assert the three renderings against the repo's real `flags.yml`,
because a register that answers correctly about a fixture and wrongly about this
fleet is the failure the command exists to prevent.
"""

from __future__ import annotations

import dataclasses as dc
import json
import tomllib

import pytest
from typer.testing import CliRunner

from dotfiles import machine as machines
from dotfiles.commands import machines as commands
from dotfiles.main import app
from dotfiles.vocabulary import ExitCode

runner = CliRunner()


def run(*args: str) -> str:
    result = runner.invoke(app, ['machines', 'requirements', *args])
    assert result.exit_code == ExitCode.CONVERGED, result.output
    return result.output


@pytest.fixture
def work() -> machines.Machine:
    return machines.load('wsl-work-workstation')


def test_the_register_names_every_value_and_file_the_machine_needs(work: machines.Machine) -> None:
    printed = run('wsl-work-workstation')

    for entry in work.requirements:
        assert (entry.path or entry.name) in printed


def test_a_machine_that_needs_nothing_says_so_rather_than_printing_a_bare_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty section reads as a command that failed to find the file it was
    looking in.

    The one case in this module reached through a stand-in rather than a real
    manifest. Every machine the repo declares needs at least one thing by hand,
    so the empty register has no machine to be asserted against — and the
    rendering still has to be right the first time one does."""
    empty = dc.replace(machines.load('linux-lxc-server'), requirements=())
    monkeypatch.setattr(commands, '_loaded', lambda _: empty)

    printed = run('linux-lxc-server')

    assert 'nothing' in printed


def test_json_carries_the_narrowing_that_decided_each_entry() -> None:
    """Which axis pulled an entry in is the part a reader cannot reconstruct, and
    the part that answers "why does this machine need it and that one not". An
    empty narrowing is itself an answer — every machine — so the key is always
    present and only sometimes populated."""
    entries = json.loads(run('wsl-work-workstation', '--json'))

    assert {entry['name'] for entry in entries}
    assert all(entry['kind'] in {'file', 'value'} for entry in entries)
    assert all(isinstance(entry['narrowing'], dict) for entry in entries)


def test_the_safekeep_block_is_parseable_toml_carrying_every_file(work: machines.Machine) -> None:
    """Pasted into a config safekeep parses, so a block that is not valid TOML
    breaks the backup rather than this command."""
    block = tomllib.loads(run('wsl-work-workstation', '--safekeep'))

    assert [path['path'] for path in block['back_up_paths']] == [entry.path for entry in work.required_files]


def test_every_backed_up_path_carries_the_tag_that_selects_this_register() -> None:
    """`safekeep restore --tag dotfiles` has to be exactly the register — that is
    what makes the generated block worth having over a hand-written list."""
    block = tomllib.loads(run('wsl-work-workstation', '--safekeep'))

    assert all('dotfiles' in path['tags'] for path in block['back_up_paths'])


def test_required_values_survive_as_comments_rather_than_being_dropped() -> None:
    """They have no path to back up and a rebuild still needs them. This is the
    only listing that knows both halves, so dropping them here loses them."""
    emitted = run('wsl-work-workstation', '--safekeep')

    assert 'WINDOWS_USER' in emitted
    assert 'WINDOWS_USER' not in tomllib.loads(emitted)


def test_asking_for_two_formats_at_once_is_a_usage_error() -> None:
    """Exit 2, not 1: a caller has to tell "you typed it wrong" from "it ran and
    failed", because only the first is worth retrying with different arguments."""
    result = runner.invoke(app, ['machines', 'requirements', 'wsl-work-workstation', '--json', '--safekeep'])

    assert result.exit_code == ExitCode.USAGE


def test_the_one_file_safekeep_cannot_restore_says_how_to_get_it_back() -> None:
    """Its own config, on a machine with no backup yet. Every other entry defaults
    to "restore it with safekeep", which for this one is a circle."""
    entry = next(item for item in json.loads(run('wsl-work-workstation', '--json')) if 'safekeep' in item['path'])

    assert 'safekeep config init' in entry['restore']


def test_every_entry_carries_a_way_to_get_it_back(work: machines.Machine) -> None:
    """A register naming a file with no route to it is a checklist you cannot act
    on, which is the whole failure the listing exists to prevent."""
    entries = json.loads(run('wsl-work-workstation', '--json'))

    assert len(entries) == len(work.requirements)
    assert all(entry['restore'] for entry in entries)


def test_the_safekeep_config_is_itself_in_the_register() -> None:
    """The file that restores the others has to be in the snapshot too, or a
    rebuild has every declared file back and nothing that knows where they went."""
    entries = json.loads(run('wsl-work-workstation', '--json'))

    assert any('safekeep' in entry['path'] for entry in entries)


def test_a_fleet_machine_needs_no_safekeep_config() -> None:
    """Syncthing is the transport there and Proxmox holds the backups, so a fleet
    machine without one is not a machine missing anything. Narrowed on capacity
    at first, which reported both Macs short of a file neither needs."""
    entries = json.loads(run('macos-personal-workstation', '--json'))

    assert not [entry for entry in entries if 'safekeep' in entry['path']]
