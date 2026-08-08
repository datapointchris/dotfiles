"""Tests for core symlink management functions and utilities."""

from pathlib import Path

import dotfiles.symlinks.core as core

# ─── Utility Tests ────────────────────────────────────────────────────────────


def test_should_exclude_git_dir():
    assert core.should_exclude(Path('.git/config'))
    assert core.should_exclude(Path('some/path/.git/hooks'))


def test_should_not_exclude_gitconfig():
    """Regression: .gitconfig must NOT be excluded by the .git/ directory pattern."""
    assert not core.should_exclude(Path('.gitconfig'))
    assert not core.should_exclude(Path('some/dir/.gitconfig'))


def test_should_not_exclude_git_related_files():
    assert not core.should_exclude(Path('.gitignore'))
    assert not core.should_exclude(Path('.gitattributes'))
    assert not core.should_exclude(Path('.github/workflows/ci.yml'))
    assert not core.should_exclude(Path('some/.gitkeep'))


def test_should_exclude_git_directory():
    assert core.should_exclude(Path('.git/config'))
    assert core.should_exclude(Path('foo/.git/hooks'))
    assert core.should_exclude(Path('bar/.git/objects/abc123'))


def test_should_not_exclude_similar_named_files():
    assert not core.should_exclude(Path('.DSConfig'))
    assert not core.should_exclude(Path('node_modules.txt'))
    assert not core.should_exclude(Path('my_node_modules.js'))
    assert not core.should_exclude(Path('.pytest.ini'))
    assert not core.should_exclude(Path('pytest.cfg'))
    assert not core.should_exclude(Path('template.txt'))
    assert not core.should_exclude(Path('tmp_file.txt'))
    assert not core.should_exclude(Path('temporary.md'))


def test_tmux_plugin_exclusion():
    assert core.should_exclude(Path('tmux/plugins/tpm'))
    assert core.should_exclude(Path('.tmux/plugins/vim-tmux-navigator'))
    assert not core.should_exclude(Path('tmux/tmux.conf'))
    assert not core.should_exclude(Path('tmux.conf'))
    assert not core.should_exclude(Path('.config/tmux/tmux.conf'))


def test_should_exclude_ds_store():
    assert core.should_exclude(Path('.DS_Store'))
    assert core.should_exclude(Path('some/dir/.DS_Store'))


def test_should_exclude_temp_files():
    assert core.should_exclude(Path('file.tmp'))
    assert core.should_exclude(Path('file.temp'))
    assert core.should_exclude(Path('file.log'))


def test_should_not_exclude_normal_files():
    assert not core.should_exclude(Path('.zshrc'))
    assert not core.should_exclude(Path('.config/nvim/init.lua'))
    assert not core.should_exclude(Path('.local/bin/tools'))


def test_resolve_broken_symlink_absolute(tmp_path):
    symlink = tmp_path / 'link'
    target = Path('/nonexistent/file')
    symlink.symlink_to(target)

    resolved = core.resolve_broken_symlink(symlink)
    assert resolved == target


def test_resolve_broken_symlink_relative(tmp_path):
    symlink = tmp_path / 'link'
    symlink.symlink_to('../nonexistent/file')

    resolved = core.resolve_broken_symlink(symlink)
    assert resolved is not None
    assert 'nonexistent/file' in str(resolved)


def test_resolve_broken_symlink_not_a_symlink(tmp_path):
    regular_file = tmp_path / 'file.txt'
    regular_file.write_text('test')

    assert core.resolve_broken_symlink(regular_file) is None


def test_make_relative_symlink_simple():
    source = Path('/Users/chris/dotfiles/common/.config/nvim/init.lua')
    target = Path('/Users/chris/.config/nvim/init.lua')
    assert str(core.make_relative_symlink(source, target)) == '../../dotfiles/common/.config/nvim/init.lua'


def test_make_relative_symlink_zshrc():
    source = Path('/Users/chris/dotfiles/common/.config/zsh/.zshrc')
    target = Path('/Users/chris/.config/zsh/.zshrc')
    assert str(core.make_relative_symlink(source, target)) == '../../dotfiles/common/.config/zsh/.zshrc'


def test_make_relative_symlink_top_level():
    source = Path('/Users/chris/dotfiles/macos/.gitconfig')
    target = Path('/Users/chris/.gitconfig')
    assert str(core.make_relative_symlink(source, target)) == 'dotfiles/macos/.gitconfig'


def test_make_relative_symlink_actually_works(tmp_path):
    """Integration check: verify the calculated relative path produces a working symlink."""
    source_dir = tmp_path / 'dotfiles' / 'common' / '.config' / 'nvim'
    source_dir.mkdir(parents=True)
    source_file = source_dir / 'init.lua'
    source_file.write_text('-- test config')

    target_dir = tmp_path / 'home' / '.config' / 'nvim'
    target_dir.mkdir(parents=True)
    target_file = target_dir / 'init.lua'

    target_file.symlink_to(core.make_relative_symlink(source_file, target_file))

    assert target_file.exists()
    assert target_file.is_symlink()
    assert target_file.read_text() == '-- test config'


# ─── Symlink Management Tests ─────────────────────────────────────────────────


def test_create_symlinks(tmp_path):
    dotfiles = tmp_path / 'dotfiles'
    source = dotfiles / 'common'
    source.mkdir(parents=True)
    (source / 'test.txt').write_text('test content')

    target = tmp_path / 'home'
    target.mkdir()

    count = core.create_symlinks(source, 'common', target_dir=target).created

    assert count == 1
    assert (target / 'test.txt').is_symlink()
    assert (target / 'test.txt').read_text() == 'test content'


def test_create_nested_symlinks(tmp_path):
    dotfiles = tmp_path / 'dotfiles'
    source = dotfiles / 'common'
    nested = source / '.config' / 'nvim'
    nested.mkdir(parents=True)
    (nested / 'init.lua').write_text('-- config')

    target = tmp_path / 'home'
    target.mkdir()

    count = core.create_symlinks(source, 'common', target_dir=target).created

    assert count == 1
    assert (target / '.config' / 'nvim' / 'init.lua').is_symlink()


def test_remove_symlinks(tmp_path):
    dotfiles = tmp_path / 'dotfiles'
    source = dotfiles / 'macos'
    source.mkdir(parents=True)
    (source / 'test.txt').write_text('test')

    target = tmp_path / 'home'
    target.mkdir()

    core.create_symlinks(source, 'macos', target_dir=target)
    count = core.remove_symlinks(source, 'macos', target_dir=target)

    assert count == 1
    assert not (target / 'test.txt').exists()


def test_find_broken_symlinks(tmp_path):
    dotfiles = tmp_path / 'dotfiles'
    dotfiles.mkdir()

    target = tmp_path / 'home'
    target.mkdir()

    broken_link = target / 'broken'
    broken_link.symlink_to(dotfiles / 'nonexistent')

    broken = core.find_broken_symlinks(target_dir=target, dotfiles_dir=dotfiles)

    assert len(broken) == 1
    assert broken[0] == broken_link


def test_check_and_clean(tmp_path):
    dotfiles = tmp_path / 'dotfiles'
    dotfiles.mkdir()

    target = tmp_path / 'home'
    target.mkdir()

    broken_link = target / 'broken'
    broken_link.symlink_to(dotfiles / 'nonexistent')

    count = core.check_and_clean(target_dir=target, dotfiles_dir=dotfiles)

    assert count == 1
    assert not broken_link.exists()


def test_a_real_file_at_the_target_is_refused_not_replaced(tmp_path):
    """The unlink in create_symlinks removes whatever is at the path. Without
    this guard, `uv tool install` writing an executable into ~/.local/bin and a
    link pass writing into the same directory means the second destroys the
    first, silently."""
    # Deliberately a name pyproject.toml does not declare. A reserved name is
    # skipped before this check is reached, so using one would exercise the
    # reservation and silently stop testing the refusal -- which is what
    # happened when this test used `dotfiles` and that became a console script.
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'installed-tool').write_text('the repo copy')

    target = tmp_path / 'target'
    target.mkdir()
    executable = target / 'installed-tool'
    executable.write_text('an installed console script')

    result = core.create_symlinks(source, 'apps', target_dir=target)

    assert result.created == 0
    assert result.refused == (executable,)
    assert executable.read_text() == 'an installed console script'
    assert not executable.is_symlink()


def test_force_adopts_a_target_the_manager_did_not_create(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / '.zshrc').write_text('managed')

    target = tmp_path / 'target'
    target.mkdir()
    (target / '.zshrc').write_text('whatever was here before')

    result = core.create_symlinks(source, 'common', target_dir=target, force=True)

    assert result.created == 1
    assert result.refused == ()
    assert (target / '.zshrc').is_symlink()


def test_a_link_this_manager_made_is_replaced_without_force(tmp_path):
    """Relinking has to stay idempotent, or every second run refuses everything."""
    source = tmp_path / 'source'
    source.mkdir()
    (source / '.zshrc').write_text('managed')
    target = tmp_path / 'target'
    target.mkdir()

    core.create_symlinks(source, 'common', target_dir=target)
    result = core.create_symlinks(source, 'common', target_dir=target)

    assert result.created == 1
    assert result.refused == ()


def test_a_symlink_pointing_outside_the_repo_is_refused(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / '.zshrc').write_text('managed')

    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    (elsewhere / 'other.zshrc').write_text('someone else manages this')

    target = tmp_path / 'target'
    target.mkdir()
    (target / '.zshrc').symlink_to(elsewhere / 'other.zshrc')

    result = core.create_symlinks(source, 'common', target_dir=target)

    assert result.refused == (target / '.zshrc',)
    assert (target / '.zshrc').resolve() == (elsewhere / 'other.zshrc').resolve()


def test_a_name_project_scripts_declares_is_never_linked(tmp_path):
    """`uv tool dir --bin` is ~/.local/bin, the same directory the apps layer
    links into, so a console script and an apps/ file of the same name compete
    for one path. The declaration wins."""
    source = tmp_path / 'apps'
    source.mkdir()
    (source / 'dotfiles').write_text('the bash front door')
    (source / 'notes').write_text('an ordinary app')

    target = tmp_path / 'bin'
    target.mkdir()

    result = core.create_symlinks(source, 'apps-common', target_dir=target, reserved_names={'dotfiles'})

    assert result.created == 1
    assert (target / 'notes').is_symlink()
    assert not (target / 'dotfiles').exists()


def test_force_does_not_override_a_reserved_name(tmp_path):
    """There is no state of the machine in which replacing the console script
    with an apps/ file is right, so --force must not reach this one."""
    source = tmp_path / 'apps'
    source.mkdir()
    (source / 'dotfiles').write_text('the bash front door')

    target = tmp_path / 'bin'
    target.mkdir()
    (target / 'dotfiles').write_text('the installed console script')

    result = core.create_symlinks(source, 'apps-common', target_dir=target, force=True, reserved_names={'dotfiles'})

    assert result.created == 0
    assert (target / 'dotfiles').read_text() == 'the installed console script'


def test_the_reserved_names_come_from_pyproject(tmp_path):
    """Read from the declaration rather than the installed distribution: during
    a bootstrap nothing is installed, and the answer has to be the same."""
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text('[project.scripts]\ndotfiles = "dotfiles.cli:app"\nsymlinks = "dotfiles.symlinks.cli:app"\n')

    assert core.console_script_names(pyproject) == {'dotfiles', 'symlinks'}


def test_a_missing_pyproject_reserves_nothing(tmp_path):
    assert core.console_script_names(tmp_path / 'absent.toml') == set()


def test_this_repo_declares_its_own_scripts(tmp_path):
    """The default path resolves, so the exclusion is live rather than a
    parameter nothing ever fills."""
    assert 'symlinks' in core.console_script_names()


def test_an_untouched_skeleton_file_is_adopted_without_force(tmp_path, monkeypatch):
    """`useradd` copies /etc/skel into every new home, so a fresh Debian or
    Ubuntu account starts with a .bashrc nobody wrote. Refusing it made the very
    first apply on every such machine report the symlink phase failed, having
    deployed everything else correctly — and the advice printed was `--force`,
    which on any other machine is the dangerous answer."""
    skel = tmp_path / 'skel'
    skel.mkdir()
    (skel / '.bashrc').write_text('# ~/.bashrc: executed by bash(1)\n')
    monkeypatch.setattr(core, 'SKEL_DIR', skel)

    source = tmp_path / 'source'
    source.mkdir()
    (source / '.bashrc').write_text('the repo copy')

    target = tmp_path / 'target'
    target.mkdir()
    (target / '.bashrc').write_text('# ~/.bashrc: executed by bash(1)\n')

    result = core.create_symlinks(source, 'common', target_dir=target)

    assert result.refused == ()
    assert result.created == 1
    assert (target / '.bashrc').is_symlink()


def test_an_edited_skeleton_file_is_still_refused(tmp_path, monkeypatch):
    """One byte different and it is someone's work, which is the whole reason
    the comparison is on content rather than on two filenames."""
    skel = tmp_path / 'skel'
    skel.mkdir()
    (skel / '.bashrc').write_text('# ~/.bashrc: executed by bash(1)\n')
    monkeypatch.setattr(core, 'SKEL_DIR', skel)

    source = tmp_path / 'source'
    source.mkdir()
    (source / '.bashrc').write_text('the repo copy')

    target = tmp_path / 'target'
    target.mkdir()
    edited = target / '.bashrc'
    edited.write_text('# ~/.bashrc: executed by bash(1)\nexport EDITOR=vim\n')

    result = core.create_symlinks(source, 'common', target_dir=target)

    assert result.refused == (edited,)
    assert edited.read_text().endswith('export EDITOR=vim\n')
