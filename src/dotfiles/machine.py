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
how a wsl manifest once deployed the linux shell layer for a whole install.
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
from dotfiles import settings
from dotfiles.catalog import DeclarationIssue
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode


class MachineError(Refusal):
    """A manifest declares something no reader can consume, or omits something one needs."""

    def __init__(self, issues: tuple[DeclarationIssue, ...]) -> None:
        self.issues = issues
        super().__init__('\n'.join(str(issue) for issue in issues))


class NoSuchMachine(MachineError):
    """No manifest carries this name, which is a typo rather than a fault.

    Split from its parent because the two ask different things of a caller. A
    name nothing declares is worth retrying with a different name, and every
    front door already answers that with `ExitCode.USAGE` — `_manifest_path` in
    `commands/machines.py` has done so for `machines show` all along, by testing
    `exists()` before loading rather than by catching anything.

    A manifest that will not parse is not retryable, so it stays `MachineError`
    and `ExitCode.ISSUE`. Reporting it as a typo would send a caller looking for
    a misspelling in a name that is spelt correctly.

    A subclass rather than a second exception, so the five sites that catch
    `MachineError` keep catching both and only the ones that care split it out.

    `code` is what that split was always for, and until it existed the difference
    lived in whichever caller happened to remember it.
    """

    code = ExitCode.USAGE


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
    the Go toolchain because it declared `go_tools`, which is why no manifest
    boolean gates it."""


SUBSCRIPTIONS: dict[str, tuple[Spelling, str]] = {
    'system_packages': (Spelling.TIER, 'system_packages'),
    'github_releases': (Spelling.NAMES, 'github_releases'),
    'custom_installers': (Spelling.NAMES, 'custom_installers'),
    'cargo_packages': (Spelling.NAMES, 'cargo_packages'),
    'winget_packages': (Spelling.NAMES, 'winget_packages'),
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

FEATURES = ('nvim_plugins', 'configure_zsh', 'deploy_by_copy')
"""Manifest booleans that gate work with no catalog section behind it — lazy.nvim
bootstrapping itself, making zsh the login shell, and deploying the three trees as
copies on a machine whose admin policy refuses to create a symlink.

`deploy_by_copy` swaps a mechanism rather than adding work, which is the one that
does not read like the others. It is here because the question it answers has the
same shape: a boolean about this machine that no catalog section speaks for.
`resources/symlinks.py` holds what it costs."""

RETIRED_KEYS = {
    key: 'install is derived from the corresponding name-list now (go_tools non-empty → Go)' for key in ('go', 'rust', 'nvm', 'uv', 'tenv')
}
"""Retired runtime-gate booleans, named rather than merely unknown, because the
replacement is not guessable from the error."""


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

    An internal hostname and an account name are not the repo's to know, so it
    declares that a machine needs one and `check` reports it missing. `path` is
    empty for a value and set for a file, which is the only difference between
    the two and not worth a second class.
    """

    name: str
    description: str
    path: str
    consumers: tuple[str, ...]
    narrowing: Mapping[str, str]
    restore: str = ''
    """How to get this one back, where safekeep is not the answer.

    Every entry here is restored from a snapshot except the one that says where
    the snapshots are: `~/.config/safekeep/` on a machine with no
    backup yet cannot be restored from the backup it configures. The default
    covers the rest, and an entry overrides it only when it is genuinely wrong.
    """

    tags: tuple[str, ...] = ()
    """Restore scenarios, for the safekeep block `machines requirements` emits.

    Additive rather than the whole set: everything here is tagged `dotfiles` by
    the emitter, because `safekeep restore --tag dotfiles` wanting exactly this
    register is the point. A declared tag says which *other* scenario an entry
    also belongs to, and only earns its place where that is not obvious.
    """

    file_must_exist: bool = False
    """This value names a file, and the file has to be there.

    The value half of `requires_values`, and the same rule: a declaration records
    what has to be true, never only that something was answered. A machine can
    name `$HOMELAB_HOSTS_JSON` and have no inventory at that path, and today the
    register reports it satisfied — the answer arrived, so nothing looks further.

    Worth checking here even though every consumer refuses loudly, because the
    entry's own declaration says why: the consumers are outside this repo and fail
    at deploy time, and a `dotfiles check` that fails now is earlier than that.
    """

    requires_values: tuple[str, ...] = ()
    """Values that must be set before this file can do its job.

    Presence is not readiness. A file entry records that a machine needs a file,
    and a check that only asks whether it is there reports converged on a machine
    where the file exists and the variable its contents read was never set — so
    the one mechanism built to make a missing value loud goes quiet at the moment
    the value is present and useless. A declared requirement states what has to be
    true, not only that the thing exists.

    On the declaration and never in the file, because such a file is machine-local
    by construction — it is declared precisely because the repo must not hold it,
    so it cannot state its own preconditions anywhere the repo can read them.

    Resolved against *this machine's* register, so a name it does not declare is a
    precondition that does not apply rather than one that failed. `local.sh` is
    required on both halves of one laptop and only the WSL half declares
    `WINDOWS_USER`; the Windows half is native, reaches no `/mnt/c`, and needs
    nothing.
    """

    @property
    def is_file(self) -> bool:
        return bool(self.path)

    @property
    def declared_names(self) -> tuple[str, ...]:
        """Every name that has to resolve before this entry can be measured.

        A value is its own name; a file is named by whatever variables its path
        references, which is usually one and may be none. What this is for is
        letting a caller collect the whole register's names and answer them in one
        reading, rather than each entry reaching for the rungs as it is reached.
        """
        return settings.variables(self.path) if self.is_file else (self.name,)

    def resolved_path(self, resolved: settings.Resolved) -> str:
        """`path` with $VARIABLES and ~ resolved, for touching the filesystem here.

        A declared entry may name its own location through a variable this repo also
        declares, for a file whose path differs per machine and which the repo must
        never carry. Read as a literal, `check` reports a missing file named `$NAME`,
        which is the failure this exists to avoid.

        Answered from a snapshot rather than resolved here, and that is what makes it
        a method: the rungs include a config file, so an entry that resolved itself
        would be a read at every point of use and two entries in one report could
        disagree about what the machine says.

        Only for *this* machine, and only where the filesystem is actually touched.
        Everything that shows the path shows the declaration instead: a listing and the
        ~/.env comment block are more useful naming the variable, and the safekeep block
        is generated for a named machine and pasted on it — expanding there would write
        the generating machine's answer into another machine's config.
        """
        return resolved.expand(self.path)

    def is_present(self, resolved: settings.Resolved) -> bool:
        """Whether the declared file is actually on this machine.

        A declaration nothing answers keeps its `$NAME` literal, and no file is named
        that — so an unanswered entry reports absent rather than resolving to
        something plausible. A set-but-empty variable takes the same road, because
        `settings.resolve` skips a falsy rung instead of substituting it.
        """
        return Path(self.resolved_path(resolved)).exists()


@dc.dataclass(frozen=True, slots=True)
class Machine:
    """One machine's whole declaration."""

    name: str
    coordinates: axes.Coordinates
    subscriptions: Mapping[str, Subscription]
    features: frozenset[str]
    flags: Mapping[str, str]
    requirements: tuple[Requirement, ...]
    source: Path

    auth: tuple[str, ...] = ()
    """The tools this machine has to be able to log in to.

    Named for the manifest key it reads, as `features` and `flags` are. A second
    word for it — `logins` — is what `machines show --json` emitted while the key
    stayed `auth:`, so a reader who found the field and went to edit the manifest
    grepped for a key that was not there.

    Its own field rather than a `SUBSCRIPTIONS` entry, because there is no catalog
    section behind it — the same shape as `FEATURES`. Half the roster is installed
    outside this repo entirely (`aws` through a custom installer, `bbkt` by hand on
    one machine), so a field on a `packages.yml` row could never reach them.

    Which tools, and nothing about how each is asked: `resources/auth.py` holds the
    probes and a test asserts the two sets match in both directions.
    """

    @property
    def platform_label(self) -> str:
        """Which platform label this machine carries, derived from its coordinates.

        Derived rather than stored, because a manifest is free not to spell it. One
        declaring `coordinates:` names no platform at all, so a stored field is
        empty on exactly the machine whose coordinates say `windows` — and that
        empty answer is reached from three sides at once: `machines show` prints
        `custom coordinates`, `as_dict` emits an empty `platform`, and `applies_to`
        compares a narrowing against it, so a `platform: windows` narrowing cannot
        match the only machine it could mean.

        Deriving closes that structurally rather than by keeping two fields in
        step, and costs nothing on the bundle path: the label is a function of the
        tuple, a manifest naming both a platform and coordinates is refused, and
        `tests/cli/test_apply.py` asserts the round trip is exact for every bundle.

        What it does give up is the ability to say *how the manifest was written*.
        That is a property of the file rather than of the machine, `machines show
        --raw` answers it exactly, and this field is named for the platform rather
        than for the declaration.
        """
        return axes.platform_label(self.coordinates)

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
            'auth': list(self.auth),
        }


def names(root: Path | None = None) -> list[str]:
    """Every manifest in the repo, read from disk and listed nowhere."""
    directory = (root / 'install' / 'manifests') if root else paths.MANIFESTS_DIR
    return sorted(path.stem for path in directory.glob('*.yml')) if directory.is_dir() else []


def manifest_path(name: str, root: Path | None = None) -> Path:
    """Where this machine's manifest is, refusing a name nothing declares.

    One function raising one error, so a caller wanting the *file* and a caller
    wanting the *machine* cannot describe a missing name two ways. `machines show
    --raw` and `machines edit` want the path and never parse it, which is the whole
    reason a second answer to "is there a manifest called this" is available to be
    worded differently — a different key word for the list, and silence about where
    it looked. The alternative is two messages kept in step by hand.
    """
    install = (root / 'install') if root else paths.INSTALL_DIR
    source = install / 'manifests' / f'{name}.yml'
    if not source.is_file():
        available = ', '.join(names(root)) or 'none found'
        raise NoSuchMachine((DeclarationIssue(name, f'has no manifest at {source}. Available: {available}'),))
    return source


def load(name: str, root: Path | None = None) -> Machine:
    """Read one manifest and `flags.yml`, or raise with everything wrong in it."""
    install = (root / 'install') if root else paths.INSTALL_DIR
    source = manifest_path(name, root)

    declared = yaml.safe_load(source.read_text()) or {}
    flags_file = install / 'flags.yml'
    flag_data = yaml.safe_load(flags_file.read_text()) if flags_file.is_file() else {}

    issues: list[DeclarationIssue] = []
    if not isinstance(declared, Mapping):
        raise MachineError((DeclarationIssue(name, f'is a {type(declared).__name__} where a mapping is expected'),))

    issues.extend(_unknown_keys(name, declared))
    coordinates = _coordinates(name, declared, issues)
    flags = _flags(declared, flag_data or {}, issues)
    auth = _auth(name, declared, issues)

    if issues:
        raise MachineError(tuple(issues))

    return Machine(
        name=declared.get('machine') or name,
        coordinates=coordinates,
        subscriptions={section: _subscribe(section, declared) for section in catalog.SECTIONS},
        features=frozenset(feature for feature in FEATURES if declared.get(feature) is True),
        flags=flags,
        requirements=_requirements(flag_data or {}, declared.get('machine') or name, coordinates),
        source=source,
        auth=auth,
    )


def applies_to(narrowing: Mapping[str, str], machine_name: str, coordinates: axes.Coordinates) -> bool:
    """Whether a `flags.yml` declaration narrows to this machine.

    Every coordinate is a narrowing key, not just `platform:`. That is the fix
    for `WINDOWS_USER` being declared `platform: wsl` and therefore invisible to
    an Arch-on-WSL box: as `host: wsl` the distro stops mattering. The mechanism
    that exists to make a missing value loud was itself keyed on the wrong axis.

    The label is derived here rather than passed in, which is what stops the same
    fault reappearing on the `platform:` key itself. A caller handed the label the
    manifest happened to spell, and a manifest declaring `coordinates:` spells
    none — so a `platform:` narrowing was compared against `''` and could match
    nothing on exactly the machines that need naming most.
    """
    if narrowing.get('machine', machine_name) != machine_name:
        return False
    for axis in axes.AXES:
        wanted = narrowing.get(axis)
        if wanted is not None and wanted != str(getattr(coordinates, axis)):
            return False
    # `platform:` stays legal and means the whole bundle.
    label = axes.platform_label(coordinates)
    return narrowing.get('platform', label) == label


def _auth(name: str, declared: Mapping[str, Any], issues: list[DeclarationIssue]) -> tuple[str, ...]:
    """The tools this machine names in `auth:`, or none where it names none.

    Absent is the ordinary case rather than a fault. A machine that names nothing
    here is a machine nothing asks about, which is the right answer for a box
    whose whole job is to be SSHed into.
    """
    value = declared.get('auth')
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(tool, str) for tool in value):
        issues.append(DeclarationIssue(name, f'declares auth as a {type(value).__name__}, where a list of tool names is expected'))
        return ()
    return tuple(value)


def _unknown_keys(name: str, declared: Mapping[str, Any]) -> list[DeclarationIssue]:
    known = {'machine', 'platform', 'coordinates', 'flags', 'auth', *FEATURES, *(key for _, key in SUBSCRIPTIONS.values() if key)}
    return [
        DeclarationIssue(
            name, f'declares {key} — {RETIRED_KEYS[key]}' if key in RETIRED_KEYS else f'declares {key}, which no reader consumes'
        )
        for key in sorted(set(declared) - known)
    ]


def _coordinates(name: str, declared: Mapping[str, Any], issues: list[DeclarationIssue]) -> axes.Coordinates:
    """Resolve the platform bundle, or the axes a manifest names directly.

    Never both: two spellings of the same fact is the drift the split exists to
    end, and a manifest carrying both would leave a reader unable to say which
    one the install used.

    Only the tuple is returned, never the label beside it. `coordinates.platform_label`
    derives that from the tuple, and a copy returned alongside is a second answer
    free to disagree with the first — `Machine.platform_label` holds what that
    costs.
    """
    label = declared.get('platform')
    overrides = declared.get('coordinates') or {}

    if label is None and not overrides:
        issues.append(DeclarationIssue(name, 'declares neither a platform nor coordinates, so nothing knows what kind of machine it is'))
        return axes.PLATFORM_BUNDLES['linux']

    if label is not None and label not in axes.PLATFORM_BUNDLES:
        issues.append(DeclarationIssue(name, f'declares platform {label!r}. Known: {", ".join(axes.PLATFORM_BUNDLES)}'))
        return axes.PLATFORM_BUNDLES['linux']

    base = axes.PLATFORM_BUNDLES[label] if label else None
    if base is not None and not overrides:
        return base

    if base is not None and overrides:
        issues.append(DeclarationIssue(name, 'declares both a platform and coordinates; a fact spelled twice is a fact that can disagree'))
        return base

    return _from_axes(name, overrides, issues)


def _from_axes(name: str, overrides: Mapping[str, Any], issues: list[DeclarationIssue]) -> axes.Coordinates:
    """Build coordinates a manifest names directly, one axis at a time.

    A rejected value still yields *something*, because the caller raises on the
    collected issues and a second exception here would hide the rest of them.
    """
    values: dict[str, Any] = {}
    substituted = False
    for axis, enum_type in axes.AXIS_TYPES.items():
        raw = overrides.get(axis)
        if raw is None:
            issues.append(DeclarationIssue(name, f'declares coordinates without {axis}; every axis is required once one is named'))
        elif raw not in set(enum_type):
            issues.append(DeclarationIssue(name, f'declares {axis} {raw!r}. Known: {", ".join(enum_type)}'))
        substituted = substituted or raw not in set(enum_type)
        values[axis] = enum_type(raw) if raw in set(enum_type) else next(iter(enum_type))

    for unknown in sorted(set(overrides) - set(axes.AXES)):
        issues.append(DeclarationIssue(name, f'declares coordinate {unknown!r}, which is not one of the axes'))

    # Only where the manifest named every axis: a substituted placeholder makes
    # an arbitrary tuple, and reporting that it cannot exist would bury the real
    # problem under a contradiction the manifest never wrote.
    point = axes.Coordinates(**values)
    if not substituted:
        issues.extend(DeclarationIssue(name, f'declares a machine that cannot exist: {problem}') for problem in axes.incoherent(point))
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


def _flags(declared: Mapping[str, Any], flag_data: Mapping[str, Any], issues: list[DeclarationIssue]) -> dict[str, str]:
    """Every declared flag's value for this machine: its override, else its default.

    Rendered as the shell reads it, because `~/.env` is the only consumer and a
    Python bool spelled `True` is not a value `flag_enabled` understands.
    """
    overrides = declared.get('flags') or {}
    resolved = {}
    for flag in _declared_flags(flag_data):
        resolved[flag.name] = _shell_value(overrides.get(flag.name, flag.default))
    for unknown in sorted(set(overrides) - set(resolved)):
        issues.append(DeclarationIssue(declared.get('machine', ''), f'overrides {unknown}, which flags.yml does not declare'))
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


def _requirements(flag_data: Mapping[str, Any], machine_name: str, coordinates: axes.Coordinates) -> tuple[Requirement, ...]:
    found = []
    for key in ('required', 'required_files'):
        for entry in flag_data.get(key) or ():
            narrowing = {axis: str(entry[axis]) for axis in (*axes.AXES, 'machine', 'platform') if axis in entry}
            if not applies_to(narrowing, machine_name, coordinates):
                continue
            found.append(
                Requirement(
                    name=entry.get('name', ''),
                    description=entry.get('description', ''),
                    path=str(entry.get('path', '')),
                    consumers=tuple(entry.get('consumers') or ()),
                    narrowing=narrowing,
                    restore=str(entry.get('restore', '')),
                    tags=tuple(str(tag) for tag in entry.get('tags') or ()),
                    requires_values=tuple(str(value) for value in entry.get('requires_values') or ()),
                    file_must_exist=bool(entry.get('file_must_exist', False)),
                )
            )
    return tuple(found)
