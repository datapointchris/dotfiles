"""Tests for core symlink management functions and utilities."""

from pathlib import Path

import symlinks.core as core


# ─── Utility Tests ────────────────────────────────────────────────────────────


def test_should_exclude_git_dir():
    assert core.should_exclude(Path(".git/config"))
    assert core.should_exclude(Path("some/path/.git/hooks"))


def test_should_not_exclude_gitconfig():
    """Regression: .gitconfig must NOT be excluded by the .git/ directory pattern."""
    assert not core.should_exclude(Path(".gitconfig"))
    assert not core.should_exclude(Path("some/dir/.gitconfig"))


def test_should_not_exclude_git_related_files():
    assert not core.should_exclude(Path(".gitignore"))
    assert not core.should_exclude(Path(".gitattributes"))
    assert not core.should_exclude(Path(".github/workflows/ci.yml"))
    assert not core.should_exclude(Path("some/.gitkeep"))


def test_should_exclude_git_directory():
    assert core.should_exclude(Path(".git/config"))
    assert core.should_exclude(Path("foo/.git/hooks"))
    assert core.should_exclude(Path("bar/.git/objects/abc123"))


def test_should_not_exclude_similar_named_files():
    assert not core.should_exclude(Path(".DSConfig"))
    assert not core.should_exclude(Path("node_modules.txt"))
    assert not core.should_exclude(Path("my_node_modules.js"))
    assert not core.should_exclude(Path(".pytest.ini"))
    assert not core.should_exclude(Path("pytest.cfg"))
    assert not core.should_exclude(Path("template.txt"))
    assert not core.should_exclude(Path("tmp_file.txt"))
    assert not core.should_exclude(Path("temporary.md"))


def test_tmux_plugin_exclusion():
    assert core.should_exclude(Path("tmux/plugins/tpm"))
    assert core.should_exclude(Path(".tmux/plugins/vim-tmux-navigator"))
    assert not core.should_exclude(Path("tmux/tmux.conf"))
    assert not core.should_exclude(Path("tmux.conf"))
    assert not core.should_exclude(Path(".config/tmux/tmux.conf"))


def test_should_exclude_ds_store():
    assert core.should_exclude(Path(".DS_Store"))
    assert core.should_exclude(Path("some/dir/.DS_Store"))


def test_should_exclude_temp_files():
    assert core.should_exclude(Path("file.tmp"))
    assert core.should_exclude(Path("file.temp"))
    assert core.should_exclude(Path("file.log"))


def test_should_not_exclude_normal_files():
    assert not core.should_exclude(Path(".zshrc"))
    assert not core.should_exclude(Path(".config/nvim/init.lua"))
    assert not core.should_exclude(Path(".local/bin/tools"))


def test_resolve_broken_symlink_absolute(tmp_path):
    symlink = tmp_path / "link"
    target = Path("/nonexistent/file")
    symlink.symlink_to(target)

    resolved = core.resolve_broken_symlink(symlink)
    assert resolved == target


def test_resolve_broken_symlink_relative(tmp_path):
    symlink = tmp_path / "link"
    symlink.symlink_to("../nonexistent/file")

    resolved = core.resolve_broken_symlink(symlink)
    assert resolved is not None
    assert "nonexistent/file" in str(resolved)


def test_resolve_broken_symlink_not_a_symlink(tmp_path):
    regular_file = tmp_path / "file.txt"
    regular_file.write_text("test")

    assert core.resolve_broken_symlink(regular_file) is None


def test_make_relative_symlink_simple():
    source = Path("/Users/chris/dotfiles/common/.config/nvim/init.lua")
    target = Path("/Users/chris/.config/nvim/init.lua")
    assert str(core.make_relative_symlink(source, target)) == "../../dotfiles/common/.config/nvim/init.lua"


def test_make_relative_symlink_zshrc():
    source = Path("/Users/chris/dotfiles/common/.config/zsh/.zshrc")
    target = Path("/Users/chris/.config/zsh/.zshrc")
    assert str(core.make_relative_symlink(source, target)) == "../../dotfiles/common/.config/zsh/.zshrc"


def test_make_relative_symlink_top_level():
    source = Path("/Users/chris/dotfiles/macos/.gitconfig")
    target = Path("/Users/chris/.gitconfig")
    assert str(core.make_relative_symlink(source, target)) == "dotfiles/macos/.gitconfig"


def test_make_relative_symlink_actually_works(tmp_path):
    """Integration check: verify the calculated relative path produces a working symlink."""
    source_dir = tmp_path / "dotfiles" / "common" / ".config" / "nvim"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "init.lua"
    source_file.write_text("-- test config")

    target_dir = tmp_path / "home" / ".config" / "nvim"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "init.lua"

    target_file.symlink_to(core.make_relative_symlink(source_file, target_file))

    assert target_file.exists()
    assert target_file.is_symlink()
    assert target_file.read_text() == "-- test config"


# ─── Symlink Management Tests ─────────────────────────────────────────────────


def test_create_symlinks(tmp_path):
    dotfiles = tmp_path / "dotfiles"
    source = dotfiles / "common"
    source.mkdir(parents=True)
    (source / "test.txt").write_text("test content")

    target = tmp_path / "home"
    target.mkdir()

    count = core.create_symlinks(source, "common", target_dir=target)

    assert count == 1
    assert (target / "test.txt").is_symlink()
    assert (target / "test.txt").read_text() == "test content"


def test_create_nested_symlinks(tmp_path):
    dotfiles = tmp_path / "dotfiles"
    source = dotfiles / "common"
    nested = source / ".config" / "nvim"
    nested.mkdir(parents=True)
    (nested / "init.lua").write_text("-- config")

    target = tmp_path / "home"
    target.mkdir()

    count = core.create_symlinks(source, "common", target_dir=target)

    assert count == 1
    assert (target / ".config" / "nvim" / "init.lua").is_symlink()


def test_remove_symlinks(tmp_path):
    dotfiles = tmp_path / "dotfiles"
    source = dotfiles / "macos"
    source.mkdir(parents=True)
    (source / "test.txt").write_text("test")

    target = tmp_path / "home"
    target.mkdir()

    core.create_symlinks(source, "macos", target_dir=target)
    count = core.remove_symlinks(source, "macos", target_dir=target)

    assert count == 1
    assert not (target / "test.txt").exists()


def test_find_broken_symlinks(tmp_path):
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()

    target = tmp_path / "home"
    target.mkdir()

    broken_link = target / "broken"
    broken_link.symlink_to(dotfiles / "nonexistent")

    broken = core.find_broken_symlinks(target_dir=target, dotfiles_dir=dotfiles)

    assert len(broken) == 1
    assert broken[0] == broken_link


def test_check_and_clean(tmp_path):
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()

    target = tmp_path / "home"
    target.mkdir()

    broken_link = target / "broken"
    broken_link.symlink_to(dotfiles / "nonexistent")

    count = core.check_and_clean(target_dir=target, dotfiles_dir=dotfiles)

    assert count == 1
    assert not broken_link.exists()
