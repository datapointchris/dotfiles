"""The Windows tools a WSL machine puts on its Git Bash PATH, and how they get there.

Two install paths reach the same eight binaries: winget where the network allows
it, and a bundle of GitHub release assets where it does not. **They are declared
once, here.** Nothing else keeps the two channels in step, so a tool declared for
one and not the other installs online and is missing from the bundle, or the
reverse, with nothing reporting either.

`packages.yml` deliberately does not describe these. Its sections carry the Linux
and macOS asset patterns, and these repos name their Windows assets differently
enough that neither can be derived from the other — `eza` publishes
`eza.exe_x86_64-pc-windows-gnu.zip` where its Linux row says nothing of the sort.

Everything here that touches Windows goes through `/mnt/c` or `cmd.exe`, so it
runs only under WSL. `windows_home` is the guard: off WSL there is no Windows user
to ask about, and it says so rather than inventing a path.
"""

from __future__ import annotations

import dataclasses as dc
import shutil
import tarfile
import tempfile
from pathlib import Path

from dotfiles import effects
from dotfiles.refusal import Refusal


@dc.dataclass(frozen=True, slots=True)
class Tool:
    """One binary, and both ways of getting it.

    `winget` and `repo` are the same tool through two channels rather than two
    tools: winget ids are not GitHub coordinates, which is why both are written
    out instead of one being derived.
    """

    name: str
    repo: str
    asset: str
    exe: str
    winget: str


# Placeholders are packages.yml's, not a second vocabulary — {version} is the tag,
# {version_num} the tag without its leading v.
TOOLS: tuple[Tool, ...] = (
    Tool('zoxide', 'ajeetdsouza/zoxide', 'zoxide-{version_num}-x86_64-pc-windows-msvc.zip', 'zoxide.exe', 'ajeetdsouza.zoxide'),
    Tool('eza', 'eza-community/eza', 'eza.exe_x86_64-pc-windows-gnu.zip', 'eza.exe', 'eza-community.eza'),
    Tool('fzf', 'junegunn/fzf', 'fzf-{version_num}-windows_amd64.zip', 'fzf.exe', 'junegunn.fzf'),
    Tool('jq', 'jqlang/jq', 'jq-windows-amd64.exe', 'jq.exe', 'jqlang.jq'),
    Tool('bat', 'sharkdp/bat', 'bat-{version}-x86_64-pc-windows-msvc.zip', 'bat.exe', 'sharkdp.bat'),
    Tool('rg', 'BurntSushi/ripgrep', 'ripgrep-{version}-x86_64-pc-windows-msvc.zip', 'rg.exe', 'BurntSushi.ripgrep'),
    Tool('fd', 'sharkdp/fd', 'fd-{version}-x86_64-pc-windows-msvc.zip', 'fd.exe', 'sharkdp.fd'),
    Tool('delta', 'dandavison/delta', 'delta-{version}-x86_64-pc-windows-msvc.zip', 'delta.exe', 'dandavison.delta'),
)

WINGET_PACKAGES = 'AppData/Local/Microsoft/WinGet/Packages'
"""Where winget unpacks a package, relative to the Windows home.

Copied out of rather than added to PATH: the Git Bash side gets one PATH entry,
`~/.local/bin`, and eight package directories with version-stamped names is what
that entry exists to avoid.
"""


class WindowsSideError(Refusal):
    """A failure to report with a message rather than a traceback.

    Not `WindowsError`: that is a builtin, an `OSError` alias defined on Windows,
    and shadowing it is at its most confusing in the module whose subject is
    Windows.
    """


def under_wsl() -> bool:
    """Whether there is a Windows side to reach at all.

    `/proc/version` rather than an environment variable, because the marker has to
    survive `sudo` and a login shell that sets nothing.
    """
    try:
        return any(marker in Path('/proc/version').read_text() for marker in ('Microsoft', 'WSL'))
    except OSError:
        return False


def windows_home() -> Path:
    """The Windows user's home under `/mnt/c`, asked of Windows.

    `cmd.exe /c echo %USERNAME%` rather than the WSL username or a hardcoded
    account: the two differ on this fleet, and the employee id that the Windows
    account is named after is exactly what does not go in this repo.
    """
    if not under_wsl():
        raise WindowsSideError('not running under WSL, so there is no Windows home to find')

    answered = effects.run(('cmd.exe', '/c', 'echo %USERNAME%'), output=effects.Output.QUIET)
    user = answered.stdout.strip().strip('\r')
    if not answered.ok or not user:
        raise WindowsSideError('could not ask Windows for its username')

    home = Path('/mnt/c/Users') / user
    if not home.is_dir():
        raise WindowsSideError(f'Windows home does not exist at {home}')
    return home


def destination(home: Path | None = None) -> Path:
    """The one directory Git Bash puts on its PATH."""
    return (home or windows_home()) / '.local' / 'bin'


def installed(into: Path) -> tuple[str, ...]:
    """Which declared tools are actually on the Windows PATH directory.

    The measurement `windows check` reports and the reason it can exist at all:
    the answer is a set of filenames in one directory, which needs no winget and
    no network.
    """
    return tuple(tool.name for tool in TOOLS if (into / tool.exe).is_file())


def missing(into: Path) -> tuple[str, ...]:
    present = set(installed(into))
    return tuple(tool.name for tool in TOOLS if tool.name not in present)


def install_via_winget(into: Path) -> tuple[str, ...]:
    """Install every tool through winget, then copy its binary into `into`.

    Returns the tools whose binary could not be found afterwards. winget exits
    non-zero for "already at latest version", which is not a failure and is why
    the install's own status is ignored — what decides the outcome is whether the
    binary landed, which the copy below measures directly.
    """
    into.mkdir(parents=True, exist_ok=True)
    home = windows_home()

    # From the Windows home, or cmd.exe warns about a UNC path it cannot use as a
    # working directory and falls back to C:\Windows — the WSL cwd it inherits is
    # `\\wsl$\...` and is not a path Windows can be *in*.
    for tool in TOOLS:
        effects.run(
            ('cmd.exe', '/c', f'winget install --accept-package-agreements --accept-source-agreements {tool.winget}'),
            cwd=home,
            output=effects.Output.STREAM,
        )

    return tuple(tool.name for tool in TOOLS if not _copy_winget_binary(home, into, tool))


def _copy_winget_binary(home: Path, into: Path, tool: Tool) -> bool:
    """Find one winget-installed exe and copy it, or say it is not there.

    The package directory carries a version in its name, so it is matched by
    prefix; some packages then nest the exe a level down, which is the recursive
    search below and not a fallback for a mistake.
    """
    packages = home / WINGET_PACKAGES
    if not packages.is_dir():
        return False

    for candidate in sorted(packages.glob(f'{tool.winget}*')):
        direct = candidate / tool.exe
        if direct.is_file():
            shutil.copy2(direct, into / tool.exe)
            return True
        for nested in sorted(candidate.rglob(tool.exe)):
            if nested.is_file():
                shutil.copy2(nested, into / tool.exe)
                return True
    return False


def install_from_bundle(source: Path, into: Path) -> tuple[str, ...]:
    """Copy the bundle's binaries into `into`, and report what it did not carry.

    A directory is used where it is given, and an archive is extracted to a
    temporary one — the same two shapes `windows_bundle` can produce, so a bundle
    can be inspected before it is installed.
    """
    if source.is_dir():
        return _copy_bundle(source, into)
    if not source.is_file():
        raise WindowsSideError(f'bundle not found: {source}')

    with tempfile.TemporaryDirectory() as workspace:
        try:
            with tarfile.open(source) as archive:
                archive.extractall(workspace, filter='data')
        except (tarfile.TarError, OSError) as unreadable:
            raise WindowsSideError(f'could not extract bundle archive {source}: {unreadable}') from unreadable
        return _copy_bundle(Path(workspace), into)


def _copy_bundle(bundle: Path, into: Path) -> tuple[str, ...]:
    """Copy what the bundle holds, measured against what is declared.

    Every `.exe` is copied rather than only the declared ones, so a bundle built
    from a newer declaration still installs in full — but what is *reported* is
    the declared set, because a tool this machine expects and the bundle lacks is
    the failure worth naming.
    """
    executables = sorted(bundle.glob('*.exe'))
    if not executables:
        raise WindowsSideError(f'no .exe files in {bundle}')

    into.mkdir(parents=True, exist_ok=True)
    for executable in executables:
        shutil.copy2(executable, into / executable.name)

    carried = {executable.name for executable in executables}
    return tuple(tool.name for tool in TOOLS if tool.exe not in carried)
