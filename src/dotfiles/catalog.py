"""`packages.yml`, parsed once into typed rows.

One dataclass per section, rather than one generic row plus a table of
`required` / `forbidden` / `id_field` rules. The table existed because nothing
else pinned a section's shape, and it only ever described the fields someone
remembered to describe: `install_script` sat on all 23 `github_releases` entries
naming scripts that half of them no longer had, and `binary_pattern` drifted into
naming assets that no longer existed. Both were invisible for the same reason —
no reader consumed them, and nothing said one had to.

A field on a dataclass is either read by its provider or visibly unused, and a
key that is not a field is an error at load time rather than decoration. That is
the whole argument for the rewrite: the section's schema and the section's reader
stop being two documents that can disagree.

Everything is collected before anything is raised. A caller fixing `packages.yml`
wants every problem in it, not the first one — which is also what lets
`dotfiles machines check` render this as a report instead of a stack trace.
"""

from __future__ import annotations

import dataclasses as dc
import enum
import typing
from collections.abc import Iterator
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from typing import ClassVar
from typing import Self

import yaml

from dotfiles import paths


@dc.dataclass(frozen=True, slots=True)
class Issue:
    """One thing wrong with the declaration, named where it is."""

    section: str
    message: str

    def __str__(self) -> str:
        return f'{self.section}: {self.message}'


class CatalogError(Exception):
    """`packages.yml` declares something no reader can consume."""

    def __init__(self, issues: tuple[Issue, ...]) -> None:
        self.issues = issues
        super().__init__('\n'.join(str(issue) for issue in issues))


class EntryError(ValueError):
    """One row cannot be built. Caught by `load`, which reports it as an Issue."""


class Structure(enum.Enum):
    """How a section is spelled in the YAML.

    `GROUPED` sections nest their rows under editorial category keys
    (`npm_globals.language_servers`); the categories organise the file and are
    read by nothing, so they are flattened away here rather than carried as a
    field no provider consumes. `KEYED` sections are a mapping whose key is the
    row's name.
    """

    LIST = enum.auto()
    GROUPED = enum.auto()
    KEYED = enum.auto()


UNREAD_KEYS: dict[str, str] = {
    'binary_pattern': 'the asset URL is built in code for this section, so a pattern here goes unread and drifts',
    'install_dir': 'only tmux_plugins declares one; a release binary uses binary_link',
    'install_script': 'the installer is found by name at install/common/<dir>/<name>.sh',
    'build_method': 'nothing branches on how upstream builds its release',
}
"""Keys that were carried for long enough to look like configuration.

An unknown key is an error either way; these get the reason attached, because
"unknown key" tells a reader what happened and not what to do instead. Each one
here was measured as read by nothing before it was removed.
"""

CONSTRAINTS = ('version', 'min_version', 'max_version')

GRANDFATHERED_CONSTRAINTS = frozenset(
    {
        ('github_releases', 'neovim', 'min_version'),
        ('github_releases', 'fzf', 'min_version'),
        # go.sh fetches whatever go.dev currently offers and never reads this floor.
        ('runtimes', 'go', 'min_version'),
    }
)
"""Floors that predate enforcement. All are satisfied, so they mislead nobody, and
naming them keeps the information alive for the resolver instead of deleting it to
silence a check."""

CHECKSUM_REQUIRED = 'required'
CHECKSUM_UNPUBLISHED = 'unpublished'
CHECKSUM_UNLISTED = 'unlisted'

CHECKSUM_STATES = frozenset({CHECKSUM_REQUIRED, CHECKSUM_UNPUBLISHED, CHECKSUM_UNLISTED})
"""What a release can be verified against, declared rather than discovered.

`required` is the default because the alternative default is silence: the shell
library it replaces let each installer set `CHECKSUM_REQUIRED=false` for itself,
and four of the eight that cannot verify never called the shared helper at all,
so they skipped verification without ever saying so. Naming the exception in the
declaration is what makes it countable, reviewable, and testable against what
upstream actually publishes — which `tests/install/test_release_urls.py` does,
failing in *both* directions so a project that starts publishing checksums stops
being an exception.

The two exceptions are separate values because they are separate upstream facts;
`github_release.Verification` carries the same distinction and says why.
"""


def owner_of(value: str) -> str | None:
    """The GitHub owner carried by a `repo`, `github_repo` or `package` field.

    Derived rather than tagged, per `data.md` § "Ownership is derived from data,
    never from a tag" — it is what `--owner` filters on, and it caught an entry
    the four hand-written tags had missed. The shapes disagree: `owner/name`, a
    clone URL, and a Go import path all appear.
    """
    path = value.split('://', 1)[-1].removesuffix('.git').strip('/')
    segments = [segment for segment in path.split('/') if segment]
    # A leading host (github.com) appears only in the URL and Go-import forms.
    if segments and '.' in segments[0]:
        segments = segments[1:]
    return segments[0] if segments else None


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class Entry:
    """One row of `packages.yml`. The subclass is the section's schema.

    The three version constraints sit here rather than on the sections that pin
    today, because any section could grow one and only its *provider* decides
    whether it means anything. `honoured_constraints` is that decision, declared
    beside the class whose installer reads it — so declaring a constraint where
    nothing honours it is an error rather than a silent no-op. Four such fields
    sat unread in `packages.yml` until a URL audit found them, one eight versions
    stale. `.planning/version-constraints.md` carries the vocabulary.
    """

    name: str
    description: str = ''
    tags: tuple[str, ...] = ()
    command: str = ''
    version: str = ''
    min_version: str = ''
    max_version: str = ''

    section: ClassVar[str]
    structure: ClassVar[Structure] = Structure.LIST
    honoured_constraints: ClassVar[tuple[str, ...]] = ()

    @property
    def executable(self) -> str:
        """The binary this entry puts on PATH.

        `command` is the override for a package whose binary is named differently
        — ripgrep ships rg, `@taplo/cli` ships taplo.
        """
        return self.command or self.name

    @property
    def owner(self) -> str | None:
        """The GitHub owner, or None for an entry sourced from a registry.

        npm, PyPI, apt/brew/pacman entries have no owner and correctly match
        nothing under `--owner`.
        """
        return None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        fields = {field.name: field for field in dc.fields(cls)}

        if unknown := sorted(set(raw) - set(fields)):
            named = ', '.join(f'{key} ({UNREAD_KEYS[key]})' if key in UNREAD_KEYS else key for key in unknown)
            raise EntryError(f'declares {named}, which no reader consumes')

        if missing := sorted(name for name, field in fields.items() if _is_required(field) and name not in raw):
            raise EntryError(f'is missing required field(s) {", ".join(missing)}')

        hints = _hints(cls)
        return cls(**{key: _typed(key, hints[key], value) for key, value in raw.items()})

    def problems(self) -> tuple[str, ...]:
        """Cross-field rules a single field cannot express."""
        found = []
        declared = [key for key in CONSTRAINTS if getattr(self, key)]

        for key in declared:
            if key not in self.honoured_constraints and (self.section, self.name, key) not in GRANDFATHERED_CONSTRAINTS:
                found.append(
                    f"declares '{key}', which nothing honours for {self.section}. Remove it, or make it real and "
                    f'widen honoured_constraints on the same class in the same change.'
                )
            if getattr(self, key).startswith('v') or '/' in getattr(self, key):
                found.append(
                    f"declares '{key}' as {getattr(self, key)!r}, which is a tag. Constraints are bare versions — "
                    f"resolving one to this tool's tag spelling is the resolver's job."
                )

        if self.version and (self.min_version or self.max_version):
            found.append("declares 'version', which pins exactly, beside a floor or ceiling describing a window nobody can predict")

        return tuple(found)


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class SystemPackage(Entry):
    """Installed by the OS package manager. The one section with a tier.

    A `core` entry goes on every machine including a minimal LXC server;
    untagged means workstation-only, so a heavy new package can never silently
    bloat a server. One list rather than parallel per-tier lists, which would
    drift.
    """

    section: ClassVar[str] = 'system_packages'

    tier: str = ''
    apt: str = ''
    pacman: str = ''
    brew: str = ''
    aur: str = ''

    def package_for(self, manager: str) -> str:
        """This package's name under one manager, or '' where it has none."""
        return getattr(self, manager, '')

    def problems(self) -> tuple[str, ...]:
        # `Entry.problems(self)` rather than `super()`: dataclass(slots=True)
        # rebuilds the class, leaving the zero-argument form's __class__ cell
        # pointing at the original and raising TypeError on every call.
        managers = ('apt', 'pacman', 'brew', 'aur')
        if any(self.package_for(manager) for manager in managers):
            return Entry.problems(self)
        return (f'names no package under any of {", ".join(managers)}, so no machine can install it', *Entry.problems(self))


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class GithubRelease(Entry):
    """A prebuilt binary from a GitHub release.

    The asset name is deliberately *not* here. It stays in code, because three of
    the 23 defeat any placeholder vocabulary — shellcheck needs aarch64-on-darwin
    and a `.tar.xz`, trivy needs `ARM64`/`64bit`, and zk spells its architecture
    per OS. Measured across all 23 and rejected twice; see
    `docs/architecture/github-release-installer.md` § "Why Not More Abstraction?".
    """

    section: ClassVar[str] = 'github_releases'
    honoured_constraints: ClassVar[tuple[str, ...]] = ('version',)

    repo: str
    binary_link: str = ''
    release_tag_prefix: str = ''
    requires_wsl_host: bool = False
    requires_github_auth: bool = False
    checksum: str = CHECKSUM_REQUIRED

    @property
    def executable(self) -> str:
        """neovim declares the full symlink it creates, so the name comes off its end."""
        if self.command:
            return self.command
        return Path(self.binary_link).name if self.binary_link else self.name

    @property
    def owner(self) -> str | None:
        return owner_of(self.repo)

    def problems(self) -> tuple[str, ...]:
        if self.checksum in CHECKSUM_STATES:
            return Entry.problems(self)
        allowed = ', '.join(sorted(CHECKSUM_STATES))
        return (f"declares 'checksum' as {self.checksum!r}, which is not one of {allowed}", *Entry.problems(self))


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class CustomInstaller(Entry):
    """A tool with its own distribution mechanism, wrapped by one script."""

    section: ClassVar[str] = 'custom_installers'

    source_type: str
    description: str
    repo: str = ''
    support_repo: str = ''
    assert_repo: str = ''
    url: str = ''
    install_url: str = ''
    installed_path: str = ''
    bundle_install_script: bool = False

    @property
    def owner(self) -> str | None:
        return owner_of(self.repo) if self.repo else None


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class CargoPackage(Entry):
    """A Rust CLI, installed by `cargo binstall` from its own release binaries.

    `linux_target` and `darwin_target` override the Rust target triple for tools
    whose assets are not named after it — fnm ships `fnm-linux.zip`.
    """

    section: ClassVar[str] = 'cargo_packages'

    github_repo: str = ''
    binary_pattern: str = ''
    linux_target: str = ''
    darwin_target: str = ''

    @property
    def owner(self) -> str | None:
        return owner_of(self.github_repo) if self.github_repo else None


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class GoTool(Entry):
    section: ClassVar[str] = 'go_tools'

    package: str
    github_repo: str = ''
    binary_pattern: str = ''

    @property
    def owner(self) -> str | None:
        return owner_of(self.github_repo) if self.github_repo else owner_of(self.package)


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class NpmGlobal(Entry):
    section: ClassVar[str] = 'npm_globals'
    structure: ClassVar[Structure] = Structure.GROUPED


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class UvTool(Entry):
    """A PyPI tool installed with `uv tool install`.

    `library_only` marks one pulled in for another tool's benefit — numpy for the
    Jupyter stack — which installs a directory and no console script, so nothing
    should look for it on PATH.
    """

    section: ClassVar[str] = 'uv_tools'
    structure: ClassVar[Structure] = Structure.GROUPED

    library_only: bool = False


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class GitUvTool(Entry):
    """A Python tool installed with `uv tool install` from a git repo.

    `tracks_branch` follows the default branch for a repo publishing no releases;
    everything else pins to the newest release tag, because an unpinned git
    install is the degraded state rather than the flexible one.
    """

    section: ClassVar[str] = 'git_uv_tools'

    repo: str
    tracks_branch: bool = False
    requires_github_auth: bool = False

    @property
    def owner(self) -> str | None:
        return owner_of(self.repo)


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class ShellPlugin(Entry):
    section: ClassVar[str] = 'shell_plugins'

    repo: str

    @property
    def owner(self) -> str | None:
        return owner_of(self.repo)


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class TmuxPlugin(Entry):
    section: ClassVar[str] = 'tmux_plugins'
    structure: ClassVar[Structure] = Structure.KEYED

    repo: str
    install_dir: str

    @property
    def owner(self) -> str | None:
        return owner_of(self.repo)


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class Runtime(Entry):
    """A language runtime, installed by its own version manager."""

    section: ClassVar[str] = 'runtimes'
    structure: ClassVar[Structure] = Structure.KEYED
    honoured_constraints: ClassVar[tuple[str, ...]] = ('version',)

    install_method: str
    repo: str = ''
    url: str = ''


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class MasApp(Entry):
    section: ClassVar[str] = 'mas_apps'

    id: int


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class MacosCask(Entry):
    section: ClassVar[str] = 'macos_casks'


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class FlatpakApp(Entry):
    section: ClassVar[str] = 'flatpak_apps'

    flatpak_id: str


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class ZenExtension(Entry):
    section: ClassVar[str] = 'zen_extensions'

    url: str


SECTION_CLASSES: tuple[type[Entry], ...] = (
    SystemPackage,
    Runtime,
    GithubRelease,
    CustomInstaller,
    CargoPackage,
    GoTool,
    NpmGlobal,
    UvTool,
    GitUvTool,
    ShellPlugin,
    TmuxPlugin,
    MasApp,
    MacosCask,
    FlatpakApp,
    ZenExtension,
)
"""In `packages.yml` order, which is what `packages list` and the run record render."""

SECTIONS: dict[str, type[Entry]] = {cls.section: cls for cls in SECTION_CLASSES}

BARE_SECTIONS = frozenset({'macos_taps'})
"""Sections holding bare strings, so there is no row to carry a field or a
constraint. `macos_taps` is the only one, and a dataclass for it would validate
nothing."""


@dc.dataclass(frozen=True, slots=True)
class Catalog:
    """`packages.yml`, parsed once and indexed.

    Nothing downstream re-reads the file and no provider takes a path: the 28
    bash call sites that each spawned an interpreter and re-parsed 258 entries
    become attribute access on this object.
    """

    entries: Mapping[str, tuple[Entry, ...]]
    macos_taps: tuple[str, ...]
    source: Path

    def section(self, name: str) -> tuple[Entry, ...]:
        return self.entries[name]

    def find(self, section: str, name: str) -> Entry:
        """Fail rather than default: a manifest naming a package that does not
        exist is the drift `packages verify` was written to catch, and it is
        caught here now, on every command, instead of in a separate verb."""
        for entry in self.entries[section]:
            if entry.name == name:
                return entry
        raise CatalogError((Issue(section, f'no entry named {name!r} in {self.source}'),))

    def runtime(self, name: str) -> Runtime:
        found = self.find('runtimes', name)
        assert isinstance(found, Runtime)
        return found

    def all_entries(self) -> Iterator[Entry]:
        for section in SECTIONS:
            yield from self.entries[section]


def load(path: Path | None = None) -> Catalog:
    """Parse and validate the whole declaration, or raise with every problem in it."""
    source = path or paths.PACKAGES_FILE
    raw = yaml.safe_load(source.read_text()) or {}

    issues: list[Issue] = []
    entries: dict[str, tuple[Entry, ...]] = {}

    for section, cls in SECTIONS.items():
        rows, section_issues = _build(raw.get(section), cls)
        entries[section] = rows
        issues.extend(section_issues)

    for unknown in sorted(set(raw) - set(SECTIONS) - BARE_SECTIONS):
        issues.append(Issue(unknown, 'is not a section any reader knows, so nothing installs it'))

    if issues:
        raise CatalogError(tuple(issues))

    return Catalog(entries=entries, macos_taps=tuple(raw.get('macos_taps') or ()), source=source)


def _build(declared: Any, cls: type[Entry]) -> tuple[tuple[Entry, ...], list[Issue]]:
    """One section's rows, plus everything wrong with them."""
    issues: list[Issue] = []
    rows: list[Entry] = []
    seen: set[str] = set()

    if declared is not None and not isinstance(declared, _CONTAINER[cls.structure]):
        wanted = 'a list of entries' if cls.structure is Structure.LIST else 'a mapping'
        return (), [Issue(cls.section, f'is a {type(declared).__name__} where every reader expects {wanted}')]

    for label, raw in _raw_rows(declared, cls):
        if not isinstance(raw, Mapping):
            issues.append(Issue(cls.section, f'{label} is {type(raw).__name__}, not a mapping'))
            continue
        try:
            entry = cls.from_mapping(raw)
        except EntryError as problem:
            # The name where there is one: a positional label is the fallback for
            # the row that is broken *because* it has no name.
            issues.append(Issue(cls.section, f'{raw.get("name") or label} {problem}'))
            continue

        issues.extend(Issue(cls.section, f'{entry.name} {problem}') for problem in entry.problems())
        if entry.name in seen:
            issues.append(Issue(cls.section, f'{entry.name} is declared more than once'))
        seen.add(entry.name)
        rows.append(entry)

    return tuple(rows), issues


_CONTAINER: dict[Structure, type] = {Structure.LIST: list, Structure.GROUPED: dict, Structure.KEYED: dict}


def _raw_rows(declared: Any, cls: type[Entry]) -> Iterator[tuple[str, Any]]:
    """Yield `(label, mapping)` for each row, flattening whichever shape the section uses.

    The label is what an Issue names the row by before it is known to have a
    name — an entry missing its `name` still has to be findable in the file.
    """
    if declared is None:
        return

    if cls.structure is Structure.LIST:
        for index, raw in enumerate(declared):
            yield f'entry #{index}', raw

    elif cls.structure is Structure.GROUPED:
        for group, rows in declared.items():
            for index, raw in enumerate(rows or ()):
                yield f'{group} entry #{index}', raw

    else:
        for key, raw in declared.items():
            yield key, {'name': key, **raw} if isinstance(raw, Mapping) else raw


_HINTS: dict[type, dict[str, Any]] = {}


def _hints(cls: type[Entry]) -> dict[str, Any]:
    """Resolved annotations, cached — `from __future__ import annotations` makes
    the raw ones strings, and every row of a section would otherwise re-resolve."""
    if cls not in _HINTS:
        _HINTS[cls] = typing.get_type_hints(cls)
    return _HINTS[cls]


def _is_required(field: dc.Field) -> bool:
    return field.default is dc.MISSING and field.default_factory is dc.MISSING


def _typed(key: str, annotation: Any, value: Any) -> Any:
    """Check one value against its declared type, converting only lists to tuples.

    Nothing is coerced. An unquoted `min_version: 0.11` is a float, and silently
    stringifying it turns 0.10 into "0.1" — so it is rejected with the fix in the
    message instead.
    """
    if annotation is str and not isinstance(value, str):
        raise EntryError(f"declares '{key}' as the {type(value).__name__} {value!r}; quote it to make it a string")

    if annotation is str:
        return value
    if annotation is bool and isinstance(value, bool):
        return value
    # bool is a subclass of int, so `requires_wsl_host: true` would otherwise
    # pass as an id.
    if annotation is int and isinstance(value, int) and not isinstance(value, bool):
        return value
    if annotation is not bool and annotation is not int and isinstance(value, list) and all(isinstance(row, str) for row in value):
        return tuple(value)

    raise EntryError(f"declares '{key}' as {value!r}, which is not the {_spelled(annotation)} this section reads")


def _spelled(annotation: Any) -> str:
    return getattr(annotation, '__name__', None) or 'list of strings'
