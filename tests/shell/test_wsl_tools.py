"""wsl-reclaim and wsl-doctor, driven on a machine that is not WSL.

Neither tool can be exercised where it runs. The fleet's WSL box is the work
machine, and a mistake in either is expensive in a way a normal app is not:
`compact` shuts down every distro and hands an elevated diskpart a path, so a
wrong path is a failed reclaim at best and an attached read-only disk at worst.

What is testable off WSL is everything up to the handoff — the registry query,
the extended-length path the registry answers with, and the diskpart script that
gets written. A stub `powershell.exe` supplies the Windows half, and it replies
in UTF-16LE because that is what a real one does and stripping it is the step
that most easily regresses into silence.
"""

from __future__ import annotations

import dataclasses as dc
import os
import stat
from pathlib import Path

import pytest
from shells import REPO
from shells import Shell
from shells import shell_out

RECLAIM = str(REPO / 'apps' / 'host' / 'wsl' / 'wsl-reclaim')
DOCTOR = str(REPO / 'apps' / 'host' / 'wsl' / 'wsl-doctor')
WSLCONFIG = str(REPO / 'install' / 'wsl' / 'install-wslconfig.sh')
TEMPLATE = REPO / 'install' / 'wsl' / 'wslconfig.template'

BASE_PATH = r'C:\Users\me\AppData\Local\wsl\{7f3a}'
DEVICE_PREFIX = '\\\\?\\'

STUB_POWERSHELL = """#!/usr/bin/env python3
import os
import sys

# A Windows console tool answers in UTF-16LE with CRLF endings. Reproduced
# rather than approximated: an ASCII reply would pass whether or not the callers
# strip the NULs, which is the whole property under test.
with open(os.environ['ARGV_LOG'], 'a', encoding='utf-8') as log:
    log.write('\\x1f'.join(sys.argv[1:]) + '\\n')

sys.stdout.buffer.write(os.environ.get('STUB_REPLY', '').encode('utf-16-le'))
sys.stdout.buffer.write('\\r\\n'.encode('utf-16-le'))
"""

STUB_WSLPATH = """#!/usr/bin/env bash
# wslpath exists only on WSL. The fixtures hand it paths that are already POSIX,
# so echoing the last argument is the identity this off-WSL run needs.
echo "${@: -1}"
"""


def uncommented(path: str) -> list[str]:
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    return [line for line in lines if not line.lstrip().startswith('#')]


@dc.dataclass(frozen=True, slots=True)
class Windows:
    """A stubbed Windows side: one fake powershell.exe, and the argv it saw."""

    path: Path
    argv_log: Path

    @property
    def calls(self) -> list[str]:
        if not self.argv_log.is_file():
            return []
        return self.argv_log.read_text(encoding='utf-8').splitlines()


@pytest.fixture
def windows(tmp_path: Path) -> Windows:
    binaries = tmp_path / 'bin'
    binaries.mkdir()

    for name, body in (('powershell.exe', STUB_POWERSHELL), ('wslpath', STUB_WSLPATH)):
        stub = binaries / name
        stub.write_text(body)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    return Windows(path=binaries, argv_log=tmp_path / 'argv.log')


def run(script: str, snippet: str, windows: Windows, *args: str, reply: str = '', **environment: str) -> Shell:
    """Source one of the tools and run `snippet` against its functions.

    Sourcing runs neither `main` nor the WSL guard, which is what lets these run
    on Arch and macOS.
    """
    return shell_out(
        f'source "$1"; {snippet}',
        script,
        *args,
        PATH=f'{windows.path}{os.pathsep}{os.environ["PATH"]}',
        ARGV_LOG=str(windows.argv_log),
        STUB_REPLY=reply,
        **environment,
    )


# ================================================================
# The Windows half
# ================================================================


def test_utf16_reply_reaches_bash_as_a_plain_string(windows: Windows) -> None:
    result = run(RECLAIM, 'powershell_out "Write-Output x"', windows, reply='hello')
    assert result.stdout.strip() == 'hello'


def test_registry_query_carries_the_distro_and_the_pipeline_variable(windows: Windows) -> None:
    """`$_` is PowerShell's, and bash must not expand it on the way through.

    Expanded, the query becomes `.GetValue(...)` on nothing, matches no
    distribution, and returns an empty BasePath — which every caller here reads
    as "not on WSL" rather than as a bug.
    """
    run(RECLAIM, 'vhdx_windows_path', windows, reply=BASE_PATH, WSL_DISTRO_NAME='Ubuntu-Work')

    assert windows.calls, 'the registry lookup never reached powershell.exe'
    query = windows.calls[0]
    assert '$_.GetValue' in query
    assert 'Ubuntu-Work' in query
    assert 'CurrentVersion\\Lxss' in query


def test_extended_length_prefix_is_stripped(windows: Windows) -> None:
    """The registry answers `\\\\?\\C:\\...` and wslpath returns nothing for one."""
    result = run(RECLAIM, 'vhdx_windows_path', windows, reply=DEVICE_PREFIX + BASE_PATH, WSL_DISTRO_NAME='Ubuntu')
    assert result.stdout.strip() == BASE_PATH + r'\ext4.vhdx'


def test_a_plain_base_path_is_left_alone(windows: Windows) -> None:
    result = run(RECLAIM, 'vhdx_windows_path', windows, reply=BASE_PATH, WSL_DISTRO_NAME='Ubuntu')
    assert result.stdout.strip() == BASE_PATH + r'\ext4.vhdx'


def test_no_distro_name_is_a_failure_not_an_empty_path(windows: Windows) -> None:
    """An empty answer would be handed to diskpart as `select vdisk file=""`."""
    result = run(RECLAIM, 'vhdx_windows_path', windows, reply=BASE_PATH, WSL_DISTRO_NAME='')
    assert not result.ok
    assert result.stdout.strip() == ''


def test_an_unregistered_distro_is_a_failure(windows: Windows) -> None:
    result = run(RECLAIM, 'vhdx_windows_path', windows, reply='', WSL_DISTRO_NAME='Ubuntu')
    assert not result.ok


# ================================================================
# The diskpart script
# ================================================================


def compact_script(tmp_path: Path, windows: Windows, vhdx: str) -> str:
    destination = tmp_path / 'compact.ps1'
    run(RECLAIM, 'write_compact_script "$2" "$3"', windows, str(destination), vhdx)
    return destination.read_text(encoding='utf-8')


def test_the_disk_is_attached_read_only_before_it_is_compacted(tmp_path: Path, windows: Windows) -> None:
    """Order is the whole safety property. Attaching writable hands an elevated
    diskpart a mounted ext4 filesystem it does not understand."""
    written = compact_script(tmp_path, windows, BASE_PATH + r'\ext4.vhdx')

    attach = written.index('attach vdisk readonly')
    compact = written.index('compact vdisk')
    detach = written.index('detach vdisk')
    assert attach < compact < detach


def test_wsl_is_shut_down_before_diskpart_runs(tmp_path: Path, windows: Windows) -> None:
    """diskpart cannot attach a vhdx the utility VM still holds open."""
    written = compact_script(tmp_path, windows, BASE_PATH + r'\ext4.vhdx')
    assert written.index('wsl.exe --shutdown') < written.index('diskpart.exe')


def test_the_shutdown_is_followed_by_a_wait(tmp_path: Path, windows: Windows) -> None:
    """WSL keeps the VM alive for about eight seconds after the last shell exits."""
    written = compact_script(tmp_path, windows, BASE_PATH + r'\ext4.vhdx')
    assert 'Start-Sleep' in written


def test_a_path_with_spaces_stays_one_argument(tmp_path: Path, windows: Windows) -> None:
    """diskpart splits an unquoted path on the space and selects nothing. The
    path reaches it through a PowerShell variable, so both the assignment and
    the use have to quote."""
    spaced = r'C:\Users\Chris Birch\AppData\Local\wsl\ext4.vhdx'
    written = compact_script(tmp_path, windows, spaced)

    assert f"$vhdx = '{spaced}'" in written
    assert 'select vdisk file="$vhdx"' in written


def test_the_vhdx_path_is_not_expanded_by_powershell(tmp_path: Path, windows: Windows) -> None:
    """A Windows path is full of backslashes and braces. Written into a
    double-quoted PowerShell literal, `$` or a here-string terminator in a
    username would rewrite the target."""
    written = compact_script(tmp_path, windows, BASE_PATH + r'\ext4.vhdx')
    assert f"$vhdx = '{BASE_PATH}" + r"\ext4.vhdx'" in written


# ================================================================
# Sparse mode stays refused
# ================================================================


@pytest.mark.parametrize('tool', [RECLAIM, DOCTOR])
def test_no_tool_offers_to_enable_sparse_mode(tool: str) -> None:
    """`--set-sparse true` has been gated behind --allow-unsafe since WSL 2.5.6
    after ext4 corruption reports, and a sparse vhdx cannot be compacted at all.
    It is the obvious-looking fix for exactly this problem, so the refusal is
    pinned rather than left to the comment explaining it."""
    code = uncommented(tool)
    assert not [line for line in code if '--set-sparse' in line]
    assert not [line for line in code if '--allow-unsafe' in line]


def test_the_template_does_not_enable_sparse_vhd() -> None:
    active = [line for line in TEMPLATE.read_text(encoding='utf-8').splitlines() if not line.lstrip().startswith('#')]
    assert not [line for line in active if 'sparseVhd' in line]


def test_the_template_sets_the_memory_reclaim_mode() -> None:
    """The shipped default is dropCache, which discards the guest's page cache."""
    assert 'autoMemoryReclaim=gradual' in TEMPLATE.read_text(encoding='utf-8')


# ================================================================
# .wslconfig install
# ================================================================


def wslconfig(windows: Windows, profile: Path, *args: str) -> Shell:
    """`is_wsl` is overridden after sourcing, so the body runs on a machine that
    is not WSL. The guard itself is tested separately, by running the script."""
    return shell_out(
        'source "$1"; is_wsl() { return 0; }; main "${@:2}"',
        WSLCONFIG,
        *args,
        PATH=f'{windows.path}{os.pathsep}{os.environ["PATH"]}',
        ARGV_LOG=str(windows.argv_log),
        STUB_REPLY=str(profile),
        DOTFILES_DIR=str(REPO),
    )


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    """Stands in for %USERPROFILE%. The stub answers a Linux path, which wslpath
    passes through unchanged for anything already absolute and POSIX."""
    home = tmp_path / 'win-home'
    home.mkdir()
    return home


def test_check_reports_a_missing_wslconfig(windows: Windows, profile: Path) -> None:
    result = wslconfig(windows, profile, '--check')
    assert 'missing: .wslconfig' in result.stdout


def test_check_reports_a_wslconfig_that_differs(windows: Windows, profile: Path) -> None:
    (profile / '.wslconfig').write_text('[wsl2]\nmemory=2GB\n')
    result = wslconfig(windows, profile, '--check')
    assert 'differs: .wslconfig' in result.stdout


def test_check_is_silent_when_converged(windows: Windows, profile: Path) -> None:
    (profile / '.wslconfig').write_text(TEMPLATE.read_text(encoding='utf-8'))
    result = wslconfig(windows, profile, '--check')
    assert result.stdout.strip() == ''
    assert result.ok


def test_an_existing_wslconfig_is_backed_up_before_it_is_replaced(windows: Windows, profile: Path) -> None:
    """It is a file edited by hand at the moment something is broken. Losing
    that edit to an unrelated install is silent."""
    existing = profile / '.wslconfig'
    existing.write_text('[wsl2]\nmemory=2GB\n')

    wslconfig(windows, profile)

    backups = list(profile.glob('.wslconfig.*.bak'))
    assert len(backups) == 1
    assert backups[0].read_text(encoding='utf-8') == '[wsl2]\nmemory=2GB\n'
    assert existing.read_text(encoding='utf-8') == TEMPLATE.read_text(encoding='utf-8')


def test_a_converged_wslconfig_is_not_backed_up_every_run(windows: Windows, profile: Path) -> None:
    (profile / '.wslconfig').write_text(TEMPLATE.read_text(encoding='utf-8'))
    wslconfig(windows, profile)
    assert list(profile.glob('.wslconfig.*.bak')) == []


# ================================================================
# The guard
# ================================================================


@pytest.mark.parametrize('tool', [RECLAIM, DOCTOR])
def test_help_works_off_wsl(tool: str) -> None:
    """The WSL guard sits after help, so `--help` answers on any machine. A tool
    that refuses to describe itself where it does not run is undiscoverable from
    the machine you would read about it on."""
    result = shell_out('bash "$1" --help', tool)
    assert result.ok
    assert 'Usage:' in result.stdout


@pytest.mark.parametrize('tool', [RECLAIM, DOCTOR])
def test_the_report_refuses_off_wsl(tool: str) -> None:
    result = shell_out('bash "$1"', tool)
    assert not result.ok


def test_the_wslconfig_installer_skips_off_wsl(windows: Windows, profile: Path) -> None:
    """A skip, not a failure: it is called from a task that also runs on the
    machines this repo deploys to that are not WSL."""
    result = shell_out(
        'bash "$1"',
        WSLCONFIG,
        PATH=f'{windows.path}{os.pathsep}{os.environ["PATH"]}',
        ARGV_LOG=str(windows.argv_log),
        STUB_REPLY=str(profile),
        DOTFILES_DIR=str(REPO),
    )
    assert result.ok
    assert 'Not in WSL' in result.stdout
    assert not (profile / '.wslconfig').exists()
