"""Installing OS packages: one transaction per manager, and the refresh before it.

The four managers differ in three ways and agree on everything else, so this is a
table plus one function rather than four installers.

**Root is per manager, not per package.** pacman and apt write to the system and
escalate; brew owns its own prefix and must *not* be run under sudo, which it
refuses outright; yay escalates itself per operation and breaks if handed a
prefix it did not ask for. Getting that backwards is not a style question — `sudo
brew` is an error message, and `sudo yay` is a build running as root.

**The refresh is a precondition, not politeness.** `pacman -Syu` before `-S`
because Arch does not support partial upgrades: installing against a stale
database is how a machine ends up with a binary linked against a library version
the repo has already moved past. `apt update` because apt resolves against its
cached lists, and a cache older than the archive's last publish gives 404s on
files that exist. Once per manager per run, not once per package.

**A failed transaction is retried one package at a time.** That is not a
workaround for flakiness, it is how the report gets to name the package that
failed: `brew install a b c` exiting 1 says nothing about which of the three is
broken, and the machine still wants the other two. The bash did this for brew
alone; every manager gets it here, because the reason has nothing to do with
brew.
"""

from __future__ import annotations

from collections.abc import Sequence

from dotfiles import effects
from dotfiles.effects import Output
from dotfiles.privilege import Privilege
from dotfiles.privilege import PrivilegeUnavailable
from dotfiles.privilege import refusal
from dotfiles.providers import Result

INSTALL: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-S', '--needed', '--noconfirm'),
    'aur': ('yay', '-S', '--needed', '--noconfirm'),
    'apt': ('apt-get', 'install', '-y'),
    'brew': ('brew', 'install', '--quiet'),
    'cask': ('brew', 'install', '--quiet', '--cask'),
    'mas': ('mas', 'install'),
    'flatpak': ('flatpak', 'install', '-y', 'flathub'),
}
"""How each manager is told to install, before the names are appended.

`--needed` and `-y` and `--quiet` are all the same instruction in three dialects:
do not ask, and do not reinstall what is already there. `apt-get` rather than
`apt`, which prints "this is not a stable CLI" to stderr on every scripted call.

The last three are here rather than in three modules of their own because they
differ from the first four in nothing this file knows about: same batching, same
per-package fallback, same absence of a refresh. A cask is a formula installed
from a different tap of the same manager, `mas install` takes numeric ids where
the others take names, and flatpak names a remote before its ids. That is the
whole of the difference, and each of those is one tuple.
"""

REFRESH: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-Syu', '--noconfirm'),
    'apt': ('apt-get', 'update'),
}
"""What has to happen once before the first install. brew, yay, mas and flatpak
refresh themselves as part of installing, so naming them here would be a second
download of the same index."""

ESCALATES: frozenset[str] = frozenset({'pacman', 'apt'})
"""Which managers this package runs through sudo.

brew and its casks are absent deliberately and refuse to run as root; yay is
absent because it escalates itself for the parts that need it, and running the
whole build as root is how an AUR package ends up with root-owned files in the
build cache. mas installs into the user's App Store session and flatpak into a
per-user installation, so neither has anything to escalate for.
"""

PREFERENCE: tuple[str, ...] = ('pacman', 'apt', 'brew', 'aur')
"""Which manager wins where an entry declares a package under several.

The AUR is last on purpose: a package in both the official repos and the AUR
should come from the repos, where it is built and signed rather than compiled
here. The order is otherwise irrelevant, since no machine has two of the first
three.

Casks, App Store apps and flatpak apps are absent because their sections declare
one name and no alternative — there is nothing to prefer between.
"""


def install(manager: str, names: Sequence[str], privilege: Privilege) -> Result:
    """One transaction. The caller has already refreshed and grouped.

    Streamed on both branches, and the escalating one has to ask: `Privilege.run`
    defaults to `Output.QUIET` where `effects.run` defaults to `Output.STREAM`, so
    without this apt and pacman — the two managers that install the most — go
    silent through a transaction over every declared package while brew and
    flatpak do not. `Output.STREAM` records the reason in its own docstring, and
    it keeps the transcript, so the failure detail below is unaffected.
    """
    command = [*INSTALL[manager], *names]
    try:
        completed = (
            privilege.run(command, reason=f'install {len(names)} package(s) with {manager}', output=Output.STREAM)
            if manager in ESCALATES
            else effects.run(command)
        )
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state))

    if completed.ok:
        return Result(True, f'{manager}: {" ".join(names)}')
    return Result(False, f'{" ".join(command[:2])} exited {completed.returncode}')


def refresh(manager: str, privilege: Privilege) -> Result:
    """Bring the manager's index up to date, or say why the install should stop.

    A failure here is fatal to the batch rather than a warning. Installing against
    a database that could not be refreshed is the partial-upgrade case on Arch and
    the 404 case on apt, and both fail later in a way that names the wrong cause.
    """
    command = REFRESH.get(manager)
    if command is None:
        return Result(True, '')
    try:
        completed = privilege.run(list(command), reason=f'refresh the {manager} package database')
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state))
    return Result(True, '') if completed.ok else Result(False, f'{" ".join(command)} exited {completed.returncode}')


def available(manager: str) -> bool:
    return effects.run([INSTALL[manager][0], '--version'], output=Output.QUIET, timeout=PROBE_SECONDS).ok


# ─────────────────────────────────────────────────────────────────────────────
# Currency: what is installed and behind
# ─────────────────────────────────────────────────────────────────────────────

OUTDATED: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-Qu'),
    'aur': ('yay', '-Qu'),
    'apt': ('apt', 'list', '--upgradable'),
    'brew': ('brew', 'outdated', '--formula', '--quiet'),
    'cask': ('brew', 'outdated', '--cask', '--greedy', '--quiet'),
    'flatpak': ('flatpak', 'remote-ls', '--updates', '--columns=application'),
    'mas': ('mas', 'outdated'),
}
"""How each manager is asked what it has installed and behind.

The first five read a local index and cost milliseconds; the last two are network
calls, which is why `NETWORKED` exists rather than this table being uniform.

`yay -Qu` rather than `pacman -Qu` for the AUR: both list the same local
packages, but only yay knows an AUR package's upstream version, so pacman reports
every one of them current forever.

`--greedy` on the casks because an auto-updating cask is excluded otherwise, and
this repo installed it and would like to know. That is the flag `update.sh` used
and the reason it used it.
"""

EMPTY_IS_NONZERO: frozenset[str] = frozenset({'pacman', 'aur'})
"""Which currency queries report "nothing to upgrade" as a failure.

`pacman -Qu` exits 1 having printed nothing when every package is current, which
is the query's convention for an empty result rather than an error — the same one
`grep` uses. Reading that as "the manager could not answer" is what the first
version of this did, and it reported a fully-current Arch box as unmeasurable.

Only these two, and only with no output: a genuine pacman failure prints to
stderr, which `Output.QUIET` keeps in the same transcript, so a non-zero exit that
said something is still a non-answer.
"""

NETWORKED: frozenset[str] = frozenset({'flatpak', 'mas'})
"""Which currency reads reach the network, and so are measured only on request.

There is no local answer for either: Flathub's available versions live on
Flathub, and the App Store has no offline catalogue. `check` runs at a prompt, in
a pre-commit hook and on a timer, so it must not spend a round trip to say
whether Discord is behind — the same rule the release cache follows, arrived at
for the same reason.
"""

UPGRADE: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-Syu', '--noconfirm'),
    'aur': ('yay', '-Syu', '--noconfirm'),
    'apt': ('apt-get', 'upgrade', '-y'),
    'brew': ('brew', 'upgrade'),
    'cask': ('brew', 'upgrade', '--cask', '--greedy'),
    'flatpak': ('flatpak', 'update', '-y'),
    'mas': ('mas', 'upgrade'),
}
"""How each manager upgrades everything it installed.

Whole-machine rather than per package, which is not a shortcut: Arch does not
support partial upgrades at all, and for the rest a declared package's
dependencies are as much this repo's business as the package. `pacman -S <name>`
would upgrade one package and leave the machine in a combination nobody tests.

The pacman and yay rows are the same command as their `REFRESH`, because on Arch
the sync *is* the upgrade. Spelling it twice is deliberate: `refresh` runs before
an install, `upgrade` runs because a machine is behind, and a later change to one
should not silently move the other.
"""


def outdated(manager: str) -> frozenset[str] | None:
    """What this manager has installed and behind, or None where it cannot say.

    None rather than an empty set, because "nothing is behind" and "nobody
    asked" are the difference between MATCHED and UNKNOWN — and reporting a
    machine current because its package manager is absent is the failure this
    whole resource exists to avoid.

    An empty result is also returned for a manager with nothing to upgrade, and
    that is the answer, not a non-answer: the command exited 0 having listed
    nothing.
    """
    command = OUTDATED.get(manager)
    if command is None or not effects.run([command[0], '--version'], output=Output.QUIET, timeout=PROBE_SECONDS).ok:
        return None
    listed = effects.run(list(command), output=Output.QUIET)
    if listed.ok:
        return _names(listed.transcript)
    silent = not listed.transcript.strip()
    return frozenset() if manager in EMPTY_IS_NONZERO and silent else None


def _names(transcript: str) -> frozenset[str]:
    """The package each line names, ignoring the lines that name none.

    Field one, since every one of these prints `<name> <versions…>` or a bare
    name — `mas` included, whose field one is the numeric id it is addressed by.
    Two adjustments, both apt's: it spells the name `curl/noble-updates`, so a
    name ends at its first `/`, and it prefaces the list with `Listing...` and a
    warning that its CLI is not stable, on the same stream as the answer. A first
    field ending in `.` or `:` is apt talking rather than apt answering.
    """
    found = set()
    for line in transcript.splitlines():
        field = line.split()[0] if line.split() else ''
        if not field or field.endswith(('.', ':')):
            continue
        found.add(field.split('/')[0])
    return frozenset(found)


def upgrade(manager: str, privilege: Privilege) -> Result:
    """Bring everything this manager installed up to date."""
    command = list(UPGRADE[manager])
    try:
        completed = (
            privilege.run(command, reason=f'upgrade every {manager} package', output=Output.STREAM)
            if manager in ESCALATES
            else effects.run(command)
        )
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state))
    if completed.ok:
        return Result(True, f'{" ".join(command)}')
    return Result(False, f'{" ".join(command[:2])} exited {completed.returncode}')


PROBE_SECONDS = 10.0
"""Long enough for a cold binary, short enough that a manager which is not going
to answer does not hold the run. Same bound and same reason as
`evidence.PROBE_SECONDS`."""
