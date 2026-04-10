"""Tests for utility functions."""

from pathlib import Path

from symlinks.utils import should_exclude, resolve_broken_symlink, make_relative_symlink


def test_should_exclude_git_dir():
    """Test that .git directories are excluded."""
    assert should_exclude(Path(".git/config"))
    assert should_exclude(Path("some/path/.git/hooks"))


def test_should_not_exclude_gitconfig():
    """Test that .gitconfig is NOT excluded (regression test for .git/ pattern bug)."""
    assert not should_exclude(Path(".gitconfig"))
    assert not should_exclude(Path("some/dir/.gitconfig"))


def test_should_not_exclude_git_related_files():
    """Test that .git* files (not .git/ directory) are NOT excluded."""
    assert not should_exclude(Path(".gitignore"))
    assert not should_exclude(Path(".gitattributes"))
    assert not should_exclude(Path(".github/workflows/ci.yml"))
    assert not should_exclude(Path("some/.gitkeep"))


def test_should_exclude_git_directory():
    """Test that .git/ directory IS excluded."""
    assert should_exclude(Path(".git/config"))
    assert should_exclude(Path("foo/.git/hooks"))
    assert should_exclude(Path("bar/.git/objects/abc123"))


def test_should_not_exclude_similar_named_files():
    """Test that files with similar names to exclusions are NOT excluded."""
    # Similar to .DS_Store but not exact match
    assert not should_exclude(Path(".DSConfig"))

    # Similar to node_modules but not directory
    assert not should_exclude(Path("node_modules.txt"))
    assert not should_exclude(Path("my_node_modules.js"))

    # Similar to .pytest_cache but not directory
    assert not should_exclude(Path(".pytest.ini"))
    assert not should_exclude(Path("pytest.cfg"))

    # Contains "tmp" but not .tmp extension
    assert not should_exclude(Path("template.txt"))
    assert not should_exclude(Path("tmp_file.txt"))
    assert not should_exclude(Path("temporary.md"))


def test_tmux_plugin_exclusion():
    """Test that tmux plugin directories are excluded but other tmux files are not."""
    # Should be excluded
    assert should_exclude(Path("tmux/plugins/tpm"))
    assert should_exclude(Path(".tmux/plugins/vim-tmux-navigator"))

    # Should NOT be excluded
    assert not should_exclude(Path("tmux/tmux.conf"))
    assert not should_exclude(Path("tmux.conf"))
    assert not should_exclude(Path(".config/tmux/tmux.conf"))


def test_should_exclude_ds_store():
    """Test that .DS_Store files are excluded."""
    assert should_exclude(Path(".DS_Store"))
    assert should_exclude(Path("some/dir/.DS_Store"))


def test_should_exclude_temp_files():
    """Test that temp files are excluded."""
    assert should_exclude(Path("file.tmp"))
    assert should_exclude(Path("file.temp"))
    assert should_exclude(Path("file.log"))


def test_should_not_exclude_normal_files():
    """Test that normal files are not excluded."""
    assert not should_exclude(Path(".zshrc"))
    assert not should_exclude(Path(".config/nvim/init.lua"))
    assert not should_exclude(Path(".local/bin/tools"))


def test_resolve_broken_symlink_absolute(tmp_path):
    """Test resolving broken symlink with absolute target."""
    symlink = tmp_path / "link"
    target = Path("/nonexistent/file")
    symlink.symlink_to(target)

    resolved = resolve_broken_symlink(symlink)
    assert resolved == target


def test_resolve_broken_symlink_relative(tmp_path):
    """Test resolving broken symlink with relative target."""
    symlink = tmp_path / "link"
    symlink.symlink_to("../nonexistent/file")

    resolved = resolve_broken_symlink(symlink)
    assert resolved is not None
    assert "nonexistent/file" in str(resolved)


def test_resolve_broken_symlink_not_a_symlink(tmp_path):
    """Test that regular files return None."""
    regular_file = tmp_path / "file.txt"
    regular_file.write_text("test")

    resolved = resolve_broken_symlink(regular_file)
    assert resolved is None


def test_make_relative_symlink_simple():
    """Test relative path calculation for simple case."""
    # Source: /Users/chris/dotfiles/common/.config/nvim/init.lua
    # Target: /Users/chris/.config/nvim/init.lua
    # Symlink parent: /Users/chris/.config/nvim/
    # From /Users/chris/.config/nvim/ go up 2 to /Users/chris, then down to dotfiles
    # Expected: ../../dotfiles/common/.config/nvim/init.lua

    source = Path("/Users/chris/dotfiles/common/.config/nvim/init.lua")
    target = Path("/Users/chris/.config/nvim/init.lua")

    result = make_relative_symlink(source, target)

    # Verify the result is a relative path with correct number of ../
    assert str(result) == "../../dotfiles/common/.config/nvim/init.lua"


def test_make_relative_symlink_zshrc():
    """Test relative path calculation for .zshrc."""
    # Source: /Users/chris/dotfiles/common/.config/zsh/.zshrc
    # Target: /Users/chris/.config/zsh/.zshrc
    # Symlink parent: /Users/chris/.config/zsh/
    # From /Users/chris/.config/zsh/ go up 2 to /Users/chris, then down to dotfiles
    # Expected: ../../dotfiles/common/.config/zsh/.zshrc

    source = Path("/Users/chris/dotfiles/common/.config/zsh/.zshrc")
    target = Path("/Users/chris/.config/zsh/.zshrc")

    result = make_relative_symlink(source, target)

    assert str(result) == "../../dotfiles/common/.config/zsh/.zshrc"


def test_make_relative_symlink_top_level():
    """Test relative path calculation for top-level file."""
    # Source: /Users/chris/dotfiles/macos/.gitconfig
    # Target: /Users/chris/.gitconfig
    # Expected: dotfiles/macos/.gitconfig

    source = Path("/Users/chris/dotfiles/macos/.gitconfig")
    target = Path("/Users/chris/.gitconfig")

    result = make_relative_symlink(source, target)

    assert str(result) == "dotfiles/macos/.gitconfig"


def test_make_relative_symlink_actually_works(tmp_path):
    """Integration test: verify symlink actually works with calculated path."""
    # Create source file
    source_dir = tmp_path / "dotfiles" / "common" / ".config" / "nvim"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "init.lua"
    source_file.write_text("-- test config")

    # Create target location
    target_dir = tmp_path / "home" / ".config" / "nvim"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "init.lua"

    # Calculate relative path
    relative_path = make_relative_symlink(source_file, target_file)

    # Create symlink using calculated path
    target_file.symlink_to(relative_path)

    # Verify symlink works: can read through it
    assert target_file.exists()
    assert target_file.is_symlink()
    assert target_file.read_text() == "-- test config"
