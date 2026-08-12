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

from dotfiles import catalog
from dotfiles import effects
from dotfiles import github_release
from dotfiles.effects import Output
from dotfiles.output import warn
from dotfiles.providers import Result

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
    return _uv_tool_install(entry.name, requirement(entry), offline=offline, again=again)


def requirement(entry: catalog.GitUvTool) -> str:
    """What to hand uv: a release-pinned requirement, or the bare repo.

    The tool's name is repeated ahead of the URL because that is what makes uv
    record the requirement under the tool's own name, which is what makes the
    receipt readable afterwards.

    A repo that should pin and cannot is warned about rather than failed. The
    install still works; it is the tool's own updater that will not, and saying
    so at install time is the only moment anyone would notice.
    """
    if entry.tracks_branch:
        return entry.repo

    tag = latest_release(entry.repo)
    if tag is None:
        warn(f'{entry.name}: no release found, installing from the default branch (its own update will refuse to run)')
        return entry.repo
    return f'{entry.name} @ git+{entry.repo}@{tag}'


def latest_release(repo: str) -> str | None:
    """The newest release tag of a git tool's repo, or None.

    None for a host that is not GitHub as well as for a repo publishing no
    release: both mean "nothing to pin to", and the caller does the same thing
    with either.
    """
    found = SLUG.match(repo)
    return github_release.latest_version(found.group(1)) if found else None


def _uv_tool_install(name: str, target: str, *, offline: bool, again: bool) -> Result:
    """`again` is what makes a repair of an already-present tool do anything.

    uv compares the requirement against its receipt and exits 0 printing
    "already installed" when the two match, and this reads that exit code as
    success — so without the flag a PyPI tool and an already-pinned git tool both
    record DONE having installed nothing.
    """
    command = ['uv', 'tool', 'install', '--reinstall', target] if again else ['uv', 'tool', 'install', target]
    completed = effects.run(command, output=Output.QUIET)
    if completed.ok:
        return Result(True, f'{name} installed from {target}')

    unreachable = ', and the offline bundle stages no Python tools to fall back on' if offline else ''
    return Result(False, f'uv tool install {target} exited {completed.returncode}{unreachable}: {completed.transcript.strip()}')
