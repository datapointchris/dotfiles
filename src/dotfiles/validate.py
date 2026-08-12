"""Is the declaration itself sound, before any machine is measured against it.

`packages verify` asked this by re-parsing `packages.yml` and every manifest as
raw dictionaries — a second parser beside `catalog.py` and `machine.py`, walking
the same files with its own idea of how a section is spelled and its own copy of
which manifest keys were retired. Two descriptions of one file is the drift the
typed loaders were built to end, and `verify` was the last thing still holding
the untyped one.

Everything here reads the loaded objects. A rule the dataclasses can enforce is
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
from pathlib import Path

from dotfiles import catalog as catalogs
from dotfiles import machine as machines
from dotfiles import paths


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
        for tool in sorted(set(manifest.logins) - set(auth.PROBES)):
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
