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
import re
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
    'SHELL_VI_MODE',
    'SHELL_AUTOSUGGESTIONS',
    'SHELL_SYNTAX_HIGHLIGHTING',
    'SHELL_FORGIT',
    'SHELL_HISTORY_DB',
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


def run(argv: list[str], home: Path, path: str) -> Shell:
    """A zsh in `home`, with the two streams kept apart.

    Separate for the reason `shell_out` states: a merged stream passes whichever
    one the code chose. The timeout is a backstop rather than an expectation —
    every shell here is given a command and exits on it, so hitting it means one
    of them started waiting for input, which is a hang and not a slow test.
    """
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env={'HOME': str(home), 'PATH': path, 'TERM': 'xterm'},
        check=False,
        cwd=home,
        timeout=60,
    )
    return Shell(completed.stdout, completed.stderr, completed.returncode)


def start(home: Path, *, path: str = BARE_PATH, snippet: str = 'true') -> Shell:
    """Start an interactive zsh in `home`, which is the only kind that reads `.zshrc`."""
    return run(['zsh', '-i', '-c', snippet], home, path)


def sourced(home: Path, *, path: str = BARE_PATH, snippet: str) -> Shell:
    """Run `snippet` in a zsh that sourced `.zshrc` without being interactive.

    For the one assertion that needs compinit to have finished. `zsh -i` requires
    a terminal it can open, and a GitHub runner has none — it answers `not
    interactive and can't open terminal`, compinit answers `initialization
    aborted`, and an assertion about a *registered* completion then fails on the
    harness rather than on the config.

    *Rejected*: handing stdin a pty. It removes the error and replaces it with a
    hang — with a real terminal, `zsh -i -c` stops being run-and-exit and the
    shell sits there until the timeout fires. Measured on a runner at 60s.

    Interactivity is not what this asserts about. `.zshrc` branches on no such
    thing, compinit needs none, and what is being measured is whether the
    function a generator wrote is indexed by the time the file has finished. The
    tests above keep `zsh -i`, because reading the file is exactly their subject.
    """
    return run(['zsh', '-c', f'source "$HOME/.config/zsh/.zshrc"; {snippet}'], home, path)


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


def test_wt_walks_into_the_path_the_picker_printed(tmp_path: Path) -> None:
    """`worktree choose` prints a path because a child cannot move its parent's shell.

    `wt` is the half that does the moving, so wiring it is the whole feature —
    and the cd has to actually happen, which `typeset -f` alone would not show.
    Backing out of the picker is asserted separately below.
    """
    home = deployed_home(tmp_path)
    fake = home / 'bin'
    fake.mkdir()
    target = home / 'chosen'
    target.mkdir()
    (fake / 'worktree').write_text(f'#!/bin/sh\necho {target}\n')
    (fake / 'worktree').chmod(0o755)

    result = start(home, path=f'{fake}{os.pathsep}{BARE_PATH}', snippet='wt; pwd')

    assert result.stdout.strip().endswith(str(target))
    assert reported(result) == [], 'a start with worktree present reported:\n' + '\n'.join(reported(result))


def test_backing_out_of_the_picker_is_not_a_failure(tmp_path: Path) -> None:
    """fzf exits 0 with no selection when you press escape, and `worktree choose`
    passes that through. Letting the empty test supply the status would return 1,
    which the prompt renders as a failed command every time you change your mind."""
    home = deployed_home(tmp_path)
    fake = home / 'bin'
    fake.mkdir()
    (fake / 'worktree').write_text('#!/bin/sh\nexit 0\n')
    (fake / 'worktree').chmod(0o755)

    result = start(home, path=f'{fake}{os.pathsep}{BARE_PATH}', snippet='wt; echo "rc=$?"')

    assert result.stdout.strip().endswith('rc=0')


@pytest.mark.parametrize('tool', ('broot', 'yazi', 'worktree'))
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


# ─────────────────────────────────────────────────────────────────────────────
# Completions are autoloaded off fpath, never sourced at startup
# ─────────────────────────────────────────────────────────────────────────────

ZSHRC = ZSH_CONFIG / '.zshrc'

SOURCED_AT_STARTUP = {'zoxide', 'fzf', 'atuin', 'direnv', 'doit-widgets'}
"""The blocks `cache_eval` may still source, because none of them is a completion.

Each defines an alias, a hook or a keybinding that has to exist before the first
prompt, so there is nothing to defer. Everything else a tool generates is a
completion function and belongs on fpath.
"""

CACHE_EVAL_CALL = re.compile(r'\bcache_eval\s+(?:-b\s+\S+\s+)?(\S+)')
"""One `cache_eval` call, capturing the cache key it writes and sources.

Matched anywhere on the line rather than at its start: the calls are variously
indented inside an `if`, chained behind a `flag_enabled &&`, and inside a
function body, so anchoring finds a third of them and the assertion below passes
on the ones it never looked at. `-b BIN` is consumed and discarded — the binary
is what staleness is measured against, and the key is what names the file.
"""


def test_the_function_directory_joins_fpath_before_compinit_reads_it() -> None:
    """compinit scans fpath once and caches the result in its dump.

    A directory added afterwards is never indexed, and the failure is silent in
    the worst way: every shell starts clean, nothing reaches stderr, and Tab does
    nothing for every tool whose completion is generated. Ordering is the whole
    correctness of the arrangement, so it is asserted on position in the file
    rather than on behaviour, which would need a machine carrying the tools.
    """
    lines = ZSHRC.read_text().splitlines()
    joined = next(i for i, line in enumerate(lines) if line.startswith('fpath=("$ZSH_COMPLETION_FPATH"'))
    initialised = next(i for i, line in enumerate(lines) if line.startswith('compinit -d '))

    assert joined < initialised, 'the generated functions are written where compinit will never index them'


def test_every_generated_completion_is_written_rather_than_sourced() -> None:
    """`cache_eval` sources its file; `cache_completion` writes it to fpath.

    Sourcing a completion costs its whole size on every shell, whether or not
    anything ever completes that tool — `ruff` and `uv` generate 668K and 516K of
    clap definitions between them. The split is what keeps that off the startup
    path, and a completion moved back to `cache_eval` would reintroduce it
    silently, because sourcing works perfectly well and only costs time.
    """
    body = [line for line in ZSHRC.read_text().splitlines() if not line.lstrip().startswith('#')]
    sourced = {matched.group(1) for line in body for matched in [CACHE_EVAL_CALL.search(line)] if matched}

    assert sourced, 'no cache_eval call was matched, so this asserts nothing'
    assert sourced <= SOURCED_AT_STARTUP, f'a completion is sourced at startup rather than autoloaded: {sourced}'


def test_a_generated_completion_is_reachable_by_the_time_there_is_a_prompt(tmp_path: Path) -> None:
    """The other half of the ordering test, end to end on a real shell.

    Position in the file says the directory joins fpath in time; this says the
    function a generator wrote is actually registered against its command. A stub
    tool stands in for a real one, so this asserts on the mechanism rather than on
    whatever the machine running it happens to have installed.
    """
    home = deployed_home(tmp_path)
    fake = home / 'bin'
    fake.mkdir()
    (fake / 'stubtool').write_text("#!/bin/sh\nprintf '#compdef stubtool\\n_stubtool() { _message stub }\\n'\n")
    (fake / 'stubtool').chmod(0o755)

    # Two shells: the first generates the function, the second is the one that
    # finds it. compinit in the first ran before the file existed, which is the
    # ordinary case for a tool installed since the last shell started.
    where = f'{fake}{os.pathsep}{BARE_PATH}'
    sourced(home, path=where, snippet='cache_completion stubtool stubtool')
    result = sourced(home, path=where, snippet='print "registered=${_comps[stubtool]:-none}"')

    assert 'initialization aborted' not in result.stderr, 'compinit never ran, so this asserts nothing'
    assert result.stdout.strip().endswith('registered=_stubtool')
