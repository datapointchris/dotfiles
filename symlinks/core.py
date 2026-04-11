"""Dotfiles symlink manager: configuration constants, utilities, and management functions."""

import fnmatch
import os
from pathlib import Path

from rich import print

# ─── Configuration ────────────────────────────────────────────────────────────

DOTFILES_DIR = Path(os.environ.get("DOTFILES", Path.home() / "dotfiles")).resolve()
TARGET_DIR = Path.home().resolve()
SEARCH_DEPTH = 5

CLEANUP_DIRS = [".config", ".local/shell", ".local/share/workflows", ".local/share/applications"]

PROTECTED_DIRS = {
    ".local/state/claude",
    ".local/state/claude/locks",
    ".local/state/nvim",
    ".local/share/nvim",
    ".cache",
    ".venv",
    ".git",
}

EXCLUDE_PATTERNS = [
    "tmux/plugins/",
    ".tmux/plugins/",
    ".git/",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*.tmp",
    "*.temp",
    "*.log",
    "*.cache",
    "*.swap",
    "*.swp",
    "*~",
    "node_modules/",
    ".venv/",
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
]

# Directories to skip entirely during symlink searches (never descend into these)
EXCLUDE_SEARCH_DIRS = [
    "Library/",
    ".Trash/",
    "Applications/",
    "Movies/",
    "Music/",
    "Pictures/",
    "Downloads/",
    ".cache/",
    ".local/share/Trash/",
    "snap/",
    "node_modules/",
    ".npm/",
    ".nvm/",
    ".pyenv/",
    ".cargo/",
    ".rustup/",
    ".rbenv/",
    ".git/",
    "venv/",
    ".venv/",
    "env/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "vendor/",
    ".bundle/",
    "target/",
    "dist/",
    "build/",
    ".idea/",
    ".vscode/",
    ".vim/",
]


# ─── Utilities ────────────────────────────────────────────────────────────────


def should_exclude(path: Path) -> bool:
    """Check if a file should be excluded from symlinking."""
    path_str = str(path)
    filename = path.name

    for pattern in EXCLUDE_PATTERNS:
        if pattern.endswith("/"):
            # e.g. ".git/" must match path components, not prefix-match filenames like ".gitconfig"
            dir_name = pattern.rstrip("/")
            if f"/{dir_name}/" in path_str or path_str.startswith(f"{dir_name}/"):
                return True
        elif "*" in pattern and fnmatch.fnmatch(filename, pattern):
            return True
        elif filename == pattern:
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
        for dirpath in sorted(cleanup_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if not dirpath.is_dir() or any(dirpath.iterdir()):
                continue

            try:
                relative = dirpath.relative_to(base_dir)
                if any(
                    str(relative) == p or str(relative).startswith(f"{p}/")
                    for p in PROTECTED_DIRS
                ):
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

    def should_skip(path: Path) -> bool:
        path_str = str(path)
        return any(pattern.rstrip("/") in path_str for pattern in EXCLUDE_SEARCH_DIRS)

    def walk(directory: Path, depth: int = 0) -> None:
        if depth >= SEARCH_DEPTH:
            return
        try:
            for item in directory.iterdir():
                if item.is_dir() and should_skip(item):
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


def create_symlinks(
    source_dir: Path,
    layer: str,
    *,
    verbose: bool = False,
    target_dir: Path | None = None,
) -> int:
    """Create symlinks from source_dir into target_dir, preserving relative paths."""
    _target_dir = (target_dir or TARGET_DIR).resolve()

    if not source_dir.exists():
        print(f"[red]✗[/] Source directory does not exist: {source_dir}")
        return 0

    print(f"[blue]Creating {layer} symlinks...[/]")
    count = 0

    for item in source_dir.rglob("*"):
        if not (item.is_file() or item.is_symlink()):
            continue

        try:
            relative_path = item.relative_to(source_dir)
        except ValueError:
            continue

        if should_exclude(relative_path):
            continue

        target_path = _target_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        relative_link = make_relative_symlink(item, target_path)

        try:
            if target_path.exists() or target_path.is_symlink():
                target_path.unlink()
            target_path.symlink_to(relative_link, target_is_directory=item.is_dir())
            if verbose:
                print(f"[green]✓[/] [default]{relative_path}[/] → [magenta]{relative_link}[/]")
            count += 1
        except (OSError, PermissionError) as e:
            print(f"[yellow]⚠[/] Failed to link {relative_path}: {e}")

    print(f"[green]Created {count} symlinks[/]")
    return count


def remove_symlinks(
    source_dir: Path,
    layer: str,
    *,
    verbose: bool = False,
    target_dir: Path | None = None,
) -> int:
    """Remove all symlinks in target_dir that point into source_dir."""
    _target_dir = (target_dir or TARGET_DIR).resolve()
    source_dir = source_dir.resolve()

    print(f"[blue]Removing {layer} symlinks...[/]")
    count = 0

    for symlink in _find_symlinks(_target_dir):
        try:
            target = resolve_broken_symlink(symlink) if not symlink.exists() else symlink.resolve()
            if target and str(target).startswith(str(source_dir)):
                symlink.unlink()
                if verbose:
                    print(f"[green]✓[/] Removed: {symlink.relative_to(_target_dir)}")
                count += 1
        except (OSError, ValueError):
            continue

    removed_dirs = cleanup_empty_directories(_target_dir, [_target_dir / d for d in CLEANUP_DIRS])
    if removed_dirs and verbose:
        print(f"[dim]Cleaned up {len(removed_dirs)} empty directories[/]")

    print(f"[green]Removed {count} symlinks[/]")
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
        if target and str(target).startswith(str(_dotfiles_dir)):
            broken.append(symlink)

    return broken


def check_and_clean(
    target_dir: Path | None = None,
    dotfiles_dir: Path | None = None,
) -> int:
    """Find and remove broken symlinks, then clean up empty directories."""
    _target_dir = (target_dir or TARGET_DIR).resolve()
    _dotfiles_dir = (dotfiles_dir or DOTFILES_DIR).resolve()

    print("[blue]Scanning for broken symlinks...[/]")
    broken = find_broken_symlinks(_target_dir, _dotfiles_dir)

    if not broken:
        print("[green]✓[/] No broken symlinks found")
        return 0

    print(f"[yellow]Found {len(broken)} broken symlinks:[/]")
    for symlink in broken:
        try:
            print(f"  [red]✗[/] {symlink.relative_to(_target_dir)} → {symlink.readlink()}")
        except (OSError, ValueError):
            pass

    print("\n[blue]Removing broken symlinks...[/]")
    count = 0
    for symlink in broken:
        try:
            symlink.unlink()
            count += 1
        except OSError:
            pass

    removed_dirs = cleanup_empty_directories(_target_dir, [_target_dir / d for d in CLEANUP_DIRS])
    if removed_dirs:
        print(f"[dim]Cleaned up {len(removed_dirs)} empty directories[/]")

    print(f"[green]✓[/] Removed {count} broken symlinks")
    return count


def show_symlinks(
    source_dir: Path | None,
    layer: str,
    target_dir: Path | None = None,
    dotfiles_dir: Path | None = None,
) -> int:
    """Show current symlinks for a layer, or all dotfiles symlinks if source_dir is None."""
    _target_dir = (target_dir or TARGET_DIR).resolve()
    _dotfiles_dir = (dotfiles_dir or DOTFILES_DIR).resolve()
    source_filter = source_dir.resolve() if source_dir else _dotfiles_dir

    print(f"[blue]Symlinks for {layer}:[/]")
    count = 0
    broken_count = 0

    for symlink in _find_symlinks(_target_dir):
        try:
            target = symlink.resolve() if symlink.exists() else resolve_broken_symlink(symlink)
            if not target or not str(target).startswith(str(source_filter)):
                continue

            relative_path = symlink.relative_to(_target_dir)
            link_target = symlink.readlink()

            if not symlink.exists():
                print(f"  [red]✗[/] {relative_path} → {link_target} (BROKEN)")
                broken_count += 1
            else:
                print(f"  [green]→[/] {relative_path} → {link_target}")
            count += 1
        except (OSError, ValueError):
            continue

    if count == 0:
        print("[dim]No symlinks found[/]")
    else:
        suffix = f" [yellow]({broken_count} broken)[/]" if broken_count else ""
        print(f"\n[green]Found {count} symlinks[/]{suffix}")

    return count


def relink(
    platform: str,
    *,
    verbose: bool = False,
    dotfiles_dir: Path | None = None,
    target_dir: Path | None = None,
) -> None:
    """Complete refresh: remove old symlinks, clean up broken ones, recreate everything."""
    _dotfiles_dir = (dotfiles_dir or DOTFILES_DIR).resolve()
    _target_dir = (target_dir or TARGET_DIR).resolve()

    platform_dir = _dotfiles_dir / "configs" / platform
    common_dir = _dotfiles_dir / "configs" / "common"
    shell_dir = _dotfiles_dir / "shell"
    target_shell = _target_dir / ".local" / "shell"
    target_bin = _target_dir / ".local" / "bin"

    if not platform_dir.exists():
        print(f"[red]✗[/] Platform directory does not exist: {platform}")
        return

    def link_if_exists(source: Path, layer: str, dest: Path) -> None:
        if source.exists():
            create_symlinks(source, layer, verbose=verbose, target_dir=dest)

    print(f"[bold cyan]Complete relink for {platform}[/]")
    print()

    steps = [
        ("Removing platform symlinks", lambda: remove_symlinks(platform_dir, platform, verbose=verbose, target_dir=_target_dir)),
        ("Removing common symlinks", lambda: remove_symlinks(common_dir, "common", verbose=verbose, target_dir=_target_dir)),
        ("Removing shell symlinks", lambda: remove_symlinks(shell_dir, "shell", verbose=verbose, target_dir=_target_dir)),
        ("Checking for broken symlinks", lambda: check_and_clean(_target_dir, _dotfiles_dir)),
        ("Creating common base layer", lambda: create_symlinks(common_dir, "common", verbose=verbose, target_dir=_target_dir)),
        ("Creating platform overlay", lambda: create_symlinks(platform_dir, platform, verbose=verbose, target_dir=_target_dir)),
        ("Linking shell files", lambda: (link_if_exists(shell_dir / "common", "shell-common", target_shell), link_if_exists(shell_dir / platform, f"shell-{platform}", target_shell))),
        ("Linking apps", lambda: (link_if_exists(_dotfiles_dir / "apps" / "common", "apps-common", target_bin), link_if_exists(_dotfiles_dir / "apps" / platform, f"apps-{platform}", target_bin))),
    ]

    for i, (desc, fn) in enumerate(steps, 1):
        print(f"[yellow]Step [green]{i}/{len(steps)}[/green]: {desc}[/yellow]")
        fn()
        print()

    print(f"[bold green]✓ Relink complete![/] {platform} environment refreshed.")
