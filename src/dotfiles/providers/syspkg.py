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

import contextlib
import functools
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from dotfiles import effects
from dotfiles.effects import Output
from dotfiles.privilege import Privilege
from dotfiles.privilege import PrivilegeUnavailable
from dotfiles.privilege import refusal
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import systemd

REMOVE: dict[str, str] = {
    'pacman': 'sudo pacman -R',
    'aur': 'sudo pacman -R',
    'apt': 'sudo apt-get remove',
    'brew': 'brew uninstall',
    'cask': 'brew uninstall --cask',
    'flatpak': 'flatpak uninstall',
}
"""How a person is told to remove a package. Strings to read and paste, not argv.

Removal is inferred nowhere: a declaration names what a machine should have, and an
uninstall worked out from what it does not name takes a package off the machine on
the strength of a typo. The one removal this repo performs is the one that is
*named* and then *authorised* — a release's `supersedes` row, reviewed in a commit,
with `--force` typed on the apply — and `UNINSTALL` below is what performs it.
Everything else measures the need and stops, with the sentence it stops with built
from here.

`aur` removes as `pacman`, because an AUR package is a pacman package once it is
installed. `mas` has no entry at all — the App Store ships no uninstall verb, so
there is no command to offer and a wrong one would be worse than none. Nothing
looks one up for it either: `evidence.blocker` indexes this directly, over the
installers `evidence.declared_names` and `evidence.superseded` return, and an App
Store app is measured by `by_app_store` instead. An installer added to either and
not to this mapping raises here rather than offering a blank command.
"""

UNINSTALL: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-R', '--noconfirm'),
    'aur': ('pacman', '-R', '--noconfirm'),
    'apt': ('dpkg', '--remove'),
    'brew': ('brew', 'uninstall'),
    'cask': ('brew', 'uninstall', '--cask'),
    'flatpak': ('flatpak', 'uninstall', '-y'),
}
"""How each manager is told to remove one named package unattended.

Deliberately not derived from `REMOVE` and not the source of it, because the two are
written for different readers. A person pasting `sudo pacman -R syncthing` is asked
before anything happens, which is right at a prompt and a deadlock in a run nobody is
watching, so deriving either from the other would put `--noconfirm` in front of a
person or a prompt in front of a timer.

**`dpkg --remove` rather than `apt-get remove -y`, and that is the second difference.**
`pacman -R` refuses while another installed package needs the one being removed, so an
authorisation to remove one name cannot take a set. apt resolves reverse dependencies
instead, and `-y` answers the confirmation that would have shown the list — so the same
`--force` authorising one removal on Arch authorises an unbounded one on Debian. `dpkg
--remove` is apt's fail-safe spelling of the same act: same database, same package
state, and it refuses exactly where pacman does. What it does not do is resolve
dependencies, which is the whole point here — this is only ever handed one name that a
`supersedes` row already wrote down.

Keyed identically to `REMOVE`, and a manager missing from one is missing from both:
`uninstall` reads this and `evidence.blocker` reads that, so a manager present in only
one would offer a sentence nothing can run, or run something nobody was shown.
"""

REMOVES_AS_ROOT: frozenset[str] = frozenset({'pacman', 'aur', 'apt'})
"""Which removals escalate, which is not the same set as `ESCALATES`.

`aur` is the difference. yay escalates itself for the parts of a *build* that need
it, which is why it is absent from `ESCALATES`; removing what it built is `pacman -R`
and that escalates like any other pacman write.
"""

INSTALL: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-S', '--needed', '--noconfirm'),
    'aur': ('yay', '-S', '--needed', '--noconfirm'),
    'apt': ('apt-get', 'install', '-y'),
    'brew': ('brew', 'install', '--quiet'),
    'cask': ('brew', 'install', '--quiet', '--cask', '--adopt'),
    'mas': ('mas', 'install'),
    'flatpak': ('flatpak', 'install', '-y', 'flathub'),
}
"""How each manager is told to install, before the names are appended.

`--needed` and `-y` and `--quiet` are all the same instruction in three dialects:
do not ask, and do not reinstall what is already there. `apt-get` rather than
`apt`, which prints "this is not a stable CLI" to stderr on every scripted call.

`--adopt` is the cask equivalent of the same idea, one step further out. A cask
whose app is already in /Applications — installed by hand before this repo
managed it, or restored by Migration Assistant — fails with "It seems there is
already an App at ...", every run, forever: the evidence check reads `brew list
--cask`, which never learns about a bundle brew did not put there. `--adopt`
takes ownership of an artifact *identical* to the one being installed and still
refuses anything else, so it converges the machine without being able to
overwrite a version nobody asked to replace.

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

OWNER: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-Qoq'),
    'apt': ('dpkg-query', '-S'),
}
"""How to ask which package a file on disk came from.

Only the two managers that own paths outside a prefix of their own, because this
answers one question: whether a second copy of a declared binary is something the
machine asked for. brew keeps its formulae in its own cellar and `Inventories`
already speaks for it; a cask, an App Store app and a flatpak put nothing on PATH
to attribute.
"""


UNCHOSEN: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-Qdq'),
    'apt': ('apt-mark', 'showauto'),
}
"""How to ask which packages are here to satisfy something else.

The distinction both managers already keep, and the one that separates a second
copy somebody installed from a second copy that arrived underneath one they did.
Measured in the Arch container: `/usr/lib/go/bin/go` sits beside the tarball's Go
because yay needs a compiler to build AUR packages, and on the personal
workstation `ripgrep` and `fzf` are there for the same kind of reason.
"""


def _answers(binary: str) -> bool:
    """Whether a package manager is here and will run.

    `owner_of` is called once per stray copy and asks two managers each time, so a
    machine with several strays spent dozens of forks re-establishing a constant.
    What is cached is the probe, and the fix for that is one `shutil.which` — a
    stat rather than a fork — in front of it.

    **Keyed on the resolved path, never on the name.** PATH is not fixed for the
    life of a process: `providers/toolchain.put_on_path` extends it as each
    runtime lands, and a test hands the resource a PATH of its own. Cached under
    the bare name, one test's fake `pacman` answers for the next test's — green on
    a desk where a real pacman makes the two agree, red on a runner without one.

    Still a probe rather than `which` alone, because the question is whether the
    manager *runs*: a `dpkg-query` present but broken and one absent are the same
    answer to this caller and different answers to `which`. `which` only decides
    *which* binary is being asked about, and answers the absent case for free.
    """
    found = shutil.which(binary)
    return bool(found) and _probe(found)


@functools.cache
def _probe(path: str) -> bool:
    return effects.run([path, '--version'], output=Output.QUIET, timeout=PROBE_SECONDS).ok


def unchosen() -> frozenset[str]:
    """Every package installed as a dependency rather than asked for by name."""
    found: set[str] = set()
    for manager, command in UNCHOSEN.items():
        if not _answers(INSTALL[manager][0]):
            continue
        listed = effects.run(list(command), output=Output.QUIET, timeout=PROBE_SECONDS)
        if listed.ok:
            found.update(line.strip() for line in listed.stdout.splitlines() if line.strip())
    return frozenset(found)


def owner_of(path: str) -> str:
    """The package that put a file there, or '' when no manager claims it.

    Empty for a file this repo installed itself — a release binary in
    `~/.local/bin`, a Go tool in `~/go/bin` — which is the answer, not a failure:
    those are placed by a provider rather than by a package manager, and the
    caller is asking precisely whether something *else* put a copy on PATH.

    The first manager that answers wins, and no machine here has two of them.
    """
    for manager, command in OWNER.items():
        if not _answers(command[0]):
            continue
        found = effects.run([*command, path], output=Output.QUIET, timeout=PROBE_SECONDS)
        if not found.ok or not found.stdout.strip():
            continue
        # `pacman -Qoq` prints the bare name; `dpkg-query -S` prints
        # `<package>: <path>`, and a diverted file lists several comma-separated.
        answer = found.stdout.splitlines()[0].strip()
        return answer.split(':')[0].split(',')[0].strip() if manager == 'apt' else answer
    return ''


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
        return Result(False, refusal(privilege.state), kind=Kind.PRIVILEGE_UNAVAILABLE)

    if completed.ok:
        return Result(True, f'{manager}: {" ".join(names)}', kind=Kind.APPLIED)
    return Result(False, f'{" ".join(command[:2])} exited {completed.returncode}', kind=Kind.COMMAND_FAILED)


def stop_service(manager: str, package: str, unit: str) -> None:
    """Stop whatever supervises a package, before the package goes.

    Neither `pacman -R` nor `brew uninstall` stops a running daemon: the process
    outlives its own package, holding the ports and the state directory the
    replacement is about to be pointed at — which is the two-daemons-over-one-config
    state `GithubRelease.supersedes` exists to prevent, recreated by the very act of
    honouring it.

    Best effort, and deliberately so. A package with no service, a service already
    stopped, and a `brew` that never registered one all report failure, and all three
    are the ordinary case. What is not tolerable is not trying.

    `unit` comes from the release's own declaration rather than from the package,
    because upstream and the distro package publish the same unit filename — which
    is what makes the name knowable here at all.
    """
    if manager in REMOVES_AS_ROOT and unit and systemd.available():
        systemd.disable(unit)
    elif manager in {'brew', 'cask'} and shutil.which('brew'):
        effects.run(['brew', 'services', 'stop', package], output=Output.QUIET)


def uninstall(manager: str, names: Sequence[str], privilege: Privilege) -> Result:
    """Take named packages off the machine, for a caller that was authorised to.

    Nothing here decides that it should happen. `evidence.superseded` measures the
    package, an entry's `supersedes` names it, and `--force` authorises it — so this
    is handed a list somebody wrote down and confirmed, which is the whole of what
    separates it from the inference `REMOVE` refuses to make.

    Streamed on both branches for `install`'s reason: a removal that resolves reverse
    dependencies can take a while, and a silent transaction reads as a hung run.
    """
    command = [*UNINSTALL[manager], *names]
    try:
        completed = (
            privilege.run(command, reason=f'remove {", ".join(names)} with {manager}', output=Output.STREAM)
            if manager in REMOVES_AS_ROOT
            else effects.run(command)
        )
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state), kind=Kind.PRIVILEGE_UNAVAILABLE)

    if completed.ok:
        return Result(True, f'{manager}: removed {" ".join(names)}', kind=Kind.APPLIED)
    return Result(False, f'{" ".join(command[:2])} exited {completed.returncode}', kind=Kind.COMMAND_FAILED)


def refresh(manager: str, privilege: Privilege) -> Result:
    """Bring the manager's index up to date, or say why the install should stop.

    A failure here is fatal to the batch rather than a warning. Installing against
    a database that could not be refreshed is the partial-upgrade case on Arch and
    the 404 case on apt, and both fail later in a way that names the wrong cause.
    """
    command = REFRESH.get(manager)
    if command is None:
        return Result(True, '', kind=Kind.UNCHANGED)
    try:
        completed = privilege.run(list(command), reason=f'refresh the {manager} package database')
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state), kind=Kind.PRIVILEGE_UNAVAILABLE)
    return (
        Result(True, '', kind=Kind.APPLIED)
        if completed.ok
        else Result(False, f'{" ".join(command)} exited {completed.returncode}', kind=Kind.COMMAND_FAILED)
    )


def available(manager: str) -> bool:
    return effects.run([INSTALL[manager][0], '--version'], output=Output.QUIET, timeout=PROBE_SECONDS).ok


# ─────────────────────────────────────────────────────────────────────────────
# Currency: what is installed and behind
# ─────────────────────────────────────────────────────────────────────────────

OUTDATED: dict[str, tuple[str, ...]] = {
    'pacman': ('checkupdates', '--nocolor'),
    'aur': ('yay', '-Qu', '--aur'),
    'apt': ('apt', 'list', '--upgradable'),
    'brew': ('brew', 'outdated', '--formula', '--quiet'),
    'cask': ('brew', 'outdated', '--cask', '--greedy', '--quiet'),
    'flatpak': ('flatpak', 'remote-ls', '--updates', '--columns=application'),
    'mas': ('mas', 'outdated'),
}
"""How each manager is asked what it has installed and behind.

**A manager that compares against a local index answers from whenever that index
was last synced.** `pacman -Qu` reads `/var/lib/pacman/sync`, so it reports what
was behind at the last `-Sy` and nothing since. Measured on this machine
2026-08-22, against a database 39 hours old: `pacman -Qu` printed nothing while
ten packages were behind, and `plan` said "pacman has nothing to upgrade". That
is the release cache's bug in a second manager — a figure correct when written,
answering a question asked later.

`checkupdates` is pacman-contrib's answer to it. It copies the sync database to a
private path, refreshes *that* under `fakeroot`, and reads the copy — so the
machine's own database is untouched and nothing needs root. Refreshing the real
one is not an option: `pacman -Sy` without the `-u` is the partial-upgrade state
Arch does not support, and a read verb must not leave a machine in it.

apt has the same defect and ships no equivalent, so `_apt_outdated` does the same
thing by hand and the row here is only its second half — the listing, which that
function runs against the copy it refreshed.

`--nocolor` because `Color` in `pacman.conf` would otherwise put escape codes in
front of the first field, and `_names` reads that field. A parser that depends on
a config file is one that works here and not on the next box.

`yay -Qu --aur` rather than a bare `-Qu`: both list the same local packages, but
only yay knows an AUR package's upstream version, so pacman reports every one of
them current forever. `--aur` is what keeps the two Arch rows from counting the
same repo package twice once `checkupdates` starts finding them.

`--greedy` on the casks because an auto-updating cask is excluded otherwise, and
this repo installed it and would like to know.
"""

EMPTY_IS_NONZERO: frozenset[str] = frozenset({'pacman', 'aur'})
"""Which currency queries report "nothing to upgrade" as a failure.

`checkupdates` exits 2 having printed nothing when every package is current, and
`yay -Qu` exits 1 — both the query's convention for an empty result rather than an
error, the same one `grep` uses. Reading that as "the manager could not answer" is
what the first version of this did, and it reported a fully-current Arch box as
unmeasurable.

Only these two, and only with no output: a genuine failure prints to stderr, which
`Output.QUIET` keeps in the same transcript, so a non-zero exit that said something
is still a non-answer. `checkupdates` dies that way for every real fault it has —
no fakeroot, an unwritable database copy, a sync that failed.
"""

NETWORKED: frozenset[str] = frozenset({'flatpak', 'mas', 'aur', 'pacman', 'apt'})
"""Which currency reads reach the network, and so are the ones `--cached` declines.

None of them has a local answer worth giving. Flathub's available versions live on
Flathub, the App Store has no offline catalogue, and `yay -Qu` asks the AUR's RPC
about every AUR package — measured at 41% CPU against `yay -Qu --repo`'s 103%,
which is the tell that a process is waiting rather than working.

`pacman` and `apt` are the two that look wrong and are not. Each names a read that
refreshes a private copy of an index before consulting it, and the local answer
each replaced was worse than no answer: `pacman -Qu` and `apt list --upgradable`
against stale indexes report a machine current, which reads as measured. `OUTDATED`
and `_apt_outdated` carry what each was measured at.

brew and its casks are the ones genuinely left out. `brew outdated` reads a local
tap clone that goes stale the same way, and this has not been measured on a Mac —
so their absence here records what was checked rather than a claim they are exempt.

**This names round trips; it does not ration them.** Every read verb measures, so
all five are asked on a plain `plan` or `check`, and the set is what a run declining
the network consults to know which reads it must skip. Together they are a couple of
seconds, worth not spending when somebody has said they do not want the network —
and worth spending every other time, because what a machine is behind on is exactly
what they asked about.
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


APT_LISTS = Path('/var/lib/apt/lists')
"""The index `apt list --upgradable` compares against, and cannot refresh unprivileged.

Read to seed the private copy below. Never written: refreshing it is `apt-get
update` as root, which a read verb does not get to be.
"""


def _apt_redirect(scratch: Path) -> tuple[str, ...]:
    """Where an unprivileged apt keeps the state it would otherwise need root for.

    Both options are needed. `Dir::State::lists` is the index itself, and
    `Dir::Cache` moves the partial downloads that land beside it — without the
    second, apt writes into `/var/cache/apt/archives/partial` and complains it
    cannot.
    """
    return ('-o', f'Dir::State::lists={scratch / "lists"}', '-o', f'Dir::Cache={scratch / "cache"}')


def _apt_outdated() -> frozenset[str] | None:
    """apt's currency, measured against an index this run refreshed itself.

    The same defect `checkupdates` exists to cure on Arch, and apt ships nothing
    equivalent. `apt list --upgradable` reads `/var/lib/apt/lists`, so it answers
    from whenever that was last `apt-get update`d. Measured 2026-08-22 in the
    Ubuntu test image: the machine's own lists reported nothing upgradable while a
    refreshed copy reported eighteen packages.

    apt takes its whole state layout from options, so a redirected `update` needs no
    root and touches nothing the machine reads. The copy is seeded from
    `APT_LISTS` for the reason checkupdates copies the pacman database: a cold fetch
    is 25.6 MB and a delta from what the machine already has is 2.8 MB. Thrown away
    afterwards, so nothing accumulates and there is no second index on disk.

    A refresh that fails is not fatal. The listing still runs, against the seeded
    copy, which is the machine's own answer — worse than a current one and better
    than none, and the row says a number either way.

    An `apply` therefore runs `apt-get update` twice: this one to decide what is
    behind, and `REFRESH`'s privileged one before installing. That is the order
    doing its job rather than a duplicate — measuring must not escalate, and
    installing must resolve against the machine's real index.
    """
    with tempfile.TemporaryDirectory(prefix='dotfiles-apt-') as directory:
        scratch = Path(directory)
        for leaf in ('lists/partial', 'cache/archives/partial'):
            (scratch / leaf).mkdir(parents=True)
        # Whatever it managed to copy is the seed. `copytree` collects per-file
        # failures and raises at the end, so a `lists/partial` this account cannot
        # read costs the files under it and not the other forty megabytes.
        with contextlib.suppress(OSError, shutil.Error):
            shutil.copytree(APT_LISTS, scratch / 'lists', dirs_exist_ok=True)
        redirect = _apt_redirect(scratch)
        effects.run(['apt-get', 'update', '-qq', *redirect], output=Output.QUIET)
        listed = effects.run([*OUTDATED['apt'], *redirect], output=Output.QUIET)
    return _names(listed.stdout) if listed.ok else None


def outdated(manager: str) -> frozenset[str] | None:
    """What this manager has installed and behind, or None where it cannot say.

    None rather than an empty set, because "nothing is behind" and "nobody
    asked" are the difference between MATCHED and UNKNOWN — and reporting a
    machine current because its package manager is absent is the failure this
    whole resource exists to avoid.

    An empty result is also returned for a manager with nothing to upgrade, and
    that is the answer, not a non-answer: the command exited 0 having listed
    nothing.

    apt is the one manager whose read is two commands and a scratch directory
    rather than a row of argv, which is why it branches here instead of being
    expressed in `OUTDATED`. The probe still guards it: `apt-get` ships in the same
    package as `apt`, so one answering `--version` vouches for both.
    """
    command = OUTDATED.get(manager)
    if command is None or not effects.run([command[0], '--version'], output=Output.QUIET, timeout=PROBE_SECONDS).ok:
        return None
    if manager == 'apt':
        return _apt_outdated()
    listed = effects.run(list(command), output=Output.QUIET)
    if listed.ok:
        return _names(listed.stdout)
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
        return Result(False, refusal(privilege.state), kind=Kind.PRIVILEGE_UNAVAILABLE)
    if completed.ok:
        return Result(True, f'{" ".join(command)}', kind=Kind.APPLIED)
    return Result(False, f'{" ".join(command[:2])} exited {completed.returncode}', kind=Kind.COMMAND_FAILED)


PROBE_SECONDS = 10.0
"""Long enough for a cold binary, short enough that a manager which is not going
to answer does not hold the run. Same bound and same reason as
`evidence.PROBE_SECONDS`."""
