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
    EMPLOYER = 'employer'


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

    def as_dict(self) -> dict[str, str]:
        return {field.name: str(getattr(self, field.name)) for field in dc.fields(self)}


PLATFORM_BUNDLES: dict[str, Coordinates] = {
    'macos': Coordinates(PackageManager.BREW, OSFamily.DARWIN, DisplayStack.AQUA, Host.NATIVE, NetworkTrust.FLEET, Capacity.WORKSTATION),
    'archlinux': Coordinates(
        PackageManager.PACMAN, OSFamily.LINUX, DisplayStack.WAYLAND, Host.NATIVE, NetworkTrust.FLEET, Capacity.WORKSTATION
    ),
    'wsl': Coordinates(PackageManager.APT, OSFamily.LINUX, DisplayStack.NONE, Host.WSL, NetworkTrust.EMPLOYER, Capacity.WORKSTATION),
    'linux': Coordinates(PackageManager.APT, OSFamily.LINUX, DisplayStack.NONE, Host.NATIVE, NetworkTrust.FLEET, Capacity.SERVER),
}
"""The four platform strings, written out as the tuples they always were.

A manifest resolves through this table or declares `coordinates:` directly —
never both, because two spellings of the same fact is the drift this exists to
end.
"""

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
    overlay for a whole install. But a mismatch is worth *reporting*, which
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
