"""`packages.yml`, parsed once into typed rows.

One dataclass per section, rather than one generic row plus a table of
`required` / `forbidden` / `id_field` rules. A field on a dataclass is either
read by its provider or visibly unused, and a key that is not a field is an error
at load time rather than decoration — so a section's schema and its reader cannot
be two documents that disagree.

A rules table cannot hold that line. Nothing consumes its entries, so it
describes only the fields someone remembered to describe and the descriptions rot
unread: `install_script` naming scripts that `github_releases` entries do not
have, `binary_pattern` naming assets that do not exist.

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

from dotfiles import coordinates as axes
from dotfiles import paths
from dotfiles.refusal import Refusal


@dc.dataclass(frozen=True, slots=True)
class DeclarationIssue:
    """One thing wrong with the declaration, named where it is."""

    section: str
    message: str

    def __str__(self) -> str:
        return f'{self.section}: {self.message}'


class CatalogError(Refusal):
    """`packages.yml` declares something no reader can consume."""

    def __init__(self, issues: tuple[DeclarationIssue, ...]) -> None:
        self.issues = issues
        super().__init__('\n'.join(str(issue) for issue in issues))


class EntryError(ValueError):
    """One row cannot be built. Caught by `load`, which reports it as a DeclarationIssue."""


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
    'source_type': 'how a custom installer distributes itself is its function in providers/custom.py, not a word here',
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
        # The Go installer fetches whatever go.dev currently offers, so no floor applies.
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

VERSION_FROM_RELEASES = 'releases'
VERSION_FROM_TAGS = 'tags'

VERSION_SOURCES = frozenset({VERSION_FROM_RELEASES, VERSION_FROM_TAGS})
"""Which of a repo's two answers names its newest version.

Same shape as `CHECKSUM_STATES` and for the same reason: an upstream fact the
declaration states, so the exception is countable rather than discovered by a
lookup quietly returning nothing. One entry declares `tags` — `aws/aws-cli`,
which tags every build and publishes no release.
"""


def _repo_segments(value: str) -> list[str]:
    """A `repo`, `github_repo` or `package` field reduced to its path segments.

    The shapes disagree: `owner/name`, a clone URL, and a Go import path all
    appear, which is why this is a parse rather than a split.
    """
    path = value.split('://', 1)[-1].removesuffix('.git').strip('/')
    segments = [segment for segment in path.split('/') if segment]
    # A leading host (github.com) appears only in the URL and Go-import forms.
    if segments and '.' in segments[0]:
        segments = segments[1:]
    return segments


def owner_of(value: str) -> str | None:
    """The GitHub owner carried by a `repo`, `github_repo` or `package` field.

    Derived rather than tagged, per `data.md` § "Ownership is derived from data,
    never from a tag" — it is what `--owner` filters on, and it caught an entry
    the four hand-written tags had missed.
    """
    segments = _repo_segments(value)
    return segments[0] if segments else None


def repo_slug_of(value: str) -> str:
    """`owner/name`, which is what a GitHub API path and the release cache key on.

    Empty when the value names no repository. A caller cannot ask GitHub about a
    Go import path that carries only a host and an owner, and an empty answer is
    already how `_has_currency` reads "not a question this entry can be asked".
    """
    segments = _repo_segments(value)
    return '/'.join(segments[:2]) if len(segments) >= 2 else ''


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

    requires_github_auth: bool = False
    """Whether reaching this entry's upstream needs a GitHub login.

    On the base rather than on the two sections that use it today, for the reason
    `reports_version` is: it is a property of the artifact, and any section can
    name a private repo. Declared here, `precondition_of` reads it as a plain
    attribute that raises on a rename instead of a `getattr` default standing in
    for "this subclass has no such field" — whose quiet answer is
    `Precondition.NONE`, the absence of the gate.
    """

    requires_amd_gpu: bool = False
    """Whether this entry is a ROCm build, useless without an AMD device.

    Checked live and never filtered out of the plan: `available()` reads
    coordinates, and coordinates are what a *manifest* says a machine is, so
    resolution stays the same answer from every machine.
    `resolve.Precondition.AMD_GPU` carries the argument for why this is not a
    seventh coordinate axis.

    One entry uses it — `ollama`, whose pacman name is `ollama-rocm` and whose
    dependency closure is 12 GiB. On the base like its neighbour above, which
    means any section may declare it while only the resources that evaluate
    preconditions honour it. The same trade `reports_version` accepts.
    """

    reports_version: bool = True
    """Whether asking this binary for its version is a read.

    Almost always. A CLI answers `--version` or `version` and exits, which is what
    makes currency measurable at all. A GUI does not: `webviewrs` takes a URL as
    its first positional argument, so the probe opened a window titled `version`
    and blocked on the event loop until someone closed it — on a scheduled
    `dotfiles check`, forever.

    On the base class rather than on `CargoPackage`, because it is a property of
    the artifact and any section can declare a GUI. An entry that sets it false is
    simply not currency-checked: there is nothing to measure, and an `UNKNOWN` row
    on every plan is noise rather than a finding.
    """

    release_tag_prefix: str = ''
    """Which tags in `repo` are this entry's, for a repo that releases more than one thing.

    On the base for the same reason as the two above: it describes the *repo the
    entry is measured against*, and both `github_releases` and `custom_installers`
    name one. `mount-s3` is the case that moved it — its releases are tagged
    `mountpoint-s3-1.23.0` in a repo that tags other things too, and that prefix
    lived as a constant in `providers/custom.py` beside a second copy of the repo
    name the declaration already carried.
    """

    version_source: str = VERSION_FROM_RELEASES
    """Which of a repo's two answers says what the newest version is.

    Almost always its releases. `aws/aws-cli` is the exception and the reason this
    field exists: it tags every build and publishes no release at all, so
    `releases/latest` answers 404 and the entry would have to declare no `repo`,
    leaving `check` unable to say whether awscli is behind.

    Declared rather than discovered. Falling back to tags when the release lookup
    fails would read a *network* failure as "this project tags instead", so a
    rate-limited minute would silently change which question is being asked.
    """

    section: ClassVar[str]
    structure: ClassVar[Structure] = Structure.LIST
    honoured_constraints: ClassVar[tuple[str, ...]] = ()
    declared_in: ClassVar[str] = 'packages.yml'
    """Which declaration file holds this section, so an error names the file a
    reader has to open rather than the one most sections happen to live in."""

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

        if self.version_source not in VERSION_SOURCES:
            found.append(f"declares 'version_source' as {self.version_source!r}, which is not one of {', '.join(sorted(VERSION_SOURCES))}")

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

    excludes_host: str = ''
    """One host whose package manager cannot resolve this entry, however it is named.

    The negative form, and the only negative narrowing in the file, because the
    fact being recorded is negative: the docker family lives in Docker's own apt
    repository, which `docker-repo.sh` adds by hand as a documented escape hatch
    and no installer configures. Ubuntu-on-metal would be the same, and Arch is
    unaffected because pacman carries docker in the official repos — so this is a
    fact about one host rather than about apt.

    `install/wsl/system-packages.sh` said it as a `grep -v -E` over five package
    names piped between the parser and apt, which excluded them from the install
    and from nothing else. `check` went on planning all five and reporting them
    missing on a machine that was deliberately never going to have them.
    """

    supersedes: tuple[str, ...] = ()
    """Package names this entry took over from, which may still be installed.

    Declared rather than discovered, and the alternative was weighed. A package
    manager can be asked what a candidate conflicts with — `yay -Si` answers it
    for the AUR — but asking costs a subprocess per missing package and, for the
    AUR, a call to a remote RPC. `check` runs at a prompt, in a pre-commit hook,
    on a timer and under `--offline`, and its verdicts come from unprivileged
    local reads for exactly that reason. Putting a network round-trip behind it
    to learn a fact that changed once, in a commit, is the wrong trade.

    The moment the fact is known is the moment the entry is renamed, which is the
    moment someone is editing this file. That is what makes it cheap to declare
    and expensive to detect.
    """

    def package_for(self, manager: str) -> str:
        """This package's name under one manager, or '' where it has none."""
        return getattr(self, manager, '')

    def problems(self) -> tuple[str, ...]:
        # `Entry.problems(self)` rather than `super()`: dataclass(slots=True)
        # rebuilds the class, leaving the zero-argument form's __class__ cell
        # pointing at the original and raising TypeError on every call.
        managers = ('apt', 'pacman', 'brew', 'aur')
        found = []
        if not any(self.package_for(manager) for manager in managers):
            found.append(f'names no package under any of {", ".join(managers)}, so no machine can install it')
        if self.excludes_host and self.excludes_host not in set(axes.AXIS_TYPES['host']):
            found.append(f'excludes host {self.excludes_host!r}, which is not a host. Known: {", ".join(axes.AXIS_TYPES["host"])}')
        installs_as = {name for manager in managers if (name := self.package_for(manager))}
        if own := sorted(installs_as & set(self.supersedes)):
            found.append(
                f'supersedes {", ".join(own)}, which is a name it installs under. An entry that supersedes itself '
                f'reports itself blocked by its own installation, and never converges.'
            )
        return (*found, *Entry.problems(self))


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class GithubRelease(Entry):
    """A prebuilt binary from a GitHub release.

    The asset name is deliberately *not* here. It stays in code, because three of
    the 23 defeat any placeholder vocabulary — shellcheck needs aarch64-on-darwin
    and a `.tar.xz`, trivy needs `ARM64`/`64bit`, and zk spells its architecture
    per OS. Measured across all 23 and rejected twice; see
    `docs/architecture/github-releases.md` § "Why asset naming is code".
    """

    section: ClassVar[str] = 'github_releases'
    honoured_constraints: ClassVar[tuple[str, ...]] = ('version',)

    repo: str
    binary_link: str = ''
    requires_wsl_host: bool = False
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
    """A tool with its own distribution mechanism, installed by its own function.

    Everything here is declarative — a host, a repo, a path. *How* the bytes are
    fetched, verified and placed is `providers/custom.py`, because nine vendors
    with nothing in common do not survive being flattened into fields.
    """

    section: ClassVar[str] = 'custom_installers'

    description: str
    repo: str = ''
    support_repo: str = ''
    assert_repo: str = ''
    url: str = ''
    install_url: str = ''
    installed_path: str = ''
    bundle_install_script: bool = False

    excludes_os_family: str = ''
    """An OS family this installer must never run on, because something else
    already supplies the tool there.

    Same shape as `excludes_host` on SystemPackage and for the same reason: the
    entry is not *declined* on that machine, it cannot apply. awscli is the case
    — a Homebrew formula on macOS and AWS's own 73MB installer everywhere else —
    and without this the Mac planned it, ran the function, and had it report
    success having done nothing, on every run of a converged machine.
    """

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
class WingetPackage(Entry):
    """A Windows CLI, installed by the Microsoft Store client.

    Its own section rather than a `winget:` column on `SystemPackage`, and the
    reason is mechanism rather than destination. Most of these are `cargo_packages`
    or `github_releases` rows elsewhere; what none of them can be on Windows is the
    thing they are elsewhere, because binstall, the Rust target triple and this
    repo's release-asset code all end at the Unix side. A fifth manager column
    would instead have to be threaded through every table keyed on manager name —
    preference, escalation, the installed-query, the bootstrap — to say that one
    machine installs a tool a different way.

    `repo` and `asset` name where the same binary is published on GitHub, which is
    the offline channel rather than a note about one: the machine that needs these
    most cannot use winget at all, because an employer network blocks it outright.
    `create_bundle.add_winget_binaries` stages from that coordinate and
    `providers.winget` installs what it staged — in the general bundler beside
    every other category, because Windows is one more machine to build a bundle
    for rather than a side reached across a boundary.

    `asset` is a field where `GithubRelease` keeps its asset names in code, and the
    split is not an inconsistency. That convention exists because the release
    entries defeat any placeholder vocabulary between them; these need exactly the
    two `{version}` and `{version_num}` spellings, and the alternative — a function
    per tool in a second module — would be code for a fact one string states.

    Deliberately outside the currency check: winget is a registry that owns its own
    upgrades, so asking each package whether it is behind asks a question
    `winget upgrade` already answers for all of them at once. That is the same
    verdict `npm_globals` gets, for the same reason.
    """

    section: ClassVar[str] = 'winget_packages'

    winget: str
    """The Microsoft Store id, which is not derivable from `repo`: ripgrep is
    `BurntSushi.ripgrep` and fd is `sharkdp.fd`, but jq is `jqlang.jq` against a
    repo of `jqlang/jq` and eza is `eza-community.eza` — close enough to look like
    a rule and wrong often enough that both are written out."""

    repo: str
    asset: str
    """Where the same binary is published outside the Store, as `owner/name` and
    the Windows asset inside that release's tag.

    The tag is not known until the release is looked up, so the asset carries
    `{version}` or `{version_num}` where the publisher stamps one in — the tag as
    written and the tag from its first digit on."""

    @property
    def filename(self) -> str:
        """`rg.exe` — what winget leaves behind, what a bundle carries, and what
        has to land in `~/.local/bin`.

        Derived from `command` rather than declared, so a row cannot name a binary
        under one spelling and a filename under another. Windows is the only place
        the suffix is real, which is why it is added here and not carried in
        `command`: `Entry.executable` is what PATH is asked about, and asking it
        for `rg.exe` would be wrong on the interpreter that appends the suffix
        itself.
        """
        return f'{self.executable}.exe'

    @property
    def owner(self) -> str | None:
        return owner_of(self.repo)


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
class YaziPlugin(Entry):
    """A yazi plugin, cloned to `~/.config/yazi/plugins/<name>.yazi`.

    Declared here rather than left to `ya pkg add`, which is yazi's own package
    manager and writes its state to `~/.config/yazi/package.toml` — a path this
    repo also deployed a file to. Two writers on one path, and the symptom was
    every fresh install failing the symlink stage.

    `name` is what the config asks for and what the directory is called: yazi
    appends the `.yazi` suffix itself, `init.lua` says `require('git')`, and
    `keymap.toml` says `plugin what-size`.
    """

    section: ClassVar[str] = 'yazi_plugins'

    repo: str
    subdirectory: str = ''
    """Where the plugin sits inside its repo, for the one that is a monorepo.
    `yazi-rs/plugins` carries two dozen plugins at its root, so cloning it whole
    would put all of them at the path yazi expects to be one."""

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


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class SystemConfig(Entry):
    """Configuration the machine owns, rather than payload it installs.

    Its own file, because `packages --source <section>` names a payload and these
    are not payloads: nothing here is fetched, versioned or upgraded. What they
    share with a package is the shape of the question — declared, observed,
    repaired — which is why they are `Entry` rows and not a second mechanism.

    Narrowing is per entry rather than per section, because these rows do not
    divide the way a package section does. TTY auto-login belongs to a machine
    whose compositor replaced the display manager, the docker group belongs to a
    machine that installed docker, and pointing `/etc/zshenv` at the XDG config
    belongs to every machine that asked for zsh. Three unrelated questions, and
    no one coordinate answers them — so an entry names the one that decides it,
    and a new axis is a new field rather than a general narrowing language.
    """

    declared_in: ClassVar[str] = 'system.yml'

    needs_root: bool = True
    """Whether repairing this row escalates.

    A field with a per-section default rather than a class constant, because it
    is mostly a property of the section and occasionally not: macOS preferences
    are user-level throughout, and the Xcode licence is the one step in the repo
    whose *read* needs root. Treating a whole section as privileged would put a
    password prompt in front of a Mac that needs none.
    """

    os_family: str = ''
    host: str = ''
    display_stack: str = ''
    """Coordinate narrowings, and only the three anything declares.

    Hyprland replacing gdm is a fact about the display stack, not about Arch; the
    Windows font path is a fact about the host, not about Ubuntu. A fourth axis is
    a fourth field when a row needs one — until then declaring it is a load-time
    error rather than a key read by nothing.

    `capacity` was a fourth for one commit, for the rows that pointed a tool at
    the shared registry. Those rows became config files the tools read for
    themselves, so the field went back out under the same rule that admitted it.
    """

    excludes_os_family: str = ''
    """An OS family this row can never describe, for a row that fits every other.

    The negative form, for the reason `SystemPackage.excludes_host` and
    `CustomInstaller.excludes_os_family` are negative: the positive fields above
    name *one* value, and a row true of two families out of three cannot say so
    without a narrowing language this file deliberately does not have.

    `check-schedule` is the case. It is a systemd user timer or a LaunchAgent, and
    Windows is neither — the row reached `providers/schedule.py`, took the systemd
    branch because the dispatch there is a two-way, and was saved from running
    `systemctl` only by a `which` guard. What it left was `UNKNOWN` on every run of
    a machine where nothing is wrong and nothing can be repaired, which is the
    reading `available()` exists to prevent.
    """

    requires_package: str = ''
    """Only where this machine's plan installs that system package. Configuring
    docker's group on a server that never installs docker would create a group
    for nothing, and report drift forever on a machine with nothing wrong."""

    feature: str = ''
    """Only where the manifest sets this boolean — `configure_zsh` and its kind."""

    @property
    def narrowing(self) -> dict[str, str]:
        """The coordinates this row narrows on, keyed as `Coordinates` spells them."""
        declared = (('os_family', self.os_family), ('host', self.host), ('display_stack', self.display_stack))
        return {axis: value for axis, value in declared if value}

    def problems(self) -> tuple[str, ...]:
        wrong = [
            f'declares {axis} {value!r}, which is not an axis value. Known: {", ".join(axes.AXIS_TYPES[axis])}'
            for axis, value in self.narrowing.items()
            if value not in set(axes.AXIS_TYPES[axis])
        ]
        if self.excludes_os_family and self.excludes_os_family not in set(axes.AXIS_TYPES['os_family']):
            known = ', '.join(axes.AXIS_TYPES['os_family'])
            wrong.append(f'excludes os_family {self.excludes_os_family!r}, which is not an OS family. Known: {known}')
        return (*wrong, *Entry.problems(self))


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class GroupMembership(SystemConfig):
    """The current user belongs to a group. `name` is the group."""

    section: ClassVar[str] = 'group_memberships'

    create_group: bool = False
    """Whether to create the group when the package that owns it did not."""


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class SystemdUnit(SystemConfig):
    """A unit's enablement, and optionally that it is running. `name` is the unit."""

    section: ClassVar[str] = 'systemd_units'

    enabled: bool = True
    active: bool = False
    """An *additional* requirement to start it, and only meaningful beside
    `enabled: true` — disabling a unit has never stopped one, and asserting that
    it also stopped would report drift on the machine that just disabled it."""


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class ManagedFile(SystemConfig):
    """A root-owned configuration file this repo owns some or all of.

    `content` means the whole file is ours and is compared exactly; `append_line`
    means the file is the OS's and only the presence of one line is ours. Exactly
    one of them, because a file that is both wholly ours and only partly ours is
    not a state anything can converge on.

    Mostly `/etc`, and not defined as `/etc`: macOS keeps the equivalent under
    `/Library/Managed Preferences`, and both are the same question — a
    world-readable file a root write repairs.
    """

    section: ClassVar[str] = 'managed_files'

    path: str
    content: str = ''
    append_line: str = ''
    mode: str = '0644'

    alternate_path: str = ''
    """Where the file lives instead, when that path's parent directory exists.

    One entry rather than two, and one field rather than a coordinate, because
    the fact is neither a distribution nor a package manager: Debian builds zsh
    with `--enable-etcdir=/etc/zsh`, so its system zshenv is `/etc/zsh/zshenv`
    and everyone else's is `/etc/zshenv`. Writing ours to the wrong one is silent
    — zsh reads the other, and `~/.config/zsh/.zshrc` never loads at all.
    """

    def problems(self) -> tuple[str, ...]:
        if bool(self.content) == bool(self.append_line):
            declared = 'both content and append_line' if self.content else 'neither content nor append_line'
            return (f'declares {declared}; a managed file is either wholly ours or one line of ours', *SystemConfig.problems(self))
        return SystemConfig.problems(self)


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class LoginShell(SystemConfig):
    """The current user's login shell. `name` is the shell's binary."""

    section: ClassVar[str] = 'login_shell'


DEFAULTS_TYPES = ('bool', 'int', 'string')


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class MacosDefault(SystemConfig):
    """One `defaults` key, and the value this Mac should have for it.

    The best conversion candidate in the repository, and the reason is specific:
    `defaults` is the only subsystem here with a native, unprivileged, exact read
    side. Seventy-three write-only `defaults write` calls could never answer
    "does this Mac match?"; the same seventy-three rows as data can.

    `value` is a string whatever `type` says, and always quoted in the YAML. An
    unquoted `0.11` is a float that stringifies to `0.1`, which is the mistake
    the version constraints already made once — and `defaults` takes a string on
    the command line regardless.
    """

    section: ClassVar[str] = 'macos_defaults'

    domain: str
    key: str
    type: str
    value: str
    name: str = ''
    needs_root: bool = False

    dict_key: str = ''
    """The key *inside* the value, for the five entries using `-dict-add`. Their
    read is a plist lookup rather than a string compare, which is why the schema
    says so rather than the provider guessing from the shape of the output."""

    current_host: bool = False
    """`defaults -currentHost`, which is a different store and not a flag on the
    same one. One entry uses it, and reading it from the ordinary store answers
    "absent" forever."""

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        """Derive `name` from the address rather than asking for it twice.

        A row's identity *is* its domain, key and dict key; a hand-written slug
        beside them would be a second spelling that can disagree, and 73 of them
        would be invented rather than meant. The derived form is also what
        `check` prints, which is the string to paste after `defaults read`.

        `Entry.from_mapping.__func__` rather than `super()`: `dataclass(slots=True)`
        rebuilds the class, leaving the zero-argument form's `__class__` cell
        pointing at the original and raising TypeError on every call.
        """
        if 'name' not in raw and 'domain' in raw and 'key' in raw:
            address = [str(raw['domain']), str(raw['key']), *([str(raw['dict_key'])] if raw.get('dict_key') else [])]
            raw = {**raw, 'name': '/'.join(address)}
        return Entry.from_mapping.__func__(cls, raw)  # type: ignore[attr-defined,no-any-return]

    def problems(self) -> tuple[str, ...]:
        if self.type in DEFAULTS_TYPES:
            return SystemConfig.problems(self)
        return (f'declares type {self.type!r}, which is not one of {", ".join(DEFAULTS_TYPES)}', *SystemConfig.problems(self))


@dc.dataclass(frozen=True, slots=True, kw_only=True)
class Step(SystemConfig):
    """A piece of machine state with no shared mechanism behind it.

    `~/Library` being visible is a file flag, the screenshot directory existing
    is a directory existing, the Xcode licence is a `sudo` read, OrbStack's
    plugin directory is a JSON merge, and the Windows font path is discovered by
    asking Windows. Five rows with nothing in common.

    This is the `custom_installers` shape — the declaration says which, and
    `providers/steps.py` says how — because a `check:`/`apply:` argv pair in YAML
    would be a command language invented for five rows, and three of them would
    not fit it anyway.

    `needs_root` defaults to False here rather than to the section default: four
    of the five are user-level, and the Xcode licence declares its own exception.
    """

    section: ClassVar[str] = 'steps'

    needs_root: bool = False


SECTION_CLASSES: tuple[type[Entry], ...] = (
    SystemPackage,
    Runtime,
    GithubRelease,
    CustomInstaller,
    CargoPackage,
    WingetPackage,
    GoTool,
    NpmGlobal,
    UvTool,
    GitUvTool,
    ShellPlugin,
    TmuxPlugin,
    YaziPlugin,
    MasApp,
    MacosCask,
    FlatpakApp,
    ZenExtension,
)
"""In `packages.yml` order, which is what `packages list` and the run record render."""

SECTIONS: dict[str, type[Entry]] = {cls.section: cls for cls in SECTION_CLASSES}

SYSTEM_SECTION_CLASSES: tuple[type[SystemConfig], ...] = (
    GroupMembership,
    SystemdUnit,
    ManagedFile,
    LoginShell,
    MacosDefault,
    Step,
)
"""`system.yml`, in its own map rather than merged into `SECTIONS`.

`SECTIONS` is what a manifest subscribes to, what `packages list --section`
offers and what `validate.py` walks. None of those are true of a group
membership, so merging the two would put system configuration behind the
`packages` noun — which the whole point of a `system` resource is to stop.
"""

SYSTEM_SECTIONS: dict[str, type[Entry]] = {cls.section: cls for cls in SYSTEM_SECTION_CLASSES}

ALL_SECTIONS: dict[str, type[Entry]] = {**SECTIONS, **SYSTEM_SECTIONS}

BARE_SECTIONS = frozenset({'macos_taps'})
"""Sections holding bare strings, so there is no row to carry a field or a
constraint. `macos_taps` is the only one, and a dataclass for it would validate
nothing."""


@dc.dataclass(frozen=True, slots=True)
class Catalog:
    """`packages.yml`, parsed once and indexed.

    Nothing downstream re-reads the file and no provider takes a path — every
    reader gets attribute access on this object instead.
    """

    entries: Mapping[str, tuple[Entry, ...]]
    macos_taps: tuple[str, ...]
    source: Path
    system_source: Path

    def section(self, name: str) -> tuple[Entry, ...]:
        return self.entries[name]

    def file_for(self, section: str) -> Path:
        return self.system_source if section in SYSTEM_SECTIONS else self.source

    def find(self, section: str, name: str) -> Entry:
        """Fail rather than default: a manifest naming a package that does not
        exist is the drift `packages verify` was written to catch, and it is
        caught here now, on every command, instead of in a separate verb."""
        for entry in self.entries[section]:
            if entry.name == name:
                return entry
        raise CatalogError((DeclarationIssue(section, f'no entry named {name!r} in {self.file_for(section)}'),))

    def runtime(self, name: str) -> Runtime:
        found = self.find('runtimes', name)
        assert isinstance(found, Runtime)
        return found

    def all_entries(self) -> Iterator[Entry]:
        for section in ALL_SECTIONS:
            yield from self.entries[section]


def _parsed(source: Path) -> dict[str, Any]:
    """One declaration file as a mapping, or a refusal naming where it broke.

    A file that will not parse as YAML is the same kind of answer as one that
    parses and declares something no reader can consume, and it has to arrive as
    the same kind of exception. Untried, `yaml.safe_load` raised a `YAMLError`
    that no handler here catches: `validate.declaration` catches `CatalogError`
    alone, so the parser's own exception reached the boundary as a traceback and
    exit 1 — which is `DRIFT`, the code for a machine that merely differs from a
    declaration nothing could read.

    The parser's message carries the line and column, so it is kept whole rather
    than summarised. `problem_mark` is what makes it worth keeping.
    """
    try:
        return yaml.safe_load(source.read_text()) or {}
    except yaml.YAMLError as unparseable:
        raise CatalogError((DeclarationIssue(source.name, f'will not parse as YAML — {unparseable}'),)) from unparseable


def load(path: Path | None = None, *, system: Path | None = None) -> Catalog:
    """Parse and validate the whole declaration, or raise with every problem in it.

    Two files, one object. `system` defaults to `system.yml` beside the packages
    file rather than to an absolute path, so a test pointing `path` at a
    synthetic tree gets that tree's system declaration — or, where it wrote none,
    an empty one — instead of silently reading the real machine's.
    """
    source = path or paths.PACKAGES_FILE
    system_source = system or (source.parent / 'system.yml')
    declared = {
        source: _parsed(source),
        system_source: _parsed(system_source) if system_source.is_file() else {},
    }

    issues: list[DeclarationIssue] = []
    entries: dict[str, tuple[Entry, ...]] = {}

    for section, cls in ALL_SECTIONS.items():
        rows, section_issues = _build(declared[_file_for(cls, source, system_source)].get(section), cls)
        entries[section] = rows
        issues.extend(section_issues)

    for file, raw in declared.items():
        known = set(SYSTEM_SECTIONS) if file == system_source else set(SECTIONS) | BARE_SECTIONS
        for unknown in sorted(set(raw) - known):
            where = 'system.yml' if file == system_source else 'packages.yml'
            issues.append(DeclarationIssue(unknown, f'is not a section any reader knows, so nothing reads it out of {where}'))

    if issues:
        raise CatalogError(tuple(issues))

    return Catalog(
        entries=entries,
        macos_taps=tuple(declared[source].get('macos_taps') or ()),
        source=source,
        system_source=system_source,
    )


def raw_sections(path: Path) -> dict[str, Any]:
    """A declaration file as written, before any of it is modelled.

    For the questions a `Catalog` cannot answer because modelling is what
    discards them: which sections the file names *including* the ones no
    dataclass claims, and what a manifest body holds when it is about to be
    rewritten into a fixture. Both need the file rather than the object, and both
    would otherwise reach for a second `yaml.safe_load` — a second copy of the
    grammar this module owns, invisible as a copy because it reads as opening a
    file.

    An empty file is `{}`, which is `load`'s own reading of one. A missing file
    raises, for the same reason `load` lets one raise: nothing here can say what
    a caller meant by a path that is not there.
    """
    return yaml.safe_load(path.read_text()) or {}


def _file_for(cls: type[Entry], packages: Path, system: Path) -> Path:
    return system if cls.declared_in == 'system.yml' else packages


def _build(declared: Any, cls: type[Entry]) -> tuple[tuple[Entry, ...], list[DeclarationIssue]]:
    """One section's rows, plus everything wrong with them."""
    issues: list[DeclarationIssue] = []
    rows: list[Entry] = []
    seen: set[str] = set()

    if declared is not None and not isinstance(declared, _CONTAINER[cls.structure]):
        wanted = 'a list of entries' if cls.structure is Structure.LIST else 'a mapping'
        return (), [DeclarationIssue(cls.section, f'is a {type(declared).__name__} where every reader expects {wanted}')]

    for label, raw in _raw_rows(declared, cls):
        if not isinstance(raw, Mapping):
            issues.append(DeclarationIssue(cls.section, f'{label} is {type(raw).__name__}, not a mapping'))
            continue
        try:
            entry = cls.from_mapping(raw)
        except EntryError as problem:
            # The name where there is one: a positional label is the fallback for
            # the row that is broken *because* it has no name.
            issues.append(DeclarationIssue(cls.section, f'{raw.get("name") or label} {problem}'))
            continue

        issues.extend(DeclarationIssue(cls.section, f'{entry.name} {problem}') for problem in entry.problems())
        if entry.name in seen:
            issues.append(DeclarationIssue(cls.section, f'{entry.name} is declared more than once'))
        seen.add(entry.name)
        rows.append(entry)

    return tuple(rows), issues


_CONTAINER: dict[Structure, type] = {Structure.LIST: list, Structure.GROUPED: dict, Structure.KEYED: dict}


def _raw_rows(declared: Any, cls: type[Entry]) -> Iterator[tuple[str, Any]]:
    """Yield `(label, mapping)` for each row, flattening whichever shape the section uses.

    The label is what a DeclarationIssue names the row by before it is known to have a
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
