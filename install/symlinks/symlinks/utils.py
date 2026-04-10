"""Utility functions for symlink manager."""

import fnmatch
from pathlib import Path

from symlinks.config import settings


def should_exclude(path: Path) -> bool:
    """Check if a file should be excluded from symlinking.

    Args:
        path: Path to check

    Returns:
        True if the path should be excluded
    """
    path_str = str(path)
    filename = path.name

    for pattern in settings.exclude_patterns:
        # Directory patterns (end with /)
        if pattern.endswith("/"):
            # Check if this directory appears as a path component
            # e.g., ".git/" should match "foo/.git/bar" but NOT ".gitconfig"
            dir_name = pattern.rstrip("/")
            # Check if it appears as a complete directory in the path
            if f"/{dir_name}/" in path_str or path_str.startswith(f"{dir_name}/"):
                return True
        # Wildcard patterns
        elif "*" in pattern and fnmatch.fnmatch(filename, pattern):
            return True
        # Exact filename match
        elif filename == pattern:
            return True

    return False


def make_relative_symlink(source: Path, target: Path) -> Path:
    """Calculate relative path from target to source for symlink creation.

    Uses pathlib's relative_to with walk_up=True (Python 3.12+) to properly
    calculate relative paths with .. navigation.

    Args:
        source: The actual file/directory (absolute path)
        target: Where the symlink will be created (absolute path)

    Returns:
        Relative path from target's parent to source

    Example:
        >>> source = Path("/Users/chris/dotfiles/common/.config/nvim/init.lua")
        >>> target = Path("/Users/chris/.config/nvim/init.lua")
        >>> make_relative_symlink(source, target)
        PosixPath('../../dotfiles/common/.config/nvim/init.lua')
    """
    return source.relative_to(target.parent, walk_up=True)


def cleanup_empty_directories(base_dir: Path, dirs_to_clean: list[Path]) -> list[Path]:
    """Remove empty directories within specified paths.

    Args:
        base_dir: Base directory for relative paths (usually $HOME)
        dirs_to_clean: List of directories to clean

    Returns:
        List of directories that were removed (relative to base_dir)
    """
    # Directories that should NEVER be removed, even if empty
    protected_dirs = {
        ".local/state/claude",
        ".local/state/claude/locks",
        ".local/state/nvim",
        ".local/share/nvim",
        ".cache",
        ".venv",
        ".git",
    }

    removed = []
    for cleanup_dir in dirs_to_clean:
        if not cleanup_dir.exists():
            continue

        # Walk from deepest to shallowest
        for dirpath in sorted(cleanup_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if not dirpath.is_dir() or any(dirpath.iterdir()):
                continue

            # Check if this directory is protected
            try:
                relative = dirpath.relative_to(base_dir)
                is_protected = any(
                    str(relative) == protected or str(relative).startswith(f"{protected}/")
                    for protected in protected_dirs
                )
                if is_protected:
                    continue
            except ValueError:
                pass

            # Safe to remove
            try:
                dirpath.rmdir()
                # Store relative path from base_dir for cleaner output
                try:
                    relative = dirpath.relative_to(base_dir)
                    removed.append(relative)
                except ValueError:
                    # If can't make relative, use full path
                    removed.append(dirpath)
            except (OSError, PermissionError):
                pass

    return removed


def resolve_broken_symlink(symlink: Path) -> Path | None:
    """Resolve a broken symlink's target path.

    Args:
        symlink: The broken symlink

    Returns:
        Resolved absolute path the symlink points to, or None if can't resolve
    """
    if not symlink.is_symlink():
        return None

    try:
        # readlink gets the raw target (relative or absolute)
        target = symlink.readlink()

        # If absolute, return as-is
        if target.is_absolute():
            return target

        # If relative, resolve from symlink's directory
        return (symlink.parent / target).resolve()
    except (OSError, RuntimeError):
        return None
