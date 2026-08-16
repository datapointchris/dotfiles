"""What a shell says on a machine that does not carry every optional tool.

`.zshrc` wires an integration for a handful of tools it does not require —
`yazi`, `broot` — and a machine is free not to declare them. `scheduler.yml`
declares neither, because a headless grading box has no use for a TUI file
browser. A shell there must still start clean.

Measured 2026-08-16 on scheduler-lxc, the first machine converged against a
manifest that omits them: every shell wrote `❌ Setup  : broot not found` to
stderr. `log()` is gated behind `ZSHRC_DEBUG` and `log_error()` is not, so the
absence was reported on every start while the presence was silent — the two
halves of one branch answering to different rules.

Nothing exercised `.zshrc` as a whole before this file, which is why a manifest
that omits a tool never met the config that assumes it. The shell libraries have
their own tests; the file that sources them had none.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from shells import REPO
from shells import Shell
from shells import requires

pytestmark = requires('zsh')

ZSH_CONFIG = REPO / 'configs' / 'common' / '.config' / 'zsh'
SHELL_LIBRARIES = (
    REPO / 'configs' / 'common' / '.local' / 'shell',
    REPO / 'shell' / 'common',
)
"""Both directories deploy to `~/.local/shell/`, so a home that carries one and
not the other fails on a `source` that has nothing to do with the subject."""

BARE_PATH = '/usr/bin:/bin'
"""No `~/.local/bin` and no `~/.cargo/bin`, which is where every optional tool
here installs. The temp home has neither anyway; naming the PATH says so."""

FLAGS_OFF = (
    'ZSHRC_DEBUG',
    'SHELL_NUDGE',
    'SHELL_VI_MODE',
    'SHELL_AUTOSUGGESTIONS',
    'SHELL_SYNTAX_HIGHLIGHTING',
    'SHELL_FORGIT',
    'SHELL_HISTORY_DB',
    'SHELL_CLISTENO',
    'SHELL_YOU_SHOULD_USE',
)
"""Every plugin gate `.zshrc` reads, held off so the fixture declares nothing.

The plugin blocks are three-way and correct: flag off skips silently, flag on
with the file missing is a real error. A fixture leaving them on would report
plugins it never installed, which is a fault in the fixture rather than in the
config. Off, the only thing left that can write to stderr is a tool no flag
governs — which is the subject.
"""


def deployed_home(root: Path) -> Path:
    """A home carrying what `symlinks apply` would put there, and nothing else.

    `/etc/zsh/zshenv` exports `ZDOTDIR="$HOME/.config/zsh"` on this fleet, so
    setting `ZDOTDIR` in the environment does not reach zsh — the system file
    runs first and overwrites it. The config has to sit at the path that file
    names, which is why this builds a home rather than pointing at the repo.

    A host without that system file is the other half, and it is silent. zsh
    then reads `$HOME/.zshenv` and `$HOME/.zshrc`, finds neither, and starts a
    shell that sourced no config at all — on which every assertion about an
    absence passes and only an assertion about a *presence* fails. The home
    `.zshenv` written below stands in for the system file, so the same two files
    run either way. Measured 2026-08-16: a GitHub runner ships no such
    `/etc/zsh/zshenv`, and `br` was reported missing from a `.zshrc` that had
    never been read.
    """
    home = root / 'home'
    shell_dir = home / '.local' / 'shell'
    shell_dir.mkdir(parents=True)
    (home / '.config').mkdir(parents=True)

    shutil.copytree(ZSH_CONFIG, home / '.config' / 'zsh')
    for source in SHELL_LIBRARIES:
        shutil.copytree(source, shell_dir, dirs_exist_ok=True)
    (home / '.zshenv').write_text('export ZDOTDIR="$HOME/.config/zsh"\nsource "$ZDOTDIR/.zshenv"\n')

    plugin = home / '.config' / 'zsh' / 'plugins' / 'git-open'
    plugin.mkdir(parents=True)
    (plugin / 'git-open').touch()

    env = '\n'.join(f'export {flag}=false' for flag in FLAGS_OFF)
    (home / '.env').write_text(f'{env}\n')
    return home


ERROR_MARK = '❌'
"""What `log_error` prefixes every line with, and the only thing these assert on.

Not a bare `stderr == ''`. An interactive zsh driven without a terminal writes
`can't change option: zle` on its own account, which is the harness rather than
the config — asserting emptiness would fail forever on noise nothing here
produced.
"""


def reported(result: Shell) -> list[str]:
    """The lines `.zshrc` chose to report, with zsh's own chatter dropped."""
    return [line for line in result.stderr.splitlines() if ERROR_MARK in line]


def start(home: Path, *, path: str = BARE_PATH, snippet: str = 'true') -> Shell:
    """Start an interactive zsh in `home` and report what each stream carried.

    Interactive because `.zshrc` is only read by one, and the streams stay apart
    for the reason `shell_out` states: a merged stream passes whichever one the
    code chose.
    """
    completed = subprocess.run(
        ['zsh', '-i', '-c', snippet],
        capture_output=True,
        text=True,
        env={'HOME': str(home), 'PATH': path, 'TERM': 'xterm'},
        check=False,
        cwd=home,
    )
    return Shell(completed.stdout, completed.stderr, completed.returncode)


def test_a_shell_starting_without_the_optional_tools_says_nothing(tmp_path: Path) -> None:
    """An absent optional integration is a machine's declaration, not a fault.

    This is the regression. A grading box carries no `broot`, and reporting that
    on every shell start trains the reader to ignore stderr — which is where the
    faults that do matter are written.
    """
    result = start(deployed_home(tmp_path))

    assert reported(result) == [], 'a clean start reported:\n' + '\n'.join(reported(result))


def test_the_tools_that_are_absent_are_the_ones_this_asserts_about(tmp_path: Path) -> None:
    """Guards the test above against passing because the branch never ran.

    An assertion that stderr is empty also passes when `.zshrc` stopped before
    reaching the integrations. Naming them absent is what makes the silence mean
    something.
    """
    home = deployed_home(tmp_path)
    result = start(home, snippet='command -v broot >/dev/null && echo present || echo absent')

    assert result.stdout.strip().endswith('absent')


def test_the_fixture_home_is_one_zsh_actually_reads(tmp_path: Path) -> None:
    """Every other test here is vacuous on a shell that sourced nothing.

    An assertion about an absent tool, and an assertion that stderr carried no
    error, both hold perfectly for a `.zshrc` zsh never opened — so the fixture's
    own failure looks exactly like the config behaving. `flag_enabled` is defined
    by a library `.zshrc` sources, which no bare shell has.
    """
    home = deployed_home(tmp_path)

    result = start(home, snippet='typeset -f flag_enabled >/dev/null && echo sourced || echo bare')

    assert result.stdout.strip().endswith('sourced')


def test_the_integration_is_wired_when_the_tool_is_there(tmp_path: Path) -> None:
    """The fix may not be deleting the branch.

    `br` is the whole reason `.zshrc` mentions broot: it wraps `--outcmd` so a
    directory change survives the subshell. A silent absence that also stopped
    defining the function would pass the test above and lose the feature.
    """
    home = deployed_home(tmp_path)
    fake = home / 'bin'
    fake.mkdir()
    (fake / 'broot').write_text('#!/bin/sh\nexit 0\n')
    (fake / 'broot').chmod(0o755)

    result = start(
        home,
        path=f'{fake}{os.pathsep}{BARE_PATH}',
        snippet='typeset -f br >/dev/null && echo wired || echo missing',
    )

    assert result.stdout.strip().endswith('wired')
    assert reported(result) == [], 'a start with broot present reported:\n' + '\n'.join(reported(result))


@pytest.mark.parametrize('tool', ('broot', 'yazi'))
def test_neither_branch_of_an_optional_tool_writes_to_stderr(tmp_path: Path, tool: str) -> None:
    """Both tools carry the same shape, so both are held to the same rule.

    Parametrised rather than folded into one assertion: a failure names which
    tool regressed, and the next one added to `.zshrc` is a row here.

    `git-open` is deliberately not here. It is a plugin rather than a tool, every
    manifest declares `shell_plugins: true`, and it is on disk on the machine this
    was measured against — so its missing file is a real fault and reporting one
    is correct. The fixture installs a stub for it to say so.
    """
    result = start(deployed_home(tmp_path))
    said = [line for line in reported(result) if tool in line]

    assert said == [], f'{tool} reported its own absence: ' + '; '.join(said)
