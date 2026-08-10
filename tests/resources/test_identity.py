"""The git identity: checked, and deliberately never written.

`GIT_CONFIG_GLOBAL` is the seam — a real knob git honours, pointed at a temp
file, so nothing in `src/dotfiles/` is patched to make these run and the command
under test is the same one a machine runs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import identity
from dotfiles.session import Session


@pytest.fixture
def gitconfig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / 'gitconfig'
    config.write_text('')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', str(config))
    return config


@pytest.fixture
def session(tmp_path: Path) -> Session:
    """A minimal declaration, because a Session always has a repo behind it.

    This resource reads nothing from it — the identity is in `~/.gitconfig` — but
    building a Session that could not resolve one would be a fixture no real run
    ever has.
    """
    install = tmp_path / 'install'
    (install / 'manifests').mkdir(parents=True)
    (install / 'packages.yml').write_text('{}')
    (install / 'flags.yml').write_text('{}')
    (install / 'manifests' / 'box.yml').write_text('machine: box\nplatform: linux\n')
    return Session(machine_name='box', repo=tmp_path, home=tmp_path)


def changes(session: Session) -> tuple:
    return identity.RESOURCE.diff(session.plan, identity.RESOURCE.observe(session, session.plan))


def test_a_machine_with_both_fields_has_no_drift(gitconfig: Path, session: Session) -> None:
    gitconfig.write_text('[user]\n\tname = Chris\n\temail = chris@example.com\n')

    assert changes(session) == ()


def test_the_identity_reads_back_as_one_line(gitconfig: Path, session: Session) -> None:
    gitconfig.write_text('[user]\n\tname = Chris\n\temail = chris@example.com\n')

    assert identity.RESOURCE.observe(session, session.plan).who == 'Chris <chris@example.com>'


@pytest.mark.parametrize(
    ('config', 'expected'),
    [
        ('', ['user.name', 'user.email']),
        ('[user]\n\tname = Chris\n', ['user.email']),
        ('[user]\n\temail = chris@example.com\n', ['user.name']),
    ],
)
def test_each_missing_field_is_named(gitconfig: Path, session: Session, config: str, expected: list[str]) -> None:
    gitconfig.write_text(config)

    assert [change.item for change in changes(session)] == expected


def test_a_missing_identity_is_reported_and_never_written(gitconfig: Path, session: Session) -> None:
    """An identity is personal and per-machine, so there is nothing in the repo
    for `apply` to write — which is why this resource has a check and no fix."""
    found = changes(session)

    assert all(change.verdict is Verdict.MISSING for change in found)
    assert all(change.repair is Repair.BY_HAND for change in found)
    assert not any(change.actionable for change in found)


def test_a_repo_local_identity_does_not_mask_an_unset_machine(
    gitconfig: Path, session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--global` rather than a plain `--get`: the check usually runs from inside
    a clone, and a clone setting its own identity would otherwise answer for the
    machine — reporting converged on a box that cannot commit anywhere else."""
    clone = tmp_path / 'clone'
    clone.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=clone, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Repo Local'], cwd=clone, check=True)
    subprocess.run(['git', 'config', 'user.email', 'local@example.com'], cwd=clone, check=True)
    monkeypatch.chdir(clone)

    assert [change.item for change in changes(session)] == ['user.name', 'user.email']


def test_a_local_override_elsewhere_is_not_this_checkouts_problem(
    gitconfig: Path, session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repo-local identity is legitimate in another clone — an employer address
    kept out of a personal repo, deliberately — so only `session.repo` itself is
    compared, not whatever directory the check happens to run from."""
    gitconfig.write_text('[user]\n\tname = Chris\n\temail = chris@example.com\n')
    clone = tmp_path / 'clone'
    clone.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=clone, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Work Self'], cwd=clone, check=True)
    subprocess.run(['git', 'config', 'user.email', 'work@employer.com'], cwd=clone, check=True)
    monkeypatch.chdir(clone)

    assert changes(session) == ()


@pytest.mark.parametrize(
    ('local_name', 'local_email', 'expected'),
    [
        ('Repo Local', 'chris@example.com', ['user.name']),
        ('Chris', 'local@example.com', ['user.email']),
        ('Repo Local', 'local@example.com', ['user.name', 'user.email']),
    ],
)
def test_a_local_override_in_this_checkout_is_named(
    gitconfig: Path, session: Session, local_name: str, local_email: str, expected: list[str]
) -> None:
    """This is the failure from 2026-08-09: `~/dotfiles` itself carried a
    repo-local override and `check` reported the machine's identity as
    converged while every commit it produced was attributed to something
    else."""
    gitconfig.write_text('[user]\n\tname = Chris\n\temail = chris@example.com\n')
    subprocess.run(['git', 'init', '-q'], cwd=session.repo, check=True)
    subprocess.run(['git', 'config', 'user.name', local_name], cwd=session.repo, check=True)
    subprocess.run(['git', 'config', 'user.email', local_email], cwd=session.repo, check=True)

    found = changes(session)

    assert [change.item for change in found] == expected
    assert all(change.verdict is Verdict.STALE for change in found)
    assert all(change.repair is Repair.BY_HAND for change in found)
    assert not any(change.actionable for change in found)
