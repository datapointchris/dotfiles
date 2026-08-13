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

from dotfiles import paths
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


def resolve(declared: str = DECLARED) -> settings.Resolution | None:
    """One name, through one reading of the config file — what a caller does."""
    return settings.resolve(declared, settings.read_config())


def answered(declared: str = DECLARED) -> settings.Resolution:
    """The same, where the test is about *which* rung answered rather than whether one did."""
    found = resolve(declared)
    assert found is not None, f'{declared} was answered by no rung'
    return found


def resolved(*names: str) -> settings.Resolved:
    """A snapshot answering the given names, defaulting to the shared registry."""
    return settings.resolve_all(names or (DECLARED,), settings.read_config())


def describe() -> tuple[settings.Setting, ...]:
    """Every setting, resolved — the record `config show` renders from."""
    return settings.describe(settings.read_config(), Path('/home/someone/.env'))


# ─────────────────────────────────────────────────────────────────────────────
# The order, rung by rung
# ─────────────────────────────────────────────────────────────────────────────


def test_nothing_names_it_and_nothing_is_invented(config_home: Path) -> None:
    """No fourth rung. A default naming a path outside this tool's own XDG dirs is
    what standards/data.md forbids, so the honest answer to silence is silence."""
    assert resolve() is None


def test_the_config_key_answers_when_no_variable_does(config_home: Path) -> None:
    config = write_config(config_home, f'{KEY} = "/from/config.json"\n')

    found = answered()

    assert found.value == '/from/config.json'
    assert found.source == str(config)


def test_the_shared_variable_beats_the_config_key(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(config_home, f'{KEY} = "/from/config.json"\n')
    monkeypatch.setenv(DECLARED, '/from/shared.json')

    found = answered()

    assert found.value == '/from/shared.json'
    assert found.source == f'${DECLARED}'


def test_the_private_variable_beats_the_shared_one(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DECLARED, '/from/shared.json')
    monkeypatch.setenv(PRIVATE, '/from/private.json')

    found = answered()

    assert found.value == '/from/private.json'
    assert found.source == f'${PRIVATE}'


def test_the_private_variable_beats_every_rung_below_it(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(config_home, f'{KEY} = "/from/config.json"\n')
    monkeypatch.setenv(DECLARED, '/from/shared.json')
    monkeypatch.setenv(PRIVATE, '/from/private.json')

    assert answered().value == '/from/private.json'


def test_the_shared_variable_beats_the_config_key_with_all_three_present(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The middle rung is the one an ordering bug lands on, because it wins in one
    direction and loses in the other."""
    write_config(config_home, f'{KEY} = "/from/config.json"\n')
    monkeypatch.setenv(DECLARED, '/from/shared.json')
    monkeypatch.delenv(PRIVATE, raising=False)

    assert answered().value == '/from/shared.json'


@pytest.mark.parametrize('rung', [PRIVATE, DECLARED])
def test_an_empty_variable_falls_through_rather_than_answering(rung: str, config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Path('') is the current directory, which always exists — so a variable
    exported as nothing would resolve a declared file to something present while
    the machine had answered nothing at all."""
    write_config(config_home, f'{KEY} = "/from/config.json"\n')
    monkeypatch.setenv(rung, '')

    assert answered().value == '/from/config.json'


def test_an_empty_config_value_is_unset_too(config_home: Path) -> None:
    write_config(config_home, f'{KEY} = ""\n')

    assert resolve() is None


# ─────────────────────────────────────────────────────────────────────────────
# A name with no shared file behind it
# ─────────────────────────────────────────────────────────────────────────────


def test_an_ordinary_declared_value_has_one_rung(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WINDOWS_USER is the case. It is a machine fact rather than a setting of this
    tool, so it takes no prefix and no config key — only its own variable."""
    monkeypatch.setenv('WINDOWS_USER', 'someone')

    found = answered('WINDOWS_USER')

    assert found.value == 'someone'
    assert found.source == '$WINDOWS_USER'


def test_an_ordinary_declared_value_reads_no_prefixed_twin(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DOTFILES_WINDOWS_USER', 'someone')

    assert resolve('WINDOWS_USER') is None


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

    assert resolved().expand('$REPOS_JSON') == '/from/config.json'


@pytest.mark.parametrize('declaration', ['$REPOS_JSON', '${REPOS_JSON}'])
def test_both_variable_spellings_expand(declaration: str, config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DECLARED, '/from/shared.json')

    assert resolved().expand(declaration) == '/from/shared.json'


def test_an_unanswered_variable_is_left_literal(config_home: Path) -> None:
    """Loud rather than plausible: no file is named `$REPOS_JSON`, so the check
    reports the declaration unanswered instead of resolving to a path that exists."""
    assert resolved().expand('$REPOS_JSON') == '$REPOS_JSON'
    assert resolved().unresolved('$REPOS_JSON') == (DECLARED,)


def test_an_empty_rung_leaves_the_declaration_literal_rather_than_blank(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Why a declared file needs no emptiness guard before it is stat'd.

    `Path('')` is the current directory and always exists, so an expansion that
    could return '' would report every such entry present. It cannot: a falsy rung
    is skipped rather than substituted, so the `$NAME` survives and no file is
    named that.
    """
    monkeypatch.setenv(DECLARED, '')

    assert resolved().expand('$REPOS_JSON') == '$REPOS_JSON'


def test_a_literal_path_still_expands_its_tilde(config_home: Path) -> None:
    assert resolved().expand('~/.config/git/local.gitconfig').startswith(str(Path.home()))


def test_a_literal_path_names_no_source(config_home: Path) -> None:
    assert resolved().source('~/.config/git/local.gitconfig') == ''
    assert resolved().unresolved('~/.config/git/local.gitconfig') == ()


def test_the_source_names_the_rung_that_answered(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PRIVATE, '/from/private.json')

    assert resolved().source('$REPOS_JSON') == f'${PRIVATE}'


def test_a_snapshot_refuses_a_name_it_was_never_asked_for(config_home: Path) -> None:
    """Absent from the snapshot and unanswered by every rung are opposite findings:
    one is a machine that declared nothing, the other a caller that resolved the
    wrong set of names. Reading the second as the first is a silent wrong answer."""
    with pytest.raises(KeyError):
        resolved().of('WINDOWS_USER')


def test_one_reading_answers_every_name_in_a_snapshot(config_home: Path) -> None:
    """A rung is a file on disk, so a snapshot rebuilt per name can straddle a
    repair — which is what let one report reject config.toml and resolve a path
    through it at once."""
    config = write_config(config_home, f'{KEY} = "/from/config.json"\n')
    snapshot = resolved()

    config.write_text(f'{KEY} = "/repaired.json"\n')

    assert snapshot.of(DECLARED).value == '/from/config.json'


# ─────────────────────────────────────────────────────────────────────────────
# What the advice says
# ─────────────────────────────────────────────────────────────────────────────


def test_the_advice_for_a_shared_path_names_all_three_rungs(config_home: Path) -> None:
    """Asserted as membership checks rather than a sentence: the reader is looking
    at a check that found nothing, so the places it looked are the value and the
    wording around them is not. The rungs come from `SHARED_PATHS` rather than
    being spelled out, so a fourth one added there fails here until it is advised."""
    shared = settings.SHARED_PATHS[DECLARED]
    advice = settings.where_to_name(DECLARED, Path('/home/someone/.env'))

    assert all(rung in advice for rung in (shared.private_env, shared.shared_env, shared.config_key))
    assert str(settings.config_file()) in advice


def test_the_advice_for_an_ordinary_value_names_only_the_env_file(config_home: Path) -> None:
    advice = settings.where_to_name('WINDOWS_USER', Path('/home/someone/.env'))

    assert 'WINDOWS_USER' in advice
    assert '/home/someone/.env' in advice
    assert str(settings.config_file()) not in advice


# ─────────────────────────────────────────────────────────────────────────────
# What `config show` reads
# ─────────────────────────────────────────────────────────────────────────────


def test_every_setting_carries_the_rung_that_answered_it(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The value alone is the plausible-wrong-answer case: a registry read from a
    stale export and one read from the config file look identical."""
    monkeypatch.setenv(DECLARED, '/from/shared.json')

    described = {setting.name: setting for setting in describe()}

    assert described[DECLARED].value == '/from/shared.json'
    assert described[DECLARED].source == f'${DECLARED}'


def test_a_setting_nothing_answers_is_reported_unanswered_rather_than_omitted(config_home: Path) -> None:
    """A row that vanishes when nothing sets it is the one a reader most needs,
    because 'no such setting' and 'nobody has set it' read the same as silence."""
    described = describe()

    assert [setting.name for setting in described] == list(settings.SHARED_PATHS)
    assert not described[0].answered


def test_a_settings_value_is_expanded_rather_than_echoed(config_home: Path) -> None:
    """`repos_file = "~/dev/repos.json"` is an ordinary thing to write, and the
    question this answers is what the tool will do, not what somebody typed."""
    write_config(config_home, f'{KEY} = "~/dev/repos.json"\n')

    described = describe()

    assert described[0].value == str(Path.home() / 'dev/repos.json')


def test_a_setting_reports_whether_the_file_it_names_is_there(config_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry = tmp_path / 'repos.json'
    registry.write_text('{}')
    monkeypatch.setenv(DECLARED, str(registry))

    assert describe()[0].exists

    registry.unlink()

    assert not describe()[0].exists


def test_a_path_under_this_home_is_written_the_way_a_person_types_it() -> None:
    """For a screen, never for a filesystem call. `/home/chris/.config/git/config`
    spends fourteen characters saying whose machine it is, on every row of a column
    that has to align."""
    assert paths.under_home(Path('/home/someone/.config/git/config'), Path('/home/someone')) == '~/.config/git/config'


def test_a_path_outside_this_home_is_left_absolute() -> None:
    """A path outside it is a finding on its own, and rewriting it would hide
    that."""
    assert paths.under_home(Path('/etc/zshenv'), Path('/home/someone')) == '/etc/zshenv'
