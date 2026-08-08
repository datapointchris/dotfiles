"""Everything installed from a package manager, a registry or a release.

The observation half of what `packages missing` answered, with one difference
that matters: the evidence is per provider rather than one `check_installed`
walking a raw dict and guessing from the section name. A uv tool installs a
directory and sometimes no console script, a cask installs an app bundle and
sometimes no binary, and `bashselfupdate` installs neither — the old function
handled all three with a chain of `if section in (...)` branches, which is why a
section it did not name defaulted to "look for a binary called that" and read as
permanently missing.

An item nothing can measure comes back `UNKNOWN` rather than present or absent.
Unverified is not permission, and "will reinstall" from an empty version string
is the wrong answer with no way to tell it from a measured one.
"""

from __future__ import annotations

import dataclasses as dc
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from dotfiles import catalog
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Precondition
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'packages'


@dc.dataclass(frozen=True, slots=True)
class Evidence:
    """What was found for one item, and where."""

    verdict: Verdict
    detail: str = ''


def uv_tool_dir() -> Path:
    """Where `uv tool install` puts a tool's own environment.

    From the environment, because that is the knob uv itself honours — which is
    also what lets a test point it somewhere without patching anything.
    """
    return Path(os.environ.get('UV_TOOL_DIR') or Path.home() / '.local/share/uv/tools')


def macos_app(name: str) -> Path | None:
    """A `.app` bundle by name, case-insensitively.

    The declaration spells an app the way the App Store does, and the bundle on
    disk does not always agree.
    """
    wanted = f'{name}.app'.lower()
    for base in (Path('/Applications'), Path.home() / 'Applications'):
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            if entry.name.lower() == wanted:
                return entry
    return None


QUERIES: dict[str, list[str]] = {
    'pacman': ['pacman', '-Qq'],
    'apt': ['dpkg-query', '-W', '-f=${Package}\n'],
    'brew': ['brew', 'list', '--formula', '-1'],
    'cask': ['brew', 'list', '--cask', '-1'],
    'flatpak': ['flatpak', 'list', '--app', '--columns=application'],
}
"""The unprivileged read behind each privileged write.

Every one of these answers without sudo, which is what lets `observe` never
escalate — and what lets the container harnesses run without a passwordless-sudo
carve-out.
"""

INSTALLER_QUERIES = {
    'apt': 'apt',
    'pacman': 'pacman',
    'aur': 'pacman',
    'brew': 'brew',
    'cask': 'cask',
    'flatpak': 'flatpak',
    'mas': '',
}
"""Which query answers for an installer.

`aur` shares pacman's, because an AUR package is a pacman package once it is
installed. `mas` has none — an App Store app is judged by its bundle — and that
empty string is why every installer needs an entry here rather than a `.get`
default: a missing key and a deliberately unqueryable one would look the same,
and `flatpak` was exactly that, reporting UNKNOWN on a machine where the query
works and both apps are installed.
"""


def by_command(item: DesiredItem) -> Evidence:
    """The default: a binary on PATH named by the entry."""
    if not item.executable:
        return Evidence(Verdict.UNKNOWN, 'installs no binary and declares no path, so nothing here can measure it')
    found = shutil.which(item.executable)
    return Evidence(Verdict.MATCHED, found) if found else Evidence(Verdict.MISSING, f'{item.executable} is not on PATH')


def by_path(item: DesiredItem) -> Evidence:
    """A declared `installed_path`, for an entry that puts nothing on PATH.

    `bashselfupdate` is a sourced library: the checkout is the only evidence.
    """
    target = Path(item.evidence_path).expanduser()
    return Evidence(Verdict.MATCHED if target.exists() else Verdict.MISSING, str(target))


def by_uv_tool(item: DesiredItem) -> Evidence:
    """uv installs a tool per directory, and some are libraries with no script.

    numpy is pulled in for the Jupyter stack and has nothing for `which` to find,
    so asking PATH about it answers "missing" forever.
    """
    directory = uv_tool_dir() / item.name
    if directory.is_dir():
        return Evidence(Verdict.MATCHED, str(directory))
    if item.executable:
        return by_command(item)
    return Evidence(Verdict.MISSING, f'no tool directory at {directory}')


def by_app_bundle(item: DesiredItem) -> Evidence:
    """A cask or App Store app. Its CLI, where it has one, is a second question."""
    bundle = macos_app(item.name)
    if bundle:
        return Evidence(Verdict.MATCHED, str(bundle))
    if item.executable:
        return by_command(item)
    return Evidence(Verdict.MISSING, f'no {item.name}.app in /Applications')


EVIDENCE: dict[str, Callable[[DesiredItem], Evidence]] = {
    'uv': by_uv_tool,
    'uv-git': by_uv_tool,
    'mas': by_app_bundle,
}
"""How to tell whether one provider's item is present, where the answer is local.

Absent from this map means one of two things: a binary on PATH — right for
releases, go, cargo, npm and the custom installers — or, for the providers in
`REGISTRY_PROVIDERS`, asking the package manager. A declared `installed_path`
overrides both, because an entry saying where it lands is more specific than any
rule about its provider.
"""

REGISTRY_PROVIDERS = frozenset({'system', 'cask', 'flatpak'})
"""Providers whose items are only answerable by their manager.

A package name is not a binary name: `p7zip-full` installs `7zz`, and
`build-essential` and `ca-certificates` install no executable at all. Asking PATH
about them reports every one of them missing on a fully-installed machine, which
is why the check that predated this skipped these sections rather than getting
them wrong.
"""


@dc.dataclass(frozen=True, slots=True)
class Observed:
    evidence: dict[str, Evidence]
    have_github_credentials: bool
    queried: frozenset[str]
    """Which managers answered, so a provider whose manager is absent can report
    UNKNOWN rather than reporting everything it declares as missing."""


def query(name: str) -> frozenset[str] | None:
    """What one manager says it has installed, or None when it cannot answer."""
    command = QUERIES.get(name)
    if command is None or not shutil.which(command[0]):
        return None
    result = run(command, output=Output.QUIET)
    if not result.ok:
        return None
    return frozenset(line.strip() for line in result.transcript.splitlines() if line.strip())


def by_registry(item: DesiredItem, installed: dict[str, frozenset[str]]) -> Evidence:
    """Whether any name this entry declares appears in its manager's inventory.

    Per declared name rather than per entry name: the entry is `7zip` and the
    package is `p7zip-full` on apt and `7zip` on pacman.
    """
    for installer, names in _declared_names(item).items():
        inventory = installed.get(INSTALLER_QUERIES.get(installer, ''))
        if inventory is None:
            continue
        for name in names:
            if name in inventory:
                return Evidence(Verdict.MATCHED, f'{installer}: {name}')

    answered = [installer for installer in _declared_names(item) if installed.get(INSTALLER_QUERIES.get(installer, '')) is not None]
    if not answered:
        return Evidence(Verdict.UNKNOWN, 'no package manager on this machine could be asked')
    return Evidence(Verdict.MISSING, f'not installed by {", ".join(answered)}')


def _declared_names(item: DesiredItem) -> dict[str, list[str]]:
    """The names this item goes by, per installer."""
    if isinstance(item.entry, catalog.SystemPackage):
        return {installer: [name] for installer in ('apt', 'pacman', 'aur', 'brew') if (name := item.entry.package_for(installer))}
    if isinstance(item.entry, catalog.FlatpakApp):
        return {'flatpak': [item.entry.flatpak_id]}
    if isinstance(item.entry, catalog.MacosCask):
        return {'cask': [item.entry.name]}
    return {}


def evidence_for(item: DesiredItem, installed: dict[str, frozenset[str]]) -> Evidence:
    if item.evidence_path:
        return by_path(item)
    if item.provider in REGISTRY_PROVIDERS:
        return by_registry(item, installed)
    return EVIDENCE.get(item.provider, by_command)(item)


class PackagesResource:
    name = NAME
    help = 'everything installed from a package manager or a release'

    def observe(self, session: Session, plan: Plan) -> Observed:
        """One inventory query per manager, not one per package.

        The whole reason this is a resource: `packages missing` asked the world
        per entry, so the answer cost a subprocess 195 times.
        """
        mine = plan.for_resource(NAME)
        wanted = {INSTALLER_QUERIES.get(installer, '') for item in mine for installer in _declared_names(item)}
        installed = {name: answer for name in wanted if name and (answer := query(name)) is not None}

        return Observed(
            evidence={item.address: evidence_for(item, installed) for item in mine},
            have_github_credentials=have_github_credentials(),
            queried=frozenset(installed),
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        changes = []
        for item in plan.for_resource(NAME):
            evidence = observed.evidence[item.address]
            if evidence.verdict is Verdict.MATCHED:
                continue
            changes.append(
                Change(
                    NAME,
                    item.stage,
                    item.address,
                    evidence.verdict,
                    detail=evidence.detail,
                    repair=_repair(item, observed, evidence),
                    desired=item,
                )
            )
        return tuple(changes)

    def perform(self, session: Session, change: Change) -> Outcome:
        """Not yet this resource's to do.

        Every provider's install still runs through the phase registry in
        `apply.py`, which knows the PATH each one needs and the order they have to
        happen in. Refused rather than silently skipped, because a resource that
        did nothing quietly would leave `apply` reporting a converged machine.
        """
        return Outcome(change, OutcomeStatus.REFUSED, "run 'dotfiles packages apply', which still drives the phase registry")


def _repair(item: DesiredItem, observed: Observed, evidence: Evidence) -> Repair:
    """Whether `apply` could do anything about this.

    A private repo without credentials cannot be installed here: attempting it
    records a failure for something the machine was never able to have, and the
    run exits non-zero for a reason no change to this repo can fix. Warned rather
    than silent, because a `gh` login is state a machine can lose.

    An unmeasurable item is nobody's to repair either — there is no verdict to
    act on, only one to report.
    """
    if evidence.verdict is Verdict.UNKNOWN:
        return Repair.NONE
    if item.precondition is Precondition.GITHUB_AUTH and not observed.have_github_credentials:
        return Repair.BY_HAND
    return Repair.AUTOMATIC


def have_github_credentials() -> bool:
    """The same question `github_token` in `version-helpers.sh` asks, so the check
    and the installers it gates cannot disagree about whether to try."""
    return bool(os.environ.get('GITHUB_TOKEN')) or run(['gh', 'auth', 'token'], output=Output.QUIET).ok


RESOURCE = PackagesResource()
