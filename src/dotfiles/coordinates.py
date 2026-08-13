"""The six axes a machine actually varies along, and the four points named today.

`PLATFORM` is not an axis. It is a *fused point* — package manager, OS family,
display stack, host and capacity collapsed into one string — which is why
Arch-on-WSL is inexpressible: it needs pacman from `archlinux` and the WSL host
from `wsl`, and no single string carries both. A Ubuntu desktop is the same
problem from the other side, costing a third apt installer and 19 duplicated
Wayland files despite every one of its coordinates already existing.
`.planning/machine-axes.md` carries the measurement.

The label survives the split. `archlinux` stays a legal thing for a manifest to
declare and means exactly one row of `PLATFORM_BUNDLES` — Bazel's correction,
which kept the platform name as a convenience bundle over the constraint tuple.
What changes is that code asking *one* coordinate stops having to ask for the
whole point.
"""

from __future__ import annotations

import dataclasses as dc
import enum
import os
import platform
import shutil
from pathlib import Path


class PackageManager(enum.StrEnum):
    APT = 'apt'
    PACMAN = 'pacman'
    BREW = 'brew'


class OSFamily(enum.StrEnum):
    DARWIN = 'darwin'
    LINUX = 'linux'


class DisplayStack(enum.StrEnum):
    AQUA = 'aqua'
    WAYLAND = 'wayland'
    NONE = 'none'


class Host(enum.StrEnum):
    NATIVE = 'native'
    WSL = 'wsl'


class NetworkTrust(enum.StrEnum):
    FLEET = 'fleet'
    NONFLEET = 'nonfleet'


class Capacity(enum.StrEnum):
    WORKSTATION = 'workstation'
    SERVER = 'server'


INSTALLER_FAMILIES: dict[PackageManager, tuple[str, ...]] = {
    PackageManager.APT: ('apt',),
    PackageManager.PACMAN: ('pacman', 'aur'),
    PackageManager.BREW: ('brew', 'cask', 'mas'),
}
"""A package manager selects a *family* of installers, not one.

Reading `pacman` as a single installer drops the five `aur:` entries from
archlinux-personal; reading `brew` as one drops all 21 casks and 12 Mac App Store
apps from macos-personal. Both machines would install and neither would say
anything was missing.
"""


@dc.dataclass(frozen=True, slots=True)
class Coordinates:
    package_manager: PackageManager
    os_family: OSFamily
    display_stack: DisplayStack
    host: Host
    network_trust: NetworkTrust
    capacity: Capacity

    @property
    def installers(self) -> tuple[str, ...]:
        return INSTALLER_FAMILIES[self.package_manager]

    @property
    def directories(self) -> tuple[str, ...]:
        """The `<axis>/<value>` directories this machine selects, in axis order.

        One per axis, always — a machine is at exactly one point on each. Which
        of them exist on disk is a separate question, and most do not: an axis
        earns a directory only when something differs along it.

        Named for what it is rather than for what a tree does with it, because
        the three trees do different things. `shell/` **layers** them: every one
        that exists is sourced, additively. `configs/` and `apps/` hold
        **variants**: one file wins and nothing merges. The same tuple feeds
        both, so it can be neither word.
        """
        return tuple(f'{directory}/{getattr(self, axis)}' for axis, directory in AXIS_DIRS.items())

    def as_dict(self) -> dict[str, str]:
        return {field.name: str(getattr(self, field.name)) for field in dc.fields(self)}


def incoherent(point: Coordinates) -> tuple[str, ...]:
    """Combinations no machine can be, each with the reason it cannot.

    Six independent axes is what makes a fifth machine cheap; it is also what
    lets a manifest name a point that does not exist. `platform:` could not — it
    was four hand-written tuples — so nothing has ever had to check this, and a
    manifest declaring `coordinates:` directly is new surface.

    Deliberately only the four that are *impossible*, not the ones that are
    merely unused. Homebrew on Linux is a real thing nobody here runs, and
    forbidding it would be inventing a constraint rather than recording one.
    """
    problems = []
    if point.os_family is OSFamily.DARWIN:
        if point.package_manager is not PackageManager.BREW:
            problems.append(f'{point.package_manager} is not a macOS package manager')
        if point.host is Host.WSL:
            problems.append('wsl hosts Linux; there is no macOS inside it')
        if point.display_stack is DisplayStack.WAYLAND:
            problems.append('wayland is a Linux display stack; macOS draws on aqua')
    elif point.display_stack is DisplayStack.AQUA:
        problems.append('aqua is the macOS display stack')
    return tuple(problems)


PLATFORM_BUNDLES: dict[str, Coordinates] = {
    'macos': Coordinates(PackageManager.BREW, OSFamily.DARWIN, DisplayStack.AQUA, Host.NATIVE, NetworkTrust.FLEET, Capacity.WORKSTATION),
    'archlinux': Coordinates(
        PackageManager.PACMAN, OSFamily.LINUX, DisplayStack.WAYLAND, Host.NATIVE, NetworkTrust.FLEET, Capacity.WORKSTATION
    ),
    'wsl': Coordinates(PackageManager.APT, OSFamily.LINUX, DisplayStack.NONE, Host.WSL, NetworkTrust.NONFLEET, Capacity.WORKSTATION),
    'linux': Coordinates(PackageManager.APT, OSFamily.LINUX, DisplayStack.NONE, Host.NATIVE, NetworkTrust.FLEET, Capacity.SERVER),
}
"""The four platform strings, written out as the tuples they always were.

A manifest resolves through this table or declares `coordinates:` directly —
never both, because two spellings of the same fact is the drift this exists to
end.
"""


def platform_label(declared: Coordinates) -> str:
    """Which of the four labels these coordinates carry.

    Keyed on the package manager, with apt split by host, which is the whole of
    what the four labels distinguish. It selects nothing that deploys: a label is
    printed in a run's header and matched by a `platform:` narrowing.

    Derived rather than read off `Machine.platform_label`, because a manifest may
    declare `coordinates:` *instead of* `platform:` and then carries no label to
    read. Arch-on-WSL therefore lands on the pacman answer, which is the point of
    deriving it: the tuple it needs exists while the fused string has no row for
    it.
    """
    if declared.package_manager is PackageManager.BREW:
        return 'macos'
    if declared.package_manager is PackageManager.PACMAN:
        return 'archlinux'
    return 'wsl' if declared.host is Host.WSL else 'linux'


AXIS_TYPES: dict[str, type[enum.StrEnum]] = {
    'package_manager': PackageManager,
    'os_family': OSFamily,
    'display_stack': DisplayStack,
    'host': Host,
    'network_trust': NetworkTrust,
    'capacity': Capacity,
}
"""Named rather than read off `Coordinates.__annotations__`, which
`from __future__ import annotations` leaves as strings to be resolved by name."""

AXES = tuple(AXIS_TYPES)

AXIS_DIRS: dict[str, str] = {
    'package_manager': 'pkg',
    'os_family': 'os',
    'display_stack': 'display',
    'host': 'host',
    'network_trust': 'trust',
    'capacity': 'capacity',
}
"""What each axis is called when it names a directory in `configs/`, `shell/`
and `apps/`.

Short rather than the field name, because these appear in every deployed path
and `package_manager/pacman/.config/…` reads worse than `pkg/pacman/…` for no
extra information. The mapping is a design constant — six axes, fixed — so it is
written once here and read everywhere else.
"""


def directory_names() -> frozenset[str]:
    """Every `<axis>/<value>` directory a tree may legally contain.

    The tree validator's whole vocabulary: anything under `configs/`, `shell/` or
    `apps/` that is neither `common` nor one of these is a typo that would
    otherwise deploy to nobody and say nothing.
    """
    return frozenset(f'{directory}/{value}' for axis, directory in AXIS_DIRS.items() for value in AXIS_TYPES[axis])


class Arch(enum.StrEnum):
    """The CPU, which is measured and never declared.

    Deliberately **not** a seventh entry in `Coordinates`. That tuple is what a
    manifest says a machine is, and no manifest says what processor it runs on —
    the CPU is a fact about the box, in the same family as `Detected` below.
    Release assets are the only thing that needs it, and they need it paired with
    the OS, which is what `Target` is.
    """

    X86_64 = 'x86_64'
    ARM64 = 'arm64'


@dc.dataclass(frozen=True, slots=True)
class Target:
    """What a release asset is named for: an OS and a CPU, together.

    Together because neither answers alone. macOS is the one platform serving two
    architectures, so a tool spelling only one of them is invisible from whichever
    Mac happens to run a check — which is the exact fusion `PLATFORM` hid.
    """

    os_family: OSFamily
    arch: Arch

    @property
    def is_darwin(self) -> bool:
        return self.os_family is OSFamily.DARWIN

    @property
    def is_arm(self) -> bool:
        return self.arch is Arch.ARM64


def target_for(declared: Coordinates) -> Target:
    """What this machine's release assets are named for.

    The OS is taken from the manifest and the CPU is measured, which is the split
    the two halves are: a fresh machine has no `~/.env` to read its platform from
    and detecting it instead is how a wsl manifest once deployed the linux shell
    layer for a whole install — while no manifest anywhere says what processor
    a box has.
    """
    return Target(declared.os_family, detect_arch())


def detect_arch(machine: str | None = None) -> Arch:
    """`uname -m`, reduced to the two the fleet runs.

    Anything unrecognised answers x86_64 rather than raising: the fleet is four
    machines and two architectures, and a release installer that refused to guess
    would refuse to run at all on a box nobody has yet.
    """
    name = (machine or platform.machine()).lower()
    return Arch.ARM64 if name in {'arm64', 'aarch64'} else Arch.X86_64


@dc.dataclass(frozen=True, slots=True)
class Detected:
    """The three coordinates the box can answer about itself.

    Declare what cannot be detected, detect the rest. `display_stack` is knowable
    only at runtime — `$WAYLAND_DISPLAY` exists after an install, not during one —
    and `capacity` and `network_trust` are intentions that nothing on the machine
    knows.
    """

    os_family: OSFamily
    package_manager: PackageManager | None
    host: Host


def detect(root: Path = Path('/')) -> Detected:
    """Measure what this machine can say about itself.

    `root` exists for the tests: every probe is a file or a binary, so pointing
    them at a fixture is the whole seam and nothing in this module is patched.
    """
    family = OSFamily.DARWIN if platform.system() == 'Darwin' else OSFamily.LINUX
    return Detected(os_family=family, package_manager=_package_manager(family), host=_host(root))


def _package_manager(family: OSFamily) -> PackageManager | None:
    if family is OSFamily.DARWIN:
        return PackageManager.BREW if shutil.which('brew') else None
    for manager in (PackageManager.PACMAN, PackageManager.APT):
        if shutil.which(str(manager)):
            return manager
    return None


def _host(root: Path) -> Host:
    """WSL, by the two signals that survive a container and a systemd unit.

    `$WSL_DISTRO_NAME` is absent under any process WSL did not start, which is
    why `/proc/version` is read as well rather than instead.
    """
    if os.environ.get('WSL_DISTRO_NAME'):
        return Host.WSL
    version = root / 'proc' / 'version'
    if version.is_file() and 'microsoft' in version.read_text().lower():
        return Host.WSL
    return Host.NATIVE


def disagreements(declared: Coordinates, detected: Detected) -> list[str]:
    """Where the manifest and the machine disagree on something measurable.

    The declaration always wins — a fresh machine has no `~/.env` and detecting
    the platform instead is how a wsl manifest once deployed the linux shell
    layer for a whole install. But a mismatch is worth *reporting*, which
    nothing does today: a manifest saying pacman on an apt box currently installs
    nothing and says nothing.
    """
    found = []
    if declared.os_family is not detected.os_family:
        found.append(f'manifest declares {declared.os_family}, this machine is {detected.os_family}')
    if detected.package_manager is not None and declared.package_manager is not detected.package_manager:
        found.append(f'manifest declares {declared.package_manager}, this machine has {detected.package_manager}')
    if declared.host is not detected.host:
        found.append(f'manifest declares host {declared.host}, this machine is {detected.host}')
    return found
