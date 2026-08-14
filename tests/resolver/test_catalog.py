"""Every per-entry rule `packages.yml` is held to, against the loader that holds it.

These were subprocess tests driving `packages verify` against a synthetic tree,
because the rules lived in a table that only that command consulted. They are a
function call now: `catalog.load` is the one reader, so the rules can be asserted
where they are, in milliseconds and without a tree.

The real `install/packages.yml` is read by exactly one test — the one asserting
it parses at all — because that is the only question a fixture cannot answer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import catalog

REPO_ROOT = Path(__file__).resolve().parents[2]


def write(tmp_path: Path, declared: dict[str, Any]) -> Path:
    source = tmp_path / 'packages.yml'
    source.write_text(yaml.safe_dump(declared, sort_keys=False))
    return source


def issues(tmp_path: Path, declared: dict[str, Any]) -> list[str]:
    """Every problem the declaration has, as rendered strings.

    The list rather than the first: a caller fixing packages.yml wants all of
    them, and asserting on the collection is what proves one bad row does not
    hide the next.
    """
    with pytest.raises(catalog.CatalogError) as refused:
        catalog.load(write(tmp_path, declared))
    return [str(issue) for issue in refused.value.issues]


def assert_named(found: list[str], fragment: str) -> None:
    assert any(fragment in issue for issue in found), f'expected {fragment!r} among:\n' + '\n'.join(found)


# ─────────────────────────────────────────────────────────────────────────────
# The real declaration
# ─────────────────────────────────────────────────────────────────────────────


def test_the_repo_declaration_parses() -> None:
    """The one test that reads the real files. Everything else is a fixture.

    This is what makes a new key an error at the moment it is added rather than
    on the machine that eventually installs it.
    """
    loaded = catalog.load(REPO_ROOT / 'install' / 'packages.yml')

    assert loaded.section('github_releases'), 'the declaration parsed but came back empty'
    assert loaded.section('managed_files'), 'system.yml parsed but came back empty'
    assert set(loaded.entries) == set(catalog.ALL_SECTIONS)


@pytest.mark.parametrize('file', ['packages.yml', 'system.yml'])
def test_a_declaration_that_will_not_parse_refuses_rather_than_escaping(file: str, tmp_path: Path) -> None:
    """A file that is not YAML is a `CatalogError`, the same as one that is YAML
    and declares something no reader can consume.

    Untried, `yaml.safe_load` raised a `YAMLError` no handler here catches —
    `validate.declaration` catches `CatalogError` alone — so it reached the
    boundary as a traceback and exit 1. That is `DRIFT`, which says the machine
    differs from a declaration that in fact could not be read at all.

    Both files, because they are loaded on separate lines and only one of them
    was ever exercised by a test.
    """
    (tmp_path / 'packages.yml').write_text('github_releases: []\n')
    (tmp_path / 'system.yml').write_text('managed_files: []\n')
    (tmp_path / file).write_text('github_releases: [unclosed\n')

    with pytest.raises(catalog.CatalogError) as refused:
        catalog.load(tmp_path / 'packages.yml')

    assert file in str(refused.value)
    assert 'will not parse as YAML' in str(refused.value)


@pytest.mark.parametrize(('file', 'known'), [('packages.yml', catalog.SECTIONS), ('system.yml', catalog.SYSTEM_SECTIONS)])
def test_every_section_in_a_declaration_file_has_a_class(file: str, known: dict[str, type[catalog.Entry]]) -> None:
    """A section with no dataclass is not validated leniently but not at all.

    `runtimes` was in exactly that state while declaring both a `version` and a
    `min_version` — which is what the constraint rule exists to police — and no
    per-rule test could see it, because each one names its own section.
    """
    declared = catalog.raw_sections(REPO_ROOT / 'install' / file)
    unmodelled = set(declared) - set(known) - catalog.BARE_SECTIONS

    assert not unmodelled, (
        f'sections in {file} with no dataclass in catalog.py: {sorted(unmodelled)}. '
        'Add one, or add to catalog.BARE_SECTIONS with the reason.'
    )


def test_a_section_is_read_out_of_exactly_one_file() -> None:
    """The two maps partition the sections rather than overlapping.

    A section in both would be read from whichever file `_file_for` picked and
    silently ignored in the other, which is a declaration that can be edited with
    no effect.
    """
    assert not set(catalog.SECTIONS) & set(catalog.SYSTEM_SECTIONS)
    assert all(cls.declared_in == 'system.yml' for cls in catalog.SYSTEM_SECTIONS.values())
    assert all(cls.declared_in == 'packages.yml' for cls in catalog.SECTIONS.values())


# ─────────────────────────────────────────────────────────────────────────────
# Required fields, unknown keys, duplicates
# ─────────────────────────────────────────────────────────────────────────────


def test_a_missing_required_field_is_refused(tmp_path: Path) -> None:
    found = issues(tmp_path, {'github_releases': [{'name': 'fzf'}]})
    assert_named(found, 'fzf is missing required field(s) repo')


def test_a_row_with_no_name_is_named_by_position(tmp_path: Path) -> None:
    """An entry missing its name still has to be findable in the file."""
    found = issues(tmp_path, {'npm_globals': {'language_servers': [{'description': 'nameless'}]}})
    assert_named(found, 'language_servers entry #0 is missing required field(s) name')


def test_every_broken_row_is_reported_not_just_the_first(tmp_path: Path) -> None:
    found = issues(
        tmp_path,
        {'github_releases': [{'name': 'fzf'}, {'name': 'zk'}, {'name': 'duf'}]},
    )
    assert len(found) == 3, found


@pytest.mark.parametrize(
    ('field', 'value'),
    [('binary_pattern', 'fzf-{version}-{os}.tar.gz'), ('install_dir', '~/.local/bin'), ('install_script', 'install-fzf.sh')],
)
def test_a_key_no_reader_consumes_is_refused(tmp_path: Path, field: str, value: str) -> None:
    """Each of these was carried on nearly every entry while nothing read it, and
    each drifted — into naming assets and scripts that no longer existed."""
    found = issues(tmp_path, {'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf', field: value}]})
    assert_named(found, f'fzf declares {field}')


def test_a_key_is_only_unknown_where_its_section_does_not_read_it(tmp_path: Path) -> None:
    """binary_pattern is live on cargo_packages, where it does build a release URL."""
    loaded = catalog.load(
        write(tmp_path, {'cargo_packages': [{'name': 'fd', 'github_repo': 'sharkdp/fd', 'binary_pattern': 'fd-{version}.tar.gz'}]})
    )

    assert loaded.find('cargo_packages', 'fd')


def test_a_duplicate_name_is_refused(tmp_path: Path) -> None:
    found = issues(
        tmp_path,
        {'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf'}, {'name': 'fzf', 'repo': 'other/fzf'}]},
    )
    assert_named(found, 'fzf is declared more than once')


def test_a_section_no_reader_knows_is_refused(tmp_path: Path) -> None:
    """A section added to the file and nowhere else installs nothing and says nothing."""
    found = issues(tmp_path, {'snap_packages': [{'name': 'spotify'}]})
    assert_named(found, 'snap_packages: is not a section any reader knows')


def test_a_system_package_naming_no_manager_is_refused(tmp_path: Path) -> None:
    found = issues(tmp_path, {'system_packages': [{'name': 'git'}]})
    assert_named(found, 'names no package under any of apt, pacman, brew, aur')


def test_a_package_excluding_a_host_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    """A misspelled exclusion silently excludes nothing, which is the failure mode
    a negative narrowing has and a positive one does not: `host: wsl2` plans for
    no machine and is noticed, `excludes_host: wsl2` plans for every machine and
    is not."""
    found = issues(tmp_path, {'system_packages': [{'name': 'docker', 'apt': 'docker-ce', 'excludes_host': 'wsl2'}]})
    assert_named(found, "excludes host 'wsl2', which is not a host")


# ─────────────────────────────────────────────────────────────────────────────
# Declared types
# ─────────────────────────────────────────────────────────────────────────────


def test_an_unquoted_version_is_refused_rather_than_stringified(tmp_path: Path) -> None:
    """YAML reads 0.10 as a float, and `str()` on it is "0.1" — a different version.

    Coercing here would silently install the wrong release; the fix belongs in
    the file, so the message says to quote it.
    """
    found = issues(tmp_path, {'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf', 'version': 0.10}]})
    assert_named(found, "declares 'version' as the float 0.1; quote it")


def test_a_flag_declared_as_a_string_is_refused(tmp_path: Path) -> None:
    found = issues(tmp_path, {'github_releases': [{'name': 'win32yank', 'repo': 'x/y', 'requires_wsl_host': 'yes'}]})
    assert_named(found, "declares 'requires_wsl_host' as 'yes'")


def test_a_bare_tag_string_is_refused_where_a_list_is_read(tmp_path: Path) -> None:
    found = issues(tmp_path, {'macos_casks': [{'name': 'ghostty', 'tags': 'gui'}]})
    assert_named(found, "declares 'tags' as 'gui'")


def test_a_mas_app_id_stays_an_integer(tmp_path: Path) -> None:
    loaded = catalog.load(write(tmp_path, {'mas_apps': [{'name': 'Xcode', 'id': 497799835}]}))

    assert loaded.find('mas_apps', 'Xcode').id == 497799835


# ─────────────────────────────────────────────────────────────────────────────
# Version constraints
# ─────────────────────────────────────────────────────────────────────────────


def test_a_pin_is_accepted_where_its_installer_honours_it(tmp_path: Path) -> None:
    loaded = catalog.load(write(tmp_path, {'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf', 'version': '0.50.0'}]}))

    assert loaded.find('github_releases', 'fzf').version == '0.50.0'


def test_a_constraint_nothing_honours_is_refused(tmp_path: Path) -> None:
    """The failure this rule exists for: four version fields sat in packages.yml
    unread, one of them eight versions stale, because nothing objected."""
    found = issues(tmp_path, {'cargo_packages': [{'name': 'fd', 'version': '10.0.0'}]})
    assert_named(found, 'nothing honours for cargo_packages')


def test_a_pin_beside_a_bound_is_refused(tmp_path: Path) -> None:
    found = issues(
        tmp_path,
        {'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf', 'version': '0.50.0', 'min_version': '0.40'}]},
    )
    assert_named(found, 'describing a window nobody can predict')


@pytest.mark.parametrize('pinned', ['v0.50.0', 'cli/v0.9.0'])
def test_a_constraint_written_as_a_tag_is_refused(tmp_path: Path, pinned: str) -> None:
    """One tool spells a release v0.56.0 and another cli/v0.9.0, so a declared tag
    is only ever correct for its own tool and cannot be compared at all."""
    found = issues(tmp_path, {'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf', 'version': pinned}]})
    assert_named(found, 'which is a tag')


def test_a_grandfathered_floor_is_left_alone(tmp_path: Path) -> None:
    """Satisfied floors that predate enforcement, kept so the resolver inherits
    them rather than deleted to silence a check."""
    loaded = catalog.load(write(tmp_path, {'github_releases': [{'name': 'neovim', 'repo': 'neovim/neovim', 'min_version': '0.11'}]}))

    assert loaded.find('github_releases', 'neovim').min_version == '0.11'


# ─────────────────────────────────────────────────────────────────────────────
# Shapes: the three ways a section is spelled
# ─────────────────────────────────────────────────────────────────────────────


def test_a_grouped_section_flattens_its_categories(tmp_path: Path) -> None:
    """The category keys organise the file and are read by nothing."""
    loaded = catalog.load(
        write(
            tmp_path,
            {'npm_globals': {'language_servers': [{'name': 'bash-language-server'}], 'linters': [{'name': 'eslint'}]}},
        )
    )

    assert [entry.name for entry in loaded.section('npm_globals')] == ['bash-language-server', 'eslint']


def test_a_keyed_section_takes_its_name_from_the_key(tmp_path: Path) -> None:
    loaded = catalog.load(write(tmp_path, {'tmux_plugins': {'tpm': {'repo': 'tmux-plugins/tpm', 'install_dir': '~/.tmux/plugins/tpm'}}}))

    assert loaded.find('tmux_plugins', 'tpm').name == 'tpm'


def test_a_section_written_as_the_wrong_shape_is_refused(tmp_path: Path) -> None:
    found = issues(tmp_path, {'github_releases': {'fzf': {'repo': 'junegunn/fzf'}}})
    assert_named(found, 'is a dict where every reader expects a list of entries')


def test_an_absent_section_is_empty_not_missing(tmp_path: Path) -> None:
    """Every section is addressable whether or not the file declares it, so no
    caller has to guard a lookup."""
    loaded = catalog.load(write(tmp_path, {}))

    assert loaded.section('github_releases') == ()


# ─────────────────────────────────────────────────────────────────────────────
# What an entry answers about itself
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('declared', 'expected'),
    [
        ({'name': 'lazygit', 'repo': 'jesseduffield/lazygit'}, 'lazygit'),
        ({'name': 'ripgrep', 'repo': 'x/y', 'command': 'rg'}, 'rg'),
        ({'name': 'neovim', 'repo': 'x/y', 'binary_link': '~/.local/bin/nvim'}, 'nvim'),
    ],
)
def test_the_executable_an_entry_installs(tmp_path: Path, declared: dict[str, Any], expected: str) -> None:
    """neovim declares the full symlink it creates, so the name comes off its end."""
    loaded = catalog.load(write(tmp_path, {'github_releases': [declared]}))

    assert loaded.find('github_releases', declared['name']).executable == expected


@pytest.mark.parametrize(
    ('section', 'declared', 'expected'),
    [
        ('github_releases', {'name': 'icb', 'repo': 'datapointchris/icb'}, 'datapointchris'),
        ('git_uv_tools', {'name': 'syncer', 'repo': 'https://github.com/datapointchris/syncer.git'}, 'datapointchris'),
        ('go_tools', {'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}, 'go-task'),
        ('npm_globals', {'name': 'eslint'}, None),
    ],
)
def test_ownership_is_derived_from_whichever_field_carries_it(
    tmp_path: Path, section: str, declared: dict[str, Any], expected: str | None
) -> None:
    """`owner/name`, a clone URL and a Go import path all appear, and an entry from
    a registry has no owner at all — which is what makes `--owner` correct without
    a tag anyone has to remember to add."""
    rows = {'npm_globals': {'tools': [declared]}} if section == 'npm_globals' else {section: [declared]}
    loaded = catalog.load(write(tmp_path, rows))

    assert loaded.find(section, declared['name']).owner == expected


def test_finding_an_entry_that_does_not_exist_fails(tmp_path: Path) -> None:
    """A manifest naming a package that does not exist is drift, caught on every
    command rather than in a separate verb."""
    loaded = catalog.load(write(tmp_path, {'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf'}]}))

    with pytest.raises(catalog.CatalogError):
        loaded.find('github_releases', 'ghost')
