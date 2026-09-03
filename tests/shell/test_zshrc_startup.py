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


def start(home: Path, *, path: str = BARE_PATH, snippet: str = 'true') -> Shell:
    """Start an interactive zsh in `home` and report what each stream carried.

    Interactive because `.zshrc` is only read by one, and the streams stay apart
    for the reason `shell_out` states: a merged stream passes whichever one the
    code chose.

    The timeout is a backstop rather than an expectation — every shell here is
    given a command and exits on it, so hitting it means one started waiting for
    input, which is a hang rather than a slow test.
    """
    completed = subprocess.run(
        ['zsh', '-i', '-c', snippet],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env={'HOME': str(home), 'PATH': path, 'TERM': 'xterm'},
        check=False,
        cwd=home,
        timeout=60,
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

    Parametrized rather than folded into one assertion: a failure names which
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

CACHE_COMPLETION_CALL = re.compile(r'\bcache_completion\s+(\S+)')
"""One `cache_completion` call, capturing the tool it autoloads a completion for.

Matched anywhere on the line rather than at its start, because these calls are
variously indented and chained and anchoring would find a fraction of them —
which is the failure mode where the assertion passes on the calls it never saw.
"""


def uncommented() -> list[str]:
    return [line for line in ZSHRC.read_text().splitlines() if not line.lstrip().startswith('#')]


def test_every_autoloaded_completion_is_generated_before_compinit_reads_fpath() -> None:
    """compinit enumerates fpath once, so a function written after it is invisible.

    Derived from where the `cache_completion` calls actually sit rather than from
    the `fpath=` line alone. The hazard is a call placed after compinit, and the
    natural place to add one is beside the `cache_eval` block much further down —
    which a fixed two-line comparison passes unchanged while the tool it added
    silently has no completion.
    """
    lines = uncommented()
    calls = [i for i, line in enumerate(lines) if CACHE_COMPLETION_CALL.search(line) and 'cache_completion()' not in line]
    joined = next(i for i, line in enumerate(lines) if line.startswith('fpath=("$ZSH_AUTOLOADED"'))
    initialized = next(i for i, line in enumerate(lines) if line.startswith('compinit -d '))

    assert calls, 'no cache_completion call was matched, so this asserts nothing'
    assert joined < initialized, 'the generated functions are written where compinit will never index them'
    late = [lines[i].strip() for i in calls if i > initialized]
    assert not late, f'these run after compinit and are never registered: {late}'


def test_a_completion_that_compinit_would_skip_is_refused_rather_than_written(tmp_path: Path) -> None:
    """compinit reads the literal first line for a `#compdef` tag.

    A file without one is enumerated, skipped, and never mentioned — Tab then
    behaves exactly as it does for a tool that ships no completion, which is why
    four tools lost theirs here with every guard in this file passing. Typer's
    template emits a blank line before the tag and is the shape that caused it.

    Asserted through a stub rather than a real tool, so this runs on a machine
    carrying none of them.
    """
    home = deployed_home(tmp_path)
    fake = home / 'bin'
    fake.mkdir()
    # A leading blank line, exactly as Typer's generator emits it.
    (fake / 'blanktool').write_text("#!/bin/sh\nprintf '\\n#compdef blanktool\\n_blanktool() { _message x }\\n'\n")
    (fake / 'blanktool').chmod(0o755)

    result = start(
        home,
        path=f'{fake}{os.pathsep}{BARE_PATH}',
        snippet='cache_completion blanktool blanktool; [[ -e $ZSH_AUTOLOADED/_blanktool ]] && print left || print removed',
    )

    assert 'not a #compdef tag' in result.stderr, f'a file compinit would skip was accepted:\n{result.stderr}'
    assert result.stdout.strip().endswith('removed'), 'the unusable file was left on fpath, where it holds the dump count'


# ─────────────────────────────────────────────────────────────────────────────
# A cache directory compaudit would refuse is repaired, not complained about
# ─────────────────────────────────────────────────────────────────────────────

CACHE_DIRECTORIES = ('.', 'functions', 'completions', 'generator-state')
"""Every directory the repair loop walks, relative to `$XDG_CACHE_HOME/zsh`.

`.` is the parent, which compaudit checks as well as the fpath directories
themselves — a group-writable parent condemns children that are each correct.
"""


def cache_modes(home: Path) -> dict[str, int]:
    """The permission bits of each cache directory, keyed by the name above."""
    root = home / '.cache' / 'zsh'
    return {name: (root / name).stat().st_mode & 0o777 for name in CACHE_DIRECTORIES}


def test_a_group_writable_cache_directory_is_tightened_rather_than_reported(tmp_path: Path) -> None:
    """The repair has to run, and it has to run silently.

    `zf_chmod` from zsh/files takes an octal mode alone. Handed `go-w` it writes
    `invalid mode` to stderr and changes nothing, so the directory stays as
    compaudit found it and every subsequent start says the same thing again.
    That is two failures from one call — a shell that talks on every start, and
    a repair that never happens — and only the first is visible.

    Asserted on both, because the noisy half is the one that gets noticed and
    the silent half is the one that matters.
    """
    home = deployed_home(tmp_path)
    loose = home / '.cache' / 'zsh'
    loose.mkdir(parents=True)
    loose.chmod(0o775)

    result = start(home)

    assert 'invalid mode' not in result.stderr, f'the repair was refused:\n{result.stderr}'
    written = {name: oct(mode) for name, mode in cache_modes(home).items() if mode & 0o022}
    assert not written, f'compaudit would refuse these after a start meant to repair them: {written}'


def test_the_repair_settles_so_a_later_start_has_nothing_to_do(tmp_path: Path) -> None:
    """A repair that does not stick is a fork paid on every start, forever.

    The external `chmod` is reached for on the grounds that the cost is paid
    once. That holds only if the second start no longer matches the glob, which
    is what this measures — the first start does the work and the second finds
    the directories already tight.
    """
    home = deployed_home(tmp_path)
    loose = home / '.cache' / 'zsh'
    loose.mkdir(parents=True)
    loose.chmod(0o775)

    start(home)
    after_first = cache_modes(home)
    second = start(home)

    assert 'invalid mode' not in second.stderr, f'a settled machine still reported:\n{second.stderr}'
    assert cache_modes(home) == after_first, 'the second start moved modes the first had already settled'
