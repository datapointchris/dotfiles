"""Dotfiles symlink manager: configuration constants, utilities, and management functions."""

import dataclasses as dc
import enum
import fnmatch
import os
import tomllib
from pathlib import Path

from dotfiles import paths
from dotfiles.output import err_console


class Ownership(enum.StrEnum):
    """Who put a target where a declared link belongs.

    An enum rather than the three bare strings it replaced, because the caller
    that reads it is a dispatch with a branch per member and a fallthrough meaning
    converged. Over strings a fourth answer added here reads as converged at that
    fallthrough with nothing failing; over members, `_verdict`'s `assert_never`
    is a type error the moment this class grows.
    """

    ABSENT = 'absent'
    """Nothing is at the target, not even a broken link."""

    OURS = 'ours'
    """A symlink resolving inside the repo, which this manager may replace."""

    FOREIGN = 'foreign'
    """Anything else, including every regular file — so on a copy machine this is
    the only answer available, which is why `Observed.ownership` is left empty
    there rather than filled with it."""


# ─── Configuration ────────────────────────────────────────────────────────────

DOTFILES_DIR = paths.REPO_ROOT
TARGET_DIR = Path.home().resolve()

# The deepest deployed path sits exactly on this ceiling with no margin:
# `Library/Application Support/Vivaldi/External Extensions/<extension>.json`,
# five components below `$HOME`. Lowering this, or adding a directory level
# under `External Extensions/`, drops that link out of the orphan scan silently
# — it is still deployed, and nothing ever reports it stale.
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
# because `configs/os/darwin/Library/Application Support/` is deployed and an
# exclusion on the parent takes the deployed tree with it. Excluding
# `Application Support` with a carve-out for the deployed path was rejected:
# that writes one file's location into a general exclusion list, so the next
# thing deployed beside it stops being scanned again with nothing to say so.
#
# `Messages/Attachments` and `Mail` are named because scanning `~/Library` is a
# cost paid on every plan, apply and check, and neither is reachable as a
# deployment target. `Attachments` fans out over two levels of hex, both inside
# `SEARCH_DEPTH`, so the walk would iterate the whole of it.
EXCLUDE_SEARCH_DIRS = [
    'Library/Caches/',
    'Library/Containers/',
    'Library/Group Containers/',
    'Library/Developer/',
    'Library/Mobile Documents/',
    'Library/Messages/Attachments/',
    'Library/Mail/',
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


def ends_in_an_excluded_run(parts: tuple[str, ...]) -> bool:
    """Whether an excluded run finishes at the last of these components.

    The primitive both exclusion questions are asked through, so there is one
    definition of what an entry matches. Two predicates over
    `EXCLUDED_SEARCH_SEQUENCES` would have to agree forever, with a test on two
    hardcoded paths as the only thing holding them together.

    Whole components, matched as a contiguous run so a multi-part entry means the
    nesting it spells. Components, not substrings: `.config/environment.d` contains
    `env` and `.local/share/buildkit` contains `build`, and both are real
    deployment targets.
    """
    return any(parts[-len(sequence) :] == sequence for sequence in EXCLUDED_SEARCH_SEQUENCES if len(sequence) <= len(parts))


def is_excluded_search_dir(path: Path) -> bool:
    """Whether an excluded run appears anywhere in this path.

    Every prefix asked of `ends_in_an_excluded_run`, which is the same thing as
    testing every start position and keeps the two answers from drifting apart.

    The walk does not ask this: it asks the primitive directly, about a path whose
    parent it has already admitted. That is where the cost is — measured over this
    home directory, the whole-path form was 2.19s of a 3.0s profile at 253 tuple
    comparisons per call, against 0.1s of syscalls.
    """
    parts = path.parts
    return any(ends_in_an_excluded_run(parts[:end]) for end in range(1, len(parts) + 1))


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


def stands_in_for_an_excluded_directory(entry: os.DirEntry[str], parts: tuple[str, ...]) -> bool:
    """Whether this link is indistinguishable from an excluded directory to
    everything downstream, and so is refused rather than returned.

    Both halves have to be established. A target that cannot be stat'd is not a
    directory as far as this can tell, which is the same answer a broken link gets
    — and a broken link is the one thing the orphan scan exists to find.

    The distinction it draws is the subtlest in the walk and is not visible from
    either caller: a link *named* `Downloads` that points at a directory is refused,
    and `Downloads.txt` beside it pointing at a file is kept. At module level
    because it closes over nothing and because a decision that fine is owed a test
    of its own rather than reaching it through a traversal.
    """
    try:
        points_at_a_directory = entry.is_dir()
    except OSError:
        return False
    return points_at_a_directory and ends_in_an_excluded_run((*parts, entry.name))


@dc.dataclass(frozen=True, slots=True)
class Scan:
    """What the walk found, and what it could not read.

    `skipped` is carried rather than only printed because a shorter list and a
    complete one are otherwise the same answer to the caller, and the warning that
    distinguishes them is prose on a stream nobody parses.
    """

    found: tuple[Path, ...] = ()
    skipped: tuple[tuple[Path, str], ...] = ()
    """Each path the walk could not read, with the OS reason for it."""


def _find_symlinks(base_dir: Path) -> Scan:
    """Every symlink under base_dir, depth-limited and exclusion-aware.

    `os.scandir` departs from `python.md` § "Use `pathlib.Path` for every
    filesystem operation" with a number behind it: over one home directory,
    `iterdir` 0.59s, `Path.walk` 0.54s, this 0.13s. Both alternatives discard the
    entry type the directory read already carried, so every is-it-a-link question
    costs another syscall.

    A symlink is a result rather than a place to descend, whatever it points at,
    which is what stops a link to an ancestor turning the walk into a loop.

    Failure is caught per entry, never around the loop: an orphan scan that stops
    early reports a machine with no orphans.

    **The exclusions apply below the root, never to the root.** A caller naming a
    directory has said to scan it, so `_find_symlinks(~/Downloads/x)` scans where
    `is_excluded_search_dir` answers True about that same path.
    """
    symlinks: list[Path] = []
    skipped: list[tuple[Path, str]] = []

    def walk(directory: Path, depth: int = 0) -> None:
        if depth >= SEARCH_DEPTH:
            return
        try:
            with os.scandir(directory) as scan:
                entries = list(scan)
        except OSError as unreadable:
            skipped.append((directory, unreadable.strerror or ''))
            err_console.print(f'[yellow]not scanned for orphans:[/] {directory} ({unreadable.strerror})')
            return
        parts = directory.parts
        for entry in entries:
            try:
                is_link = entry.is_symlink()
                descend = not is_link and entry.is_dir(follow_symlinks=False)
            except OSError as unreadable:
                skipped.append((Path(entry.path), unreadable.strerror or ''))
                err_console.print(f'[yellow]not examined:[/] {entry.path} ({unreadable.strerror})')
                continue
            if is_link and not stands_in_for_an_excluded_directory(entry, parts):
                symlinks.append(Path(entry.path))
            elif descend and not ends_in_an_excluded_run((*parts, entry.name)):
                walk(Path(entry.path), depth + 1)

    walk(base_dir)
    return Scan(tuple(symlinks), tuple(skipped))


# ─── Symlink Management ───────────────────────────────────────────────────────


def console_script_names(pyproject: Path | None = None) -> set[str]:
    """Names `[project.scripts]` claims in ~/.local/bin.

    Read from pyproject rather than from the installed distribution's entry
    points, because during a bootstrap nothing is installed yet and the answer
    has to be the same either way — the declaration is what reserves the name,
    not the state of the machine.

    `uv tool dir --bin` is ~/.local/bin, the same directory the apps tree links
    into, so a console script and an apps/ file of the same name are two things
    competing for one path. The declaration wins; linking the other over it would
    replace the executable that is running.
    """
    declaration = pyproject or paths.PYPROJECT_FILE
    if not declaration.exists():
        return set()
    return set(tomllib.loads(declaration.read_text()).get('project', {}).get('scripts', {}))


def link_ownership(target_path: Path, *roots: Path) -> Ownership:
    """Who put this target here.

    `OURS` is a symlink pointing anywhere inside the repo or inside one of
    `roots`, including a broken one left by a deleted source — that is still
    this manager's to replace. `roots` carries the tree currently being linked,
    so a caller pointed at a tree that is not the installed repo still
    recognises its own links.

    Containment is compared by path component, never by string prefix.
    `~/dotfiles-backup` and `~/dotfiles.bak` both start with `~/dotfiles`, and
    calling a link into one of them `OURS` is what lets an apply replace the copy
    somebody took before a risky change — without the foreign refusal and without
    `--force`.
    """
    if not (target_path.exists() or target_path.is_symlink()):
        return Ownership.ABSENT
    if not target_path.is_symlink():
        return Ownership.FOREIGN

    destination = resolve_broken_symlink(target_path) if not target_path.exists() else target_path.resolve()
    if not destination:
        return Ownership.FOREIGN

    owned = (DOTFILES_DIR, *(root.resolve() for root in roots))
    return Ownership.OURS if any(destination.is_relative_to(root) for root in owned) else Ownership.FOREIGN


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
    origin: str,
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

    err_console.print(f'[blue]Removing {origin} symlinks...[/]')
    count = 0

    for symlink in _find_symlinks(_target_dir).found:
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

    for symlink in _find_symlinks(_target_dir).found:
        if symlink.exists():
            continue
        target = resolve_broken_symlink(symlink)
        if target and target.is_relative_to(_dotfiles_dir):
            broken.append(symlink)

    return broken
