"""Whether a declared item is actually installed, and how that was decided.

One module because two resources ask it. `packages` owns the tools and `system`
owns what the OS package manager put there, and both need the same answer to "is
this present" — so the evidence rules live below both rather than in one of them
importing the other.

The rules are per provider rather than one function branching on a section name.
`check_installed` was the latter, with a chain of `if section in (...)` tests,
which is why a section it did not name defaulted to "look for a binary called
that" and read as permanently missing.

Which rule answers for which provider is not here: it is the provider's own, in
`registry.py`. This file holds the rules and the inventory queries — the parts
that are about *how* to look rather than about *who* installs what.

An item nothing can measure comes back `UNKNOWN`. Unverified is not permission,
and "will reinstall" from an empty version string is the wrong answer with no way
to tell it from a measured one.
"""

from __future__ import annotations

import dataclasses as dc
import os
import shutil
from pathlib import Path
from typing import Protocol

from dotfiles import catalog
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.providers import syspkg
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Preconditions
from dotfiles.resources import Verdict


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


def executables_on_path(checkout: Path, search: str | None = None) -> dict[str, tuple[str, ...]]:
    """Every name PATH can resolve, to every location that answers for it.

    `shutil.which` answers with the winner alone, which is the right answer to
    "is it installed" and no answer at all to "how many of it are there". One walk
    of the PATH directories rather than a `which -a` per item: the check this
    replaced ran a subprocess per declared tool, and `symlinks._link_for` is the
    same lesson from the other direction.

    Deduplicated by real path, because `~/.local/bin/fd` pointing at `/usr/bin/fd`
    is one installation reachable by two names and not two installations. Order is
    PATH order, so the first entry is the copy that wins.

    `checkout` is left out entirely: `uv run dotfiles check` from the repo puts
    `.venv/bin` in front, and a second `mypy` that exists for the duration of a
    development command is not machine state. Taken as an argument rather than
    read from `paths` because the run's own checkout is the one that matters — the
    same reason `Session` carries `repo`.
    """
    found: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    excluded = str(checkout)

    for directory in (os.environ.get('PATH', '') if search is None else search).split(os.pathsep):
        if not directory or directory == excluded or directory.startswith(f'{excluded}{os.sep}'):
            continue
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError:
            continue
        for entry in entries:
            if not entry.is_file() or not os.access(entry.path, os.X_OK):
                continue
            real = os.path.realpath(entry.path)
            if real in seen.setdefault(entry.name, set()):
                continue
            seen[entry.name].add(real)
            found.setdefault(entry.name, []).append(entry.path)

    return {name: tuple(paths_) for name, paths_ in found.items()}


QUERIES: dict[str, list[str]] = {
    'pacman': ['pacman', '-Qq'],
    'apt': ['dpkg-query', '-W', '-f=${Package}\n'],
    'brew': ['brew', 'list', '--formula', '-1'],
    'cask': ['brew', 'list', '--cask', '-1'],
    'flatpak': ['flatpak', 'list', '--app', '--columns=application'],
    'mas': ['mas', 'list'],
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
    'mas': 'mas',
}
"""Which query answers for an installer.

`aur` shares pacman's, because an AUR package is a pacman package once it is
installed. Every installer needs an entry here rather than a `.get` default: a
missing key and an unqueryable one would look the same, and `flatpak` was exactly
that, reporting UNKNOWN on a machine where the query works and both apps are
installed.
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
    """A cask. Its CLI, where it has one, is a second question."""
    bundle = macos_app(item.name)
    if bundle:
        return Evidence(Verdict.MATCHED, str(bundle))
    if item.executable:
        return by_command(item)
    return Evidence(Verdict.MISSING, f'no {item.name}.app in /Applications')


def by_app_store(item: DesiredItem, installed: Inventory) -> Evidence:
    """An App Store app: its bundle first, then what `mas` says it installed.

    Two sources because neither alone is the truth. The bundle catches an app
    restored by Migration Assistant — present and working, and absent from `mas
    list` because mas never installed it here. `mas` catches an app whose bundle
    name is not its store title, which no name-derived path can find: 446243721
    is `Disk Space Analyzer` in the store and `Disk Inspector.app` on disk.

    What was here before asked the bundle and then fell through to `by_command`,
    which is `shutil.which`. A GUI app is never on PATH, so every app the bundle
    name missed was permanently MISSING — and `apply` re-ran `mas install` for it
    on every run, which is the unconditional re-run standing in for a measurement
    that this engine is built to not have.
    """
    bundle = macos_app(item.name)
    if bundle:
        return Evidence(Verdict.MATCHED, str(bundle))

    identifier = item.entry.id if isinstance(item.entry, catalog.MasApp) else None
    inventory = installed.get(INSTALLER_QUERIES['mas'])
    if inventory is None:
        return Evidence(Verdict.UNKNOWN, f'no {item.name}.app in /Applications, and mas could not be asked')
    if identifier is not None and str(identifier) in inventory:
        return Evidence(Verdict.MATCHED, f'mas: {identifier}')
    return Evidence(Verdict.MISSING, f'no {item.name}.app in /Applications, and mas has not installed {identifier}')


OUTDATED_PREFIX = 'outdated:'
"""What turns an inventory key into a currency question: `outdated:pacman`.

A prefix on the same `get` rather than a second method on the protocol, because
the protocol's whole value is that a test can hand in a plain dict of the answers
it wants. A second method makes a dict stop being an Inventory, and every test
that measures a package would need a fake instead.
"""


def query(name: str, *, refresh: bool = False) -> frozenset[str] | None:
    """What one manager says, or None when it cannot answer or was not asked.

    Two questions through one door: what is installed, and what is installed and
    behind. The second is prefixed, and the networked ones among them answer only
    under `refresh` — Flathub and the App Store have no offline catalogue, and
    `check` runs at a prompt, in a pre-commit hook and on a timer.
    """
    if name.startswith(OUTDATED_PREFIX):
        manager = name.removeprefix(OUTDATED_PREFIX)
        return None if manager in syspkg.NETWORKED and not refresh else syspkg.outdated(manager)

    command = QUERIES.get(name)
    if command is None or not shutil.which(command[0]):
        return None
    result = run(command, output=Output.QUIET)
    if not result.ok:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if name == 'mas':
        # `mas list` prints `<id>  <Name>  (<version>)`, and the id is the only
        # field an entry can be matched on: the App Store title and the bundle
        # name are free to differ, and for 446243721 they do — the store calls it
        # `Disk Space Analyzer` and it installs as `Disk Inspector.app`.
        return frozenset(line.split()[0] for line in lines)
    return frozenset(lines)


class Inventory(Protocol):
    """Whatever can answer "what does this manager have installed".

    A protocol rather than the concrete `Inventories`, so a test hands in a plain
    dict of the answers it wants and never reaches a subprocess. That is the
    whole reason the lookup is `.get(name)` — it is `Mapping.get`'s shape.
    """

    def get(self, name: str) -> frozenset[str] | None: ...


def by_currency(item: DesiredItem, installed: Inventory) -> Evidence:
    """Whether one package manager has anything installed and behind.

    STALE rather than MISSING, because the manager is there and doing its job —
    what has drifted is the machine's distance from what its repositories now
    hold. `Change.actionable` covers STALE, so this is repaired by `apply` without
    anything else having to know it is a different kind of row.

    A named sample rather than a bare count. "23 pacman package(s) behind" says a
    machine is behind and nothing about whether that matters; the first few names
    are usually enough to tell a routine sync from a kernel bump.
    """
    behind = installed.get(f'{OUTDATED_PREFIX}{item.name}')
    if behind is None:
        return Evidence(Verdict.UNKNOWN, f'nothing asked {item.name} what is behind — it is a network call, so pass --refresh')
    if not behind:
        return Evidence(Verdict.MATCHED, f'{item.name} has nothing to upgrade')
    named = ', '.join(sorted(behind)[:3])
    more = f' and {len(behind) - 3} more' if len(behind) > 3 else ''
    return Evidence(Verdict.STALE, f'{len(behind)} {item.name} package(s) behind: {named}{more}')


def by_registry(item: DesiredItem, installed: Inventory) -> Evidence:
    """Whether any name this entry declares appears in its manager's inventory.

    Per declared name rather than per entry name: the entry is `7zip` and the
    package is `p7zip-full` on apt and `7zip` on pacman.
    """
    for installer, names in declared_names(item).items():
        inventory = installed.get(INSTALLER_QUERIES[installer])
        if inventory is None:
            continue
        for name in names:
            if name in inventory:
                return Evidence(Verdict.MATCHED, f'{installer}: {name}')

    answered = [installer for installer in declared_names(item) if installed.get(INSTALLER_QUERIES[installer]) is not None]
    if not answered:
        return Evidence(Verdict.UNKNOWN, 'no package manager on this machine could be asked')
    return Evidence(Verdict.MISSING, f'not installed by {", ".join(answered)}')


def declared_names(item: DesiredItem) -> dict[str, list[str]]:
    """The names this item goes by, per installer."""
    if isinstance(item.entry, catalog.SystemPackage):
        return {installer: [name] for installer in ('apt', 'pacman', 'aur', 'brew') if (name := item.entry.package_for(installer))}
    if isinstance(item.entry, catalog.FlatpakApp):
        return {'flatpak': [item.entry.flatpak_id]}
    if isinstance(item.entry, catalog.MacosCask):
        return {'cask': [item.entry.name]}
    return {}


class Inventories:
    """What each package manager says it has, asked at most once per manager.

    Per manager, not per package: the check this replaced asked the world once per
    entry, which is 195 subprocesses to answer one question.

    Lazy per manager rather than computed up front from the plan, which is the
    shape it had while it belonged to one resource. Nothing under `packages` names
    a registry package — a release, a go tool and a cargo crate are all answered by
    PATH — so building the dict eagerly would spend `pacman -Qq` on behalf of a
    verb that never reads it. `system` asks for the two or three its own items
    name, and a whole-machine run asks for each of those exactly once.

    A manager that cannot answer caches its `None`, so a machine without flatpak
    is not re-asked once per flatpak app.
    """

    def __init__(self, *, refresh: bool = False) -> None:
        self._answers: dict[str, frozenset[str] | None] = {}
        self._refresh = refresh
        """Permission to spend the network on a currency question. See `query`."""

    def get(self, name: str) -> frozenset[str] | None:
        if name not in self._answers:
            self._answers[name] = query(name, refresh=self._refresh)
        return self._answers[name]

    @property
    def asked(self) -> frozenset[str]:
        """Which managers answered *what they have installed*, for a summary that
        would otherwise be a shrug.

        Currency keys are excluded rather than stripped to their manager: this
        names who vouched for the package inventory, and a manager that answered
        `outdated:` while its `pacman -Qq` failed vouched for nothing.
        """
        return frozenset(name for name, answer in self._answers.items() if answer is not None and not name.startswith(OUTDATED_PREFIX))


VERSION_PROBES = ('--version', 'version')
"""How to ask a binary what it is, in the order worth trying.

Two rather than one because `terrascan` takes the subcommand and rejects the
flag, and two rather than a per-tool field because a field carrying one
exception for 23 tools is a field nobody maintains. Both spellings are reads on
every CLI that has either.

Which is exactly the assumption `reports_version` on the entry exists to let a
declaration retract: a bare `version` is a read on a CLI and a *URL* to
`webviewrs`, whose first positional argument is what it opens.
"""

PROBE_SECONDS = 10.0
"""Long enough for a cold binary on a loaded machine, short enough that a tool
which is not going to answer does not hold the run.

The bound is here rather than left to the caller because the binary being run is
whatever a declaration names, and the failure it prevents is silent: a GUI blocks
on its event loop until a person closes a window, and the scheduled
`dotfiles check` has no person.
"""


def reported_version(executable: str) -> str | None:
    """What a binary says its version is, or None when it will not say.

    A non-zero exit is None rather than "whatever it printed": a tool that does
    not recognise the probe prints its usage, and usage text is full of numbers
    `versions.parse` would otherwise read as a version and report as behind. A
    probe that runs past `PROBE_SECONDS` is one more way of not saying.
    """
    found = shutil.which(executable)
    if not found:
        return None
    for probe in VERSION_PROBES:
        result = run([found, probe], output=Output.QUIET, timeout=PROBE_SECONDS)
        if result.ok and result.stdout.strip():
            return result.stdout.strip()
    return None


def have_github_credentials() -> bool:
    """The same question `github_token` in `version-helpers.sh` asks, so a check
    and the installers it gates cannot disagree about whether to try."""
    return bool(os.environ.get('GITHUB_TOKEN')) or run(['gh', 'auth', 'token'], output=Output.QUIET).ok


AMD_KFD = Path('/dev/kfd')
"""The kernel driver node ROCm talks to, and what a container has none of.

The same shape as `bootstrap.SYSTEM_BUS`, and for the same reason: ask the real
precondition rather than whether this is a test. A container without `--device`
has no `/dev/kfd`, and so does a machine with an Nvidia card or no discrete GPU
at all — one probe, right in all three cases, where `DOTFILES_DOCKER_TEST` would
be a test harness telling production code it is being tested.

`lspci` was the alternative and is worse: it answers "an AMD device exists"
rather than "the compute stack can reach it", and it is one more binary to
require on a machine deciding whether to install 12 GiB.
"""


def have_amd_gpu() -> bool:
    return AMD_KFD.exists()


def measured_preconditions() -> Preconditions:
    """Every precondition, answered once for the whole observation.

    Both probes here rather than one per resource, because a machine's credentials
    and its GPU do not vary between two entries asking about them — and because
    the `gh` call is the expensive one and was already being made per resource.
    """
    return Preconditions(github_auth=have_github_credentials(), amd_gpu=have_amd_gpu())
