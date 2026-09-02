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
from dotfiles.privilege import Escalates
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
*named* and then *authorized* — a release's `supersedes` row, reviewed in a commit,
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
authorization to remove one name cannot take a set. apt resolves reverse dependencies
instead, and `-y` answers the confirmation that would have shown the list — so the same
`--force` authorizing one removal on Arch authorizes an unbounded one on Debian. `dpkg
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

REQUESTED: dict[str, tuple[str, ...]] = {
    'brew': ('brew', 'leaves', '--installed-on-request'),
}
"""How to ask which packages somebody chose, for the managers whose answer is
comparable to a declaration.

**brew alone, and the other two are not an oversight.** `pacman -Qqe` and
`apt-mark showmanual` are the same query, and their answer is a different kind of
thing: pacman and apt own the base system, so what they call explicitly installed
includes packages no manifest here would ever name. Measured on the fleet's Arch
workstation — `pacman -Qqe` returns 123 names and 40 of them appear nowhere in
`packages.yml`, `base`, `linux` and `linux-firmware` among them. Those 40 rows
would advise `pacman -R` on the kernel. brew owns nothing it was not asked for, so
every name it returns is one somebody typed. Same reasoning as
`packages._undeclared_own_tools` scoping itself to Go.

**`--installed-on-request` rather than a bare `brew leaves`.** A dependency
outliving whatever wanted it is a leaf nobody chose, and reporting it undeclared
asks someone to tidy up after brew rather than after themselves.

The one-manager membership is pinned by a test rather than left to this sentence,
because a name claiming a category invites an addition that the paragraph above
would have refused.
"""


def _answers(binary: str) -> bool:
    """Whether a package manager is here and will run.

    **The cache is keyed on the resolved path, never on the name.** PATH changes
    within a process — `toolchain.put_on_path` extends it as each runtime lands,
    and a test hands the resource its own — so a bare name lets one test's fake
    `pacman` answer for the next test's.

    A probe rather than `which` alone, because the question is whether the manager
    *runs*: a `dpkg-query` present but broken and one absent are the same answer
    here and different answers to `which`.
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


def requested(manager: str) -> frozenset[str] | None:
    """Which of this manager's packages someone asked for by name, or None.

    **None rather than an empty set where the manager cannot be asked**, for the
    reason `outdated` gives: "nobody chose anything" and "nobody was asked" would
    otherwise both read as a machine whose declaration explains all of it, and the
    second is the state of every machine without brew.

    **That is the one place this and `unchosen` deliberately part**, and they are
    otherwise complements — `pacman -Qqe` is the exact inverse of the `pacman -Qdq`
    in `UNCHOSEN`. `unchosen` unions every manager and skips one that fails, because
    its caller is asking whether *some* manager explains a second copy on PATH and a
    silent manager subtracts nothing from that. This answers per manager and reports
    a failed read as unknown, because its caller subtracts the declaration from this
    set and a silent manager would turn into a clean machine. Whoever adds a manager
    here inherits the second convention, and the choice is what decides whether a
    failed read reads as "nothing" or as "cannot say".

    Tap-qualified names are reduced to the formula, because that is the spelling
    every other reader uses. `brew leaves` prints `felixkratz/formulae/borders`
    while `brew list --formula` prints `borders`, so a declaration naming the
    short form would be reported undeclared against the long one on every run.
    """
    command = REQUESTED.get(manager)
    if command is None or not _answers(command[0]):
        return None
    # `PROBE_SECONDS`, not `CURRENCY_SECONDS`. This reads bookkeeping the manager
    # already holds and touches no network, which is what the currency bound is for
    # — `unchosen` above is the mirror local read and uses the same one. Measured:
    # `brew leaves --installed-on-request` answers 67 names in about 1.4s, against a
    # whole `dotfiles system check` of 4.4s. A wedged brew holds the scheduled timer
    # for 10 seconds rather than 90.
    listed = effects.run(list(command), output=Output.QUIET, timeout=PROBE_SECONDS)
    if not listed.ok:
        return None
    return frozenset(line.strip().rsplit('/', 1)[-1] for line in listed.stdout.splitlines() if line.strip())


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


def install(manager: str, names: Sequence[str], privilege: Escalates) -> Result:
    """One transaction. The caller has already refreshed and grouped.

    Streamed on both branches, and the escalating one has to ask: `Escalates.run`
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

    Neither `pacman -R` nor `brew uninstall` stops a running daemon, so the process
    outlives its package holding the ports and state directory the replacement is
    about to be pointed at.

    **Best effort by design**: a package with no service, one already stopped, and a
    `brew` that never registered one all report failure and are all ordinary.

    `unit` comes from the release's declaration rather than the package, because
    upstream and the distro publish the same unit filename.
    """
    if manager in REMOVES_AS_ROOT and unit and systemd.available():
        systemd.disable(unit)
    elif manager in {'brew', 'cask'} and shutil.which('brew'):
        effects.run(['brew', 'services', 'stop', package], output=Output.QUIET)


def uninstall(manager: str, names: Sequence[str], privilege: Escalates) -> Result:
    """Take named packages off the machine, for a caller that was authorized to.

    Nothing here decides that it should happen. `evidence.superseded` measures the
    package, an entry's `supersedes` names it, and `--force` authorizes it — so this
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


def refresh(manager: str, privilege: Escalates) -> Result:
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
    'cask': ('brew', 'outdated', '--cask', '--quiet'),
    'flatpak': ('flatpak', 'remote-ls', '--updates', '--columns=application'),
    'mas': ('mas', 'outdated'),
}
"""How each manager is asked what it has installed and behind.

**A manager comparing against a local index answers from whenever that index was
last synced.** `pacman -Qu` reports what was behind at the last `-Sy` and nothing
since. `checkupdates` cures it by refreshing a private copy under `fakeroot`;
refreshing the real one is not an option, because `pacman -Sy` without the `-u` is
the partial-upgrade state Arch does not support. apt has the same defect and no
equivalent, which is what `_apt_outdated` does by hand.

`--nocolor` because `Color` in `pacman.conf` puts escape codes in front of the
first field, which `_names` reads.

`yay -Qu --aur` rather than a bare `-Qu`: only yay knows an AUR package's upstream
version, and `--aur` stops the two Arch rows counting the same repo package twice.

**The cask read is deliberately not greedy.** A cask declaring `auto_updates`
carries its own updater, and brew reads the Caskroom metadata rather than the
bundle — so a greedy ask reports an app that already updated itself as behind, and
the row never converges however often `apply` runs.
"""

EMPTY_IS_NONZERO: frozenset[str] = frozenset({'pacman', 'aur'})
"""Which currency queries report "nothing to upgrade" as a failure.

`checkupdates` exits 2 and `yay -Qu` exits 1 having printed nothing when every
package is current — the empty-result convention `grep` uses. Read as "could not
answer", a fully-current Arch box is unmeasurable.

**Only with no output.** A genuine failure prints to stderr, which `Output.QUIET`
keeps in the same transcript, so a non-zero exit that said something is still a
non-answer — which is how `checkupdates` dies for every real fault it has.
"""

NETWORKED: frozenset[str] = frozenset({'flatpak', 'mas', 'aur', 'pacman', 'apt'})
"""Which currency reads reach the network, and so are the ones `--cached` declines.

None has a local answer worth giving: Flathub's versions live on Flathub, the App
Store has no offline catalog, and `yay -Qu --aur` asks the AUR's RPC per package.

**`pacman` and `apt` look wrong here and are not.** Each names a read that
refreshes a private index copy first, replacing a local answer that was worse than
none — a stale index reports a machine current, which reads as measured.

**brew and its casks are left out because nobody has measured them on a Mac**, not
because they are exempt. `brew outdated` reads a tap clone that goes stale the same
way.

This names round trips and does not ration them: all five are asked on a plain
`plan` or `check`, and this is what a run declining the network skips.
"""

UPGRADE: dict[str, tuple[str, ...]] = {
    'pacman': ('pacman', '-Syu', '--noconfirm'),
    'aur': ('yay', '-Syu', '--noconfirm'),
    'apt': ('apt-get', 'upgrade', '-y'),
    'brew': ('brew', 'upgrade'),
    'cask': ('brew', 'upgrade', '--cask'),
    'flatpak': ('flatpak', 'update', '-y'),
    'mas': ('mas', 'upgrade'),
}
"""How each manager upgrades everything it installed.

Whole-machine rather than per package, which is not a shortcut: Arch does not
support partial upgrades at all, and for the rest a declared package's
dependencies are as much this repo's business as the package. `pacman -S <name>`
would upgrade one package and leave the machine in a combination nobody tests.

The pacman and yay rows repeat their `REFRESH` command, because on Arch the sync
*is* the upgrade. Spelled twice deliberately: a later change to one must not
silently move the other.

**Brew is the cask's installer and never its updater**, which is what leaving
`--greedy` off buys. An upgrade unpacks a fresh bundle, macOS can read it as a
different app and drop the TCC grants the old one held — and for an app holding
Accessibility that freezes mouse and keyboard until it is re-granted by hand.
`--adopt` on `INSTALL` is the other half.
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

    `apt list --upgradable` reads `/var/lib/apt/lists`, so it answers from whenever
    that was last updated — the defect `checkupdates` cures on Arch, with no apt
    equivalent. A redirected `update` needs no root and touches nothing the machine
    reads, seeded from `APT_LISTS` because a cold fetch is 25.6 MB against a 2.8 MB
    delta.

    **A refresh that fails is a non-answer, never a smaller one.** An empty seed
    reports *nothing behind*, which declares a machine current on a run that
    reached no archive — and the Debian test image builds exactly that state.
    `by_currency` turns the `None` into UNKNOWN with a cause.

    An `apply` therefore runs `apt-get update` twice, which is the order working:
    measuring must not escalate, and installing must resolve against the machine's
    real index.
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
        refreshed = effects.run(['apt-get', 'update', '-qq', *redirect], output=Output.QUIET, timeout=CURRENCY_SECONDS)
        if not refreshed.ok:
            return None
        listed = effects.run([*OUTDATED['apt'], *redirect], output=Output.QUIET, timeout=CURRENCY_SECONDS)
    return _names(listed.stdout) if listed.ok else None


def outdated(manager: str) -> frozenset[str] | None:
    """What this manager has installed and behind, or None where it cannot say.

    **None rather than an empty set**: "nothing is behind" and "nobody asked" are
    MATCHED against UNKNOWN, and reporting a machine current because its package
    manager is absent is the failure this resource exists to avoid. An empty set is
    the answer for a manager that listed nothing.

    apt branches here rather than in `OUTDATED` because its read is two commands
    and a scratch directory. `apt-get` ships with `apt`, so one `--version` vouches
    for both.
    """
    command = OUTDATED.get(manager)
    if command is None or not effects.run([command[0], '--version'], output=Output.QUIET, timeout=PROBE_SECONDS).ok:
        return None
    if manager == 'apt':
        return _apt_outdated()
    listed = effects.run(list(command), output=Output.QUIET, timeout=CURRENCY_SECONDS)
    if listed.ok:
        return _names(listed.stdout)
    # A timeout is not the "exited non-zero having printed nothing" that
    # `EMPTY_IS_NONZERO` decodes as *nothing behind*. `effects.run` names the
    # expiry in the transcript, so the silence test already separates them — and
    # getting it wrong would report a firewalled Arch box as current.
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


def upgrade(manager: str, privilege: Escalates) -> Result:
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

CURRENCY_SECONDS = 90.0
"""How long a currency read may take before it is a non-answer.

**Bounded here because no layer above does**: `httpx2` carries its own timeout and
`effects.run` defaults to none, so a subprocess reaching the network is unbounded
otherwise. A `checkupdates` hanging behind a firewall hangs `dotfiles plan` with
nothing on screen, and hangs the timer's `Type=oneshot` unit — whose start timeout
systemd disables by default, so an active unit suppresses its own next fire.

Much longer than `PROBE_SECONDS`, which bounds a local binary answering
`--version` rather than a package-index sync.
"""
