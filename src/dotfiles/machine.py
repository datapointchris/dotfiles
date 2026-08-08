"""A machine manifest and `flags.yml`, read once into one object.

Two things live here that were spread across a shell script and six near-identical
Python functions.

**What the machine subscribes to.** `filter_go_packages_by_manifest` and its five
siblings are the same three branches — `true` means all, an empty list means
none, a list means membership — written once per section, diverging on which
`--format` each supported. One `Subscription` says it once, and says the third
state out loud: a section the manifest never mentions is *undeclared*, which is
not the same as declared-empty. No manifest names `macos_casks` or `mas_apps`,
and collapsing the two states stops macOS installing casks at all.

**What the machine is.** `MACHINE` selects the manifest and everything else is
derived from it — the platform, the coordinates, every flag's value. Nothing is
detected, because a fresh machine has no `~/.env` to read and guessing instead is
how a wsl manifest once deployed the linux shell overlay for a whole install.
"""

from __future__ import annotations

import dataclasses as dc
import enum
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from dotfiles import catalog
from dotfiles import coordinates as axes
from dotfiles import paths
from dotfiles.catalog import Issue


class MachineError(Exception):
    """A manifest declares something no reader can consume, or omits something one needs."""

    def __init__(self, issues: tuple[Issue, ...]) -> None:
        self.issues = issues
        super().__init__('\n'.join(str(issue) for issue in issues))


class Coverage(enum.Enum):
    ALL = enum.auto()
    NAMED = enum.auto()
    NONE = enum.auto()


class Spelling(enum.Enum):
    """How a manifest expresses its interest in one catalog section."""

    NAMES = enum.auto()
    """A list of names; `true` for all of them, absent or empty for none."""

    TIER = enum.auto()
    """A tier word. `core` is the base every machine gets including a minimal
    server; `workstation` is everything. `true` still means workstation, because
    manifests predating the tier said so that way."""

    GATE = enum.auto()
    """A boolean over the whole section — there is nothing to name individually."""

    WHOLESALE = enum.auto()
    """Not in the manifest at all: the catalog is the declaration, and the
    coordinates decide whether this machine can have any of it."""

    DERIVED = enum.auto()
    """Not subscribed to at all: something else's presence decides. A machine gets
    the Go toolchain because it declared `go_tools`, which is why the manifest
    booleans that used to gate it — `go:`, `rust:`, `nvm:` — were removed."""


SUBSCRIPTIONS: dict[str, tuple[Spelling, str]] = {
    'system_packages': (Spelling.TIER, 'system_packages'),
    'github_releases': (Spelling.NAMES, 'github_releases'),
    'custom_installers': (Spelling.NAMES, 'custom_installers'),
    'cargo_packages': (Spelling.NAMES, 'cargo_packages'),
    'go_tools': (Spelling.NAMES, 'go_tools'),
    'npm_globals': (Spelling.NAMES, 'npm_globals'),
    'uv_tools': (Spelling.NAMES, 'uv_tools'),
    'git_uv_tools': (Spelling.NAMES, 'git_uv_tools'),
    'shell_plugins': (Spelling.GATE, 'shell_plugins'),
    'tmux_plugins': (Spelling.GATE, 'tmux_plugins'),
    'yazi_plugins': (Spelling.GATE, 'yazi_plugins'),
    'flatpak_apps': (Spelling.GATE, 'flatpak'),
    'macos_casks': (Spelling.WHOLESALE, ''),
    'mas_apps': (Spelling.WHOLESALE, ''),
    'zen_extensions': (Spelling.WHOLESALE, ''),
    'runtimes': (Spelling.DERIVED, ''),
}
"""Every catalog section, and the manifest key that speaks for it.

The two names differ where the key gates something wider than one section:
`flatpak: true` is about the runtime as much as the apps. A section missing from
this table is a section no machine can ever subscribe to, so the load asserts
coverage rather than defaulting."""

FEATURES = ('nvim_plugins', 'configure_zsh')
"""Manifest booleans that gate work with no catalog section behind it — lazy.nvim
bootstrapping itself, and making zsh the login shell."""

RETIRED_KEYS = {
    key: 'install is derived from the corresponding name-list now (go_tools non-empty → Go)' for key in ('go', 'rust', 'nvm', 'uv', 'tenv')
}
"""Runtime-gate booleans removed in Phase 1.6. Named rather than merely unknown,
because the replacement is not guessable from the error."""


@dc.dataclass(frozen=True, slots=True)
class Subscription:
    """What one manifest says about one catalog section."""

    section: str
    coverage: Coverage
    declared: bool
    names: frozenset[str] = frozenset()
    tier: str = ''

    def wants(self, entry: catalog.Entry) -> bool:
        if self.coverage is Coverage.NONE:
            return False
        if self.coverage is Coverage.NAMED:
            return entry.name in self.names
        if self.tier == 'core':
            return isinstance(entry, catalog.SystemPackage) and entry.tier == 'core'
        return True


@dc.dataclass(frozen=True, slots=True)
class Flag:
    """One declared on/off switch, and where it is read."""

    name: str
    description: str
    default: bool
    consumers: tuple[str, ...]


@dc.dataclass(frozen=True, slots=True)
class Requirement:
    """A machine-local value or file the repo declares and never contains.

    An employer's hostname and an account name are not the repo's to know, so it
    declares that a machine needs one and `check` reports it missing. `path` is
    empty for a value and set for a file, which is the only difference between
    the two and not worth a second class.
    """

    name: str
    description: str
    path: str
    consumers: tuple[str, ...]
    narrowing: Mapping[str, str]

    @property
    def is_file(self) -> bool:
        return bool(self.path)


@dc.dataclass(frozen=True, slots=True)
class Machine:
    """One machine's whole declaration."""

    name: str
    coordinates: axes.Coordinates
    platform_label: str
    subscriptions: Mapping[str, Subscription]
    features: frozenset[str]
    flags: Mapping[str, str]
    requirements: tuple[Requirement, ...]
    source: Path

    def wants(self, feature: str) -> bool:
        return feature in self.features

    def subscription(self, section: str) -> Subscription:
        return self.subscriptions[section]

    @property
    def required_values(self) -> tuple[Requirement, ...]:
        return tuple(entry for entry in self.requirements if not entry.is_file)

    @property
    def required_files(self) -> tuple[Requirement, ...]:
        return tuple(entry for entry in self.requirements if entry.is_file)

    def as_dict(self) -> dict[str, Any]:
        return {
            'machine': self.name,
            'platform': self.platform_label,
            'coordinates': self.coordinates.as_dict(),
            'features': sorted(self.features),
            'flags': dict(self.flags),
        }


def names(root: Path | None = None) -> list[str]:
    """Every manifest in the repo, read from disk and listed nowhere."""
    directory = (root / 'install' / 'manifests') if root else paths.MANIFESTS_DIR
    return sorted(path.stem for path in directory.glob('*.yml')) if directory.is_dir() else []


def load(name: str, root: Path | None = None) -> Machine:
    """Read one manifest and `flags.yml`, or raise with everything wrong in it."""
    install = (root / 'install') if root else paths.INSTALL_DIR
    source = install / 'manifests' / f'{name}.yml'
    if not source.is_file():
        available = ', '.join(names(root)) or 'none found'
        raise MachineError((Issue(name, f'has no manifest at {source}. Available: {available}'),))

    declared = yaml.safe_load(source.read_text()) or {}
    flags_file = install / 'flags.yml'
    flag_data = yaml.safe_load(flags_file.read_text()) if flags_file.is_file() else {}

    issues: list[Issue] = []
    if not isinstance(declared, Mapping):
        raise MachineError((Issue(name, f'is a {type(declared).__name__} where a mapping is expected'),))

    issues.extend(_unknown_keys(name, declared))
    coordinates, label = _coordinates(name, declared, issues)
    flags = _flags(declared, flag_data or {}, issues)

    if issues:
        raise MachineError(tuple(issues))

    return Machine(
        name=declared.get('machine') or name,
        coordinates=coordinates,
        platform_label=label,
        subscriptions={section: _subscribe(section, declared) for section in catalog.SECTIONS},
        features=frozenset(feature for feature in FEATURES if declared.get(feature) is True),
        flags=flags,
        requirements=_requirements(flag_data or {}, declared.get('machine') or name, coordinates, label),
        source=source,
    )


def applies_to(narrowing: Mapping[str, str], machine_name: str, coordinates: axes.Coordinates, platform_label: str) -> bool:
    """Whether a `flags.yml` declaration narrows to this machine.

    Every coordinate is a narrowing key, not just `platform:`. That is the fix
    for `WINDOWS_USER` being declared `platform: wsl` and therefore invisible to
    an Arch-on-WSL box: as `host: wsl` the distro stops mattering. The mechanism
    that exists to make a missing value loud was itself keyed on the wrong axis.
    """
    if narrowing.get('machine', machine_name) != machine_name:
        return False
    for axis in axes.AXES:
        wanted = narrowing.get(axis)
        if wanted is not None and wanted != str(getattr(coordinates, axis)):
            return False
    # `platform:` stays legal and means the whole bundle.
    return narrowing.get('platform', platform_label) == platform_label


def _unknown_keys(name: str, declared: Mapping[str, Any]) -> list[Issue]:
    known = {'machine', 'platform', 'coordinates', 'flags', *FEATURES, *(key for _, key in SUBSCRIPTIONS.values() if key)}
    return [
        Issue(name, f'declares {key} — {RETIRED_KEYS[key]}' if key in RETIRED_KEYS else f'declares {key}, which no reader consumes')
        for key in sorted(set(declared) - known)
    ]


def _coordinates(name: str, declared: Mapping[str, Any], issues: list[Issue]) -> tuple[axes.Coordinates, str]:
    """Resolve the platform bundle, or the axes a manifest names directly.

    Never both: two spellings of the same fact is the drift the split exists to
    end, and a manifest carrying both would leave a reader unable to say which
    one the install used.
    """
    label = declared.get('platform')
    overrides = declared.get('coordinates') or {}

    if label is None and not overrides:
        issues.append(Issue(name, 'declares neither a platform nor coordinates, so nothing knows what kind of machine it is'))
        return axes.PLATFORM_BUNDLES['linux'], ''

    if label is not None and label not in axes.PLATFORM_BUNDLES:
        issues.append(Issue(name, f'declares platform {label!r}. Known: {", ".join(axes.PLATFORM_BUNDLES)}'))
        return axes.PLATFORM_BUNDLES['linux'], str(label)

    base = axes.PLATFORM_BUNDLES[label] if label else None
    if base is not None and not overrides:
        return base, str(label)

    if base is not None and overrides:
        issues.append(Issue(name, 'declares both a platform and coordinates; a fact spelled twice is a fact that can disagree'))
        return base, str(label)

    return _from_axes(name, overrides, issues), ''


def _from_axes(name: str, overrides: Mapping[str, Any], issues: list[Issue]) -> axes.Coordinates:
    """Build coordinates a manifest names directly, one axis at a time.

    A rejected value still yields *something*, because the caller raises on the
    collected issues and a second exception here would hide the rest of them.
    """
    values: dict[str, Any] = {}
    substituted = False
    for axis, enum_type in axes.AXIS_TYPES.items():
        raw = overrides.get(axis)
        if raw is None:
            issues.append(Issue(name, f'declares coordinates without {axis}; every axis is required once one is named'))
        elif raw not in set(enum_type):
            issues.append(Issue(name, f'declares {axis} {raw!r}. Known: {", ".join(enum_type)}'))
        substituted = substituted or raw not in set(enum_type)
        values[axis] = enum_type(raw) if raw in set(enum_type) else next(iter(enum_type))

    for unknown in sorted(set(overrides) - set(axes.AXES)):
        issues.append(Issue(name, f'declares coordinate {unknown!r}, which is not one of the axes'))

    # Only where the manifest named every axis: a substituted placeholder makes
    # an arbitrary tuple, and reporting that it cannot exist would bury the real
    # problem under a contradiction the manifest never wrote.
    point = axes.Coordinates(**values)
    if not substituted:
        issues.extend(Issue(name, f'declares a machine that cannot exist: {problem}') for problem in axes.incoherent(point))
    return point


def _subscribe(section: str, declared: Mapping[str, Any]) -> Subscription:
    spelling, key = SUBSCRIPTIONS[section]

    if spelling is Spelling.WHOLESALE:
        return Subscription(section, Coverage.ALL, declared=False)

    if spelling is Spelling.DERIVED:
        return Subscription(section, Coverage.NONE, declared=False)

    if key not in declared:
        return Subscription(section, Coverage.NONE, declared=False)

    value = declared[key]

    if spelling is Spelling.GATE:
        return Subscription(section, Coverage.ALL if value is True else Coverage.NONE, declared=True)

    if spelling is Spelling.TIER:
        if value is True:
            return Subscription(section, Coverage.ALL, declared=True, tier='workstation')
        if not value:
            return Subscription(section, Coverage.NONE, declared=True)
        return Subscription(section, Coverage.ALL, declared=True, tier=str(value))

    if value is True:
        return Subscription(section, Coverage.ALL, declared=True)
    if not value:
        return Subscription(section, Coverage.NONE, declared=True)
    return Subscription(section, Coverage.NAMED, declared=True, names=frozenset(value))


def _flags(declared: Mapping[str, Any], flag_data: Mapping[str, Any], issues: list[Issue]) -> dict[str, str]:
    """Every declared flag's value for this machine: its override, else its default.

    Rendered as the shell reads it, because `~/.env` is the only consumer and a
    Python bool spelled `True` is not a value `flag_enabled` understands.
    """
    overrides = declared.get('flags') or {}
    resolved = {}
    for flag in _declared_flags(flag_data):
        resolved[flag.name] = _shell_value(overrides.get(flag.name, flag.default))
    for unknown in sorted(set(overrides) - set(resolved)):
        issues.append(Issue(declared.get('machine', ''), f'overrides {unknown}, which flags.yml does not declare'))
    return resolved


def _declared_flags(flag_data: Mapping[str, Any]) -> tuple[Flag, ...]:
    return tuple(
        Flag(
            name=entry['name'],
            description=entry.get('description', ''),
            default=bool(entry.get('default', True)),
            consumers=tuple(entry.get('consumers') or ()),
        )
        for entry in flag_data.get('flags') or ()
    )


def _shell_value(value: Any) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def _requirements(
    flag_data: Mapping[str, Any],
    machine_name: str,
    coordinates: axes.Coordinates,
    platform_label: str,
) -> tuple[Requirement, ...]:
    found = []
    for key in ('required', 'required_files'):
        for entry in flag_data.get(key) or ():
            narrowing = {axis: str(entry[axis]) for axis in (*axes.AXES, 'machine', 'platform') if axis in entry}
            if not applies_to(narrowing, machine_name, coordinates, platform_label):
                continue
            found.append(
                Requirement(
                    name=entry.get('name', ''),
                    description=entry.get('description', ''),
                    path=str(entry.get('path', '')),
                    consumers=tuple(entry.get('consumers') or ()),
                    narrowing=narrowing,
                )
            )
    return tuple(found)


def declared_flags(root: Path | None = None) -> tuple[Flag, ...]:
    """Every flag the repo declares, machine-independent."""
    install = (root / 'install') if root else paths.INSTALL_DIR
    flags_file = install / 'flags.yml'
    return _declared_flags(yaml.safe_load(flags_file.read_text()) if flags_file.is_file() else {})
