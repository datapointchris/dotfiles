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

IDENTITY = '[user]\n\tname = Chris\n\temail = chris@example.com\n'
"""A machine with nothing wrong with its identity, so a test asserting on the
arrangement around it is not also asserting on a missing address."""


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


# ─────────────────────────────────────────────────────────────────────────────
# The arrangement the identity arrives through
# ─────────────────────────────────────────────────────────────────────────────


def test_a_home_gitconfig_masking_the_chain_is_reported(gitconfig: Path, session: Session) -> None:
    """git prefers `~/.gitconfig` over the XDG entry point, for reads and writes
    both, so one sitting there silently outranks every include below it. `apply`
    has removed one since the entry point moved; `check` never mentioned it, so a
    machine between applies could be overridden by a file no verb named."""
    gitconfig.write_text(IDENTITY)
    (session.home / '.gitconfig').write_text('[user]\n\temail = someone-else@example.com\n')

    (found,) = [change for change in changes(session) if change.item == '~/.gitconfig']

    assert found.verdict is Verdict.UNDECLARED
    assert found.repair is Repair.BY_HAND
    assert not found.actionable


def test_a_dangling_home_gitconfig_is_still_masking(gitconfig: Path, session: Session, tmp_path: Path) -> None:
    """`exists` follows a link, so a dangling one reads as absent — while git
    still picks it as the file to write to, which is the whole failure."""
    gitconfig.write_text(IDENTITY)
    (session.home / '.gitconfig').symlink_to(tmp_path / 'gone')

    assert any(change.item == '~/.gitconfig' for change in changes(session))


def test_a_symlinked_entry_point_is_reported(gitconfig: Path, session: Session) -> None:
    """git follows a symlink when it writes, so an entry point linked into the
    checkout takes an identity with it — which is the one outcome
    `deploy._ensure_git_config_entry` exists to prevent."""
    gitconfig.write_text(IDENTITY)
    entry = session.home / '.config' / 'git' / 'config'
    entry.parent.mkdir(parents=True)
    entry.symlink_to(gitconfig)

    (found,) = [change for change in changes(session) if change.item == 'git entry point']

    assert found.verdict is Verdict.UNDECLARED
    assert not found.actionable


def test_a_machine_whose_config_is_in_one_file_reports_no_layering_findings(gitconfig: Path, session: Session) -> None:
    """The quiet case, which is every healthy machine. A detector that spoke here
    would be one nobody reads by the end of the week."""
    gitconfig.write_text(IDENTITY)

    assert changes(session) == ()
