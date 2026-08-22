"""Tests for core symlink management functions and utilities."""

from pathlib import Path

import pytest

import dotfiles.symlinks.core as core
from dotfiles import paths

# ─── Utility Tests ────────────────────────────────────────────────────────────


EXCLUSIONS: tuple[tuple[str, bool], ...] = (
    # A directory pattern owns whole path components. `.gitconfig` and `.gitignore`
    # are dotfiles this repo deploys, and a prefix match on `.git` takes all of them.
    ('.git/config', True),
    ('some/path/.git/hooks', True),
    ('bar/.git/objects/abc123', True),
    ('.gitconfig', False),
    ('some/dir/.gitconfig', False),
    ('.gitignore', False),
    ('.gitattributes', False),
    ('.github/workflows/ci.yml', False),
    ('some/.gitkeep', False),
    # A plugin directory is cloned by its own manager; the config beside it is ours.
    ('tmux/plugins/tpm', True),
    ('.tmux/plugins/vim-tmux-navigator', True),
    ('tmux/tmux.conf', False),
    ('tmux.conf', False),
    ('.config/tmux/tmux.conf', False),
    # A filename pattern matches the whole name, never a name that starts with it.
    ('.DS_Store', True),
    ('some/dir/.DS_Store', True),
    ('.DSConfig', False),
    ('node_modules.txt', False),
    ('my_node_modules.js', False),
    ('.pytest.ini', False),
    ('pytest.cfg', False),
    # An extension pattern matches the extension, never a name containing the word.
    ('file.tmp', True),
    ('file.temp', True),
    ('file.log', True),
    ('template.txt', False),
    ('tmp_file.txt', False),
    ('temporary.md', False),
    ('.zshrc', False),
    ('.config/nvim/init.lua', False),
    ('.local/bin/tools', False),
)


@pytest.mark.parametrize(('path', 'excluded'), EXCLUSIONS, ids=[path for path, _ in EXCLUSIONS])
def test_a_pattern_matches_a_whole_component_and_never_a_prefix(path: str, excluded: bool) -> None:
    """What the deploy refuses to carry into `$HOME`, and what it must not refuse.

    Both halves in one table, because every entry here is a pair: the thing the
    pattern is for, and the dotfile whose name begins with the same letters.
    """
    assert core.should_exclude(Path(path)) is excluded


def test_resolve_broken_symlink_absolute(tmp_path):
    symlink = tmp_path / 'link'
    target = Path('/nonexistent/file')
    symlink.symlink_to(target)

    resolved = core.resolve_broken_symlink(symlink)
    assert resolved == target


def test_resolve_broken_symlink_relative(tmp_path):
    symlink = tmp_path / 'link'
    symlink.symlink_to('../nonexistent/file')

    resolved = core.resolve_broken_symlink(symlink)
    assert resolved is not None
    assert 'nonexistent/file' in str(resolved)


def test_resolve_broken_symlink_not_a_symlink(tmp_path):
    regular_file = tmp_path / 'file.txt'
    regular_file.write_text('test')

    assert core.resolve_broken_symlink(regular_file) is None


@pytest.mark.parametrize(
    ('source', 'target', 'link'),
    [
        (
            '/Users/chris/dotfiles/common/.config/nvim/init.lua',
            '/Users/chris/.config/nvim/init.lua',
            '../../dotfiles/common/.config/nvim/init.lua',
        ),
        (
            '/Users/chris/dotfiles/common/.config/zsh/.zshrc',
            '/Users/chris/.config/zsh/.zshrc',
            '../../dotfiles/common/.config/zsh/.zshrc',
        ),
        ('/Users/chris/dotfiles/macos/.gitconfig', '/Users/chris/.gitconfig', 'dotfiles/macos/.gitconfig'),
    ],
    ids=['nested', 'nested-dotfile', 'top-level'],
)
def test_the_link_is_written_relative_to_the_directory_holding_it(source: str, target: str, link: str) -> None:
    """A target in `$HOME` itself takes no `../`, which is the case that goes wrong
    when the depth is counted from the wrong end."""
    assert str(core.make_relative_symlink(Path(source), Path(target))) == link


def test_make_relative_symlink_actually_works(tmp_path):
    """Integration check: verify the calculated relative path produces a working symlink."""
    source_dir = tmp_path / 'dotfiles' / 'common' / '.config' / 'nvim'
    source_dir.mkdir(parents=True)
    source_file = source_dir / 'init.lua'
    source_file.write_text('-- test config')

    target_dir = tmp_path / 'home' / '.config' / 'nvim'
    target_dir.mkdir(parents=True)
    target_file = target_dir / 'init.lua'

    target_file.symlink_to(core.make_relative_symlink(source_file, target_file))

    assert target_file.exists()
    assert target_file.is_symlink()
    assert target_file.read_text() == '-- test config'


# ─── Symlink Management Tests ─────────────────────────────────────────────────


def test_remove_symlinks(tmp_path):
    dotfiles = tmp_path / 'dotfiles'
    source = dotfiles / 'macos'
    source.mkdir(parents=True)
    (source / 'test.txt').write_text('test')

    target = tmp_path / 'home'
    target.mkdir()
    (target / 'test.txt').symlink_to(source / 'test.txt')

    count = core.remove_symlinks(source, 'macos', target_dir=target)

    assert count == 1
    assert not (target / 'test.txt').exists()


def test_find_broken_symlinks(tmp_path):
    dotfiles = tmp_path / 'dotfiles'
    dotfiles.mkdir()

    target = tmp_path / 'home'
    target.mkdir()

    broken_link = target / 'broken'
    broken_link.symlink_to(dotfiles / 'nonexistent')

    broken = core.find_broken_symlinks(target_dir=target, dotfiles_dir=dotfiles)

    assert len(broken) == 1
    assert broken[0] == broken_link


def test_the_reserved_names_come_from_pyproject(tmp_path):
    """Read from the declaration rather than the installed distribution: during
    a bootstrap nothing is installed, and the answer has to be the same."""
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text('[project.scripts]\ndotfiles = "dotfiles.main:app"\npackages = "dotfiles.declaration:main"\n')

    assert core.console_script_names(pyproject) == {'dotfiles', 'packages'}


def test_a_missing_pyproject_reserves_nothing(tmp_path):
    assert core.console_script_names(tmp_path / 'absent.toml') == set()


def test_this_repo_declares_its_own_scripts(tmp_path):
    """The default path resolves, so the exclusion is live rather than a
    parameter nothing ever fills."""
    assert 'dotfiles' in core.console_script_names()


# ─── Path Ownership ───────────────────────────────────────────────────────────
#
# A sibling of the repo shares its whole path as a string prefix. `~/dotfiles`
# and `~/dotfiles-backup` are different trees, and the second one holds the copy
# somebody made before a risky change.


def test_a_link_into_a_repo_sibling_is_foreign(tmp_path, monkeypatch):
    repo = (tmp_path / 'dotfiles').resolve()
    repo.mkdir()

    backup = (tmp_path / 'dotfiles-backup').resolve()
    backup.mkdir()
    (backup / '.zshrc').write_text('the copy taken before the risky change')

    home = tmp_path / 'home'
    home.mkdir()
    link = home / '.zshrc'
    link.symlink_to(backup / '.zshrc')

    monkeypatch.setattr(core, 'DOTFILES_DIR', repo)

    assert core.link_ownership(link, repo) is core.Ownership.FOREIGN


def test_a_link_into_the_repo_is_still_ours(tmp_path, monkeypatch):
    repo = (tmp_path / 'dotfiles').resolve()
    (repo / 'common').mkdir(parents=True)
    (repo / 'common' / '.zshrc').write_text('deployed')

    home = tmp_path / 'home'
    home.mkdir()
    link = home / '.zshrc'
    link.symlink_to(repo / 'common' / '.zshrc')

    monkeypatch.setattr(core, 'DOTFILES_DIR', repo)

    assert core.link_ownership(link, repo) is core.Ownership.OURS


def test_a_broken_link_into_a_repo_sibling_is_not_an_orphan(tmp_path):
    repo = (tmp_path / 'dotfiles').resolve()
    repo.mkdir()

    home = tmp_path / 'home'
    home.mkdir()
    (home / '.zshrc').symlink_to(tmp_path / 'dotfiles-backup' / '.zshrc')

    assert core.find_broken_symlinks(target_dir=home, dotfiles_dir=repo) == []


def test_remove_symlinks_leaves_a_sibling_trees_links_alone(tmp_path):
    source = tmp_path / 'dotfiles' / 'common'
    source.mkdir(parents=True)
    (source / 'ours.txt').write_text('ours')

    sibling = tmp_path / 'dotfiles' / 'common-backup'
    sibling.mkdir(parents=True)
    (sibling / 'theirs.txt').write_text('theirs')

    home = tmp_path / 'home'
    home.mkdir()
    (home / 'ours.txt').symlink_to(source / 'ours.txt')
    (home / 'theirs.txt').symlink_to(sibling / 'theirs.txt')

    count = core.remove_symlinks(source, 'common', target_dir=home)

    assert count == 1
    assert not (home / 'ours.txt').is_symlink()
    assert (home / 'theirs.txt').is_symlink()


# ─── Search Exclusions ────────────────────────────────────────────────────────


DARWIN_DEPLOYED_EXTENSION = Path('Library/Application Support/Vivaldi/External Extensions/nngceckbapebfimnlniiiahkandclblb.json')


def test_the_scan_reaches_the_deepest_deployed_darwin_path(tmp_path):
    """The real path `configs/os/darwin/` deploys, at its real depth.

    Five components below `$HOME`, which is exactly `SEARCH_DEPTH` with no
    margin. A shallower stand-in is still reached by a scan that has already
    stopped short of the shipped file, so the fixture has to spell the whole
    path for the ceiling to be pinned at all.
    """
    repo = (tmp_path / 'dotfiles').resolve()
    repo.mkdir()

    home = tmp_path / 'home'
    orphan = home / DARWIN_DEPLOYED_EXTENSION
    orphan.parent.mkdir(parents=True)
    orphan.symlink_to(repo / 'deleted.json')

    assert core.find_broken_symlinks(target_dir=home, dotfiles_dir=repo) == [orphan]


def test_the_darwin_variant_still_deploys_that_path():
    """The fixture above is a copy of a path in the repo, and a copy drifts."""
    deployed = paths.REPO_ROOT / 'configs' / 'os' / 'darwin' / DARWIN_DEPLOYED_EXTENSION

    assert deployed.exists(), f'{DARWIN_DEPLOYED_EXTENSION} is no longer what configs/os/darwin/ deploys'


@pytest.mark.parametrize(
    'directory',
    [
        'Library/Caches/Vivaldi',
        'Library/Containers/com.apple.Safari',
        'Library/Messages/Attachments/a0',
        'Library/Mail/V10',
    ],
)
def test_the_scan_still_skips_the_expensive_subtrees_under_library(tmp_path, directory):
    """Naming subtrees rather than `Library` keeps each one skipped on its own."""
    repo = (tmp_path / 'dotfiles').resolve()
    repo.mkdir()

    home = tmp_path / 'home'
    skipped = home / directory
    skipped.mkdir(parents=True)
    (skipped / 'extensions.json').symlink_to(repo / 'deleted.json')

    assert core.find_broken_symlinks(target_dir=home, dotfiles_dir=repo) == []


@pytest.mark.parametrize(
    'directory',
    [
        '.config/environment.d',
        '.config/vendored',
        '.local/share/buildkit',
        '.config/distrobox',
    ],
)
def test_a_directory_merely_containing_an_excluded_name_is_scanned(tmp_path, directory):
    """`env`, `vendor`, `build` and `dist` are all excluded search dirs, and all
    four appear inside the name of a directory this repo can legitimately deploy
    into."""
    repo = (tmp_path / 'dotfiles').resolve()
    repo.mkdir()

    home = tmp_path / 'home'
    deployed = home / directory
    deployed.mkdir(parents=True)
    orphan = deployed / 'config.toml'
    orphan.symlink_to(repo / 'deleted.toml')

    assert core.find_broken_symlinks(target_dir=home, dotfiles_dir=repo) == [orphan]


# ─── What the walk decides ────────────────────────────────────────────────────


KEPT = {
    'to-a-file': 'plain.txt',
    'broken': 'gone.txt',
    'to-a-directory': 'a',
    'pointing-at-the-cache': '.cache',
    'a/b/c/d/at-the-depth-limit': 'plain.txt',
    'a-loop-back-to-the-root': '.',
    '.local/share/keep/under-a-name-containing-an-excluded-one': 'plain.txt',
    'Downloads.txt': 'plain.txt',
}
"""Every link the walk has to come back with, and what each points at.

`pointing-at-the-cache` is the one worth stating: exclusion is about where the walk
*is*, never about where a link goes. The link's own path carries no excluded
component, so it is an ordinary result and its target is not followed.
"""

REFUSED = {
    'Downloads': 'a',
    'a/b/c/d/e/past-the-depth-limit': 'plain.txt',
    '.cache/inside-an-excluded-directory': 'plain.txt',
}
"""The three it must not come back with.

A link *named* like an excluded directory and pointing at one is indistinguishable
from the directory itself to everything downstream, which is what the following
`is_dir()` is for — and why `Downloads.txt` beside it, pointing at a file, is kept.
"""


def a_tree_of_every_shape(root: Path) -> dict[str, Path]:
    """One directory holding each thing the walk decides about.

    In one tree rather than one per case, because the decisions are not
    independent: the depth cases mean nothing without a link shallow enough to
    keep beside them, and the exclusion cases nothing without one the same walk
    admits.
    """
    for directory in ('a/b/c/d/e', '.cache', '.local/share/keep'):
        (root / directory).mkdir(parents=True)
    (root / 'plain.txt').write_text('anything')

    made = {}
    for name, target in {**KEPT, **REFUSED}.items():
        link = root / name
        link.symlink_to(root / target)
        made[name] = link
    return made


def test_the_walk_keeps_every_link_it_should_and_descends_into_nothing_it_should_not(tmp_path: Path) -> None:
    """Eleven shapes, and which of them come back.

    A symlink is a result rather than a place to descend, whatever it points at —
    which is what makes the loop safe and what keeps `to-a-directory` from being
    walked twice.

    Pinned because the traversal was rewritten from a recursive `iterdir` onto
    `os.scandir`, and every answer here was previously decided by which of four
    `is_dir()`/`is_symlink()` calls fired in which order. `KEPT` and `REFUSED` carry
    what each case is for.
    """
    made = a_tree_of_every_shape(tmp_path)

    found = set(core._find_symlinks(tmp_path))

    assert found == {made[name] for name in KEPT}


def test_a_link_whose_target_cannot_be_reached_costs_only_itself(tmp_path: Path) -> None:
    """`is_dir()` follows, so a link into a directory this account cannot traverse
    raises `PermissionError` — on that one entry.

    The failure was caught around the whole loop before this walk was rewritten,
    which abandoned every remaining entry in the directory. An orphan scan that
    stops early reports a machine with no orphans, and the repair it would have
    named is a link into the repo at a file that no longer exists.

    Both links come back. The unreachable one is kept because its target cannot be
    established as a directory, which is the same answer a broken link gets — and a
    broken link is what the scan is for.
    """
    locked = tmp_path / 'locked'
    (locked / 'inside').mkdir(parents=True)
    unreachable = tmp_path / 'into-the-locked-directory'
    unreachable.symlink_to(locked / 'inside')
    ordinary = tmp_path / 'ordinary'
    ordinary.symlink_to(tmp_path / 'gone.txt')
    locked.chmod(0o000)
    try:
        found = set(core._find_symlinks(tmp_path))
    finally:
        locked.chmod(0o755)

    assert found == {unreachable, ordinary}


def test_a_directory_admitted_by_its_parent_is_judged_on_the_name_just_added(tmp_path: Path) -> None:
    """The walk's exclusion check tests only the tail, on the strength of the
    parent having passed the general one.

    Equivalent because a run present here and absent from the parent has to end at
    the component just appended. Held to the general predicate directly, since the
    walk cannot show a difference that does not exist.
    """
    admitted = Path('/home/someone/.config/environment.d')
    refused = Path('/home/someone/.local/share/Trash')

    assert core._excluded_by_the_component_just_added(admitted.parts) is core.is_excluded_search_dir(admitted) is False
    assert core._excluded_by_the_component_just_added(refused.parts) is core.is_excluded_search_dir(refused) is True


# ─── Stream Contract ──────────────────────────────────────────────────────────


def test_removing_symlinks_writes_nothing_to_stdout(tmp_path, capsys):
    """Progress is a diagnostic, and stdout carries data a caller parses."""
    source = tmp_path / 'dotfiles' / 'common'
    source.mkdir(parents=True)
    (source / 'ours.txt').write_text('ours')

    home = tmp_path / 'home'
    home.mkdir()
    (home / 'ours.txt').symlink_to(source / 'ours.txt')

    core.remove_symlinks(source, 'common', target_dir=home, verbose=True)

    written = capsys.readouterr()
    assert written.out == ''
    assert written.err != ''
