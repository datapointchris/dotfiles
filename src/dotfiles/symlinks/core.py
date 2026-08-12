"""Dotfiles symlink manager: configuration constants, utilities, and management functions."""

import fnmatch
import tomllib
from pathlib import Path

from dotfiles import paths
from dotfiles.output import err_console

# ─── Configuration ────────────────────────────────────────────────────────────

DOTFILES_DIR = paths.REPO_ROOT
TARGET_DIR = Path.home().resolve()
SEARCH_DEPTH = 5

CLEANUP_DIRS = ['.config', '.local/shell', '.local/share/applications']

PROTECTED_DIRS = {
    '.local/state/claude',
    '.local/state/claude/locks',
    '.local/state/nvim',
    '.local/share/nvim',
    '.cache',
    '.venv',
    '.git',
}

EXCLUDE_PATTERNS = [
    'tmux/plugins/',
    '.tmux/plugins/',
    '.git/',
    '.DS_Store',
    'Thumbs.db',
    'desktop.ini',
    '*.tmp',
    '*.temp',
    '*.log',
    '*.cache',
    '*.swap',
    '*.swp',
    '*~',
    'node_modules/',
    '.venv/',
    '__pycache__/',
    '*.pyc',
    '.pytest_cache/',
]

# Directories to skip entirely during symlink searches (never descend into these)
#
# `~/Library` names its expensive subtrees rather than the whole directory,
# because `configs/os/darwin/Library/Application Support/` is deployed and
# excluding the parent made the one macOS tree this manager links into the one
# tree it never scanned for orphans. Excluding `Application Support` with a
# carve-out for the deployed path was rejected: that writes one file's location
# into a general exclusion list, so the next thing deployed beside it stops
# being scanned again with nothing to say so.
EXCLUDE_SEARCH_DIRS = [
    'Library/Caches/',
    'Library/Containers/',
    'Library/Group Containers/',
    'Library/Developer/',
    'Library/Mobile Documents/',
    '.Trash/',
    'Applications/',
    'Movies/',
    'Music/',
    'Pictures/',
    'Downloads/',
    '.cache/',
    '.local/share/Trash/',
    'snap/',
    'node_modules/',
    '.npm/',
    '.nvm/',
    '.pyenv/',
    '.cargo/',
    '.rustup/',
    '.rbenv/',
    '.git/',
    'venv/',
    '.venv/',
    'env/',
    '__pycache__/',
    '.pytest_cache/',
    '.mypy_cache/',
    '.ruff_cache/',
    'vendor/',
    '.bundle/',
    'target/',
    'dist/',
    'build/',
    '.idea/',
    '.vscode/',
    '.vim/',
]

EXCLUDED_SEARCH_SEQUENCES = tuple(tuple(Path(pattern).parts) for pattern in EXCLUDE_SEARCH_DIRS)


# ─── Utilities ────────────────────────────────────────────────────────────────


def is_excluded_search_dir(path: Path) -> bool:
    """Whether the orphan scan refuses to descend into this directory.

    Whole components, matched as a contiguous run so a multi-part entry means the
    nesting it spells. A bare substring test read `env` out of
    `.config/environment.d` and `build` out of `.local/share/buildkit`, silently
    exempting real deployment targets from the only pass that removes a stale
    link.
    """
    parts = path.parts
    return any(
        parts[start : start + len(sequence)] == sequence
        for sequence in EXCLUDED_SEARCH_SEQUENCES
        for start in range(len(parts) - len(sequence) + 1)
    )


def should_exclude(path: Path) -> bool:
    """Check if a file should be excluded from symlinking."""
    path_str = str(path)
    filename = path.name

    for pattern in EXCLUDE_PATTERNS:
        if pattern.endswith('/'):
            # e.g. ".git/" must match path components, not prefix-match filenames like ".gitconfig"
            dir_name = pattern.rstrip('/')
            if f'/{dir_name}/' in path_str or path_str.startswith(f'{dir_name}/'):
                return True
        elif '*' in pattern and fnmatch.fnmatch(filename, pattern) or filename == pattern:
            return True

    return False


def make_relative_symlink(source: Path, target: Path) -> Path:
    """Calculate relative path from target's parent to source for symlink creation."""
    return source.relative_to(target.parent, walk_up=True)


def resolve_broken_symlink(symlink: Path) -> Path | None:
    """Resolve a broken symlink's target path, returning None if it can't be resolved."""
    if not symlink.is_symlink():
        return None

    try:
        target = symlink.readlink()
        if target.is_absolute():
            return target
        return (symlink.parent / target).resolve()
    except (OSError, RuntimeError):
        return None


def cleanup_empty_directories(base_dir: Path, dirs_to_clean: list[Path]) -> list[Path]:
    """Remove empty directories within specified paths, skipping protected dirs."""
    removed = []
    for cleanup_dir in dirs_to_clean:
        if not cleanup_dir.exists():
            continue

        # Walk deepest-first so parent dirs become empty after children are removed
        for dirpath in sorted(cleanup_dir.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if not dirpath.is_dir() or any(dirpath.iterdir()):
                continue

            try:
                relative = dirpath.relative_to(base_dir)
                if any(str(relative) == p or str(relative).startswith(f'{p}/') for p in PROTECTED_DIRS):
                    continue
            except ValueError:
                pass

            try:
                dirpath.rmdir()
                try:
                    removed.append(dirpath.relative_to(base_dir))
                except ValueError:
                    removed.append(dirpath)
            except (OSError, PermissionError):
                pass

    return removed


def _find_symlinks(base_dir: Path) -> list[Path]:
    """Find all symlinks under base_dir with depth-limited, exclusion-aware traversal."""
    symlinks: list[Path] = []

    def walk(directory: Path, depth: int = 0) -> None:
        if depth >= SEARCH_DEPTH:
            return
        try:
            for item in directory.iterdir():
                if item.is_dir() and is_excluded_search_dir(item):
                    continue
                if item.is_symlink():
                    symlinks.append(item)
                if item.is_dir() and not item.is_symlink():
                    walk(item, depth + 1)
        except (PermissionError, OSError):
            pass

    walk(base_dir)
    return symlinks


# ─── Symlink Management ───────────────────────────────────────────────────────


def console_script_names(pyproject: Path | None = None) -> set[str]:
    """Names `[project.scripts]` claims in ~/.local/bin.

    Read from pyproject rather than from the installed distribution's entry
    points, because during a bootstrap nothing is installed yet and the answer
    has to be the same either way — the declaration is what reserves the name,
    not the state of the machine.

    `uv tool dir --bin` is ~/.local/bin, the same directory the apps layer links
    into, so a console script and an apps/ file of the same name are two things
    competing for one path. The declaration wins; linking the other over it would
    replace the executable that is running.
    """
    declaration = pyproject or paths.PYPROJECT_FILE
    if not declaration.exists():
        return set()
    return set(tomllib.loads(declaration.read_text()).get('project', {}).get('scripts', {}))


def link_ownership(target_path: Path, *roots: Path) -> str:
    """Who put this target here: `absent`, `ours`, or `foreign`.

    `ours` is a symlink pointing anywhere inside the repo or inside one of
    `roots`, including a broken one left by a deleted source — that is still
    this manager's to replace. `roots` carries the tree currently being linked,
    so a caller pointed at a tree that is not the installed repo still
    recognises its own links.

    Containment is compared by path component, never by string prefix.
    `~/dotfiles-backup` and `~/dotfiles.bak` both start with `~/dotfiles`, and
    calling a link into one of them `ours` is what lets an apply replace the copy
    somebody took before a risky change — without the foreign refusal and without
    `--force`.
    """
    if not (target_path.exists() or target_path.is_symlink()):
        return 'absent'
    if not target_path.is_symlink():
        return 'foreign'

    destination = resolve_broken_symlink(target_path) if not target_path.exists() else target_path.resolve()
    if not destination:
        return 'foreign'

    owned = (DOTFILES_DIR, *(root.resolve() for root in roots))
    return 'ours' if any(destination.is_relative_to(root) for root in owned) else 'foreign'


SKEL_DIR = Path('/etc/skel')


def is_untouched_skeleton(target_path: Path) -> bool:
    """A distro default the user has never edited, and so not their content.

    `useradd` copies `/etc/skel` into every new home, so a fresh Debian or Ubuntu
    account starts with a `.bashrc` and `.bash_profile` nobody wrote. Refusing
    them means the very first `apply` on every such machine reports the symlink
    stage failed, having correctly deployed everything else — and the advice it
    prints is `--force`, which on any other machine is the dangerous answer.

    Byte equality is what makes this safe rather than a special case for two
    filenames: the moment a file differs from the skeleton it is someone's work,
    and refusing it is right again.
    """
    skeleton = SKEL_DIR / target_path.name
    if target_path.is_symlink() or not target_path.is_file() or not skeleton.is_file():
        return False
    try:
        return target_path.read_bytes() == skeleton.read_bytes()
    except OSError:
        return False


def remove_symlinks(
    source_dir: Path,
    layer: str,
    *,
    verbose: bool = False,
    target_dir: Path | None = None,
) -> int:
    """Remove all symlinks in target_dir that point into source_dir.

    Containment by path component, for the reason `link_ownership` gives: a
    string prefix makes `common-backup` part of `common`, and this verb unlinks
    what it matches.
    """
    _target_dir = (target_dir or TARGET_DIR).resolve()
    source_dir = source_dir.resolve()

    err_console.print(f'[blue]Removing {layer} symlinks...[/]')
    count = 0

    for symlink in _find_symlinks(_target_dir):
        try:
            target = resolve_broken_symlink(symlink) if not symlink.exists() else symlink.resolve()
            if target and target.is_relative_to(source_dir):
                symlink.unlink()
                if verbose:
                    err_console.print(f'[green]✓[/] Removed: {symlink.relative_to(_target_dir)}')
                count += 1
        except (OSError, ValueError):
            continue

    removed_dirs = cleanup_empty_directories(_target_dir, [_target_dir / d for d in CLEANUP_DIRS])
    if removed_dirs and verbose:
        err_console.print(f'Cleaned up {len(removed_dirs)} empty directories')

    err_console.print(f'[green]Removed {count} symlinks[/]')
    return count


def find_broken_symlinks(
    target_dir: Path | None = None,
    dotfiles_dir: Path | None = None,
) -> list[Path]:
    """Find all broken symlinks in target_dir that point into dotfiles_dir."""
    _target_dir = (target_dir or TARGET_DIR).resolve()
    _dotfiles_dir = (dotfiles_dir or DOTFILES_DIR).resolve()
    broken = []

    for symlink in _find_symlinks(_target_dir):
        if symlink.exists():
            continue
        target = resolve_broken_symlink(symlink)
        if target and target.is_relative_to(_dotfiles_dir):
            broken.append(symlink)

    return broken
