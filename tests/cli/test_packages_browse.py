"""Browsing the declaration: `packages list`, `show`, `search`, `sections`, `stats`, `tags`.

The module is read-only and deliberately untyped — it walks `packages.yml` *as
written* rather than as validated, so a declaration that will not load is still
listable while it is being fixed. `MALFORMED` below is what measures that claim.

Two doors, both real. `dotfiles packages list|show|search` goes through
`CliRunner` into the typer app, which reaches `declaration.main` in process via
`bridge.declaration` — so a `Refusal` travels to `boundary.Boundary` and becomes
an exit code. `declaration.main(argv)` is the same door with the click group
taken off, and it is the only way to reach `sections`, `stats` and `tags`, which
the `dotfiles` CLI does not expose at all.

**In process rather than in a subprocess.** `tests/apps/test_packages_list.py`
drives `python -m dotfiles.declaration`, which measures the same behaviour and
reports no coverage for any of it — so every branch here read as unexecuted
while three tests were passing over it.

`$DOTFILES_DIR` names the synthetic tree and `paths`' own derivation is re-run
over it, because `paths` reads that variable once at import. Same two-step, and
the same reasoning, as `tests/matrix/harness.rebind`.

**Three values exist only inside a rendered sentence**, so they are parsed back
**Every read verb here speaks `--json`**, so a count or a field is asked for
rather than recovered from the table it was printed in. `answered` is that one
call. The rendered form is asserted only where the rendering *is* the claim — a
truncated column, or the guidance an empty tally prints instead of a table.
"""

from __future__ import annotations

import dataclasses as dc
import json
import platform
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from dotfiles import catalog
from dotfiles import declaration
from dotfiles import paths
from dotfiles.declaration import Color
from dotfiles.declaration import InstallStatus
from dotfiles.declaration import Platform
from dotfiles.main import app
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode

LONG_DESCRIPTION = 'a terminal ui for docker containers, images, volumes and networks'
"""Longer than the 35 columns `list --verbose` truncates to, which is the only
way to tell a truncating renderer from one that happens to fit."""

DECLARED: dict[str, Any] = {
    'github_releases': [
        {'name': 'lazygit', 'repo': 'jesseduffield/lazygit', 'description': 'a terminal ui for git', 'tags': ['git', 'tui']},
        {'name': 'lazydocker', 'repo': 'jesseduffield/lazydocker', 'description': LONG_DESCRIPTION, 'tags': ['tui']},
    ],
    'npm_globals': {'language_servers': [{'name': 'pyright', 'description': 'a python language server', 'tags': ['lsp']}]},
    'tmux_plugins': {'tpm': {'repo': 'https://github.com/tmux-plugins/tpm', 'description': 'the tmux plugin manager'}},
    'macos_casks': [{'name': 'ghostty', 'description': 'a gpu accelerated terminal'}],
    'flatpak_apps': [{'name': 'obsidian', 'description': 'a markdown notebook'}],
}
"""One section of every structure the catalog spells, plus one of each
platform-exclusive kind.

Real section names rather than invented ones, because `iter_section_entries`
branches on `catalog.SECTIONS[section].structure` — a made-up name has no
structure and yields nothing, which passes every assertion for the wrong reason.
"""

COUNTS = {'github_releases': 2, 'npm_globals': 1, 'tmux_plugins': 1, 'macos_casks': 1, 'flatpak_apps': 1}
NAMES = {'lazygit', 'lazydocker', 'pyright', 'tpm', 'ghostty', 'obsidian'}
TAGS = {'tui': 2, 'git': 1, 'lsp': 1}
"""What the fixture declares, written out rather than derived.

Deriving them would re-implement `iter_section_entries` in the test, and a test
that computes its expectation the way the code does cannot disagree with it.
"""


# ─────────────────────────────────────────────────────────────────────────────
# A synthetic checkout, and the two rendered surfaces parsed back into values
# ─────────────────────────────────────────────────────────────────────────────


def point_at(root: Path, packages: dict[str, Any] | None, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkout holding one `packages.yml`, with `paths` re-derived over it.

    `$DOTFILES_DIR` is the knob the whole package resolves the repo through, and
    setting it alone is not enough: `paths` derives `PACKAGES_FILE` from it once,
    at import, so the constant still names `~/dotfiles`. The derivation is re-run
    rather than reimplemented — `paths._repo_root()` is the module's own call —
    so nothing here invents a value and the variable is still what decides.

    `packages` of None writes no file, which is how a test reaches the refusal
    `get_packages_file` raises when a checkout has no declaration.

    `USE_COLOR` is pinned off because it is read at import too, from the
    developer's own `$FORCE_COLOR` — left alone, every parser below reads ANSI
    escapes on one desk and plain text on the next.
    """
    (root / 'install').mkdir(parents=True, exist_ok=True)
    if packages is not None:
        (root / 'install' / 'packages.yml').write_text(yaml.safe_dump(packages, sort_keys=False))

    monkeypatch.setenv('DOTFILES_DIR', str(root))
    derived = paths._repo_root()
    monkeypatch.setattr(paths, 'REPO_ROOT', derived)
    monkeypatch.setattr(paths, 'INSTALL_DIR', derived / 'install')
    monkeypatch.setattr(paths, 'PACKAGES_FILE', derived / 'install' / 'packages.yml')
    monkeypatch.setattr(declaration, 'USE_COLOR', False)
    return derived


@pytest.fixture
def declared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return point_at(tmp_path / 'repo', DECLARED, monkeypatch)


def answered(capsys: pytest.CaptureFixture[str], *argv: str) -> Any:
    """One read verb's `--json` document.

    The counts and the `show` fields are values the command computed, so they are
    asked for rather than recovered from the table it printed — standards/testing.md
    § "Never assert on rendered output".
    """
    declaration.main([*argv, '--json'])
    return json.loads(capsys.readouterr().out)


def executable(directory: Path, name: str) -> Path:
    """A binary `shutil.which` can find. Copied rather than imported, for the
    reason `tests/conftest.py` gives about two files both named `conftest`."""
    target = directory / name
    target.write_text('#!/bin/sh\nexit 0\n')
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def uncoloured(line: str) -> str:
    return line.replace(Color.BRIGHT_CYAN.value, '').replace(Color.RESET.value, '')


# ─────────────────────────────────────────────────────────────────────────────
# The declaration reaches every shape the catalog spells
# ─────────────────────────────────────────────────────────────────────────────


def test_the_fixture_declares_one_section_of_every_structure_the_catalog_spells() -> None:
    """Guards every listing assertion below.

    `iter_section_entries` branches on the declared structure, and a fixture
    missing one leaves that branch unreached while every test still passes — the
    exact failure that made `tmux_plugins` invisible to `list`, `search` and
    `stats` at once.
    """
    covered = {declaration.SECTION_STRUCTURES[section] for section in DECLARED}

    assert covered == set(catalog.Structure)


def test_a_keyed_entry_takes_its_name_from_its_key_and_keeps_the_rest(declared: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A `KEYED` section is a mapping whose key is the row's name; there is no
    `name:` field inside the entry to fall back on."""
    declaration.main(['list', '--json', '--section', 'tmux_plugins'])

    listed = json.loads(capsys.readouterr().out)

    assert listed == [{'name': 'tpm', 'description': 'the tmux plugin manager', 'section': 'tmux_plugins', 'tags': []}]


MALFORMED = (
    ('a list section spelled as a mapping', {'github_releases': {'lazygit': {'repo': 'x'}}}),
    ('a grouped section spelled as a list', {'npm_globals': [{'name': 'pyright'}]}),
    ('a keyed section spelled as a list', {'tmux_plugins': [{'name': 'tpm'}]}),
    ('a grouped category that is not a list', {'npm_globals': {'language_servers': {'name': 'pyright'}}}),
    ('a keyed entry that is not a mapping', {'tmux_plugins': {'tpm': 'https://github.com/tmux-plugins/tpm'}}),
    ('a section declared as null', {'github_releases': None}),
    ('a list entry that is a bare string', {'github_releases': ['lazygit']}),
)
"""Every way a section can be spelled wrong, one per branch `iter_section_entries` guards."""


@pytest.mark.parametrize(('label', 'broken'), MALFORMED, ids=[label for label, _ in MALFORMED])
def test_a_section_spelled_wrong_is_skipped_and_the_rest_of_the_file_still_lists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    label: str,
    broken: dict[str, Any],
) -> None:
    """The module's whole reason for reading raw YAML: a file being fixed is
    exactly when someone wants to look at it.

    The sound section listing is the positive half — without it, "nothing was
    listed" is equally satisfied by a walk that read no file at all.
    """
    point_at(tmp_path / 'repo', {**broken, 'go_tools': [{'name': 'task', 'description': 'a task runner'}]}, monkeypatch)

    declaration.main(['list', '--json'])

    assert [entry['name'] for entry in json.loads(capsys.readouterr().out)] == ['task']


def test_a_bare_string_entry_is_skipped_by_every_reader_that_needs_a_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`list` filters non-mappings itself; `search`, `show` and `tags` reach them
    through `get_all_packages`, which has to filter again. Without that second
    filter a half-written entry — the name typed and the fields not yet —
    crashes `pkg.get` for every one of them."""
    entries = ['lazygit', {'name': 'lazydocker', 'description': LONG_DESCRIPTION, 'tags': ['tui']}]
    point_at(tmp_path / 'repo', {'github_releases': entries}, monkeypatch)

    tags = answered(capsys, 'tags')
    declaration.main(['search', 'lazy'])
    found = capsys.readouterr().out

    assert tags == {'tui': 1}
    assert 'lazydocker' in found
    assert 'lazygit' not in found


# ─────────────────────────────────────────────────────────────────────────────
# `list`, and the filters that narrow it
# ─────────────────────────────────────────────────────────────────────────────


FILTERS: tuple[tuple[tuple[str, ...], set[str]], ...] = (
    (('list', '--json'), NAMES),
    (('list', '--json', '--section', 'github_releases'), {'lazygit', 'lazydocker'}),
    (('list', '--json', '--section', 'github_releases', '--section', 'tmux_plugins'), {'lazygit', 'lazydocker', 'tpm'}),
    (('list', '--json', '--tag', 'tui'), {'lazygit', 'lazydocker'}),
    (('list', '--json', '--tag', 'lsp'), {'pyright'}),
    (('list', '--json', '--platform', 'macos'), NAMES - {'obsidian'}),
    (('list', '--json', '--platform', 'linux'), NAMES - {'ghostty'}),
    (('list', '--json', '--platform', 'all'), NAMES),
    (('list', '--json', '--tag', 'nothing-carries-this'), set()),
)


@pytest.mark.parametrize(('argv', 'expected'), FILTERS, ids=[' '.join(argv[1:]) for argv, _ in FILTERS])
def test_a_list_filter_narrows_the_payload_to_exactly_what_it_names(
    declared: Path,
    capsys: pytest.CaptureFixture[str],
    argv: tuple[str, ...],
    expected: set[str],
) -> None:
    """`--platform` selects *sections*, not this machine — a linux listing drops
    the casks wherever it is run, which is what makes the row deterministic.

    The empty row is load-bearing: `--json` is answered before the
    nothing-matched branch, so a filter matching nothing has to emit `[]` rather
    than a sentence a caller cannot parse.
    """
    declaration.main(list(argv))

    assert {entry['name'] for entry in json.loads(capsys.readouterr().out)} == expected


def test_a_verbose_listing_truncates_the_description_a_plain_one_prints_whole(declared: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verbose puts four columns on one line and a long description would push
    the tags off the end of it.

    The truncation is asserted by asking `truncated_description`, not by looking
    for the whole string's absence: at the wrong column width that absence holds
    for a reason nobody chose, and the assertion passes anyway.
    """
    declaration.main(['list'])
    plain = capsys.readouterr().out
    declaration.main(['list', '--verbose'])
    verbose = capsys.readouterr().out

    assert declaration.truncated_description(LONG_DESCRIPTION) == LONG_DESCRIPTION[: declaration.DESCRIPTION_COLUMN]
    assert len(declaration.truncated_description(LONG_DESCRIPTION)) < len(LONG_DESCRIPTION), 'the fixture has to be long enough to cut'
    assert LONG_DESCRIPTION in plain
    assert declaration.truncated_description(LONG_DESCRIPTION) in verbose
    assert {name for name in NAMES if name in verbose} == NAMES


def test_a_filter_matching_nothing_says_so_and_lists_no_package(declared: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Without `--json` there is no empty document to emit, so the assertion is
    that no declared name reached the screen and the verb still returned."""
    declaration.main(['list', '--tag', 'nothing-carries-this'])
    empty = capsys.readouterr().out

    assert not any(name in empty for name in NAMES)
    assert empty.strip()


# ─────────────────────────────────────────────────────────────────────────────
# `sections`, `stats` and `tags` — the three the `dotfiles` CLI does not expose
# ─────────────────────────────────────────────────────────────────────────────


def test_sections_and_stats_agree_with_each_other_and_with_the_declaration(declared: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Two readers over one file, asserted against the same table.

    They shared a helper that inferred a section's structure from its runtime
    type, so a mapping-of-mappings section returned nothing: `tmux_plugins` was
    absent from the listing and the total was simply wrong. Either reader
    disagreeing with `COUNTS` catches that class again.
    """
    sections = answered(capsys, 'sections')
    stats = answered(capsys, 'stats')

    assert sections == COUNTS
    assert stats == {'sections': COUNTS, 'total': sum(COUNTS.values())}


def test_a_section_declaring_nothing_is_left_out_of_both_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every section the catalog spells is walked; only the ones with rows are
    printed. A zero row per unused section is most of the file."""
    point_at(tmp_path / 'repo', {'go_tools': [{'name': 'task'}]}, monkeypatch)

    assert answered(capsys, 'sections') == {'go_tools': 1}


def test_tags_are_counted_across_every_section_rather_than_within_one(declared: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """`tui` is carried by two entries in one section and `lsp` by one in
    another, so a per-section tally and a whole-file tally differ here."""
    assert answered(capsys, 'tags') == TAGS


def test_a_declaration_with_no_tags_at_all_tallies_nothing_and_still_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The empty branch prints guidance instead of a table. Paired with the
    positive that something was printed, because an empty tally is also what a
    crash before the first row would leave."""
    point_at(tmp_path / 'repo', {'go_tools': [{'name': 'task', 'description': 'a task runner'}]}, monkeypatch)

    assert answered(capsys, 'tags') == {}

    declaration.main(['tags'])
    assert capsys.readouterr().out.strip(), 'the rendered form says what to do instead of printing nothing'


# ─────────────────────────────────────────────────────────────────────────────
# `show`, and the refusals it raises
# ─────────────────────────────────────────────────────────────────────────────


FULLY_DESCRIBED: dict[str, Any] = {
    'system_packages': [
        {
            'name': 'ripgrep',
            'command': 'absent-by-construction',
            'description': 'a fast grep',
            'tags': ['search', 'cli'],
            'apt': 'ripgrep',
            'brew': 'ripgrep',
            'aur': 'ripgrep-bin',
            'repo': 'https://github.com/BurntSushi/ripgrep',
            'github_repo': 'BurntSushi/ripgrep',
        }
    ]
}


def test_show_prints_every_field_the_entry_declares(
    machine: Machine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The platform names and the metadata fields are two separate walks over the
    entry, each printing only the keys that are there — so an entry carrying all
    of them is the only one that reaches both walks in full.

    `machine` narrows `PATH`, so the install status is this test's answer rather
    than whatever the desk running it happens to have installed.
    """
    monkeypatch.setattr(platform, 'system', lambda: 'Darwin')
    point_at(tmp_path / 'repo', FULLY_DESCRIBED, monkeypatch)

    described = answered(capsys, 'show', 'ripgrep')[0]

    assert described['description'] == 'a fast grep'
    assert described['section'] == 'system_packages'
    assert described['tags'] == ['search', 'cli']
    assert described['platforms'] == {'apt': 'ripgrep', 'brew': 'ripgrep', 'aur': 'ripgrep-bin'}
    assert described['metadata'] == {'repo': 'https://github.com/BurntSushi/ripgrep', 'github_repo': 'BurntSushi/ripgrep'}
    assert described['installed'] == InstallStatus.NOT_INSTALLED.value


def test_an_entry_declaring_no_tags_says_none_rather_than_leaving_the_row_empty(declared: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The document carries the empty list and the table carries the word, which is
    the split `--json` exists for: one is the value and one is for a person."""
    assert answered(capsys, 'show', 'tpm')[0]['tags'] == []

    declaration.main(['show', 'tpm'])
    assert 'Tags:        none' in capsys.readouterr().out


TWO_WAYS_TO_INSTALL_ONE_APP: dict[str, Any] = {
    'macos_casks': [{'name': 'obsidian', 'description': 'the cask'}],
    'flatpak_apps': [{'name': 'obsidian', 'description': 'the flatpak'}],
}
"""One name declared twice, in the order `catalog.SECTIONS` walks them.

Two *platform-exclusive* sections rather than one exclusive and one universal,
so the walk order and the wanted order disagree on exactly one of the two
platforms — which is what makes the sort load-bearing instead of a no-op that
agrees with the walk it was handed.
"""


@pytest.mark.parametrize(
    ('system', 'expected'),
    [('Linux', ['flatpak_apps', 'macos_casks']), ('Darwin', ['macos_casks', 'flatpak_apps'])],
    ids=['linux', 'macos'],
)
def test_a_name_declared_twice_is_shown_with_this_platforms_section_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], system: str, expected: list[str]
) -> None:
    """One name in two sections is ordinary — a cask on the mac and a flatpak on
    the linux box — and the one this machine can actually install is the one
    being asked about.

    The two rows are each other's reverse, so whichever way `catalog.SECTIONS`
    happens to order the sections, one of them requires the sort to have run.
    """
    monkeypatch.setattr(platform, 'system', lambda: system)
    point_at(tmp_path / 'repo', TWO_WAYS_TO_INSTALL_ONE_APP, monkeypatch)

    declaration.main(['show', 'obsidian'])
    shown = [line.split(':', 1)[1].strip() for line in capsys.readouterr().out.splitlines() if line.startswith('Section:')]

    assert shown == expected


LISTING_ADVICE = (
    (('show', 'nothing-declares-this'), 'dotfiles packages list'),
    (('show', 'lazygit', '--section', 'tmux_plugins'), 'dotfiles packages list --source tmux_plugins'),
    (('show', 'lazygit', '--section', 'tmux_plugins', '--section', 'macos_casks'), 'dotfiles packages list'),
)
"""No narrowing, one, and two — the three cases `_listing` distinguishes."""


@pytest.mark.parametrize(('argv', 'command'), LISTING_ADVICE, ids=[' '.join(argv) for argv, _ in LISTING_ADVICE])
def test_the_command_a_refusal_advises_is_one_the_front_door_actually_accepts(declared: Path, argv: tuple[str, ...], command: str) -> None:
    """`--section` is this module's own flag and the CLI spells it `--source`, so
    advice built from the internal name named a command that exits 2 — the Paste
    fault. Running the advised command is the only assertion that catches it;
    comparing the string to itself does not.

    Two sections drop the narrowing rather than half-applying it, because
    `--source` takes one value and a repeated flag would keep only the last.
    """
    with pytest.raises(Refusal) as refused:
        declaration.main(list(argv))

    assert refused.value.code is ExitCode.USAGE
    assert refused.value.advice == f'list them with: {command}'

    ran = CliRunner().invoke(app, command.split()[1:], catch_exceptions=False)
    assert ran.exit_code == ExitCode.CONVERGED, ran.stderr


def test_a_near_miss_is_suggested_instead_of_the_listing_command(declared: Path) -> None:
    """A typo has a shortlist and an unknown name does not, so only one of them
    is worth spending the advice line on."""
    with pytest.raises(Refusal) as refused:
        declaration.main(['show', 'lazy'])

    assert refused.value.code is ExitCode.USAGE
    assert refused.value.advice == 'did you mean: lazygit, lazydocker'


def test_an_unknown_section_refuses_and_names_every_section_there_is(declared: Path) -> None:
    """Read off `catalog.SECTIONS` rather than typed here, so a section added to
    the catalog is offered without anyone editing the advice."""
    with pytest.raises(Refusal) as refused:
        declaration.main(['list', '--section', 'not_a_section'])

    assert refused.value.code is ExitCode.USAGE
    assert tuple(refused.value.advice.removeprefix('available: ').split(', ')) == declaration.PACKAGE_SECTIONS


# ─────────────────────────────────────────────────────────────────────────────
# `search`, and the empty-list crash it is one line away from
# ─────────────────────────────────────────────────────────────────────────────


def test_search_matches_a_substring_of_the_name_across_every_section(declared: Path, capsys: pytest.CaptureFixture[str]) -> None:
    declaration.main(['search', 'lazy'])
    found = capsys.readouterr().out

    assert {name for name in NAMES if name in found} == {'lazygit', 'lazydocker'}


def test_search_prints_no_status_row_for_a_package_this_platform_cannot_install(
    declared: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A cask is listed on linux and deliberately carries no verdict — "not
    installed" would be a claim about a machine that could never install it.

    Counted rather than matched on wording: `search` prints a name row, a
    description row, and a status row only when there is one.
    """
    monkeypatch.setattr(platform, 'system', lambda: 'Linux')

    declaration.main(['search', 'ghostty'])
    rows = [line for line in capsys.readouterr().out.splitlines() if line.strip()]

    assert len(rows) == 2
    assert 'ghostty' in rows[0]


def test_search_returns_before_it_would_measure_a_column_over_nothing(declared: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """`calculate_column_widths` takes `max()` over the items, which raises on an
    empty sequence. `cmd_search` survives a query matching nothing only because
    its early return comes first, so the two are pinned together: reorder them
    and every unmatched search becomes a traceback.
    """
    with pytest.raises(ValueError):
        declaration.calculate_column_widths([], ['name', '_section'])

    declaration.main(['search', 'nothing-declares-this'])
    empty = capsys.readouterr().out

    assert not any(name in empty for name in NAMES)
    assert empty.strip()


WIDTHS = (
    ('the widest value plus two', [{'name': 'ab'}, {'name': 'abcd'}], ['name'], None, {'name': 6}),
    ('a field the item does not carry', [{'name': 'ab'}, {}], ['name'], None, {'name': 4}),
    ('a cap the widest value exceeds', [{'name': 'a-very-long-package-name'}], ['name'], {'name': 10}, {'name': 10}),
    ('a cap the widest value stays under', [{'name': 'ab'}], ['name'], {'name': 10}, {'name': 4}),
    ('a value that is not a string', [{'count': 1234}], ['count'], None, {'count': 6}),
    ('two fields measured apart', [{'name': 'ab', 'section': 'go_tools'}], ['name', 'section'], None, {'name': 4, 'section': 10}),
)


@pytest.mark.parametrize(('label', 'items', 'fields', 'caps', 'expected'), WIDTHS, ids=[row[0] for row in WIDTHS])
def test_a_column_is_measured_to_its_widest_value_within_its_cap(
    label: str,
    items: list[dict[str, Any]],
    fields: list[str],
    caps: dict[str, int] | None,
    expected: dict[str, int],
) -> None:
    assert declaration.calculate_column_widths(items, fields, caps) == expected


# ─────────────────────────────────────────────────────────────────────────────
# The front door, and what it turns a refusal into
# ─────────────────────────────────────────────────────────────────────────────


FRONT_DOOR = (
    (('packages', 'list'), ExitCode.CONVERGED),
    (('packages', 'list', '--json'), ExitCode.CONVERGED),
    (('packages', 'list', '--source', 'tmux_plugins'), ExitCode.CONVERGED),
    (('packages', 'show', 'lazygit'), ExitCode.CONVERGED),
    (('packages', 'search', 'lazy'), ExitCode.CONVERGED),
    (('packages', 'show', 'nothing-declares-this'), ExitCode.USAGE),
    (('packages', 'list', '--source', 'not_a_section'), ExitCode.USAGE),
)


@pytest.mark.parametrize(('argv', 'code'), FRONT_DOOR, ids=[' '.join(argv) for argv, _ in FRONT_DOOR])
def test_the_front_door_answers_on_stdout_and_refuses_on_stderr(declared: Path, argv: tuple[str, ...], code: ExitCode) -> None:
    """`bridge.declaration` runs this module in *our* process, so argparse's own
    status never becomes the exit code — a misspelt name would land on 1, which
    is DRIFT, and report the machine as having changes pending.

    The stream split is the machine contract: one refusal on stdout turns a
    `--json` parse into a syntax error.
    """
    ran = CliRunner().invoke(app, list(argv), catch_exceptions=False)

    assert ran.exit_code == code
    if code is ExitCode.CONVERGED:
        assert ran.stdout.strip()
    else:
        assert not ran.stdout.strip(), 'a refusal reached stdout, where a --json document lives'
        assert ran.stderr.strip()


def test_the_front_door_and_the_console_script_list_the_same_declaration(declared: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Two doors onto one function, and the only difference is the click group
    around it. A divergence here means the bridge is translating rather than
    calling."""
    declaration.main(['list', '--json'])
    direct = json.loads(capsys.readouterr().out)

    ran = CliRunner().invoke(app, ['packages', 'list', '--json'], catch_exceptions=False)

    assert json.loads(ran.stdout) == direct


def test_the_console_script_reports_a_refusal_rather_than_raising_it(declared: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`main` raises so the typer boundary can carry the code; `cli` is the other
    door and has no boundary, so it reports through the same `boundary.report`.
    Without it a misspelt name printed a traceback and exited 1."""
    monkeypatch.setattr(sys, 'argv', ['packages', 'show', 'nothing-declares-this'])

    with pytest.raises(SystemExit) as exited:
        declaration.cli()

    assert exited.value.code == ExitCode.USAGE


def test_version_and_the_bare_invocation_answer_without_reading_the_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both return before `load_packages`, which a checkout with no declaration
    at all is the way to prove — the refusal on `list` is what shows the tree
    really is empty rather than the assertion being vacuous."""
    import dotfiles

    point_at(tmp_path / 'repo', None, monkeypatch)

    declaration.main(['--version'])
    printed = capsys.readouterr().out.split()
    declaration.main([])
    usage = capsys.readouterr().out

    assert printed == ['packages', dotfiles.__version__]
    assert usage.strip()
    with pytest.raises(Refusal):
        declaration.main(['list'])


def test_a_declaration_can_be_read_from_a_root_the_caller_names(declared: Path, tmp_path: Path) -> None:
    """`get_packages_file(root=...)` is reachable only by a direct call — no
    subcommand declares a `--root`, so `main` always passes None.

    Read from `elsewhere` while the checkout still holds a different declaration,
    or the argument would pass by agreeing with what `paths` already answers.
    """
    elsewhere = tmp_path / 'elsewhere'
    (elsewhere / 'install').mkdir(parents=True)
    (elsewhere / 'install' / 'packages.yml').write_text('go_tools:\n  - name: task\n')
    missing = tmp_path / 'nowhere'

    assert declaration.load_packages(root=elsewhere) == {'go_tools': [{'name': 'task'}]}
    assert declaration.get_packages_file() == declared / 'install' / 'packages.yml'

    with pytest.raises(Refusal) as refused:
        declaration.get_packages_file(root=missing)
    assert str(missing / 'install' / 'packages.yml') in str(refused.value)


# ─────────────────────────────────────────────────────────────────────────────
# Installed-ness: the four statuses, and the platform gate in front of them
# ─────────────────────────────────────────────────────────────────────────────


@dc.dataclass(frozen=True)
class Machine:
    """The three places `check_installed` looks, under one tmp root."""

    home: Path
    on_path: Path
    uv_tools: Path


@pytest.fixture
def machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_bin: Path, uv_tools: Path) -> Machine:
    """Every knob real: `$HOME` for `~` and the app bundles, `$PATH` for
    `shutil.which`, `$UV_TOOL_DIR` for a tool with no console script.

    `shutil.which` itself is untouched. Narrowing `PATH` is what makes its answer
    this test's rather than this desk's, and it is the same injection point
    `tests/resources/test_packages.py` uses for the same question.
    """
    home = tmp_path / 'home'
    (home / '.local' / 'bin').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(home))
    return Machine(home=home, on_path=fake_bin, uv_tools=uv_tools)


Prepared = tuple[dict[str, Any], str | None]


def a_release_binary_at_the_link_it_declares(machine: Machine) -> Prepared:
    link = machine.home / '.local' / 'bin' / 'lazygit'
    link.touch()
    return {'name': 'lazygit', 'binary_link': '~/.local/bin/lazygit'}, str(link)


def a_release_link_that_is_not_there(machine: Machine) -> Prepared:
    return {'name': 'absent-by-construction', 'binary_link': '~/.local/bin/absent-by-construction'}, None


def a_library_at_the_path_it_declares(machine: Machine) -> Prepared:
    target = machine.home / '.local' / 'shell' / 'logging.sh'
    target.parent.mkdir(parents=True)
    target.write_text('')
    return {'name': 'logging.sh', 'installed_path': '~/.local/shell/logging.sh'}, str(target)


def a_declared_path_that_is_not_there(machine: Machine) -> Prepared:
    executable(machine.on_path, 'sourced-library')
    return {'name': 'sourced-library', 'installed_path': '~/.local/shell/absent.sh'}, None


def a_command_on_path(machine: Machine) -> Prepared:
    return {'name': 'lazygit'}, str(executable(machine.on_path, 'lazygit'))


def a_command_named_differently_from_its_entry(machine: Machine) -> Prepared:
    binary = executable(machine.on_path, 'declared-command')
    return {'name': 'absent-by-construction', 'command': 'declared-command'}, str(binary)


def nothing_anywhere(machine: Machine) -> Prepared:
    return {'name': 'absent-by-construction'}, None


def a_uv_tool_with_no_console_script(machine: Machine) -> Prepared:
    directory = machine.uv_tools / 'numpy'
    directory.mkdir()
    return {'name': 'numpy'}, str(directory)


def an_app_bundle_with_no_binary(machine: Machine) -> Prepared:
    bundle = machine.home / 'Applications' / 'Synthetic-Browser.app'
    bundle.mkdir(parents=True)
    return {'name': 'synthetic-browser'}, str(bundle)


def a_package_this_manager_does_not_carry(machine: Machine) -> Prepared:
    return {'name': 'ripgrep', 'apt': 'ripgrep'}, None


def a_package_homebrew_carries(machine: Machine) -> Prepared:
    return {'name': 'absent-by-construction', 'brew': 'absent-by-construction'}, None


INSTALL_STATES: tuple[tuple[str, str, str, Callable[[Machine], Prepared], InstallStatus], ...] = (
    (
        'a release binary at the link it declares',
        'Linux',
        'github_releases',
        a_release_binary_at_the_link_it_declares,
        InstallStatus.INSTALLED,
    ),
    ('a release link that is not there', 'Linux', 'github_releases', a_release_link_that_is_not_there, InstallStatus.NOT_INSTALLED),
    ('a library at the path it declares', 'Linux', 'shell_plugins', a_library_at_the_path_it_declares, InstallStatus.INSTALLED),
    ('a declared path that is not there', 'Linux', 'shell_plugins', a_declared_path_that_is_not_there, InstallStatus.NOT_INSTALLED),
    ('a command on PATH', 'Linux', 'github_releases', a_command_on_path, InstallStatus.INSTALLED),
    (
        'a command named differently from its entry',
        'Linux',
        'github_releases',
        a_command_named_differently_from_its_entry,
        InstallStatus.INSTALLED,
    ),
    ('nothing anywhere', 'Linux', 'github_releases', nothing_anywhere, InstallStatus.NOT_INSTALLED),
    ('a uv tool with no console script', 'Linux', 'uv_tools', a_uv_tool_with_no_console_script, InstallStatus.INSTALLED),
    ('a git uv tool with no console script', 'Linux', 'git_uv_tools', a_uv_tool_with_no_console_script, InstallStatus.INSTALLED),
    ('a uv tool nothing installed', 'Linux', 'uv_tools', nothing_anywhere, InstallStatus.NOT_INSTALLED),
    ('a cask on a linux box', 'Linux', 'macos_casks', an_app_bundle_with_no_binary, InstallStatus.NOT_AVAILABLE),
    ('a flatpak on a mac', 'Darwin', 'flatpak_apps', nothing_anywhere, InstallStatus.NOT_AVAILABLE),
    ('a cask whose bundle is installed', 'Darwin', 'macos_casks', an_app_bundle_with_no_binary, InstallStatus.APP_ONLY),
    ('a cask with neither binary nor bundle', 'Darwin', 'macos_casks', nothing_anywhere, InstallStatus.NOT_INSTALLED),
    (
        'a package this manager does not carry',
        'Darwin',
        'system_packages',
        a_package_this_manager_does_not_carry,
        InstallStatus.NOT_AVAILABLE,
    ),
    (
        'a package homebrew carries but has not installed',
        'Darwin',
        'system_packages',
        a_package_homebrew_carries,
        InstallStatus.NOT_INSTALLED,
    ),
)


@pytest.mark.parametrize(('label', 'system', 'section', 'prepare', 'expected'), INSTALL_STATES, ids=[row[0] for row in INSTALL_STATES])
def test_a_packages_status_is_read_from_the_evidence_its_section_allows(
    machine: Machine,
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    system: str,
    section: str,
    prepare: Callable[[Machine], Prepared],
    expected: InstallStatus,
) -> None:
    """All four statuses, and the order the evidence is consulted in.

    Two rows carry the reasoning. **A declared path that is not there answers
    NOT_INSTALLED and stops** — it does not fall through to `PATH`, which is why
    the row also puts a binary of that name on `PATH`; a sourced bash library has
    nothing for `which` to find and would otherwise read as installed on the
    strength of an unrelated executable. And **APP_ONLY is unreachable off
    macOS**, because the section gate refuses a cask first — so `platform.system`
    is faked. That is the machine being replaced, not the logic: nothing in
    `dotfiles` is patched by this table, and `is_available_on_platform` and
    `get_current_platform` both run for real over the faked answer.

    A path is asserted only for the two statuses that carry one; the other two
    answer None by contract, and asserting that is what stops a NOT_AVAILABLE
    entry from leaking a path it never checked.
    """
    monkeypatch.setattr(platform, 'system', lambda: system)
    entry, expected_path = prepare(machine)

    status, path = declaration.check_installed({**entry, '_section': section})

    assert status is expected
    assert path == (expected_path if expected in (InstallStatus.INSTALLED, InstallStatus.APP_ONLY) else None)


LINUX_MANAGERS = (('pacman', True), ('aur', True), ('apt', False))


@pytest.mark.parametrize(('key', 'wanted_on_arch'), LINUX_MANAGERS, ids=[key for key, _ in LINUX_MANAGERS])
@pytest.mark.parametrize('on_arch', [True, False], ids=['on-arch', 'not-on-arch'])
def test_a_system_package_is_available_only_where_its_own_manager_is(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, key: str, wanted_on_arch: bool, on_arch: bool
) -> None:
    """Which linux this is comes from `declaration.ARCH_MARKER`, and the test
    names both answers rather than reading the box it runs on. Consulting the
    same file the code consults makes the assertion hold whatever either says,
    which is no assertion at all — and the runner that gates the merge is the
    machine where it could never fail."""
    monkeypatch.setattr(platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(declaration, 'ARCH_MARKER', tmp_path / ('arch-release' if on_arch else 'nothing-here'))
    if on_arch:
        (tmp_path / 'arch-release').touch()

    available = declaration.is_available_on_platform({'_section': 'system_packages', 'name': 'ripgrep', key: 'ripgrep'})

    assert available is (on_arch if wanted_on_arch else not on_arch)


def test_an_unrecognised_system_still_answers_with_the_debian_spelling(monkeypatch: pytest.MonkeyPatch) -> None:
    """`get_current_platform` answers UNKNOWN for anything that is not Darwin or
    Linux, and the availability check has to answer something — apt is the
    fallback, so an unrecognised box lists what it can rather than nothing."""
    monkeypatch.setattr(platform, 'system', lambda: 'FreeBSD')
    packaged = {'_section': 'system_packages', 'name': 'ripgrep'}

    assert declaration.is_available_on_platform({**packaged, 'apt': 'ripgrep'}) is True
    assert declaration.is_available_on_platform({**packaged, 'brew': 'ripgrep'}) is False


PLATFORMS = (('Darwin', Platform.MACOS), ('Windows', Platform.UNKNOWN), ('FreeBSD', Platform.UNKNOWN))


@pytest.mark.parametrize(('system', 'expected'), PLATFORMS, ids=[system for system, _ in PLATFORMS])
def test_an_unrecognised_system_is_unknown_rather_than_assumed_to_be_linux(
    monkeypatch: pytest.MonkeyPatch, system: str, expected: Platform
) -> None:
    monkeypatch.setattr(platform, 'system', lambda: system)

    assert declaration.get_current_platform() is expected


@pytest.mark.parametrize(('present', 'expected'), [(True, Platform.ARCH), (False, Platform.LINUX)], ids=['arch', 'other-linux'])
def test_linux_is_split_into_arch_and_everything_else_by_one_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, present: bool, expected: Platform
) -> None:
    """`ARCH_MARKER` is what decides, and it is what selects pacman over apt one
    function later. Both answers are named here, so neither depends on the desk."""
    monkeypatch.setattr(platform, 'system', lambda: 'Linux')
    marker = tmp_path / 'arch-release'
    if present:
        marker.touch()
    monkeypatch.setattr(declaration, 'ARCH_MARKER', marker)

    assert declaration.get_current_platform() is expected


BUNDLES = (
    ('the name as declared', ('Synthetic-Browser.app',), 'Synthetic-Browser', 'Synthetic-Browser.app'),
    ('a name cased differently', ('Synthetic-Browser.app',), 'synthetic-browser', 'Synthetic-Browser.app'),
    ('a name nothing matches', ('Synthetic-Browser.app',), 'absent-by-construction', None),
    ('no Applications directory at all', (), 'synthetic-browser', None),
)


@pytest.mark.parametrize(('label', 'bundles', 'query', 'expected'), BUNDLES, ids=[row[0] for row in BUNDLES])
def test_an_app_bundle_is_matched_by_name_without_regard_to_case(
    machine: Machine, label: str, bundles: tuple[str, ...], query: str, expected: str | None
) -> None:
    """macOS-only in production, driven here through `$HOME` rather than skipped:
    `~/Applications` is one of the two directories it reads, and a test that
    skipped would leave the whole function unexecuted on every linux runner.

    The last row is the guard the loop needs — an absent directory is `continue`,
    not an exception.
    """
    for name in bundles:
        (machine.home / 'Applications' / name).mkdir(parents=True)

    found = declaration.find_macos_app(query)

    assert found == (machine.home / 'Applications' / expected if expected else None)


# ─────────────────────────────────────────────────────────────────────────────
# Colour: the preference, the override, and the two renderers
# ─────────────────────────────────────────────────────────────────────────────


COLOUR_PREFERENCES = (
    ('the user says no', {'NO_COLOR': '1'}, False),
    ('the user says no over an image that forces it', {'NO_COLOR': '1', 'FORCE_COLOR': '1'}, False),
    ('a caller that knows the detection is wrong', {'FORCE_COLOR': '1'}, True),
    ('a terminal that cannot render it', {'TERM': 'dumb'}, False),
)


@pytest.mark.parametrize(('label', 'environment', 'wanted'), COLOUR_PREFERENCES, ids=[row[0] for row in COLOUR_PREFERENCES])
def test_a_stated_preference_outranks_an_inherited_override(
    monkeypatch: pytest.MonkeyPatch, label: str, environment: dict[str, str], wanted: bool
) -> None:
    """The second row is the whole reason the two are not one chain: a
    `FORCE_COLOR` inherited from a CI image must not overrule a user who asked
    for none. `colors.sh` `color_enabled` is the shell half and agrees."""
    for variable in ('NO_COLOR', 'FORCE_COLOR', 'TERM'):
        monkeypatch.delenv(variable, raising=False)
    for variable, value in environment.items():
        monkeypatch.setenv(variable, value)

    assert declaration.use_color() is wanted


def test_a_status_carries_its_colour_only_where_colour_is_wanted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(declaration, 'USE_COLOR', True)
    lit = declaration.format_status(InstallStatus.INSTALLED, '/somewhere/bin/lazygit')
    monkeypatch.setattr(declaration, 'USE_COLOR', False)
    plain = declaration.format_status(InstallStatus.INSTALLED, '/somewhere/bin/lazygit')

    assert lit == f'{Color.GREEN.value}{plain}{Color.RESET.value}'
    assert Color.RESET.value not in plain


@pytest.mark.parametrize('status', list(InstallStatus), ids=[status.value for status in InstallStatus])
def test_only_an_unavailable_package_formats_to_no_status_row_at_all(monkeypatch: pytest.MonkeyPatch, status: InstallStatus) -> None:
    """`show` prints the Status line only when this returns something, so None is
    how "not for this machine" is said without a row claiming it is missing."""
    monkeypatch.setattr(declaration, 'USE_COLOR', False)

    formatted = declaration.format_status(status, '/somewhere/bin/lazygit')

    assert (formatted is None) is (status is InstallStatus.NOT_AVAILABLE)
    if status in (InstallStatus.INSTALLED, InstallStatus.APP_ONLY):
        assert '/somewhere/bin/lazygit' in str(formatted)
