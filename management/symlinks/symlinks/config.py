"""Configuration and settings for symlinks manager."""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SymlinksSettings(BaseSettings):
    """Configuration settings for symlinks manager."""

    model_config = SettingsConfigDict(
        env_prefix="SYMLINKS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core paths
    dotfiles_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("DOTFILES", Path.home() / "dotfiles")),
        description="Root directory of dotfiles repository",
    )

    target_dir: Path = Field(
        default_factory=lambda: Path.home(),
        description="Target directory for symlinks (usually $HOME)",
    )

    # Search configuration
    search_depth: int = Field(
        default=5,
        description="Maximum depth for finding symlinks",
    )

    # Cleanup directories (relative to target_dir)
    cleanup_dirs: list[str] = Field(
        default=[".config", ".local/shell", ".local/share/workflows"],
        description="Directories to clean up empty subdirectories",
    )

    # Exclusion patterns
    exclude_patterns: list[str] = Field(
        default=[
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
        ],
        description="File patterns to exclude from symlinking",
    )

    # Search exclusions - cross-platform directories to skip during symlink searches
    exclude_search_dirs: list[str] = Field(
        default=[
            # macOS specific
            "Library/",
            ".Trash/",
            "Applications/",
            "Movies/",
            "Music/",
            "Pictures/",
            "Downloads/",
            # Linux/WSL specific
            ".cache/",
            ".local/share/Trash/",
            "snap/",
            # Language package managers and toolchains (cross-platform)
            "node_modules/",
            ".npm/",
            ".nvm/",
            ".pyenv/",
            ".cargo/",
            ".rustup/",
            ".rbenv/",
            # Version control
            ".git/",
            # Virtual environments and build artifacts
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
            # IDE and editor directories
            ".idea/",
            ".vscode/",
            ".vim/",
        ],
        description="Directories to exclude from symlink searches (cross-platform)",
    )

    def get_cleanup_paths(self) -> list[Path]:
        """Get absolute paths for cleanup directories."""
        return [self.target_dir / d for d in self.cleanup_dirs]


# Global settings instance
settings = SymlinksSettings()
