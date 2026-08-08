"""Deploying the repo into `$HOME`, decided one link at a time.

Every test builds a whole synthetic world — a repo tree and a home — and points
a Session at both. `home` and `repo` are real fields on Session rather than
patched globals, so these exercise the same code a machine runs.

The capability being pinned is the one the previous pass could not have: a
declared link that was never deployed is *reported*, without running the write
that would create it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import symlinks
from dotfiles.session import Session


@pytest.fixture
def home(tmp_path: Path) -> Path:
    target = tmp_path / 'home'
    target.mkdir()
    return target


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / 'repo'
    install = root / 'install' / 'manifests'
    install.mkdir(parents=True)
    (root / 'install' / 'packages.yml').write_text('{}')
    (root / 'install' / 'flags.yml').write_text('{}')
    (install / 'box.yml').write_text('machine: box\nplatform: linux\n')
    (root / 'pyproject.toml').write_text('[project.scripts]\ndotfiles = "dotfiles.main:app"\n')
    return root


@pytest.fixture
def session(repo: Path, home: Path) -> Session:
    return Session(machine_name='box', repo=repo, home=home)


def declare(repo: Path, relative: str, content: str = 'config\n') -> Path:
    """Put a file in the repo, in whichever layer the path names."""
    source = repo / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(content)
    return source


def changes(session: Session) -> tuple:
    observed = symlinks.RESOURCE.observe(session, session.plan)
    return symlinks.RESOURCE.diff(session.plan, observed)


def apply(session: Session) -> list:
    """Run the same two halves the CLI runs, and return the outcomes."""
    return [symlinks.RESOURCE.perform(session, change) for change in changes(session) if change.actionable]


# ─────────────────────────────────────────────────────────────────────────────
# What the repo declares
# ─────────────────────────────────────────────────────────────────────────────


def test_every_layer_is_deployed_to_its_own_destination(session: Session, repo: Path, home: Path) -> None:
    declare(repo, 'configs/common/.config/tmux/tmux.conf')
    declare(repo, 'shell/common/functions.sh')
    declare(repo, 'apps/common/notes')

    targets = {link.target for link in symlinks.RESOURCE.observe(session, session.plan).links}

    assert targets == {
        home / '.config/tmux/tmux.conf',
        home / '.local/shell/functions.sh',
        home / '.local/bin/notes',
    }


def test_the_platform_overlay_is_optional(session: Session, repo: Path) -> None:
    """A minimal platform like `linux` ships only a shell overlay, and the common
    layer carries the rest."""
    declare(repo, 'configs/common/.bashrc')

    assert len(symlinks.RESOURCE.observe(session, session.plan).links) == 1


def test_the_platform_overlay_is_deployed_when_present(session: Session, repo: Path, home: Path) -> None:
    declare(repo, 'configs/linux/.config/hypr/hyprland.conf')

    targets = {link.target for link in symlinks.RESOURCE.observe(session, session.plan).links}

    assert targets == {home / '.config/hypr/hyprland.conf'}


def test_an_excluded_path_is_never_declared(session: Session, repo: Path) -> None:
    declare(repo, 'configs/common/.config/tmux/tmux.conf')
    declare(repo, 'configs/common/.config/tmux/plugins/tpm/tpm')
    declare(repo, 'configs/common/.DS_Store')

    assert [link.target.name for link in symlinks.RESOURCE.observe(session, session.plan).links] == ['tmux.conf']


def test_a_name_project_scripts_declares_is_never_linked(session: Session, repo: Path) -> None:
    """The two compete for one path in ~/.local/bin and the declaration wins;
    linking the other over it would replace the executable that is running."""
    declare(repo, 'apps/common/dotfiles')
    declare(repo, 'apps/common/notes')

    assert [link.target.name for link in symlinks.RESOURCE.observe(session, session.plan).links] == ['notes']


# ─────────────────────────────────────────────────────────────────────────────
# What check reports
# ─────────────────────────────────────────────────────────────────────────────


def test_a_declared_link_that_was_never_deployed_is_missing(session: Session, repo: Path) -> None:
    """The whole point of the conversion. The previous pass answered only "is
    anything broken", so a file added to configs/ and never deployed read as
    converged."""
    declare(repo, 'configs/common/.config/tmux/tmux.conf')

    found = changes(session)

    assert [change.verdict for change in found] == [Verdict.MISSING]
    assert found[0].item == 'common/.config/tmux/tmux.conf'


def test_a_deployed_link_reports_nothing(session: Session) -> None:
    declare(session.repo, 'configs/common/.config/tmux/tmux.conf')
    apply(session)

    assert changes(session) == ()


def test_a_link_pointing_at_the_wrong_file_is_stale(session: Session, repo: Path, home: Path) -> None:
    declare(repo, 'configs/common/.bashrc')
    other = declare(repo, 'configs/common/.zshrc')
    (home / '.bashrc').symlink_to(other)

    found = [change for change in changes(session) if change.item.endswith('.bashrc')]

    assert found[0].verdict is Verdict.STALE
    assert found[0].observed == str(other.resolve())


def test_a_target_this_manager_did_not_create_is_reported_and_not_ours_to_replace(session: Session, repo: Path, home: Path) -> None:
    """The write is an unlink, and `uv tool install` puts real executables in the
    same ~/.local/bin the apps layer links into."""
    declare(repo, 'apps/common/notes')
    (home / '.local' / 'bin').mkdir(parents=True)
    (home / '.local' / 'bin' / 'notes').write_text('#!/bin/sh\n# somebody else wrote this\n')

    found = changes(session)

    assert found[0].verdict is Verdict.STALE
    assert found[0].repair is Repair.BY_HAND
    assert not found[0].actionable


def test_a_link_whose_source_is_gone_is_pruned(session: Session, repo: Path, home: Path) -> None:
    declare(repo, 'configs/common/.bashrc')
    apply(session)
    (repo / 'configs/common/.bashrc').unlink()

    found = changes(session)

    assert len(found) == 1
    assert found[0].verdict is Verdict.STALE
    assert Path(found[0].item).is_absolute()


# ─────────────────────────────────────────────────────────────────────────────
# What apply does
# ─────────────────────────────────────────────────────────────────────────────


def test_applying_creates_the_link_relative(session: Session, repo: Path, home: Path) -> None:
    """Relative, so a repo moved wholesale keeps working."""
    declare(repo, 'configs/common/.config/tmux/tmux.conf')

    apply(session)

    target = home / '.config/tmux/tmux.conf'
    assert target.is_symlink()
    assert not target.readlink().is_absolute()
    assert target.read_text() == 'config\n'


def test_applying_prunes_a_link_whose_source_is_gone(session: Session, repo: Path, home: Path) -> None:
    declare(repo, 'configs/common/.bashrc')
    apply(session)
    (repo / 'configs/common/.bashrc').unlink()

    apply(session)

    assert not (home / '.bashrc').is_symlink()


def test_applying_is_idempotent(session: Session, repo: Path) -> None:
    declare(session.repo, 'configs/common/.bashrc')
    apply(session)

    assert apply(session) == []


def test_applying_replaces_a_link_this_manager_owns(session: Session, repo: Path, home: Path) -> None:
    source = declare(repo, 'configs/common/.bashrc')
    other = declare(repo, 'configs/common/.zshrc')
    (home / '.bashrc').symlink_to(other)

    apply(session)

    assert (home / '.bashrc').resolve() == source.resolve()


def test_applying_never_replaces_a_foreign_target(session: Session, repo: Path, home: Path) -> None:
    declare(repo, 'apps/common/notes')
    (home / '.local' / 'bin').mkdir(parents=True)
    theirs = home / '.local' / 'bin' / 'notes'
    theirs.write_text('#!/bin/sh\n# somebody else wrote this\n')

    apply(session)

    assert theirs.read_text() == '#!/bin/sh\n# somebody else wrote this\n'
