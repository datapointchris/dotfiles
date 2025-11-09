"""Integration tests for symlink manager."""
from pathlib import Path

import pytest

from symlinks.manager import SymlinkManager


@pytest.fixture
def dotfiles_structure(tmp_path):
    """Create a realistic dotfiles structure for testing."""
    dotfiles = tmp_path / "dotfiles"
    home = tmp_path / "home"

    # Common files
    common = dotfiles / "common"
    (common / ".config" / "nvim").mkdir(parents=True)
    (common / ".config" / "nvim" / "init.lua").write_text("-- nvim config")
    (common / ".config" / "zsh").mkdir(parents=True)
    (common / ".config" / "zsh" / ".zshrc").write_text("# zsh config")
    (common / ".local" / "bin").mkdir(parents=True)
    (common / ".local" / "bin" / "tools").write_text("#!/bin/bash\necho tools")

    # Platform-specific files (macos)
    macos = dotfiles / "macos"
    macos.mkdir()
    (macos / ".gitconfig").write_text("[user]\n  name = Test")
    (macos / ".profile").write_text("# macos profile")
    (macos / ".config" / "ghostty").mkdir(parents=True)
    (macos / ".config" / "ghostty" / "config").write_text("# ghostty config")

    # Files that should be excluded
    (common / ".git").mkdir()
    (common / ".git" / "config").write_text("# should be excluded")
    (common / "node_modules").mkdir()
    (common / "node_modules" / "package").write_text("# should be excluded")

    return {"dotfiles": dotfiles, "home": home, "common": common, "macos": macos}


def test_complete_symlink_workflow(dotfiles_structure):
    """Test complete workflow: create, verify, remove symlinks."""
    dotfiles = dotfiles_structure["dotfiles"]
    home = dotfiles_structure["home"]
    common = dotfiles_structure["common"]
    macos = dotfiles_structure["macos"]

    manager = SymlinkManager(dotfiles_dir=dotfiles, target_dir=home)

    # Create common symlinks
    count = manager.create_symlinks(common, "common")
    assert count == 3  # init.lua, .zshrc, tools (no excluded files)

    # Verify common symlinks exist and work
    assert (home / ".config" / "nvim" / "init.lua").is_symlink()
    assert (home / ".config" / "nvim" / "init.lua").read_text() == "-- nvim config"
    assert (home / ".config" / "zsh" / ".zshrc").is_symlink()
    assert (home / ".local" / "bin" / "tools").is_symlink()

    # Verify excluded files are NOT symlinked
    assert not (home / ".git" / "config").exists()
    assert not (home / "node_modules" / "package").exists()

    # Create platform symlinks
    count = manager.create_symlinks(macos, "macos")
    assert count == 3  # .gitconfig, .profile, ghostty/config

    # Verify platform symlinks
    assert (home / ".gitconfig").is_symlink()
    assert (home / ".gitconfig").read_text() == "[user]\n  name = Test"
    assert (home / ".profile").is_symlink()
    assert (home / ".config" / "ghostty" / "config").is_symlink()

    # Remove platform symlinks
    removed = manager.remove_symlinks(macos, "macos")
    assert removed == 3

    # Verify platform symlinks are gone
    assert not (home / ".gitconfig").exists()
    assert not (home / ".profile").exists()

    # But common symlinks still exist
    assert (home / ".config" / "nvim" / "init.lua").exists()


def test_gitconfig_not_excluded(dotfiles_structure):
    """Regression test: .gitconfig should be symlinked (not excluded by .git/ pattern)."""
    dotfiles = dotfiles_structure["dotfiles"]
    home = dotfiles_structure["home"]
    macos = dotfiles_structure["macos"]

    manager = SymlinkManager(dotfiles_dir=dotfiles, target_dir=home)

    # Create symlinks
    manager.create_symlinks(macos, "macos")

    # CRITICAL: .gitconfig should exist
    assert (home / ".gitconfig").exists(), ".gitconfig was incorrectly excluded!"
    assert (home / ".gitconfig").is_symlink()
    assert (home / ".gitconfig").read_text() == "[user]\n  name = Test"


def test_cross_platform_git_files(tmp_path):
    """Test that common .git* files work across all platforms."""
    dotfiles = tmp_path / "dotfiles"
    home = tmp_path / "home"
    home.mkdir()

    # Create git-related files that should be symlinked
    for platform in ["common", "macos", "wsl", "arch"]:
        platform_dir = dotfiles / platform
        platform_dir.mkdir(parents=True)

        # All platforms might have these
        (platform_dir / ".gitconfig").write_text(f"[user]\n  platform = {platform}")
        (platform_dir / ".gitignore").write_text("*.swp")
        (platform_dir / ".gitattributes").write_text("* text=auto")

    manager = SymlinkManager(dotfiles_dir=dotfiles, target_dir=home)

    # Test each platform
    for platform in ["macos", "wsl", "arch"]:
        # Clear home
        for item in home.iterdir():
            if item.is_symlink() or item.is_file():
                item.unlink()

        platform_dir = dotfiles / platform
        manager.create_symlinks(platform_dir, platform)

        # All .git* files should be symlinked
        assert (home / ".gitconfig").exists(), f"{platform}: .gitconfig missing"
        assert (home / ".gitignore").exists(), f"{platform}: .gitignore missing"
        assert (home / ".gitattributes").exists(), f"{platform}: .gitattributes missing"


def test_broken_symlink_cleanup(dotfiles_structure):
    """Test that broken symlinks are properly detected and cleaned up."""
    dotfiles = dotfiles_structure["dotfiles"]
    home = dotfiles_structure["home"]
    common = dotfiles_structure["common"]

    manager = SymlinkManager(dotfiles_dir=dotfiles, target_dir=home)

    # Create symlinks
    manager.create_symlinks(common, "common")

    # Break a symlink by removing the source file
    source_file = common / ".config" / "nvim" / "init.lua"
    source_file.unlink()

    # Find broken symlinks
    broken = manager.find_broken_symlinks()
    assert len(broken) == 1
    assert broken[0].name == "init.lua"

    # Clean up broken symlinks
    removed = manager.check_and_clean()
    assert removed == 1

    # Verify it's gone
    assert not (home / ".config" / "nvim" / "init.lua").exists()
