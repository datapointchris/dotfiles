"""Reading the include chain git assembles a machine's configuration from.

`--file` is the seam, the same way `GIT_CONFIG_GLOBAL` is in `test_identity.py`:
a real knob git honours, so the parsing under test runs against configuration git
itself resolved rather than against a fixture describing what it would have said.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles import gitconfig


@pytest.fixture
def layered(tmp_path: Path) -> Path:
    """An entry point including two files, one of which overrides it."""
    (tmp_path / 'entry.cfg').write_text('[core]\n\tpager = delta\n[include]\n\tpath = middle.cfg\n')
    (tmp_path / 'middle.cfg').write_text('[core]\n\teditor = nvim\n[include]\n\tpath = leaf.cfg\n')
    (tmp_path / 'leaf.cfg').write_text('[core]\n\tpager = less\n')
    return tmp_path / 'entry.cfg'


def read(config: Path) -> gitconfig.Layering:
    return gitconfig.read(scope=f'--file={config}')


def test_the_chain_is_read_out_of_the_configuration_itself(layered: Path) -> None:
    """Never assembled here. A second description of the layering, kept by hand,
    is one that disagrees with the deployment the first time an overlay moves."""
    edges = {(include.source.name, include.target.name) for include in read(layered).includes}

    assert edges == {('entry.cfg', 'middle.cfg'), ('middle.cfg', 'leaf.cfg')}


def test_a_key_two_files_disagree_about_names_the_one_that_wins(layered: Path) -> None:
    """The finding is the pair. Either file alone is a legitimate setting, and
    what a reader cannot see is that the second one is silently deciding."""
    (conflict,) = read(layered).conflicts

    assert conflict.key == 'core.pager'
    assert conflict.winner.origin.name == 'leaf.cfg'
    assert conflict.winner.value == 'less'
    assert [setting.origin.name for setting in conflict.losers] == ['entry.cfg']


def test_a_key_repeated_inside_one_file_is_not_a_conflict(tmp_path: Path) -> None:
    """git's own idiom for replacing an inherited credential helper is to set the
    key empty and set it again, and `common.gitconfig` does exactly that. A
    detector that called it drift would be wrong on a healthy machine on every
    run, which is how a detector comes to be ignored."""
    config = tmp_path / 'one.cfg'
    config.write_text('[credential "https://github.com"]\n\thelper =\n\thelper = !gh auth git-credential\n')

    assert read(config).conflicts == ()


def test_agreeing_files_are_not_a_conflict(tmp_path: Path) -> None:
    """Two files setting one key to the same value is not an ambiguity — the
    reader gets the value they would have predicted from either."""
    (tmp_path / 'entry.cfg').write_text('[core]\n\tpager = delta\n[include]\n\tpath = same.cfg\n')
    (tmp_path / 'same.cfg').write_text('[core]\n\tpager = delta\n')

    assert read(tmp_path / 'entry.cfg').conflicts == ()


def test_the_includes_holding_the_chain_together_are_not_themselves_a_conflict(layered: Path) -> None:
    """Every include in a chain is spelled `include.path`, so treating them as one
    key made the whole layering read as one enormous conflict with itself. That
    was this detector's first output on a machine with nothing wrong with it."""
    assert 'include.path' not in {conflict.key for conflict in read(layered).conflicts}


def test_an_absent_include_target_costs_nothing(tmp_path: Path) -> None:
    """An overlay exists only where a coordinate needs one, so git ignoring an
    include whose target is not there is what makes the scheme optional per
    axis."""
    config = tmp_path / 'entry.cfg'
    config.write_text('[core]\n\tpager = delta\n[include]\n\tpath = never-deployed.cfg\n')

    layering = read(config)

    assert [include.target.name for include in layering.includes] == ['never-deployed.cfg']
    assert [path.name for path in layering.files] == ['entry.cfg']


def test_a_conditional_include_that_did_not_fire_is_marked_as_such(tmp_path: Path) -> None:
    """It appears in the listing whether or not its condition held, so a chain
    drawn from the keys alone shows an identity that is not being used — which on
    the nonfleet machine is the personal address, from inside every directory."""
    (tmp_path / 'entry.cfg').write_text(f'[includeIf "gitdir:{tmp_path}/nowhere/"]\n\tpath = conditional.cfg\n')
    (tmp_path / 'conditional.cfg').write_text('[user]\n\temail = someone@example.com\n')

    (include,) = read(tmp_path / 'entry.cfg').includes

    assert include.condition == f'gitdir:{tmp_path}/nowhere/'
    assert not include.taken


def test_a_value_containing_a_newline_survives_the_parse(tmp_path: Path) -> None:
    """Why the listing is read NUL-delimited rather than by line. The aliases this
    repo ships contain spaces, and nothing stops a value containing worse."""
    config = tmp_path / 'entry.cfg'
    config.write_text('[alias]\n\tmulti = "!f() {\\n  echo hi\\n}; f"\n')

    (setting,) = [one for one in read(config).settings if one.key == 'alias.multi']

    assert '\n' in setting.value
    assert 'echo hi' in setting.value


def test_a_git_that_will_not_answer_reports_nothing_rather_than_raising(tmp_path: Path) -> None:
    """Nothing here is worth failing a whole check for: the caller is reporting on
    configuration, and "git could not be run" is a finding its own resource makes."""
    layering = gitconfig.read(scope=f'--file={tmp_path / "absent.cfg"}')

    assert not layering.read
    assert layering.conflicts == ()
    assert layering.files == ()


def test_a_file_setting_one_key_twice_counts_once(tmp_path: Path) -> None:
    """The two counts only diverge when both shapes are present at once, which is
    why neither of the tests above caught it: git resolves a key set twice inside
    one file to that file's last word, so a file has one answer however many times
    it says it.

    Three settings across two files read as `set in 3 files`, and the advice named
    the entry point twice — once per occurrence rather than once per file.
    """
    (tmp_path / 'entry.cfg').write_text('[core]\n\tpager = delta\n\tpager = bat\n[include]\n\tpath = leaf.cfg\n')
    (tmp_path / 'leaf.cfg').write_text('[core]\n\tpager = less\n')

    (conflict,) = read(tmp_path / 'entry.cfg').conflicts

    assert conflict.files == 2
    assert [setting.origin.name for setting in conflict.losers] == ['entry.cfg']
    assert conflict.winner.origin.name == 'leaf.cfg'


def test_a_file_repeating_a_key_speaks_with_its_last_word(tmp_path: Path) -> None:
    """Which value a file contributes is its last, so the row must not report an
    overridden one as what that file says."""
    (tmp_path / 'entry.cfg').write_text('[core]\n\tpager = delta\n\tpager = bat\n[include]\n\tpath = leaf.cfg\n')
    (tmp_path / 'leaf.cfg').write_text('[core]\n\tpager = less\n')

    (conflict,) = read(tmp_path / 'entry.cfg').conflicts

    assert [setting.value for setting in conflict.losers] == ['bat']
