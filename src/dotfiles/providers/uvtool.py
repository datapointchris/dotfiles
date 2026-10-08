"""Installing a Python tool with uv: from PyPI, or pinned to a git repo's release.

Two providers, one mechanism. What separates them is where the requirement comes
from, and only the git one has anything to decide.

**A git install is pinned to a release tag, never left tracking the branch.** Each
of these tools updates itself, and `pyselfupdate` reads uv's receipt to decide
what it may do: a git requirement with no `rev=` is a dev checkout to it, so it
prints no update notice and refuses to reinstall over one. A bare
`uv tool install <url>` therefore produces a tool whose own `update` is dead —
and once anything pins it afterwards, `uv tool upgrade` re-resolves that pin to
the same commit forever while reporting "already at latest". syncer sat eight
releases back that way. Pinning here writes the same receipt shape `<tool>
update` writes, and both read the newest release from the same API, so the two
cannot disagree about which release that is.

`tracks_branch` is the declared exception: a repo publishing no releases has no
tag to pin to.

**A git install is held to the lock at that revision.** CI tests the lock, and
`uv tool install` ignores it, so the revision is cloned first and its lock
handed over as `uv_lock` describes. A revision with no `uv.lock` installs
unconstrained, with a warning naming it, because there is nothing to hold it to. A lock
that will not clone or export refuses the install instead: installing past it
is the untested environment this exists to prevent. A `tracks_branch` install
reads the branch head a moment before uv clones it again, so a commit landing
in between installs against the previous lock.

**A repair that does not move the requirement needs `--reinstall`.** `uv tool
install` is a no-op against an unchanged requirement, which is every PyPI entry
and every git entry whose pin has not moved. A currency-driven repair does move
it — a new release changes the tag in the requirement — so the flag matters
exactly where no comparison could have seen the fault: corrupt bytes, a
half-written venv, a version string nobody can parse.

What is *not* here is the credentials check the bash carried. A private repo with
no `gh` login resolves to `Repair.BY_HAND` in `resources/packages.repair_for`, so
the engine never offers the change to a provider at all — one rule for every
provider, rather than one loop remembering to ask.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Sequence
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles import github_release
from dotfiles import uv_lock
from dotfiles.effects import Output
from dotfiles.output import warn
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import unreadable_kind

SLUG = re.compile(r'^(?:https://github\.com/|git@github\.com:)([^/:]+/[^/:]+?)(?:\.git)?/?$')
"""`owner/name` out of a clone URL, in either the https or the ssh form.

Asserted as a shape rather than tested for "has a slash, has no colon". The
weaker test in the bash passed a trailing slash through as part of the slug,
building `/repos/owner/name//releases/latest`, and accepted a three-segment path
as though it were a repo.
"""


def install(entry: catalog.UvTool, *, offline: bool, again: bool = False) -> Result:
    """One PyPI tool.

    Offline is not refused: the bundle stages wheels for this CLI's own closure
    and nothing else, while the machine that installs offline declares six uv
    tools — so refusing would install none of them on the box the offline path
    exists for.
    """
    return _uv_tool_install(entry.name, entry.name, offline=offline, again=again)


def install_git(entry: catalog.GitUvTool, *, offline: bool, again: bool = False) -> Result:
    """Refuses where the release API could not be read, rather than installing.

    The fallback below it is the bare repo, and a tool installed that way has a
    dead `update` for the reason the module docstring records. Reaching that
    fallback on an unreadable API would spend a rate-limited minute on the one
    outcome nothing afterwards can tell from a declared `tracks_branch`.

    **Offline reaches this on every entry that pins**, because resolving a tag is
    the one thing here that leaves the machine. So the sentence carries the
    clause `_uv_tool_install` would have carried: the refusal was going to happen
    either way, and a reader told only that an API could not be read would go
    looking for a network they already know is absent.
    """
    stranded = ', and the offline bundle stages no Python tools to fall back on' if offline else ''
    try:
        tag = release_tag(entry)
    except github_release.Unreadable as unreachable:
        return Result(False, f'{entry.name}: {unreachable}{stranded}', kind=unreadable_kind(unreachable.reached))

    with tempfile.TemporaryDirectory(prefix=f'dotfiles-{entry.name}-') as scratch:
        try:
            pins = locked_at(entry, tag, Path(scratch))
        except LockUnreadable as unreadable:
            return Result(False, f'{entry.name}: {unreadable}{stranded}', kind=unreadable.kind)
        held = pins.arguments(Path(scratch)) if pins is not None else []
        return _uv_tool_install(entry.name, requirement(entry, tag), offline=offline, again=again, held=held)


def release_tag(entry: catalog.GitUvTool) -> str | None:
    """The tag to pin to, or None to install from the default branch.

    A repo that should pin and cannot is warned about rather than failed. The
    install still works; it is the tool's own updater that will not, and saying
    so at install time is the only moment anyone would notice.
    """
    if entry.tracks_branch:
        return None
    tag = latest_release(entry.repo)
    if tag is None:
        warn(f'{entry.name}: no release found, installing from the default branch (its own update will refuse to run)')
    return tag


def requirement(entry: catalog.GitUvTool, tag: str | None) -> str:
    """What to hand uv: a release-pinned requirement, or the bare repo.

    The tool's name is repeated ahead of the URL because that is what makes uv
    record the requirement under the tool's own name, which is what makes the
    receipt readable afterwards.
    """
    return f'{entry.name} @ git+{entry.repo}@{tag}' if tag else entry.repo


class LockUnreadable(Exception):
    """The revision's lock could not be read, as the `Kind` that says which step failed."""

    def __init__(self, detail: str, kind: Kind) -> None:
        super().__init__(detail)
        self.kind = kind


def locked_at(entry: catalog.GitUvTool, tag: str | None, scratch: Path) -> uv_lock.Pins | None:
    """What the lock at `tag`, or at the branch head, pins. None where that revision has no lock."""
    revision = tag or 'the default branch'
    checkout = scratch / 'checkout'
    branch = ('--branch', tag) if tag else ()
    cloned = effects.run(('git', 'clone', '--quiet', '--depth', '1', *branch, entry.repo, str(checkout)), output=Output.QUIET)
    if not cloned.ok:
        raise LockUnreadable(
            f'could not clone {entry.repo} at {revision} to read its uv.lock: {cloned.transcript.strip()}', Kind.DOWNLOAD_FAILED
        )

    try:
        pins = uv_lock.read(checkout)
    except uv_lock.Unexportable as unexportable:
        raise LockUnreadable(f'uv export would not read the uv.lock at {revision}: {unexportable}', Kind.COMMAND_FAILED) from unexportable
    if pins is None:
        warn(f'{entry.name}: {revision} has no uv.lock, so its dependencies resolve to the newest rather than what its CI tested')
    return pins


def latest_release(repo: str) -> str | None:
    """The newest release tag of a git tool's repo, or None.

    None for a host that is not GitHub as well as for a repo publishing no
    release: both mean "nothing to pin to", and the caller does the same thing
    with either.

    **Raises `github_release.Unreadable`, which the annotation cannot say.** An
    API that could not be read is neither of the two above, and the exception
    travels through `release_tag` to `install_git`, which is the only caller and
    refuses on it.
    """
    found = SLUG.match(repo)
    return github_release.latest_version(found.group(1)) if found else None


def _uv_tool_install(name: str, target: str, *, offline: bool, again: bool, held: Sequence[str] = ()) -> Result:
    """`again` is what makes a repair of an already-present tool do anything.

    uv compares the requirement against its receipt and exits 0 printing
    "already installed" when the two match, and this reads that exit code as
    success — so without the flag a PyPI tool and an already-pinned git tool both
    record DONE having installed nothing.

    `held` is the flags `uv_lock.Pins.arguments` returns, empty where nothing is locked.
    """
    command = ['uv', 'tool', 'install', *(['--reinstall'] if again else []), *held, target]
    completed = effects.run(command, output=Output.QUIET)
    if completed.ok:
        return Result(True, f'{name} installed from {target}{", held to its uv.lock" if held else ""}', kind=Kind.APPLIED)

    unreachable = ', and the offline bundle stages no Python tools to fall back on' if offline else ''
    return Result(
        False,
        f'uv tool install {target} exited {completed.returncode}{unreachable}: {completed.transcript.strip()}',
        kind=Kind.COMMAND_FAILED,
    )
