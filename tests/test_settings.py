"""Resolving a shared path through three rungs, and reporting which one answered.

The order is the whole contract, so every rung is asserted winning over each one
below it and the empty case is asserted separately. That matters more here than
the count of tests suggests: the rungs are indistinguishable from their result —
every one of them yields a path — so a reordering is invisible to any test that
only checks a path came back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles import settings

DECLARED = 'REPOS_JSON'
PRIVATE = 'DOTFILES_REPOS_JSON'
KEY = 'repos_file'


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A scratch `$XDG_CONFIG_HOME` with neither variable set.

    The suite runs from an interactive shell that exports $REPOS_JSON, so every
    test here would otherwise pass on the machine's own answer rather than the
    one it wrote.
    """
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.delenv(PRIVATE, raising=False)
    monkeypatch.delenv(DECLARED, raising=False)
    return tmp_path / 'config'


def write_config(config_home: Path, body: str) -> Path:
    target = config_home / 'dotfiles' / 'config.toml'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)
    return target


# ─────────────────────────────────────────────────────────────────────────────
# The order, rung by rung
# ─────────────────────────────────────────────────────────────────────────────


def test_nothing_names_it_and_nothing_is_invented(config_home: Path) -> None:
    """No fourth rung. A default naming a path outside this tool's own XDG dirs is
    what standards/data.md forbids, so the honest answer to silence is silence."""
    assert settings.resolve(DECLARED) is None


def test_the_config_key_answers_when_no_variable_does(config_home: Path) -> None:
    config = write_config(config_home, f'{KEY} = "/from/config.json"\n')

    found = settings.resolve(DECLARED)

    assert found.value == '/from/config.json'
    assert found.source == str(config)


def test_the_shared_variable_beats_the_config_key(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(config_home, f'{KEY} = "/from/config.json"\n')
    monkeypatch.setenv(DECLARED, '/from/shared.json')

    found = settings.resolve(DECLARED)

    assert found.value == '/from/shared.json'
    assert found.source == f'${DECLARED}'


def test_the_private_variable_beats_the_shared_one(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DECLARED, '/from/shared.json')
    monkeypatch.setenv(PRIVATE, '/from/private.json')

    found = settings.resolve(DECLARED)

    assert found.value == '/from/private.json'
    assert found.source == f'${PRIVATE}'


def test_the_private_variable_beats_every_rung_below_it(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(config_home, f'{KEY} = "/from/config.json"\n')
    monkeypatch.setenv(DECLARED, '/from/shared.json')
    monkeypatch.setenv(PRIVATE, '/from/private.json')

    assert settings.resolve(DECLARED).value == '/from/private.json'


def test_the_shared_variable_beats_the_config_key_with_all_three_present(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The middle rung is the one an ordering bug lands on, because it wins in one
    direction and loses in the other."""
    write_config(config_home, f'{KEY} = "/from/config.json"\n')
    monkeypatch.setenv(DECLARED, '/from/shared.json')
    monkeypatch.delenv(PRIVATE, raising=False)

    assert settings.resolve(DECLARED).value == '/from/shared.json'


@pytest.mark.parametrize('rung', [PRIVATE, DECLARED])
def test_an_empty_variable_falls_through_rather_than_answering(rung: str, config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Path('') is the current directory, which always exists — so a variable
    exported as nothing would resolve a declared file to something present while
    the machine had answered nothing at all."""
    write_config(config_home, f'{KEY} = "/from/config.json"\n')
    monkeypatch.setenv(rung, '')

    assert settings.resolve(DECLARED).value == '/from/config.json'


def test_an_empty_config_value_is_unset_too(config_home: Path) -> None:
    write_config(config_home, f'{KEY} = ""\n')

    assert settings.resolve(DECLARED) is None


# ─────────────────────────────────────────────────────────────────────────────
# A name with no shared file behind it
# ─────────────────────────────────────────────────────────────────────────────


def test_an_ordinary_declared_value_has_one_rung(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WINDOWS_USER is the case. It is a machine fact rather than a setting of this
    tool, so it takes no prefix and no config key — only its own variable."""
    monkeypatch.setenv('WINDOWS_USER', 'someone')

    found = settings.resolve('WINDOWS_USER')

    assert found.value == 'someone'
    assert found.source == '$WINDOWS_USER'


def test_an_ordinary_declared_value_reads_no_prefixed_twin(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DOTFILES_WINDOWS_USER', 'someone')

    assert settings.resolve('WINDOWS_USER') is None


# ─────────────────────────────────────────────────────────────────────────────
# The config file itself
# ─────────────────────────────────────────────────────────────────────────────


def test_an_absent_config_file_is_not_a_problem(config_home: Path) -> None:
    assert settings.read_config() == settings.Config({})


def test_unparseable_toml_reports_a_problem_rather_than_reading_as_empty(config_home: Path) -> None:
    """A file a human hand-edited into invalid TOML must not be indistinguishable
    from a machine that named nothing — the two get opposite advice."""
    write_config(config_home, 'repos_file = "unterminated\n')

    parsed = settings.read_config()

    assert parsed.values == {}
    assert parsed.problem


# ─────────────────────────────────────────────────────────────────────────────
# Expanding a declaration
# ─────────────────────────────────────────────────────────────────────────────


def test_a_declared_path_expands_through_the_config_file(config_home: Path) -> None:
    """The rung that fixes the scheduled check: a unit inheriting no shell has
    neither variable, and the declaration still resolves."""
    write_config(config_home, f'{KEY} = "/from/config.json"\n')

    assert settings.expand('$REPOS_JSON') == '/from/config.json'


@pytest.mark.parametrize('declaration', ['$REPOS_JSON', '${REPOS_JSON}'])
def test_both_variable_spellings_expand(declaration: str, config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DECLARED, '/from/shared.json')

    assert settings.expand(declaration) == '/from/shared.json'


def test_an_unanswered_variable_is_left_literal(config_home: Path) -> None:
    """Loud rather than plausible: no file is named `$REPOS_JSON`, so the check
    reports the declaration unanswered instead of resolving to a path that exists."""
    assert settings.expand('$REPOS_JSON') == '$REPOS_JSON'
    assert settings.unresolved('$REPOS_JSON') == (DECLARED,)


def test_a_literal_path_still_expands_its_tilde(config_home: Path) -> None:
    assert settings.expand('~/.config/git/local.gitconfig').startswith(str(Path.home()))


def test_a_literal_path_names_no_source(config_home: Path) -> None:
    assert settings.path_source('~/.config/git/local.gitconfig') == ''
    assert settings.unresolved('~/.config/git/local.gitconfig') == ()


def test_the_source_names_the_rung_that_answered(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PRIVATE, '/from/private.json')

    assert settings.path_source('$REPOS_JSON') == f'${PRIVATE}'


# ─────────────────────────────────────────────────────────────────────────────
# What the advice says
# ─────────────────────────────────────────────────────────────────────────────


def test_the_advice_for_a_shared_path_names_all_three_rungs(config_home: Path) -> None:
    """Asserted as three membership checks rather than a sentence: the reader is
    looking at a check that found nothing, so the places it looked are the value
    and the wording around them is not."""
    advice = settings.where_to_name(DECLARED, Path('/home/someone/.env'))

    assert PRIVATE in advice
    assert DECLARED in advice
    assert str(settings.config_file()) in advice


def test_the_advice_for_an_ordinary_value_names_only_the_env_file(config_home: Path) -> None:
    advice = settings.where_to_name('WINDOWS_USER', Path('/home/someone/.env'))

    assert 'WINDOWS_USER' in advice
    assert '/home/someone/.env' in advice
    assert str(settings.config_file()) not in advice
