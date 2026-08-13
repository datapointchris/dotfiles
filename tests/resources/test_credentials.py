"""Whether a configured credential helper can actually run, and how it fails.

Driven through a real `git config` rather than a stubbed layering. `helpers()`
reads `gitconfig.read()`, which shells out, so a test that replaced the parse
would assert on this module's idea of git's output instead of on git's — and the
key format (`credential.<url>.helper`, with a URL full of dots and slashes) is
exactly the thing worth measuring against the real thing.

`GIT_CONFIG_GLOBAL` is what makes that affordable: git reads the named file as
the global config, so `--global` in `gitconfig.read` resolves to a temp file and
nothing touches the machine's own configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dotfiles.resources import credentials
from dotfiles.resources.credentials import Helper
from dotfiles.resources.credentials import Verdict

PE_HEADER = b'MZ\x90\x00\x03\x00\x00\x00not a real executable'
"""Enough of a DOS header to look like a Windows binary and not enough to be one.

The point is only that the kernel refuses it. A file with no ELF magic and no
shebang fails `execve` with ENOEXEC — the same errno a PE32 binary gets on a WSL
box whose binfmt handler has gone — so this reproduces the exact failure the
resource was built for, on Linux, with no WSL involved.
"""


@pytest.fixture
def global_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / 'global.gitconfig'
    config.write_text('')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', str(config))
    monkeypatch.delenv('GIT_CONFIG_SYSTEM', raising=False)
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')
    return config


def unrunnable(tmp_path: Path, name: str = 'git-credential-manager.exe') -> Path:
    """A file that exists, is executable, and that `execve` will not start."""
    binary = tmp_path / name
    binary.write_bytes(PE_HEADER)
    binary.chmod(0o755)
    return binary


# ─────────────────────────────────────────────────────────────────────────────
# Reading the configuration: which helpers exist, and for what
# ─────────────────────────────────────────────────────────────────────────────


def test_a_scoped_helper_keeps_the_url_it_is_keyed_on(global_config: Path) -> None:
    """The URL is the part a naive split on `.` destroys — it holds dots and
    slashes of its own, and the key is `credential.<url>.helper`."""
    global_config.write_text('[credential "https://github.com"]\n\thelper = /usr/bin/true\n')

    found = credentials.helpers()

    assert [(helper.scope, helper.value) for helper in found] == [('https://github.com', '/usr/bin/true')]


def test_an_unscoped_helper_reports_an_empty_scope(global_config: Path) -> None:
    global_config.write_text('[credential]\n\thelper = /usr/bin/true\n')

    found = credentials.helpers()

    assert [(helper.scope, helper.label) for helper in found] == [('', 'every remote')]


def test_the_empty_reset_helper_is_not_a_helper(global_config: Path) -> None:
    """git's own idiom for clearing an inherited helper before setting one, which
    `common.gitconfig` uses for every github.com entry. Read as a broken helper it
    would report a fault on every machine, on every run."""
    global_config.write_text('[credential "https://github.com"]\n\thelper =\n\thelper = /usr/bin/true\n')

    found = credentials.helpers()

    assert [helper.value for helper in found] == ['/usr/bin/true']


def test_the_origin_names_the_file_that_set_it(global_config: Path) -> None:
    """The reason this reads the layering instead of asking git per URL. On a
    machine with five config files, which one set the helper is most of the fix."""
    global_config.write_text('[credential]\n\thelper = /usr/bin/true\n')

    assert credentials.helpers()[0].origin == global_config


# ─────────────────────────────────────────────────────────────────────────────
# Resolving a value to the program git would run
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('value', 'program'),
    [
        (
            '/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe',
            '/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe',
        ),
        ('!gh auth git-credential', 'gh'),
        ('libsecret', 'git-credential-libsecret'),
        ('osxkeychain', 'git-credential-osxkeychain'),
    ],
)
def test_a_value_resolves_by_gits_own_three_rules(value: str, program: str) -> None:
    """A path is used as written, a `!` form is a shell command whose first word is
    the program, and a bare name expands to `git-credential-<name>` on PATH."""
    assert Helper('', value, Path('/dev/null')).program == program


def test_a_shell_helper_is_invoked_through_a_shell_with_the_operation_appended() -> None:
    """`gh get` is not a command. Appending to the program rather than to the whole
    shell string would report every `!` helper as broken."""
    helper = Helper('', '!gh auth git-credential', Path('/dev/null'))

    assert helper.invocation('get') == ['sh', '-c', 'gh auth git-credential get']


def test_a_path_helper_is_invoked_directly() -> None:
    helper = Helper('', '/usr/local/bin/gcm', Path('/dev/null'))

    assert helper.invocation('get') == ['/usr/local/bin/gcm', 'get']


# ─────────────────────────────────────────────────────────────────────────────
# The three faults, told apart
# ─────────────────────────────────────────────────────────────────────────────


def test_a_helper_the_kernel_will_not_start_is_stale_not_missing(global_config: Path, tmp_path: Path) -> None:
    """The whole reason this resource exists. The configuration is correct and the
    machine underneath it is not, so a reader sent to `common.gitconfig` by a
    `missing` verdict would be looking in the wrong file entirely.

    Measured against a real `execve` refusal rather than a patched `run`: the
    thing under test is that `effects.run` folds ENOEXEC into a code this can
    read, which a stub would assert about itself.
    """
    binary = unrunnable(tmp_path)
    global_config.write_text(f'[credential "https://employer.example.com"]\n\thelper = {binary}\n')

    found = credentials.RESOURCE.observe(None, None).found  # type: ignore[arg-type]

    assert [entry.verdict for entry in found] == [Verdict.STALE]
    assert 'Exec format error' in found[0].detail
    assert 'WSLInterop' in found[0].advice


def test_a_helper_whose_path_does_not_exist_is_missing(global_config: Path) -> None:
    global_config.write_text('[credential "https://x.example.com"]\n\thelper = /mnt/c/gone/gcm.exe\n')

    found = credentials.RESOURCE.observe(None, None).found  # type: ignore[arg-type]

    assert [entry.verdict for entry in found] == [Verdict.MISSING]
    assert 'does not exist' in found[0].detail


def test_a_bare_name_that_is_not_on_path_is_missing(global_config: Path) -> None:
    """The `git-credential-<name>` expansion, which fails differently from a path:
    there is no file to stat, so the answer comes from PATH lookup."""
    global_config.write_text('[credential]\n\thelper = nosuchhelper\n')

    found = credentials.RESOURCE.observe(None, None).found  # type: ignore[arg-type]

    assert [entry.verdict for entry in found] == [Verdict.MISSING]
    assert 'git-credential-nosuchhelper is not on PATH' in found[0].detail


def test_a_helper_that_runs_is_matched(global_config: Path) -> None:
    """`true` stands in for a helper that starts. Whatever it exits with, the
    question `check` asks is whether the kernel started it at all."""
    global_config.write_text('[credential]\n\thelper = /usr/bin/true\n')

    found = credentials.RESOURCE.observe(None, None).found  # type: ignore[arg-type]

    assert [entry.verdict for entry in found] == [Verdict.MATCHED]


def test_the_binfmt_advice_is_withheld_from_a_native_helper(global_config: Path, tmp_path: Path) -> None:
    """A broken ELF on an Arch box is not a WSL interop problem, and advice naming
    `wsl.exe` there would send a reader somewhere that does not exist."""
    binary = unrunnable(tmp_path, name='git-credential-native')
    global_config.write_text(f'[credential]\n\thelper = {binary}\n')

    found = credentials.RESOURCE.observe(None, None).found  # type: ignore[arg-type]

    assert found[0].verdict is Verdict.STALE
    assert 'WSLInterop' not in found[0].advice
    assert 'architecture' in found[0].advice


# ─────────────────────────────────────────────────────────────────────────────
# What reaches `check`, and what never does
# ─────────────────────────────────────────────────────────────────────────────


def test_a_working_helper_produces_no_change(global_config: Path) -> None:
    global_config.write_text('[credential]\n\thelper = /usr/bin/true\n')
    observed = credentials.RESOURCE.observe(None, None)  # type: ignore[arg-type]

    assert credentials.RESOURCE.diff(None, observed) == ()  # type: ignore[arg-type]


def test_a_change_names_the_file_to_open(global_config: Path) -> None:
    """The advice carries the origin because the finding is about a value the
    reader now has to go and find among several files."""
    global_config.write_text('[credential]\n\thelper = nosuchhelper\n')
    observed = credentials.RESOURCE.observe(None, None)  # type: ignore[arg-type]

    (change,) = credentials.RESOURCE.diff(None, observed)  # type: ignore[arg-type]

    assert str(global_config) in change.advice
    assert change.observed == 'nosuchhelper'


def test_nothing_configured_is_reported_as_such_rather_than_as_a_fault(global_config: Path) -> None:
    """A machine using SSH remotes only has no helper and nothing wrong with it."""
    observed = credentials.RESOURCE.observe(None, None)  # type: ignore[arg-type]

    assert credentials.RESOURCE.diff(None, observed) == ()  # type: ignore[arg-type]
    assert 'no credential helper' in observed.summary


def test_observe_never_asks_for_a_credential(global_config: Path, tmp_path: Path) -> None:
    """The constraint that keeps this runnable on a timer. A helper that recorded
    being asked for a credential would have opened a browser on a real machine.

    Asserted by giving the helper somewhere to write and checking it stayed empty:
    the exec test runs it with no arguments, so a helper distinguishing `get` from
    nothing writes only under `--probe`.
    """
    witness = tmp_path / 'asked'
    helper = tmp_path / 'git-credential-witness'
    helper.write_text(f'#!/bin/sh\n[ "$1" = get ] && echo asked > {witness}\nexit 0\n')
    helper.chmod(0o755)
    global_config.write_text(f'[credential]\n\thelper = {helper}\n')

    found = credentials.RESOURCE.observe(None, None).found  # type: ignore[arg-type]

    assert [entry.verdict for entry in found] == [Verdict.MATCHED]
    assert not witness.exists(), 'observe ran the helper with `get`, which is what opens a browser'


def test_probe_does_ask_and_reads_the_answer(global_config: Path, tmp_path: Path) -> None:
    """The opt-in half. A helper answering with `password=` is the only thing that
    counts, because a helper with nothing to say also exits 0."""
    helper = tmp_path / 'git-credential-witness'
    helper.write_text('#!/bin/sh\n[ "$1" = get ] && printf "username=u\\npassword=p\\n"\nexit 0\n')
    helper.chmod(0o755)

    answered, why = credentials.probe(Helper('https://example.com', str(helper), global_config))

    assert answered is True
    assert 'example.com' in why


def test_probe_reports_a_helper_that_runs_and_returns_nothing(global_config: Path, tmp_path: Path) -> None:
    """Logged out, which exits 0 exactly like success and is why the output is read
    rather than the exit code."""
    helper = tmp_path / 'git-credential-empty'
    helper.write_text('#!/bin/sh\nexit 0\n')
    helper.chmod(0o755)

    answered, why = credentials.probe(Helper('https://example.com', str(helper), global_config))

    assert answered is False
    assert 'no credential' in why


def test_probe_refuses_to_let_a_helper_prompt(global_config: Path, tmp_path: Path) -> None:
    """Both variables, because they belong to different programs: git's suppresses
    its own terminal fallback, GCM's suppresses the window GCM opens by itself."""
    helper = tmp_path / 'git-credential-env'
    helper.write_text('#!/bin/sh\nprintf "password=$GIT_TERMINAL_PROMPT-$GCM_INTERACTIVE\\n"\n')
    helper.chmod(0o755)

    _, why = credentials.probe(Helper('https://example.com', str(helper), global_config))

    assert os.environ.get('GIT_TERMINAL_PROMPT') is None, 'the probe leaked its environment into this process'
    assert 'example.com' in why
