"""Is the declaration itself sound, before any machine is measured against it.

Everything here reads the loaded objects. Re-parsing the files as raw dictionaries
would put a second parser beside the typed loaders, with its own idea of how a
section is spelled and its own copy of which manifest keys are retired — two
descriptions of one file, which is the drift the typed loaders exist to end.

`declaration.py` does parse raw, and that is the one place it is right: browsing
has to list a `packages.yml` that will not load, which is exactly when a reader
wants to look at it. It carries no second description either way — its section
spellings are derived from `catalog.SECTIONS`. A rule the dataclasses can enforce is
not restated: required fields, unknown keys, duplicate names, declared types and
the version constraints are `catalog.py`'s, and a manifest naming a retired
runtime-gate boolean is `machine.py`'s `RETIRED_KEYS`. What is left is the
questions no single file can answer about itself, because each is a relationship
— between two files, or between two fields of one entry that the schema sees only
one at a time.

The output is findings rather than printed lines, which is what lets one function
serve `dotfiles machines check`, the declaration row of `dotfiles check`, and
`apply`'s refusal to run against a declaration that will not hold still.
"""

from __future__ import annotations

import dataclasses as dc
import enum
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from dotfiles import catalog as catalogs
from dotfiles import coordinates as axes
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles.resources import symlinks
from dotfiles.symlinks import core


class Severity(enum.StrEnum):
    ERROR = 'error'
    """The declaration cannot be acted on. `apply` refuses; `check` reports an Issue."""

    WARNING = 'warning'
    """Worth knowing and not worth stopping for — an entry nothing subscribes to
    is a tool that was declared and then never rolled out, which is a fact about
    the fleet rather than a fault in the file."""


@dc.dataclass(frozen=True, slots=True)
class Finding:
    """One thing wrong with the declaration, and where."""

    section: str
    severity: Severity
    message: str

    def as_dict(self) -> dict[str, str]:
        return {'section': self.section, 'severity': str(self.severity), 'message': self.message}


def declaration(repo: Path | None = None) -> tuple[Finding, ...]:
    """Every finding, in the order a reader should act on them.

    A catalog that will not load short-circuits the rest, and that is the same
    rule the walk applies to a machine: everything downstream is measured
    *against* the catalog, so findings derived from a file that could not be
    parsed would describe a declaration nobody has.
    """
    root = repo or paths.REPO_ROOT
    try:
        declared = catalogs.load(root / 'install' / 'packages.yml')
    except catalogs.CatalogError as refused:
        return tuple(Finding(issue.section, Severity.ERROR, issue.message) for issue in refused.issues)

    findings: list[Finding] = []
    manifests: dict[str, machines.Machine] = {}
    for name in machines.names(root):
        try:
            manifests[name] = machines.load(name, root)
        except machines.MachineError as refused:
            findings.extend(Finding('manifest', Severity.ERROR, f'{name}: {issue.message}') for issue in refused.issues)

    findings.extend(_unresolved_names(declared, manifests))
    findings.extend(_uninstallable(declared))
    findings.extend(_unprobeable(manifests))
    findings.extend(_unbuildable_assets(declared))
    findings.extend(_unreferenced(declared, manifests))
    findings.extend(_git_variants(root))
    findings.extend(_colliding_variants(root))
    findings.extend(_registry_paths(root))
    findings.extend(_remote_tables(root))
    return tuple(findings)


def errors(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    return tuple(finding for finding in findings if finding.severity is Severity.ERROR)


def _named_sections() -> tuple[str, ...]:
    """The sections a manifest subscribes to by naming entries.

    Derived from `SUBSCRIPTIONS` rather than listed, because a hand-written copy
    is a list that stops matching — this one already existed twice and the two
    were kept in step by nothing.
    """
    return tuple(section for section, (spelling, _) in machines.SUBSCRIPTIONS.items() if spelling is machines.Spelling.NAMES)


def _unresolved_names(declared: catalogs.Catalog, manifests: dict[str, machines.Machine]) -> list[Finding]:
    """A manifest naming an entry that does not exist.

    The check the whole command was written for, and the one the resolver cannot
    make: subscription is a membership test over the catalog's entries, so a name
    matching nothing is silently dropped rather than refused. It is invisible from
    the machine where the commit happens — a typo in `linux-lxc-server.yml` costs
    nothing on the Mac until that server is rebuilt.
    """
    findings: list[Finding] = []
    for section in _named_sections():
        available = {entry.name for entry in declared.section(section)}
        for name, manifest in manifests.items():
            missing = manifest.subscription(section).names - available
            findings.extend(
                Finding(section, Severity.ERROR, f'manifest {name!r} names {absent!r}, which no {section} entry declares')
                for absent in sorted(missing)
            )
    return findings


def _uninstallable(declared: catalogs.Catalog) -> list[Finding]:
    """An entry in a code-installed section that nothing knows how to install.

    One direction only. The other half — a function naming a tool nothing declares
    — cannot be asked here, because a synthetic tree can replace the declaration
    while the functions are code and are always the real ones. `tests/install/`
    asserts that half against the real catalog.

    Both sections were a directory of one script per entry, and this asserted the
    file existed. The guarantee was never "a file exists with this name", it was
    "something knows how to install this", so the check followed the installers
    into Python rather than going with the scripts.
    """
    from dotfiles.providers import custom
    from dotfiles.providers import releases

    findings = []
    for section, known, module in (
        ('github_releases', set(releases.ASSETS), 'providers/releases.py'),
        ('custom_installers', set(custom.INSTALLERS), 'providers/custom.py'),
    ):
        for name in sorted({entry.name for entry in declared.section(section)} - known):
            findings.append(Finding(section, Severity.ERROR, f'{name!r} has no installer function in {module}'))
    return findings


def _unprobeable(manifests: dict[str, machines.Machine]) -> list[Finding]:
    """A manifest naming a login nothing knows how to ask about.

    The same shape as `_uninstallable` and the same one direction: a synthetic tree
    can replace the manifests while the probe functions are code and are always the
    real ones, so "a probe no manifest declares" belongs in `tests/resources/`.

    An error rather than a warning, because the failure is silent in the direction
    that reassures. `observe` reports an unknown name as unmeasurable, which lands
    outside the exit code — so a typo in an `auth:` list reads as a machine with
    nothing wrong with it while the login it meant to ask about goes unasked.
    """
    from dotfiles.resources import auth

    findings = []
    for name, manifest in sorted(manifests.items()):
        for tool in sorted(set(manifest.auth) - set(auth.PROBES)):
            findings.append(Finding('auth', Severity.ERROR, f'manifest {name!r} names {tool!r}, which has no probe in resources/auth.py'))
    return findings


def _unbuildable_assets(declared: catalogs.Catalog) -> list[Finding]:
    """A `binary_pattern` with no repository to expand it against.

    The pattern names an asset inside a GitHub release, so the two fields are one
    fact wearing two names: without the repo there is no URL to build and the
    pattern goes unread. The loader cannot catch it — `catalog.py` refuses a key
    the *section* never reads, which is one entry's schema, and this is a relation
    between two fields of an entry that are individually legal.

    A warning rather than an error, and the distinction is the point: the tool
    still installs, by whatever its manager does without a prebuilt asset. What
    is lost is the fast path, silently, which is exactly the failure that goes
    years unnoticed.

    Derived from the sections whose dataclass carries both fields rather than
    naming them, so a third section gaining them is covered without anyone
    remembering this list — the same rule `_named_sections` follows.
    """
    findings = []
    for section, entry_class in catalogs.SECTIONS.items():
        fields = {field.name for field in dc.fields(entry_class)}
        if not {'binary_pattern', 'github_repo'} <= fields:
            continue
        for entry in declared.section(section):
            if entry.binary_pattern and not entry.github_repo:
                findings.append(
                    Finding(
                        section,
                        Severity.WARNING,
                        f'{entry.name!r} declares binary_pattern but no github_repo, so no asset URL can be built',
                    )
                )
    return findings


def _unreferenced(declared: catalogs.Catalog, manifests: dict[str, machines.Machine]) -> list[Finding]:
    """An entry no manifest subscribes to: declared, and rolled out nowhere.

    A warning rather than an error, and the reason is `packages.yml`'s own: an
    entry lands there before the manifest that wants it, and a tool being staged
    is not a broken declaration. It becomes worth saying when nothing ever
    subscribes — `todoui` and `forge` shipped ghost-installed for weeks that way.

    A section any manifest takes wholesale is skipped: every entry in it is
    referenced by construction, and reporting them all would bury the real ones.
    """
    findings = []
    for section in _named_sections():
        subscriptions = [manifest.subscription(section) for manifest in manifests.values()]
        if any(subscription.coverage is machines.Coverage.ALL for subscription in subscriptions):
            continue
        referenced = {name for subscription in subscriptions for name in subscription.names}
        for name in sorted({entry.name for entry in declared.section(section)} - referenced):
            findings.append(Finding(section, Severity.WARNING, f'{name!r} is declared but no manifest names it'))
    return findings


GIT_VARIANT_GLOB = 'configs/*/*/.config/git/*.gitconfig'
COMMON_GITCONFIG = 'configs/common/.config/git/common.gitconfig'
GIT_INCLUDE_PREFIX = 'path = ~/.config/git/'


FLATTENING_TREES = tuple(name for name, _destination, nested in symlinks.TREES if not nested)
"""The trees where a coordinate directory drops its `<axis>/<value>` at the
destination, so two of them can land on one path.

`shell/` keeps the axis in its deployed path and is therefore incapable of a
collision — nothing but `.zshrc` reads there and it globs the directories by name.
Derived from `TREES` rather than listed, so a fourth tree is covered by whichever
half it declares itself to be."""


def _coselectable(first: str, second: str) -> bool:
    """Whether one machine can select both of these directories.

    `common` is on every machine, so it collides with anything. Two values of the
    *same* axis never co-occur — a machine sits at exactly one point per axis, so
    `pkg/apt` and `pkg/pacman` cannot both be selected and declaring one path in
    both is the normal way to write a per-manager config. Two different axes can,
    which is the case that is a mistake.
    """
    if 'common' in (first, second):
        return True
    return first.split('/')[0] != second.split('/')[0]


def _colliding_variants(root: Path) -> list[Finding]:
    """Two directories declaring one destination, which no machine can resolve.

    Deployment is ordered and appends without deduplicating, so a collision does
    not fail — `apply` writes both links at one target, the later one wins, and the
    next `plan` reports the loser as ordinary drift and repairs it, unseating the
    winner. The file alternates between the two on every run, for ever, while
    `check` reports a healthy machine: a link pointing at the wrong source *is*
    drift, and drift is what `apply` is for rather than something wrong.

    An ERROR because the gate before the walk is what makes it safe. A collision
    that stopped one target and let the rest proceed would leave the machine half
    converged against a declaration nobody can satisfy, which is the state this
    check exists to prevent rather than to describe.

    Pairwise on directories rather than by enumerating every expressible machine.
    The question is only whether two directories can co-occur, which is a fact
    about the axes and needs no coordinates resolved.
    """
    findings = []
    for tree in FLATTENING_TREES:
        declaring: dict[str, list[str]] = {}
        base = root / tree
        for directory in sorted(base.glob('*/')) + sorted(base.glob('*/*/')):
            relative = str(directory.relative_to(base))
            if relative != 'common' and relative not in axes.directory_names():
                continue
            for item in sorted(directory.rglob('*')):
                if item.is_file() and not core.should_exclude(item.relative_to(directory)):
                    declaring.setdefault(str(item.relative_to(directory)), []).append(relative)

        for deployed, sources in sorted(declaring.items()):
            clash = sorted({(a, b) for a in sources for b in sources if a < b and _coselectable(a, b)})
            for first, second in clash:
                findings.append(
                    Finding(
                        'symlinks',
                        Severity.ERROR,
                        f'{tree}/{deployed} is declared in both {first} and {second}, which one machine selects together — '
                        f'move it out of whichever should not carry it',
                    )
                )
    return findings


def _git_variants(root: Path) -> list[Finding]:
    """The two rules holding the git include scheme together, neither of which git
    can enforce.

    A variant gitconfig is named for the coordinate *value* that ships it, so
    `ls ~/.config/git/` answers what the machine is rather than which axes were
    resolved — `nonfleet.gitconfig`, not `trust.gitconfig`. And every one of them
    has to be named by an include in `common.gitconfig`, because git expands
    nothing but `~` in an `include.path` and cannot be pointed at a directory the
    way `.zshrc` globs the deployed shell tree.

    Both failures are silent, and silent in the *same* way, which is what makes
    them worth a check rather than a convention. git ignores an include whose
    target is absent — deliberately, since that is the mechanism letting one
    shared file name every value — so a file nothing includes is
    indistinguishable from a value this machine simply is not. The variant
    deploys, git never reads it, and `identity show` draws a tree it does not
    appear in.

    Errors rather than warnings, because both produce a machine configured
    differently from what the repo says it is.
    """
    variants = sorted(root.glob(GIT_VARIANT_GLOB))
    common = root / COMMON_GITCONFIG
    if not common.exists():
        # Only a fault when something is waiting to be included. A tree with no
        # git variants at all has nothing to say about the scheme either way.
        if not variants:
            return []
        return [Finding('gitconfig', Severity.ERROR, f'{COMMON_GITCONFIG} is missing, so no variant gitconfig is reachable')]

    lines = [line.strip() for line in common.read_text().splitlines()]
    included = {line.removeprefix(GIT_INCLUDE_PREFIX) for line in lines if line.startswith(GIT_INCLUDE_PREFIX)}

    findings, shipped = [], set()
    for variant in variants:
        axis, value = variant.relative_to(root / 'configs').parts[:2]
        shipped.add(variant.name)
        relative = variant.relative_to(root)
        if variant.stem != value:
            findings.append(
                Finding(
                    'gitconfig',
                    Severity.ERROR,
                    f'{relative} is named for neither its value nor anything else: '
                    f'the {axis} value here is {value!r}, so it must be {value}.gitconfig',
                )
            )
        elif variant.name not in included:
            findings.append(
                Finding(
                    'gitconfig',
                    Severity.ERROR,
                    f'{relative} is deployed but no include names it, so git never reads it; '
                    f'add `{GIT_INCLUDE_PREFIX}{variant.name}` to {COMMON_GITCONFIG}',
                )
            )

    # The stale half, and only a warning: git ignores the line, so nothing is
    # misconfigured. What it costs is a reader trusting the file, who sees a value
    # named here and goes looking for the variant that no longer ships it.
    for name in sorted(included - shipped):
        findings.append(Finding('gitconfig', Severity.WARNING, f'{COMMON_GITCONFIG} includes {name!r}, which no variant ships'))
    return findings


def _yaml_mapping(text: str) -> dict[str, Any]:
    """A YAML config as a mapping, empty for anything that is not one.

    An empty document parses to None and a list parses to a list; neither declares
    a key, and `.get` on either is an AttributeError rather than a finding.
    """
    parsed = yaml.safe_load(text)
    return parsed if isinstance(parsed, dict) else {}


REGISTRY_KEY = 'repos_registry'
PARSEABLE_CONFIGS: dict[str, Callable[[str], dict[str, Any]]] = {
    '.toml': tomllib.loads,
    '.yml': _yaml_mapping,
    '.yaml': _yaml_mapping,
}


def _registry_paths(root: Path) -> list[Finding]:
    """Every deployed config naming the repo registry has to name the same file.

    The deploy model is symlinks, so the deployed file *is* the repo file and there
    is no templating to interpolate a path with. Each tool that reads the registry
    therefore carries the literal, and the fleet side writes it out once per tool.
    Repeating it is the accepted cost; this is what keeps the copies from drifting,
    which is the failure the shared `$REPOS_JSON` variable existed to prevent and
    could not — it was unset in every process that sourced no profile.

    Two rules, both of which fail silently without one. The path may be named only
    under `configs/trust/`, because a machine selects exactly one trust variant while
    every other directory reaches both domains — a registry named in `configs/common/`
    is the fleet's answer deployed to the machine that is not on the fleet. And
    within one trust value every copy must be the same string, because they all
    resolve on the same machine and a tool reading the odd one out just answers
    about a different set of repos.

    Only `.toml`, `.yml` and `.yaml` are read, which is every format a tool config
    here is written in. Parsed rather than matched, so a commented-out example is
    correctly not a declaration.
    """
    findings: list[Finding] = []
    by_trust: dict[str, dict[str, str]] = {}
    for config in sorted((root / 'configs').rglob('*')):
        parse = PARSEABLE_CONFIGS.get(config.suffix)
        if parse is None or not config.is_file():
            continue
        try:
            declared = parse(config.read_text()).get(REGISTRY_KEY)
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, yaml.YAMLError) as unreadable:
            findings.append(Finding('registry', Severity.ERROR, f'{config.relative_to(root)} cannot be read — {unreadable}'))
            continue
        if not declared:
            continue
        relative = str(config.relative_to(root))
        axis, *within = config.relative_to(root / 'configs').parts
        if axis != 'trust':
            findings.append(
                Finding(
                    'registry',
                    Severity.ERROR,
                    f'{relative} names {REGISTRY_KEY} outside configs/trust/, so it deploys the same registry '
                    f'to both trust domains; move the file into the trust variant that wants it',
                )
            )
            continue
        by_trust.setdefault(within[0], {})[relative] = str(declared)

    for trust in sorted(by_trust):
        named = by_trust[trust]
        if len(set(named.values())) <= 1:
            continue
        disagreement = '; '.join(f'{where} says {path}' for where, path in sorted(named.items()))
        findings.append(Finding('registry', Severity.ERROR, f'the {trust} variant names more than one registry — {disagreement}'))
    return findings


REMOTE_TABLE = 'remote'
DOTFILES_CONFIG = '.config/dotfiles/config.toml'


def _remote_tables(root: Path) -> list[Finding]:
    """Every variant of this tool's own config declares the same remote, or none does.

    A bundle is built on one machine and collected on another, and the two are on
    opposite sides of the trust axis — so they read different copies of this file
    and have to arrive at one server. A copy that drifts does not fail: the upload
    succeeds onto a shelf the other end never lists, which reads as a handoff that
    was never built.

    Omission is checked as well as disagreement, and it is the likelier fault. One
    variant edited and the other forgotten leaves the declared copies trivially in
    agreement while the machine that was forgotten has no remote at all.
    """
    declared: dict[str, Any] = {}
    absent: list[str] = []
    findings: list[Finding] = []
    for config in sorted((root / 'configs').rglob(DOTFILES_CONFIG)):
        relative = str(config.relative_to(root))
        try:
            table = tomllib.loads(config.read_text()).get(REMOTE_TABLE)
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as unreadable:
            findings.append(Finding(REMOTE_TABLE, Severity.ERROR, f'{relative} cannot be read — {unreadable}'))
            continue
        if table is None:
            absent.append(relative)
        else:
            declared[relative] = table

    if not declared:
        return findings
    if absent:
        findings.append(
            Finding(
                REMOTE_TABLE,
                Severity.ERROR,
                f'{", ".join(sorted(declared))} declares a {REMOTE_TABLE} table and {", ".join(absent)} does not, '
                f'so the machines reading each address different servers',
            )
        )
    # Compared as parsed values rather than as text, so whitespace and key order
    # are not a difference and a retyped table is only reported when it says
    # something else.
    if not all(table == next(iter(declared.values())) for table in declared.values()):
        findings.append(Finding(REMOTE_TABLE, Severity.ERROR, f'{", ".join(sorted(declared))} declare different {REMOTE_TABLE} tables'))
    return findings
