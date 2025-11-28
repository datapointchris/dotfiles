"""Core symlink manager functionality."""

from pathlib import Path

from rich import print

from symlinks.config import settings
from symlinks.utils import cleanup_empty_directories, make_relative_symlink, resolve_broken_symlink, should_exclude


class SymlinkManager:
    """Manages dotfiles symlinks with layered architecture."""

    def __init__(self, dotfiles_dir: Path | None = None, target_dir: Path | None = None):
        """Initialize symlink manager.

        Args:
            dotfiles_dir: Root directory of dotfiles repository (defaults to settings)
            target_dir: Target directory for symlinks (defaults to settings)
        """
        self.dotfiles_dir = (dotfiles_dir or settings.dotfiles_dir).resolve()
        self.target_dir = (target_dir or settings.target_dir).resolve()

    def create_symlinks(self, source_dir: Path, layer: str) -> int:
        """Create symlinks from source directory to target.

        Args:
            source_dir: Source directory containing files to symlink
            layer: Description of layer (e.g., "common", "macos")

        Returns:
            Number of symlinks created
        """
        if not source_dir.exists():
            print(f"[red]✗[/] Source directory does not exist: {source_dir}")
            return 0

        print(f"[blue]Creating {layer} symlinks...[/]")
        count = 0

        # Find all files and symlinks in source
        for item in source_dir.rglob("*"):
            if not (item.is_file() or item.is_symlink()):
                continue

            # Get relative path from source dir
            try:
                relative_path = item.relative_to(source_dir)
            except ValueError:
                continue

            # Skip excluded files
            if should_exclude(relative_path):
                continue

            # Target path
            target_path = self.target_dir / relative_path

            # Create parent directory
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Calculate relative symlink path
            relative_link = make_relative_symlink(item, target_path)

            # Create symlink
            try:
                # Remove existing if it exists
                if target_path.exists() or target_path.is_symlink():
                    target_path.unlink()

                target_path.symlink_to(relative_link, target_is_directory=item.is_dir())
                print(f"[green]✓[/] [default]{relative_path}[/] → [magenta]{relative_link}[/]")
                count += 1
            except (OSError, PermissionError) as e:
                print(f"[yellow]⚠[/] Failed to link {relative_path}: {e}")

        print(f"[green]Created {count} symlinks[/]")
        return count

    def remove_symlinks(self, source_dir: Path, layer: str) -> int:
        """Remove symlinks that point to source directory.

        Args:
            source_dir: Source directory to match symlinks against
            layer: Description of layer (e.g., "common", "macos")

        Returns:
            Number of symlinks removed
        """
        print(f"[blue]Removing {layer} symlinks...[/]")
        count = 0
        source_dir = source_dir.resolve()

        # Find all symlinks in target
        for symlink in self._find_symlinks(self.target_dir):
            # Resolve symlink target
            try:
                # For broken symlinks, use resolve_broken_symlink
                if not symlink.exists():
                    target = resolve_broken_symlink(symlink)
                else:
                    target = symlink.resolve()

                # Check if symlink points to our source directory
                if target and str(target).startswith(str(source_dir)):
                    symlink.unlink()
                    relative_path = symlink.relative_to(self.target_dir)
                    print(f"[green]✓[/] Removed: {relative_path}")
                    count += 1
            except (OSError, ValueError):
                continue

        # Cleanup empty directories
        removed_dirs = cleanup_empty_directories(self.target_dir, settings.get_cleanup_paths())
        if removed_dirs:
            print(f"[dim]Cleaned up {len(removed_dirs)} empty directories:[/]")
            for dir_path in removed_dirs:
                print(f"[dim]  - {dir_path}[/]")

        print(f"[green]Removed {count} symlinks[/]")
        return count

    def find_broken_symlinks(self) -> list[Path]:
        """Find all broken symlinks that point to dotfiles.

        Returns:
            List of broken symlinks
        """
        broken = []

        for symlink in self._find_symlinks(self.target_dir):
            # Check if symlink is broken
            if symlink.exists():
                continue

            # Check if it points to dotfiles
            target = resolve_broken_symlink(symlink)
            if target and "dotfiles" in str(target):
                broken.append(symlink)

        return broken

    def check_and_clean(self) -> int:
        """Find and remove broken symlinks.

        Returns:
            Number of broken symlinks removed
        """
        print("[blue]Scanning for broken symlinks...[/]")

        broken = self.find_broken_symlinks()

        if not broken:
            print("[green]✓[/] No broken symlinks found")
            return 0

        print(f"[yellow]Found {len(broken)} broken symlinks:[/]")
        for symlink in broken:
            try:
                target = symlink.readlink()
                relative_path = symlink.relative_to(self.target_dir)
                print(f"  [red]✗[/] {relative_path} → {target}")
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

        # Cleanup empty directories
        removed_dirs = cleanup_empty_directories(self.target_dir, settings.get_cleanup_paths())
        if removed_dirs:
            print(f"[dim]Cleaned up {len(removed_dirs)} empty directories:[/]")
            for dir_path in removed_dirs:
                print(f"[dim]  - {dir_path}[/]")

        print(f"[green]✓[/] Removed {count} broken symlinks")
        return count

    def show_symlinks(self, source_dir: Path | None, layer: str) -> int:
        """Show current symlinks for a layer.

        Args:
            source_dir: Source directory to filter symlinks (None for all dotfiles symlinks)
            layer: Description of layer

        Returns:
            Number of symlinks found
        """
        print(f"[blue]Symlinks for {layer}:[/]")
        count = 0
        broken_count = 0

        source_filter = source_dir.resolve() if source_dir else self.dotfiles_dir

        for symlink in self._find_symlinks(self.target_dir):
            try:
                # Check if this symlink points to our source
                if symlink.exists():
                    target = symlink.resolve()
                else:
                    target = resolve_broken_symlink(symlink)

                if not target or not str(target).startswith(str(source_filter)):
                    continue

                relative_path = symlink.relative_to(self.target_dir)
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
            print(f"\n[green]Found {count} symlinks[/]", end="")
            if broken_count:
                print(f" [yellow]({broken_count} broken)[/]")
            else:
                print()

        return count

    def link_apps(self, platform: str) -> int:
        """Link apps from apps/{platform}/ to ~/.local/bin/

        Args:
            platform: Platform name (common, macos, wsl)

        Returns:
            Number of apps linked
        """
        apps_dir = self.dotfiles_dir / "apps" / platform
        if not apps_dir.exists():
            return 0

        target_bin = self.target_dir / ".local" / "bin"
        target_bin.mkdir(parents=True, exist_ok=True)

        print(f"[blue]Linking {platform} apps to ~/.local/bin/...[/]")
        count = 0

        for app in apps_dir.iterdir():
            # Handle directories with bin/ subdirectory (e.g., font/bin/font)
            if app.is_dir():
                bin_dir = app / "bin"
                if bin_dir.exists() and bin_dir.is_dir():
                    # Link executables from bin/ subdirectory
                    for executable in bin_dir.iterdir():
                        if executable.is_file() and not should_exclude(executable):
                            target = target_bin / executable.name

                            # Remove existing symlink or file
                            if target.exists() or target.is_symlink():
                                target.unlink()

                            # Create relative symlink
                            relative_source = make_relative_symlink(executable, target)
                            target.symlink_to(relative_source)
                            print(f"  [green]✓[/] {app.name}/{executable.name} → ~/.local/bin/{executable.name}")
                            count += 1
                # Skip other directories (like sess/ which needs building)
                continue

            if should_exclude(app):
                continue

            target = target_bin / app.name

            # Remove existing symlink or file
            if target.exists() or target.is_symlink():
                target.unlink()

            # Create relative symlink
            relative_source = make_relative_symlink(app, target)
            target.symlink_to(relative_source)
            print(f"  [green]✓[/] {app.name} → ~/.local/bin/{app.name}")
            count += 1

        if count > 0:
            print(f"[green]Linked {count} apps[/]")
        return count

    def relink(self, platform: str):
        """Complete refresh: remove old, check for broken, create new.

        Args:
            platform: Platform name (e.g., "macos", "wsl", "arch")
        """
        # Updated paths for new structure
        platform_dir = self.dotfiles_dir / "platforms" / platform
        common_dir = self.dotfiles_dir / "platforms" / "common"

        if not platform_dir.exists():
            print(f"[red]✗[/] Platform directory does not exist: {platform}")
            return

        print(f"[bold cyan]Complete relink for {platform}[/]")
        print()

        print("[yellow]Step [green]1/6[/green]: Removing platform symlinks[/yellow]")
        self.remove_symlinks(platform_dir, platform)
        print()

        print("[yellow]Step [green]2/6[/green]: Removing common symlinks[/yellow]")
        self.remove_symlinks(common_dir, "common")
        print()

        print("[yellow]Step [green]3/6[/green]: Checking for broken symlinks[/yellow]")
        self.check_and_clean()
        print()

        print("[yellow]Step [green]4/6[/green]: Creating common base layer[/yellow]")
        self.create_symlinks(common_dir, "common")
        print()

        print("[yellow]Step [green]5/6[/green]: Creating platform overlay[/yellow]")
        self.create_symlinks(platform_dir, platform)
        print()

        print("[yellow]Step [green]6/6[/green]: Linking apps[/yellow]")
        self.link_apps("common")
        self.link_apps(platform)
        print()

        print(f"[bold green]✓ Relink complete![/] {platform} environment refreshed.")

    def _find_symlinks(self, base_dir: Path) -> list[Path]:
        """Find all symlinks under base directory with efficient depth-limited search.

        Uses manual directory walking to exclude directories before traversing,
        dramatically improving performance for large directory trees.

        Args:
            base_dir: Base directory to search

        Returns:
            List of symlink paths
        """
        symlinks = []

        def should_exclude_dir(path: Path) -> bool:
            """Check if directory should be excluded from search."""
            path_str = str(path)
            for pattern in settings.exclude_search_dirs:
                if pattern.rstrip('/') in path_str:
                    return True
            return False

        def walk_limited(directory: Path, current_depth: int = 0):
            """Recursively walk directory with depth limit and early exclusions."""
            if current_depth >= settings.search_depth:
                return

            try:
                for item in directory.iterdir():
                    # Skip excluded directories BEFORE descending
                    if item.is_dir() and should_exclude_dir(item):
                        continue

                    # Check if it's a symlink
                    if item.is_symlink():
                        symlinks.append(item)

                    # Recurse into directories (but not symlink directories to avoid loops)
                    if item.is_dir() and not item.is_symlink():
                        walk_limited(item, current_depth + 1)
            except (PermissionError, OSError):
                # Skip directories we can't access
                pass

        walk_limited(base_dir)
        return symlinks
