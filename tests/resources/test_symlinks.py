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

from dotfiles import deploy
from dotfiles.privilege import Privilege
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import symlinks
from dotfiles.session import Session
from dotfiles.symlinks import core


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


@pytest.fixture
def copying(repo: Path, home: Path) -> Session:
    """A machine that deploys by copy, on the same coordinates as `box`.

    `platform: linux` deliberately, so every declaration these tests make lands in
    the same place `box`'s does and the only difference between the two fixtures
    is the mechanism. The feature is a fact about one machine's administration
    rather than about its OS, which is exactly why it is not derived from the
    coordinates and why a Linux manifest can set it.
    """
    (repo / 'install' / 'manifests' / 'copybox.yml').write_text('machine: copybox\nplatform: linux\ndeploy_by_copy: true\n')
    return Session(machine_name='copybox', repo=repo, home=home)


def declare(repo: Path, relative: str, content: str = 'config\n') -> Path:
    """Put a file in the repo, in whichever directory the path names."""
    source = repo / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(content)
    return source


def changes(session: Session) -> tuple:
    observed = symlinks.RESOURCE.observe(session, session.plan)
    return symlinks.RESOURCE.diff(session.plan, observed)


def apply(session: Session) -> list:
    """Run the same two halves the CLI runs, and return the outcomes.

    The `Privilege` is constructed here and never authorized, which is the state
    that refuses: nothing a symlink pass does needs root, so a test that somehow
    reached an escalation would fail rather than prompt.
    """
    privilege = Privilege()
    return [symlinks.RESOURCE.perform(session, change, privilege) for change in changes(session) if change.actionable]


# ─────────────────────────────────────────────────────────────────────────────
# What the repo declares
# ─────────────────────────────────────────────────────────────────────────────


def test_every_tree_is_deployed_to_its_own_destination(session: Session, repo: Path, home: Path) -> None:
    declare(repo, 'configs/common/.config/tmux/tmux.conf')
    declare(repo, 'shell/common/functions.sh')
    declare(repo, 'apps/common/notes')

    targets = {link.target for link in symlinks.RESOURCE.observe(session, session.plan).links}

    assert targets == {
        home / '.config/tmux/tmux.conf',
        home / '.local/shell/functions.sh',
        home / '.local/bin/notes',
    }


def test_every_coordinate_directory_is_optional(session: Session, repo: Path) -> None:
    """A machine sits on all six axes and has a directory for two or three of
    them. An absent directory is the normal case, not a gap."""
    declare(repo, 'configs/common/.bashrc')

    assert len(symlinks.RESOURCE.observe(session, session.plan).links) == 1


def test_the_variant_the_coordinates_select_is_deployed(session: Session, repo: Path, home: Path) -> None:
    """`box` declares `platform: linux`, which is `{apt, linux, none, native,
    fleet, server}` — so the apt variant is the one it selects, and no other
    machine's is."""
    declare(repo, 'configs/pkg/apt/.config/apt/preferences')
    declare(repo, 'configs/pkg/pacman/.config/pacman/makepkg.conf')

    targets = {link.target for link in symlinks.RESOURCE.observe(session, session.plan).links}

    assert targets == {home / '.config/apt/preferences'}


def test_a_configs_variant_flattens_and_a_shell_layer_keeps_its_axis(session: Session, repo: Path, home: Path) -> None:
    """A config has to land where the program reading it looks; a shell layer
    is read only by `.zshrc`, which walks the axis directories by name."""
    declare(repo, 'configs/host/native/.config/foo/foo.conf')
    declare(repo, 'shell/pkg/apt/apt.sh')

    targets = {link.target for link in symlinks.RESOURCE.observe(session, session.plan).links}

    assert targets == {home / '.config/foo/foo.conf', home / '.local/shell/pkg/apt/apt.sh'}


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
    assert found[0].item == 'configs/common/.config/tmux/tmux.conf'


def test_a_link_pointing_at_the_wrong_file_is_stale(session: Session, repo: Path, home: Path) -> None:
    declare(repo, 'configs/common/.bashrc')
    other = declare(repo, 'configs/common/.zshrc')
    (home / '.bashrc').symlink_to(other)

    found = [change for change in changes(session) if change.item.endswith('.bashrc')]

    assert found[0].verdict is Verdict.STALE
    assert found[0].observed == str(other.resolve())


def test_a_target_this_manager_did_not_create_is_reported_and_not_ours_to_replace(session: Session, repo: Path, home: Path) -> None:
    """The write is an unlink, and `uv tool install` puts real executables in the
    same ~/.local/bin the apps tree links into."""
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


# ─────────────────────────────────────────────────────────────────────────────
# /etc/skel: a distro default nobody wrote
# ─────────────────────────────────────────────────────────────────────────────

SKELETON = '# ~/.bashrc: executed by bash(1)\n'


@pytest.fixture
def skel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / 'skel'
    directory.mkdir()
    (directory / '.bashrc').write_text(SKELETON)
    monkeypatch.setattr(core, 'SKEL_DIR', directory)
    return directory


def test_an_untouched_skeleton_file_is_adopted_without_force(session: Session, repo: Path, home: Path, skel: Path) -> None:
    """`useradd` copies /etc/skel into every new home, so a fresh Debian account
    starts with a .bashrc nobody wrote. Refusing it made the very first apply on
    every such machine report this stage failed, having deployed everything else
    correctly — and the advice printed was --force, which on any other machine is
    the dangerous answer."""
    declare(repo, 'configs/common/.bashrc', 'the repo copy\n')
    (home / '.bashrc').write_text(SKELETON)

    apply(session)

    assert (home / '.bashrc').is_symlink()
    assert (home / '.bashrc').read_text() == 'the repo copy\n'


def test_an_edited_skeleton_file_is_still_refused(session: Session, repo: Path, home: Path, skel: Path) -> None:
    """One byte different and it is someone's work, which is why the comparison is
    on content rather than on two filenames."""
    declare(repo, 'configs/common/.bashrc', 'the repo copy\n')
    edited = home / '.bashrc'
    edited.write_text(SKELETON + 'export EDITOR=vim\n')

    apply(session)

    assert edited.read_text().endswith('export EDITOR=vim\n')
    assert not edited.is_symlink()


# ─────────────────────────────────────────────────────────────────────────────
# The window that must not come back
# ─────────────────────────────────────────────────────────────────────────────


def test_a_deployed_config_is_never_touched_by_a_later_run(session: Session, repo: Path, home: Path) -> None:
    """Hyprland reloads the moment its config changes and writes itself a default
    when it finds none. The pass this replaced removed every link before
    recreating them, handing the daemon exactly that window — and the create pass
    then refused the default as a target it had not made, so the run failed and
    the daemon kept running the stub.

    Deciding per link closes it by construction rather than by ordering: a
    deployed link produces no change at all, so nothing unlinks it, and the prune
    set is only ever links whose source is gone.
    """
    declare(repo, 'configs/common/.config/hypr/hyprland.conf', 'source = conf/keybindings.conf\n')
    apply(session)
    deployed = home / '.config' / 'hypr' / 'hyprland.conf'

    observed = symlinks.RESOURCE.observe(session, session.plan)

    assert deployed not in observed.orphans
    assert symlinks.RESOURCE.diff(session.plan, observed) == ()
    assert deployed.read_text() == 'source = conf/keybindings.conf\n'


# ─────────────────────────────────────────────────────────────────────────────
# deploy_by_copy: the same decisions, over a mechanism with no provenance
# ─────────────────────────────────────────────────────────────────────────────


def test_a_declared_file_that_was_never_copied_is_missing(copying: Session, repo: Path, home: Path) -> None:
    declare(repo, 'configs/common/.config/tmux/tmux.conf')

    found = changes(copying)

    assert [change.verdict for change in found] == [Verdict.MISSING]
    assert found[0].detail.startswith(str(home / '.config/tmux/tmux.conf'))


def test_a_copy_whose_bytes_differ_from_the_repo_is_stale(copying: Session, repo: Path, home: Path) -> None:
    """Content equality is the whole identity test here, so this row covers both
    a copy that has fallen behind and a file somebody else wrote. They are
    indistinguishable, and `apply` overwrites either."""
    declare(repo, 'configs/common/.bashrc', 'the repo copy\n')
    (home / '.bashrc').write_text('something else entirely\n')

    found = changes(copying)

    assert [change.verdict for change in found] == [Verdict.STALE]
    assert found[0].repair is Repair.AUTOMATIC
    assert found[0].actionable


def test_a_copy_matching_the_repo_reports_nothing(copying: Session, repo: Path, home: Path) -> None:
    declare(repo, 'configs/common/.bashrc', 'the repo copy\n')
    (home / '.bashrc').write_text('the repo copy\n')

    assert changes(copying) == ()


def test_a_target_that_cannot_be_read_is_unmeasured_rather_than_stale(copying: Session, repo: Path, home: Path) -> None:
    """A directory where a config belongs. Calling it stale would promise a repair
    for something nothing measured; calling it converged would hide it."""
    declare(repo, 'configs/common/.bashrc')
    (home / '.bashrc').mkdir()

    found = changes(copying)

    assert found[0].verdict is Verdict.UNKNOWN
    assert found[0].repair is Repair.NONE
    assert found[0].unmeasured


def test_applying_writes_a_regular_file_carrying_the_source_mode(copying: Session, repo: Path, home: Path) -> None:
    """An `apps/` file that arrives without its mode bit is one the shell will not
    run, which is why the copy carries mode and not only bytes."""
    source = declare(repo, 'apps/common/notes', '#!/bin/sh\necho notes\n')
    source.chmod(0o755)

    apply(copying)

    deployed = home / '.local/bin/notes'
    assert not deployed.is_symlink()
    assert deployed.read_text() == '#!/bin/sh\necho notes\n'
    assert deployed.stat().st_mode & 0o111


def test_applying_by_copy_is_idempotent(copying: Session, repo: Path) -> None:
    declare(repo, 'configs/common/.bashrc')
    apply(copying)

    assert apply(copying) == []


def test_a_file_the_repo_never_declared_is_left_alone(copying: Session, repo: Path, home: Path) -> None:
    declare(repo, 'configs/common/.bashrc')
    stray = home / '.config' / 'stray.conf'
    stray.parent.mkdir(parents=True)
    stray.write_text('the user put this here\n')

    apply(copying)

    assert stray.read_text() == 'the user put this here\n'
    assert changes(copying) == ()


def test_a_copy_whose_source_is_gone_is_never_pruned(copying: Session, repo: Path, home: Path) -> None:
    """The one thing this mechanism gives up, pinned as a behaviour rather than
    left to the docstring. A symlink into the repo says who made it, so a deleted
    source makes it an orphan to prune; a copy says nothing, so pruning would be
    guessing — and the thing guessed at is a file this repo cannot regenerate and
    the Windows side may hold the only copy of.
    """
    declare(repo, 'configs/common/.bashrc', 'the repo copy\n')
    apply(copying)
    (repo / 'configs/common/.bashrc').unlink()

    assert changes(copying) == ()
    assert (home / '.bashrc').read_text() == 'the repo copy\n'


def test_a_symlink_left_by_the_other_mechanism_is_replaced_by_a_copy(copying: Session, session: Session, repo: Path, home: Path) -> None:
    """The migration itself: the box deployed by link until policy stopped it.

    Every other row here starts from an empty home, which is the one starting
    state that cannot catch this — a target that is already a link into the repo
    reads back the source's own bytes through the link, so comparing content
    answers `same` and the run reports a converged machine still deployed the way
    policy no longer allows.
    """
    declare(repo, 'configs/common/.bashrc', 'the repo copy\n')
    apply(session)
    assert (home / '.bashrc').is_symlink()

    found = changes(copying)

    assert [change.verdict for change in found] == [Verdict.STALE]
    assert found[0].repair is Repair.AUTOMATIC
    apply(copying)
    assert not (home / '.bashrc').is_symlink()
    assert (home / '.bashrc').read_text() == 'the repo copy\n'


def test_nothing_is_deployed_as_a_symlink_on_a_copy_machine(copying: Session, repo: Path, home: Path) -> None:
    """The mechanism swaps for all three trees at once. It is per machine, not per
    tree: nothing about `configs/` wants copying that `apps/` does not."""
    declare(repo, 'configs/common/.config/tmux/tmux.conf')
    declare(repo, 'shell/common/functions.sh')
    declare(repo, 'apps/common/notes')

    apply(copying)

    deployed = [home / '.config/tmux/tmux.conf', home / '.local/shell/functions.sh', home / '.local/bin/notes']
    assert [path.is_file() for path in deployed] == [True, True, True]
    assert not any(path.is_symlink() for path in deployed)


def test_the_summary_names_the_mechanism_this_machine_deploys_by(copying: Session, session: Session, repo: Path) -> None:
    """Same count, different noun, from the one fixture difference.

    A copy machine creates no symlinks at all, so a summary counting them names a
    thing the run did not produce — and it is the line a reader keeps, above rows
    that say `copy` throughout.
    """
    declare(repo, 'configs/common/.bashrc')

    assert symlinks.RESOURCE.observe(copying, copying.plan).summary == '0 of 1 declared copies in place'
    assert symlinks.RESOURCE.observe(session, session.plan).summary == '0 of 1 declared symlinks in place'


# ─────────────────────────────────────────────────────────────────────────────
# unlink, which is the one thing copy mode does not give up
# ─────────────────────────────────────────────────────────────────────────────


def test_unlinking_a_copy_machine_removes_what_it_deployed(copying: Session, repo: Path, home: Path) -> None:
    """The claim `unlink` makes everywhere, made here over the other mechanism.

    A sweep for symlinks finds none of these — every target is a regular file — so
    the pass that only swept reported a machine it had left fully deployed as
    unconfigured, and exited converged saying so.
    """
    declare(repo, 'configs/common/.bashrc')
    declare(repo, 'shell/common/functions.sh')
    declare(repo, 'apps/common/notes')
    apply(copying)

    assert deploy.unlink(copying)

    assert not (home / '.bashrc').exists()
    assert not (home / '.local/shell/functions.sh').exists()
    assert not (home / '.local/bin/notes').exists()


def test_unlinking_leaves_a_declared_target_whose_bytes_are_not_the_repos(copying: Session, repo: Path, home: Path) -> None:
    """Content equality is the only provenance there is, so it is also the only
    thing standing between this verb and somebody's file.

    The reported half matters as much as the kept file: `unlink` promises a
    machine left unconfigured, so a run that could not finish the job says so in
    the exit code rather than in output nothing reads.
    """
    declare(repo, 'configs/common/.bashrc', 'the repo copy\n')
    apply(copying)
    (home / '.bashrc').write_text('edited on this machine\n')

    assert not deploy.unlink(copying)

    assert (home / '.bashrc').read_text() == 'edited on this machine\n'


def test_unlinking_a_copy_machine_still_removes_a_link_the_other_mechanism_left(
    copying: Session, session: Session, repo: Path, home: Path
) -> None:
    """The migration leaves both shapes on one machine, so both passes run there.

    A box that deployed by link until policy stopped it has links resolving into
    the repo, and they are this repo's to remove whatever the manifest now says
    about how to write new ones.
    """
    declare(repo, 'configs/common/.bashrc')
    apply(session)
    assert (home / '.bashrc').is_symlink()

    assert deploy.unlink(copying)

    assert not (home / '.bashrc').is_symlink()
    assert not (home / '.bashrc').exists()


def test_unlinking_a_link_machine_never_reaches_a_regular_file(session: Session, repo: Path, home: Path) -> None:
    """The copy pass is per machine, exactly as the deployment is.

    On a machine that deploys by link, a regular file at a declared target is one
    this manager refused to replace — so a removal keyed on content rather than on
    provenance would delete the very file the refusal exists to protect.
    """
    declare(repo, 'configs/common/.bashrc', 'the repo copy\n')
    (home / '.bashrc').write_text('the repo copy\n')

    assert deploy.unlink(session)

    assert (home / '.bashrc').read_text() == 'the repo copy\n'


# ─────────────────────────────────────────────────────────────────────────────
# Exclusions that were regressions
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('name', ['.gitconfig', '.gitignore', '.gitattributes'])
def test_a_dotgit_prefixed_file_is_not_caught_by_the_git_directory_pattern(session: Session, repo: Path, name: str) -> None:
    """The `.git/` exclusion matches path components, not filename prefixes."""
    declare(repo, f'configs/common/{name}')

    assert [link.target.name for link in symlinks.RESOURCE.observe(session, session.plan).links] == [name]


def test_a_whole_excluded_directory_is_skipped(session: Session, repo: Path) -> None:
    declare(repo, 'configs/common/.config/nvim/init.lua')
    declare(repo, 'configs/common/.git/config')
    declare(repo, 'configs/common/node_modules/package/index.js')

    assert [link.target.name for link in symlinks.RESOURCE.observe(session, session.plan).links] == ['init.lua']


# ─────────────────────────────────────────────────────────────────────────────
# Cost
# ─────────────────────────────────────────────────────────────────────────────


def test_the_source_trees_are_walked_once_however_many_links_are_missing(
    session: Session, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`perform` is handed a Change and not the observation that produced it, so
    it has to find the link again — and `declared()` is an rglob of three source
    trees per coordinate directory plus a pyproject parse. Deriving it per change ran that
    walk once *per link*, which on a fresh machine is every link walking every
    tree.

    Asserted as a count rather than a duration: the cost is quadratic in links,
    so a timing threshold would pass on a small fixture and fail on a real repo.
    """
    for index in range(12):
        declare(repo, f'configs/common/.config/app/file{index}.conf')

    symlinks._index.cache_clear()
    walks = 0
    original = symlinks.declared

    def counted(*args: object, **kwargs: object) -> tuple:
        nonlocal walks
        walks += 1
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(symlinks, 'declared', counted)

    pending = changes(session)
    assert len(pending) == 12
    for change in pending:
        symlinks.RESOURCE.perform(session, change, Privilege())

    assert walks == 2, 'one walk for observe, one for the index every perform shares'
    symlinks._index.cache_clear()
