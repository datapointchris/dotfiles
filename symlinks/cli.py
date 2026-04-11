"""Command-line interface for symlinks manager."""

from pathlib import Path

import typer
from rich.console import Console

import symlinks.core as core
from symlinks import __version__

app = typer.Typer(
    help="Dotfiles symlink manager with layered architecture",
    no_args_is_help=True,
)
console = Console()

# Module-level verbose flag set by the app callback
verbose: bool = False


@app.callback()
def main(
    verbose_flag: bool = typer.Option(False, "--verbose", "-v", help="Show individual file operations"),
):
    global verbose
    verbose = verbose_flag


@app.command()
def link(
    target: str = typer.Argument(..., help="Target to link (common, macos, wsl, archlinux, etc.)"),
):
    """Create symlinks for common or platform layer, including apps."""
    source_dir = core.DOTFILES_DIR / "configs" / target

    if not source_dir.exists():
        console.print(f"[red]✗[/] Config directory does not exist: {target}")
        configs_dir = core.DOTFILES_DIR / "configs"
        console.print(f"[dim]Available configs in {configs_dir}:[/]")
        if configs_dir.exists():
            for item in configs_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    console.print(f"  - {item.name}")
        raise typer.Exit(1)

    count = core.create_symlinks(source_dir, target, verbose=verbose)

    shell_dir = core.DOTFILES_DIR / "shell" / target
    shell_count = core.create_symlinks(shell_dir, f"shell-{target}", verbose=verbose, target_dir=core.TARGET_DIR / ".local" / "shell") if shell_dir.exists() else 0

    apps_dir = core.DOTFILES_DIR / "apps" / target
    app_count = core.create_symlinks(apps_dir, f"apps-{target}", verbose=verbose, target_dir=core.TARGET_DIR / ".local" / "bin") if apps_dir.exists() else 0

    if count == 0 and shell_count == 0 and app_count == 0:
        console.print("[yellow]No symlinks created[/]")
        raise typer.Exit(1)


@app.command()
def unlink(
    target: str = typer.Argument(..., help="Target to unlink (common, macos, wsl, archlinux, etc.)"),
):
    """Remove symlinks for common or platform layer."""
    source_dir = core.DOTFILES_DIR / "configs" / target

    if not source_dir.exists():
        console.print(f"[red]✗[/] Config directory does not exist: {target}")
        raise typer.Exit(1)

    count = core.remove_symlinks(source_dir, target, verbose=verbose)

    if count == 0:
        console.print("[yellow]No symlinks removed[/]")


@app.command()
def show(
    target: str = typer.Argument(None, help="Target to show (common, macos, wsl, archlinux, or omit for all)"),
):
    """Show current symlinks for a layer or all dotfiles symlinks."""
    if target:
        source_dir = core.DOTFILES_DIR / target
        if not source_dir.exists():
            console.print(f"[red]✗[/] Directory does not exist: {target}")
            raise typer.Exit(1)
        core.show_symlinks(source_dir, target)
    else:
        core.show_symlinks(None, "all dotfiles")


@app.command()
def check(
    auto_fix: bool = typer.Option(True, help="Automatically remove broken symlinks"),
):
    """Check for broken symlinks and optionally remove them."""
    if auto_fix:
        core.check_and_clean()
    else:
        broken = core.find_broken_symlinks()
        if not broken:
            console.print("[green]✓[/] No broken symlinks found")
        else:
            console.print(f"[yellow]Found {len(broken)} broken symlinks:[/]")
            for symlink in broken:
                try:
                    console.print(f"  [red]✗[/] {symlink} → {symlink.readlink()}")
                except OSError:
                    pass


@app.command()
def relink(
    platform: str = typer.Argument(..., help="Platform to relink (macos, wsl, archlinux, etc.)"),
):
    """Complete refresh: unlink platform, unlink common, check, link common, link platform."""
    platform_dir = core.DOTFILES_DIR / "configs" / platform

    if not platform_dir.exists():
        console.print(f"[red]✗[/] Config directory does not exist: {platform}")
        configs_dir = core.DOTFILES_DIR / "configs"
        console.print(f"[dim]Available configs in {configs_dir}:[/]")
        if configs_dir.exists():
            for item in configs_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    console.print(f"  - {item.name}")
        raise typer.Exit(1)

    core.relink(platform, verbose=verbose)


@app.command()
def version():
    """Show version information."""
    console.print(f"[cyan]dotfiles-symlinks[/] version [bold]{__version__}[/]")


@app.command()
def info():
    """Show dotfiles directory and configuration."""
    console.print("[cyan]Dotfiles Configuration:[/]")
    console.print(f"  Dotfiles directory: [bold]{core.DOTFILES_DIR}[/]")
    console.print(f"  Target directory: [bold]{core.TARGET_DIR}[/]")
    console.print(f"  Search depth: [bold]{core.SEARCH_DEPTH}[/]")
    console.print()
    console.print("[cyan]Available directories:[/]")
    for item in core.DOTFILES_DIR.iterdir():
        if item.is_dir() and item.name not in [".git", "tools", "docs", "scripts"]:
            layer_type = "base layer" if item.name == "common" else "overlay"
            console.print(f"  [green]•[/] {item.name} ({layer_type})")


if __name__ == "__main__":
    app()
