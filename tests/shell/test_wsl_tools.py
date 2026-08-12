"""wsl-tools, driven on a machine that is not WSL.

It cannot be exercised where it runs. The fleet's WSL box is the work
machine, and a mistake in either is expensive in a way a normal app is not:
`compact` shuts down every distro and hands an elevated diskpart a path, and
`rebuild` unregisters the distro outright and imports it back from a tar.

What is testable off WSL is everything up to the handoff — the registry query,
the extended-length path it answers with, the elevation probe, both generated
PowerShell scripts, and the arguments they are launched with. A stub
`powershell.exe` supplies the Windows half. It answers per query rather than
with one canned string, because the interesting failures are the ones where a
caller asks the wrong question, and it replies in UTF-16LE because that is what
a real one does and stripping it is the step that most easily regresses into
silence.
"""

from __future__ import annotations

import dataclasses as dc
import os
import stat
from pathlib import Path

import pytest
from shells import REPO
from shells import SHELL_DIR
from shells import Shell
from shells import shell_out

TOOL = str(REPO / 'apps' / 'host' / 'wsl' / 'wsl-tools')
WSLCONFIG = str(REPO / 'install' / 'wsl' / 'install-wslconfig.sh')
TEMPLATE = REPO / 'install' / 'wsl' / 'wslconfig.template'

BASE_PATH = r'C:\Users\me\AppData\Local\wsl\{7f3a}'
DEVICE_PREFIX = '\\\\?\\'

STUB_POWERSHELL = """#!/usr/bin/env python3
import os
import sys

query = ' '.join(sys.argv[1:])

with open(os.environ['ARGV_LOG'], 'a', encoding='utf-8') as log:
    log.write(query.replace('\\n', ' ') + '\\n')

# Answered by what was asked. One canned reply cannot serve a run that resolves
# the profile, probes group membership and reads the registry in turn, and a
# stub that ignores the question hides a caller asking the wrong one.
if 'S-1-5-32-544' in query:
    reply = os.environ.get('STUB_ELEVATE', 'no')
elif 'Lxss' in query:
    reply = os.environ.get('STUB_BASE_PATH', '')
elif 'USERPROFILE' in query:
    reply = os.environ.get('STUB_PROFILE', '')
elif 'TEMP' in query:
    reply = os.environ.get('STUB_TEMP', '')
else:
    reply = os.environ.get('STUB_REPLY', '')

# A Windows console tool answers in UTF-16LE with CRLF endings. Reproduced
# rather than approximated: an ASCII reply would pass whether or not the callers
# strip the NULs, which is the whole property under test.
sys.stdout.buffer.write((reply + '\\r\\n').encode('utf-16-le'))
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
    """A stubbed Windows side, plus the deployed shell tree the apps read.

    The tool sources only `formatting.sh`, so the repo's own shell directory is
    the whole of what it needs.
    """

    path: Path
    argv_log: Path
    shell_dir: Path

    @property
    def calls(self) -> list[str]:
        if not self.argv_log.is_file():
            return []
        return self.argv_log.read_text(encoding='utf-8').splitlines()

    def matching(self, needle: str) -> list[str]:
        return [call for call in self.calls if needle in call]


@pytest.fixture
def windows(tmp_path: Path) -> Windows:
    binaries = tmp_path / 'bin'
    binaries.mkdir()

    for name, body in (('powershell.exe', STUB_POWERSHELL), ('wslpath', STUB_WSLPATH)):
        stub = binaries / name
        stub.write_text(body)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    return Windows(path=binaries, argv_log=tmp_path / 'argv.log', shell_dir=SHELL_DIR)


def run(script: str, snippet: str, windows: Windows, *args: str, **environment: str) -> Shell:
    """Source one of the tools and run `snippet` against its functions.

    Sourcing runs neither `main` nor the WSL guard, which is what lets these run
    on Arch and macOS.
    """
    # environment last, so a test that needs to control PATH itself can.
    settings = {
        'PATH': f'{windows.path}{os.pathsep}{os.environ["PATH"]}',
        'ARGV_LOG': str(windows.argv_log),
        'SHELL_DIR': str(windows.shell_dir),
    }
    settings.update(environment)

    return shell_out(f'source "$1"; {snippet}', script, *args, **settings)


# ================================================================
# The Windows half
# ================================================================


def test_utf16_reply_reaches_bash_as_a_plain_string(windows: Windows) -> None:
    result = run(TOOL, 'powershell_out "anything"', windows, STUB_REPLY='hello')
    assert result.stdout.strip() == 'hello'


def test_the_windows_helpers_are_self_contained(windows: Windows) -> None:
    """They were briefly a library under `shell/host/wsl`, which every
    interactive shell sources — so `clean` and `report` would have landed in
    the shell's namespace and been parsed at every prompt."""
    result = run(TOOL, 'declare -F windows_can_elevate >/dev/null && echo found', windows)
    assert result.stdout.strip() == 'found'


def test_registry_query_carries_the_distro_and_the_pipeline_variable(windows: Windows) -> None:
    """`$_` is PowerShell's, and bash must not expand it on the way through.

    Expanded, the query becomes `.GetValue(...)` on nothing, matches no
    distribution, and returns an empty BasePath — which every caller here reads
    as "not on WSL" rather than as a bug.
    """
    run(TOOL, 'vhdx_windows_path', windows, STUB_BASE_PATH=BASE_PATH, WSL_DISTRO_NAME='Ubuntu-Work')

    registry = windows.matching('Lxss')
    assert registry, 'the registry lookup never reached powershell.exe'
    assert '$_.GetValue' in registry[0]
    assert 'Ubuntu-Work' in registry[0]


def test_extended_length_prefix_is_stripped(windows: Windows) -> None:
    """The registry answers `\\\\?\\C:\\...` and wslpath returns nothing for one."""
    result = run(TOOL, 'vhdx_windows_path', windows, STUB_BASE_PATH=DEVICE_PREFIX + BASE_PATH, WSL_DISTRO_NAME='Ubuntu')
    assert result.stdout.strip() == BASE_PATH + r'\ext4.vhdx'


def test_a_plain_base_path_is_left_alone(windows: Windows) -> None:
    result = run(TOOL, 'vhdx_windows_path', windows, STUB_BASE_PATH=BASE_PATH, WSL_DISTRO_NAME='Ubuntu')
    assert result.stdout.strip() == BASE_PATH + r'\ext4.vhdx'


def test_no_distro_name_is_a_failure_not_an_empty_path(windows: Windows) -> None:
    """An empty answer would be handed to diskpart as `select vdisk file=""`."""
    result = run(TOOL, 'vhdx_windows_path', windows, STUB_BASE_PATH=BASE_PATH, WSL_DISTRO_NAME='')
    assert not result.ok
    assert result.stdout.strip() == ''


def test_an_unregistered_distro_is_a_failure(windows: Windows) -> None:
    result = run(TOOL, 'vhdx_windows_path', windows, STUB_BASE_PATH='', WSL_DISTRO_NAME='Ubuntu')
    assert not result.ok


# ================================================================
# Elevation
# ================================================================


def test_an_account_in_the_administrators_group_can_elevate(windows: Windows) -> None:
    result = run(TOOL, 'windows_can_elevate && echo yes', windows, STUB_ELEVATE='yes')
    assert result.stdout.strip() == 'yes'


def test_a_standard_account_cannot(windows: Windows) -> None:
    result = run(TOOL, 'windows_can_elevate || echo no', windows, STUB_ELEVATE='no')
    assert result.stdout.strip() == 'no'


def test_the_probe_asks_for_group_membership_not_the_current_token(windows: Windows) -> None:
    """IsInRole answers false for an admin running unelevated, which is every
    admin, so a probe built on it reports every machine as unable to elevate."""
    run(TOOL, 'windows_can_elevate || true', windows, STUB_ELEVATE='no')

    probe = windows.matching('S-1-5-32-544')
    assert probe, 'the elevation probe never ran'
    assert 'IsInRole' not in probe[0]


def test_compact_refuses_before_prompting_an_account_that_cannot_elevate(windows: Windows) -> None:
    """Start-Process -Verb RunAs on a standard account raises a UAC box asking
    for somebody else's password, which is a worse answer than saying so."""
    result = run(TOOL, 'compact', windows, STUB_ELEVATE='no', STUB_BASE_PATH=BASE_PATH, WSL_DISTRO_NAME='Ubuntu')

    assert not result.ok
    assert 'rebuild' in result.stdout
    assert not windows.matching('Start-Process')


# ================================================================
# The handoff
# ================================================================


def test_the_elevated_launch_asks_for_runas(windows: Windows) -> None:
    run(TOOL, 'launch_detached "C:\\\\tmp\\\\x.ps1" RunAs -Vhdx "C:\\\\d.vhdx"', windows)

    launch = windows.matching('Start-Process')
    assert launch
    assert '-Verb RunAs' in launch[0]


def test_the_unelevated_launch_does_not(windows: Windows) -> None:
    """rebuild needs no administrator, and asking for one anyway would put a UAC
    prompt in front of the only route a standard account has."""
    run(TOOL, 'launch_detached "C:\\\\tmp\\\\x.ps1" "" -Distro Ubuntu', windows)

    launch = windows.matching('Start-Process')
    assert launch
    assert '-Verb' not in launch[0]


def test_values_reach_the_script_as_quoted_parameters(windows: Windows) -> None:
    """A Windows path is backslashes and braces. PowerShell single-quoted
    literals take it as written, which is why nothing here escapes them."""
    run(TOOL, 'launch_detached "C:\\\\tmp\\\\x.ps1" "" -Archive "D:\\\\my backups\\\\U.tar"', windows)

    launch = windows.matching('Start-Process')[0]
    assert "'-Archive','D:\\my backups\\U.tar'" in launch


def test_an_embedded_quote_is_doubled_not_dropped(windows: Windows) -> None:
    """A single quote would otherwise close the literal and turn the rest of the
    path into PowerShell code."""
    run(TOOL, """launch_detached "C:\\\\x.ps1" "" -Archive "D:\\\\O'Brien\\\\U.tar" """, windows)

    launch = windows.matching('Start-Process')[0]
    assert "D:\\O''Brien\\U.tar" in launch


# ================================================================
# The diskpart script
# ================================================================


def generated(tmp_path: Path, windows: Windows, writer: str) -> str:
    destination = tmp_path / 'generated.ps1'
    run(TOOL, f'{writer} "$2"', windows, str(destination))
    return destination.read_text(encoding='utf-8')


def test_the_disk_is_attached_read_only_before_it_is_compacted(tmp_path: Path, windows: Windows) -> None:
    """Order is the whole safety property. Attaching writable hands an elevated
    diskpart a mounted ext4 filesystem it does not understand."""
    written = generated(tmp_path, windows, 'write_compact_script')

    attach = written.index('attach vdisk readonly')
    compact = written.index('compact vdisk')
    detach = written.index('detach vdisk')
    assert attach < compact < detach


def test_wsl_is_shut_down_before_diskpart_runs(tmp_path: Path, windows: Windows) -> None:
    """diskpart cannot attach a vhdx the utility VM still holds open."""
    written = generated(tmp_path, windows, 'write_compact_script')
    assert written.index('wsl.exe --shutdown') < written.index('diskpart.exe')


def test_the_shutdown_is_followed_by_a_wait(tmp_path: Path, windows: Windows) -> None:
    """WSL keeps the VM alive for about eight seconds after the last shell exits."""
    written = generated(tmp_path, windows, 'write_compact_script')
    assert 'Start-Sleep' in written


def test_the_compact_script_takes_its_path_as_a_parameter(tmp_path: Path, windows: Windows) -> None:
    """Interpolating it into the body is what silently produced an empty path
    once already, and diskpart reads `file=""` as a valid selection of nothing."""
    written = generated(tmp_path, windows, 'write_compact_script')

    assert 'param([Parameter(Mandatory = $true)][string]$Vhdx)' in written
    assert 'select vdisk file="$Vhdx"' in written


# ================================================================
# The rebuild script
# ================================================================


def test_free_space_is_checked_before_anything_is_shut_down(tmp_path: Path, windows: Windows) -> None:
    """A truncated archive is caught by the verification below, but only after
    the export has already spent the time. Refusing up front is cheaper."""
    written = generated(tmp_path, windows, 'write_rebuild_script')
    assert written.index('$drive.Free -lt $Needed') < written.index('wsl.exe --shutdown')


def test_the_archive_is_read_back_before_the_distro_is_destroyed(tmp_path: Path, windows: Windows) -> None:
    """An export that exits 0 and leaves an unreadable archive is the failure
    that matters, because the next step cannot be undone."""
    written = generated(tmp_path, windows, 'write_rebuild_script')
    assert written.index('tar.exe -tf') < written.index('wsl.exe --unregister')


def test_the_import_follows_the_unregister(tmp_path: Path, windows: Windows) -> None:
    written = generated(tmp_path, windows, 'write_rebuild_script')
    assert written.index('wsl.exe --unregister') < written.index('wsl.exe --import')


def test_the_recovery_command_is_printed_before_the_risky_step(tmp_path: Path, windows: Windows) -> None:
    """It has to be on screen already if the import is what fails."""
    written = generated(tmp_path, windows, 'write_rebuild_script')
    assert written.index("'  wsl --import '") < written.index('wsl.exe --unregister')


def test_the_archive_is_never_deleted(tmp_path: Path, windows: Windows) -> None:
    """It is the only copy of the filesystem between the two steps, and the only
    backup afterwards. Removing it is the caller's decision, once satisfied."""
    written = generated(tmp_path, windows, 'write_rebuild_script')
    assert 'Remove-Item' not in written


def test_neither_generated_script_carries_a_bash_expansion(tmp_path: Path, windows: Windows) -> None:
    """Both heredocs are quoted. An unquoted one turned PowerShell's backtick
    escapes into bash command substitution and expanded a misspelled variable to
    nothing, and neither shows up anywhere except in the generated file."""
    for writer in ('write_compact_script', 'write_rebuild_script'):
        written = generated(tmp_path, windows, writer)
        assert '`' not in written
        assert '$(' not in written


# ================================================================
# The default user
# ================================================================


def test_the_default_user_is_pinned_when_wsl_conf_does_not_say(tmp_path: Path, windows: Windows) -> None:
    """An imported distro has no Store launcher, so it starts as root unless the
    setting is written down first. That reads as a broken rebuild."""
    conf = tmp_path / 'wsl.conf'
    conf.write_text('[boot]\nsystemd=true\n')

    run(TOOL, 'pin_default_user', windows, WSL_CONF=str(conf))

    written = conf.read_text(encoding='utf-8')
    assert '[user]' in written
    assert 'default=' in written


def test_an_existing_default_user_is_left_alone(tmp_path: Path, windows: Windows) -> None:
    conf = tmp_path / 'wsl.conf'
    conf.write_text('[user]\ndefault=chris\n')

    run(TOOL, 'pin_default_user', windows, WSL_CONF=str(conf))

    assert conf.read_text(encoding='utf-8').count('default=') == 1


# ================================================================
# Sparse mode stays refused
# ================================================================


def test_the_tool_does_not_offer_to_enable_sparse_mode() -> None:
    """`--set-sparse true` has been gated behind --allow-unsafe since WSL 2.5.6
    after ext4 corruption reports, and a sparse vhdx cannot be compacted at all.
    It is the obvious-looking fix for exactly this problem, so the refusal is
    pinned rather than left to the comment explaining it."""
    code = uncommented(TOOL)
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
        STUB_PROFILE=str(profile),
        DOTFILES_DIR=str(REPO),
    )


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    """Stands in for %USERPROFILE%. The stub answers a Linux path, which the
    wslpath stub passes through unchanged."""
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


def test_help_works_off_wsl(windows: Windows) -> None:
    """The WSL guard sits after help, so `--help` answers on any machine. A tool
    that refuses to describe itself where it does not run is undiscoverable from
    the machine you would read about it on."""
    result = shell_out('bash "$1" --help', TOOL, SHELL_DIR=str(windows.shell_dir))
    assert result.ok
    assert 'Usage:' in result.stdout


def test_a_verb_refuses_off_wsl(windows: Windows) -> None:
    result = shell_out('bash "$1" status', TOOL, SHELL_DIR=str(windows.shell_dir))
    assert not result.ok


def test_the_wslconfig_installer_skips_off_wsl(windows: Windows, profile: Path) -> None:
    """A skip, not a failure: it is called from a task that also runs on the
    machines this repo deploys to that are not WSL."""
    result = shell_out(
        'bash "$1"',
        WSLCONFIG,
        PATH=f'{windows.path}{os.pathsep}{os.environ["PATH"]}',
        ARGV_LOG=str(windows.argv_log),
        STUB_PROFILE=str(profile),
        DOTFILES_DIR=str(REPO),
    )
    assert result.ok
    assert 'Not in WSL' in result.stdout
    assert not (profile / '.wslconfig').exists()


def test_a_bare_invocation_lists_the_verbs(windows: Windows) -> None:
    """The reason this is one binary instead of a wsl-* family. It is reached for
    a few times a year, so the common case is not knowing what it can do — and a
    bare run that did the work, or errored, would answer the wrong question."""
    result = shell_out('bash "$1"', TOOL, SHELL_DIR=str(windows.shell_dir))

    assert result.ok
    for verb in ('status', 'doctor', 'clean', 'compact', 'rebuild', 'bench', 'processes', 'mounts', 'startup'):
        assert verb in result.stdout


def test_every_listed_verb_is_dispatchable(windows: Windows) -> None:
    """A verb in the help that main does not accept is the failure this file
    exists to catch, and it is invisible until someone types it."""
    listed = shell_out('bash "$1"', TOOL, SHELL_DIR=str(windows.shell_dir)).stdout
    accepted = uncommented(TOOL)

    # The allowlist is spread over more than one case line, so match on the arm
    # rather than on where it happens to be split today.
    dispatch = ' '.join(line for line in accepted if 'verb="$1"' in line)
    assert dispatch, 'the verb allowlist moved'

    for verb in ('status', 'doctor', 'clean', 'compact', 'rebuild', 'bench', 'processes', 'mounts', 'startup'):
        assert verb in listed, f'{verb} is dispatchable but unlisted'
        assert verb in dispatch, f'{verb} is listed but not dispatchable'


# ================================================================
# The diagnostics
# ================================================================


def note_for(windows: Windows, fstype: str) -> Shell:
    return run(TOOL, f'mount_note {fstype}', windows)


def test_a_native_filesystem_reads_as_fast(windows: Windows) -> None:
    assert 'native' in note_for(windows, 'ext4').stdout


def test_every_windows_backed_filesystem_reads_as_slow(windows: Windows) -> None:
    """drvfs is the name on older builds, virtiofs on newer ones, and 9p is what
    mount reports for both on some. Classifying one and missing the others would
    report the interop mount as native on exactly the machines that have it."""
    for fstype in ('9p', 'drvfs', 'virtiofs'):
        assert 'crosses to Windows' in note_for(windows, fstype).stdout


def test_an_unrecognised_filesystem_is_skipped_not_guessed(windows: Windows) -> None:
    """proc, sysfs, cgroup and tmpfs are most of the mount table and none of them
    answer where a file lives. A default arm would print thirty rows of noise."""
    result = note_for(windows, 'proc')
    assert not result.ok
    assert result.stdout.strip() == ''


def test_the_note_column_holds_no_multibyte_characters(windows: Windows) -> None:
    """printf pads by bytes. An em-dash inside a width-padded column shifts every
    row that contains one, which is how this table first rendered."""
    for fstype in ('ext4', '9p', 'cifs', 'overlay'):
        note = note_for(windows, fstype).stdout.strip()
        assert note.isascii(), f'{fstype} note is not ascii: {note!r}'


def test_the_interop_entries_are_stripped_from_a_path(windows: Windows) -> None:
    result = run(
        TOOL,
        'path_without_windows',
        windows,
        PATH=f'/usr/bin:/mnt/c/Windows:/home/me/.local/bin:/mnt/c/Program Files{os.pathsep}{os.environ["PATH"]}',
    )

    assert '/mnt/c/Windows' not in result.stdout
    assert '/mnt/c/Program Files' not in result.stdout
    assert '/usr/bin' in result.stdout
    assert '/home/me/.local/bin' in result.stdout


def test_stripping_keeps_the_path_a_colon_list(windows: Windows) -> None:
    """paste -sd re-joins the lines. Without the trailing `-` it reads a file
    named for the delimiter instead, and the result is empty."""
    result = run(TOOL, 'path_without_windows', windows, PATH='/usr/bin:/mnt/c/Windows:/bin')
    assert result.stdout.strip() == '/usr/bin:/bin'


def test_a_path_with_no_interop_entries_survives_intact(windows: Windows) -> None:
    result = run(TOOL, 'path_without_windows', windows, PATH='/usr/bin:/bin')
    assert result.stdout.strip() == '/usr/bin:/bin'


def test_the_timer_answers_in_whole_milliseconds(windows: Windows) -> None:
    result = run(TOOL, 'median_ms true', windows)
    assert result.stdout.strip().isdigit()


def test_the_timer_takes_the_median_of_three(windows: Windows) -> None:
    """A single sample is whatever else the machine was doing, and a mean is
    whatever the worst sample was."""
    result = run(TOOL, 'median_ms sleep 0.05', windows)
    assert 40 <= int(result.stdout.strip()) <= 200
