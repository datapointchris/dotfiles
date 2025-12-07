"""Command-line interface for symlinks manager."""

from pathlib import Path

import typer
from rich.console import Console

from symlinks import __version__
from symlinks.config import settings
from symlinks.manager import SymlinkManager

app = typer.Typer(
    help="Dotfiles symlink manager with layered architecture",
    no_args_is_help=True,
)
console = Console()


@app.command()
def link(
    target: str = typer.Argument(..., help="Target to link (common, macos, wsl, arch, etc.)"),
):
    """Create symlinks for common or platform layer, including apps."""
    source_dir = settings.dotfiles_dir / "platforms" / target

    if not source_dir.exists():
        console.print(f"[red]✗[/] Platform directory does not exist: {target}")
        platforms_dir = settings.dotfiles_dir / "platforms"
        console.print(f"[dim]Available platforms in {platforms_dir}:[/]")
        if platforms_dir.exists():
            for item in platforms_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    console.print(f"  - {item.name}")
        raise typer.Exit(1)

    manager = SymlinkManager()
    count = manager.create_symlinks(source_dir, target)
    app_count = manager.link_apps(target)

    if count == 0 and app_count == 0:
        console.print("[yellow]No symlinks created[/]")
        raise typer.Exit(1)


@app.command()
def unlink(
    target: str = typer.Argument(..., help="Target to unlink (common, macos, wsl, arch, etc.)"),
):
    """Remove symlinks for common or platform layer."""
    source_dir = settings.dotfiles_dir / "platforms" / target

    if not source_dir.exists():
        console.print(f"[red]✗[/] Platform directory does not exist: {target}")
        raise typer.Exit(1)

    manager = SymlinkManager()
    count = manager.remove_symlinks(source_dir, target)

    if count == 0:
        console.print("[yellow]No symlinks removed[/]")


@app.command()
def show(
    target: str = typer.Argument(None, help="Target to show (common, macos, wsl, arch, or omit for all)"),
):
    """Show current symlinks for a layer or all dotfiles symlinks."""
    manager = SymlinkManager()

    if target:
        source_dir = settings.dotfiles_dir / target
        if not source_dir.exists():
            console.print(f"[red]✗[/] Directory does not exist: {target}")
            raise typer.Exit(1)
        manager.show_symlinks(source_dir, target)
    else:
        manager.show_symlinks(None, "all dotfiles")


@app.command()
def check(
    auto_fix: bool = typer.Option(True, help="Automatically remove broken symlinks"),
):
    """Check for broken symlinks and optionally remove them."""
    manager = SymlinkManager()

    if auto_fix:
        count = manager.check_and_clean()
    else:
        broken = manager.find_broken_symlinks()
        if not broken:
            console.print("[green]✓[/] No broken symlinks found")
        else:
            console.print(f"[yellow]Found {len(broken)} broken symlinks:[/]")
            for symlink in broken:
                try:
                    target = symlink.readlink()
                    console.print(f"  [red]✗[/] {symlink} → {target}")
                except OSError:
                    pass


@app.command()
def relink(
    platform: str = typer.Argument(..., help="Platform to relink (macos, wsl, arch, etc.)"),
):
    """Complete refresh: unlink platform, unlink common, check, link common, link platform."""
    platform_dir = settings.dotfiles_dir / "platforms" / platform

    if not platform_dir.exists():
        console.print(f"[red]✗[/] Platform directory does not exist: {platform}")
        platforms_dir = settings.dotfiles_dir / "platforms"
        console.print(f"[dim]Available platforms in {platforms_dir}:[/]")
        if platforms_dir.exists():
            for item in platforms_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    console.print(f"  - {item.name}")
        raise typer.Exit(1)

    manager = SymlinkManager()
    manager.relink(platform)


@app.command()
def version():
    """Show version information."""
    console.print(f"[cyan]dotfiles-symlinks[/] version [bold]{__version__}[/]")


@app.command()
def info():
    """Show dotfiles directory and configuration."""
    console.print("[cyan]Dotfiles Configuration:[/]")
    console.print(f"  Dotfiles directory: [bold]{settings.dotfiles_dir}[/]")
    console.print(f"  Target directory: [bold]{settings.target_dir}[/]")
    console.print(f"  Search depth: [bold]{settings.search_depth}[/]")
    console.print()
    console.print("[cyan]Available directories:[/]")
    for item in settings.dotfiles_dir.iterdir():
        if item.is_dir() and item.name not in [".git", "tools", "docs", "scripts"]:
            layer_type = "base layer" if item.name == "common" else "overlay"
            console.print(f"  [green]•[/] {item.name} ({layer_type})")


if __name__ == "__main__":
    app()
