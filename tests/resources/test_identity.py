"""The git identity: checked, and deliberately never written.

`GIT_CONFIG_GLOBAL` is the seam — a real knob git honours, pointed at a temp
file, so nothing in `src/dotfiles/` is patched to make these run and the command
under test is the same one a machine runs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from dotfiles.gitconfig import Layering
from dotfiles.gitconfig import Setting
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


def personal_identity_by_remote(gitconfig: Path, session: Session) -> None:
    """The nonfleet arrangement: an employer default, and personal repos matched
    back to a second identity by their remote. What the work box actually runs."""
    (gitconfig.parent / 'personal.gitconfig').write_text('[user]\n\tname = Chris\n\temail = chris@example.com\n')
    gitconfig.write_text(
        '[user]\n\tname = Work Self\n\temail = work@employer.com\n'
        '[includeIf "hasconfig:remote.*.url:https://github.com/datapointchris/**"]\n'
        f'\tpath = {gitconfig.parent / "personal.gitconfig"}\n'
    )
    subprocess.run(['git', 'init', '-q'], cwd=session.repo, check=True)
    subprocess.run(['git', 'remote', 'add', 'origin', 'https://github.com/datapointchris/dotfiles.git'], cwd=session.repo, check=True)


def test_an_include_this_checkout_matches_is_not_a_local_override(gitconfig: Path, session: Session) -> None:
    """The arrangement working, which must not read as drift. A nonfleet box is
    *meant* to commit personal repos under a different identity from its default,
    so advising `git config --local --unset` would remove nothing — nothing local
    is set."""
    personal_identity_by_remote(gitconfig, session)

    assert changes(session) == ()


def test_the_identity_reported_is_the_one_this_checkout_commits_under(gitconfig: Path, session: Session) -> None:
    """A `--global` read cannot evaluate `hasconfig:`, so the machine default is
    the employer address even standing inside a personal repo. Reporting that as
    the identity named the wrong person at the top of every run here."""
    personal_identity_by_remote(gitconfig, session)

    observed = identity.RESOURCE.observe(session, session.plan)

    assert observed.who == 'Chris <chris@example.com>'


def test_a_field_decided_by_an_include_names_the_machine_default_beside_it(gitconfig: Path, session: Session) -> None:
    """Both, because either alone is misleading here: the effective value looks
    like the machine's, and the default looks like what the next commit carries."""
    personal_identity_by_remote(gitconfig, session)

    observed = identity.RESOURCE.observe(session, session.plan)

    assert observed.reading('user.name') == 'Chris — from an include this checkout matches; machine default Work Self'


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
    """A repo-local override inside `session.repo` is drift. Unnamed, `check`
    reports the machine's identity as converged while every commit that checkout
    produces is attributed to something else."""
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


def test_the_config_chain_is_listed_tilde_rooted_and_in_the_order_git_reads_it(tmp_path: Path) -> None:
    """The absolute paths spent fourteen characters a row saying whose machine this
    is, in the column that has to align, and the detail beside them was the same
    eight words on every line — a table with nothing in it."""
    home = tmp_path / 'home'
    chain = Layering(
        (
            Setting(home / '.config/git/config', 'user.name', 'Chris Birch'),
            Setting(home / '.config/git/personal.gitconfig', 'user.email', 'c@e.st'),
        )
    )
    address = {'user.name': 'Chris Birch', 'user.email': 'c@e.st'}
    observed = identity.Observed(address, address, dict.fromkeys(address, ''), layering=chain, home=home)

    listed = {row.item: row.detail for row in observed.inventory}

    assert listed['~/.config/git/config'] == 'read 1 of 2'
    assert listed['~/.config/git/personal.gitconfig'] == 'read 2 of 2'
