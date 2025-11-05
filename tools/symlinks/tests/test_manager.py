"""Tests for SymlinkManager."""

from pathlib import Path

from symlinks.manager import SymlinkManager


def test_create_symlinks(tmp_path):
    """Test creating symlinks."""
    # Setup
    dotfiles = tmp_path / "dotfiles"
    source = dotfiles / "common"
    source.mkdir(parents=True)
    (source / "test.txt").write_text("test content")

    target = tmp_path / "home"
    target.mkdir()

    # Execute
    manager = SymlinkManager(dotfiles, target)
    count = manager.create_symlinks(source, "common")

    # Verify
    assert count == 1
    assert (target / "test.txt").is_symlink()
    assert (target / "test.txt").read_text() == "test content"


def test_create_nested_symlinks(tmp_path):
    """Test creating nested directory symlinks."""
    # Setup
    dotfiles = tmp_path / "dotfiles"
    source = dotfiles / "common"
    nested = source / ".config" / "nvim"
    nested.mkdir(parents=True)
    (nested / "init.lua").write_text("-- config")

    target = tmp_path / "home"
    target.mkdir()

    # Execute
    manager = SymlinkManager(dotfiles, target)
    count = manager.create_symlinks(source, "common")

    # Verify
    assert count == 1
    assert (target / ".config" / "nvim" / "init.lua").is_symlink()


def test_remove_symlinks(tmp_path):
    """Test removing symlinks."""
    # Setup
    dotfiles = tmp_path / "dotfiles"
    source = dotfiles / "macos"
    source.mkdir(parents=True)
    (source / "test.txt").write_text("test")

    target = tmp_path / "home"
    target.mkdir()

    # Create symlink
    manager = SymlinkManager(dotfiles, target)
    manager.create_symlinks(source, "macos")

    # Execute
    count = manager.remove_symlinks(source, "macos")

    # Verify
    assert count == 1
    assert not (target / "test.txt").exists()


def test_find_broken_symlinks(tmp_path):
    """Test finding broken symlinks."""
    # Setup
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()

    target = tmp_path / "home"
    target.mkdir()

    # Create broken symlink pointing to dotfiles
    broken_link = target / "broken"
    broken_link.symlink_to(dotfiles / "nonexistent")

    # Execute
    manager = SymlinkManager(dotfiles, target)
    broken = manager.find_broken_symlinks()

    # Verify
    assert len(broken) == 1
    assert broken[0] == broken_link


def test_check_and_clean(tmp_path):
    """Test checking and cleaning broken symlinks."""
    # Setup
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()

    target = tmp_path / "home"
    target.mkdir()

    # Create broken symlink
    broken_link = target / "broken"
    broken_link.symlink_to(dotfiles / "nonexistent")

    # Execute
    manager = SymlinkManager(dotfiles, target)
    count = manager.check_and_clean()

    # Verify
    assert count == 1
    assert not broken_link.exists()
