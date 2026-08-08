"""Walking the machine's resources and turning what they say into one verdict.

This is `check` for the whole machine, and it is deliberately not in the CLI
layer: the walk, the verdict composition and the exit-code rule are the parts
worth testing directly, and a `CliRunner` around them tests argument parsing at
the same time as logic.

Behind each resource is still bash — see `bridge.py`. What is already final is
the shape: a walk producing one `ResourceResult` per address, and a single rule
turning the set of them into the number a caller branches on.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from dotfiles import bridge
from dotfiles import vocabulary
from dotfiles.effects import Output
from dotfiles.output import render_change
from dotfiles.resources import Change
from dotfiles.resources import Repair
from dotfiles.resources import Verdict as ItemVerdict
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode


class Verdict(StrEnum):
    """What one resource had to say.

    `DRIFT` and `ISSUE` are different kinds, not degrees. Drift is expected and
    benign — the machine differs from its declaration, which is what `apply` is
    for. An Issue is something wrong: a checker crashed, a declaration is
    invalid. Collapsing them is what would make an exit code meaningless and the
    shell nudge not worth having.

    There was a fourth, `PENDING`, for a resource whose checker had not been
    written yet. Every one of the seven answers for itself now, so a verdict
    meaning "no evidence either way" has nothing to report it.
    """

    CONVERGED = 'converged'
    DRIFT = 'drift'
    ISSUE = 'issue'


@dataclass(frozen=True)
class ResourceResult:
    address: str
    verdict: Verdict
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {'address': self.address, 'verdict': str(self.verdict), 'detail': self.detail}


def check_packages(session: Session) -> ResourceResult:
    """Every tool this machine declares, against the evidence for it.

    One inventory query per package manager rather than one probe per package,
    which is what `packages missing` did — and it asked PATH about apt and pacman
    names, so it skipped those sections entirely rather than getting them wrong.
    """
    from dotfiles.resources import packages

    observed = packages.RESOURCE.observe(session, session.plan)
    changes = packages.RESOURCE.diff(session.plan, observed)
    return from_changes('packages', changes, f'all {len(observed.evidence)} declared packages are installed')


def check_symlinks(session: Session) -> ResourceResult:
    """Read-only, and now per link rather than per broken link.

    The previous check answered only "is anything broken", so a file added to
    `configs/` and never deployed read as converged. The resource compares every
    declared link against what is at its target, which is what makes a missing
    one visible without running the write.
    """
    from dotfiles.resources import symlinks

    observed = symlinks.RESOURCE.observe(session, session.plan)
    changes = symlinks.RESOURCE.diff(session.plan, observed)
    return from_changes('symlinks', changes, f'all {len(observed.links)} declared symlinks are deployed')


def check_env(session: Session) -> ResourceResult:
    """The first resource driven by the Resource protocol rather than by bash.

    Its changes are rendered here rather than returned, because the composite
    walk prints one row per resource: the detail line says how many and of what
    kind, and the rows above it say which.
    """
    from dotfiles.resources import env

    changes = env.RESOURCE.diff(session.plan, env.RESOURCE.observe(session, session.plan))
    return from_changes('env', changes, '~/.env matches the manifest and the declared flags')


def check_toolchains(session: Session) -> ResourceResult:
    """The runtimes this machine's tool lists imply, and whether they meet their floors.

    Never what a manifest asked for: a machine gets Go because it declared
    `go_tools`, which is why the booleans that used to gate the toolchains were
    removed.
    """
    from dotfiles.resources import toolchains

    observed = toolchains.RESOURCE.observe(session, session.plan)
    changes = toolchains.RESOURCE.diff(session.plan, observed)
    named = ', '.join(sorted(observed.installed))
    return from_changes('toolchains', changes, f'{named or "none needed"}')


def check_system(session: Session) -> ResourceResult:
    """What the OS package manager installed and how the OS is configured, without escalating.

    Every row is read unprivileged — the package inventories, the group database,
    `systemctl is-enabled`, a 0644 file under `/etc`, field 7 of the passwd entry
    — so this answers at a prompt and in a container. The Xcode licence and the
    macOS defaults are the half still missing, and they arrive with the rest of
    step 6.
    """
    from dotfiles.resources import system

    observed = system.RESOURCE.observe(session, session.plan)
    changes = system.RESOURCE.diff(session.plan, observed)
    asked = ', '.join(sorted(observed.asked)) or 'nothing'
    converged = f'all {len(observed.evidence)} declared system packages installed (asked {asked})'
    if observed.config:
        converged += f', and {len(observed.config)} configuration item(s) match'
    return from_changes('system', changes, converged)


def check_plugins(session: Session) -> ResourceResult:
    """The cloned plugins only, and the detail line says so.

    TPM and lazy.nvim each own a plugin list this repo does not declare — tmux's
    is in `tmux.conf`, Neovim's is in lua — so there is nothing here to compare
    them against. Claiming to have checked them would be worse than not checking.
    """
    from dotfiles.resources import plugins

    observed = plugins.RESOURCE.observe(session, session.plan)
    changes = plugins.RESOURCE.diff(session.plan, observed)
    return from_changes('plugins', changes, f'all {len(observed.present)} cloned plugins are present (tmux and nvim sync on apply)')


def check_identity(session: Session) -> ResourceResult:
    """Ask now rather than at the first commit, mid-work."""
    from dotfiles.resources import identity

    observed = identity.RESOURCE.observe(session, session.plan)
    changes = identity.RESOURCE.diff(session.plan, observed)
    return from_changes('identity', changes, observed.who)


def check_declaration() -> ResourceResult:
    """Validate `packages.yml` against the manifests and the installer scripts.

    An Issue rather than drift whatever it finds, and first in the walk: a
    machine checked against an invalid declaration produces a verdict that means
    nothing. This is what `packages verify` does today, reached through
    `machines check` in the new grammar.
    """
    status = bridge.declaration('verify', output=Output.STREAM)
    if status == 0:
        return ResourceResult('machines', Verdict.CONVERGED, 'packages.yml matches the manifests and installer scripts')
    return ResourceResult('machines', Verdict.ISSUE, "the declaration is invalid — 'dotfiles machines check' lists why")


def from_changes(address: str, changes: Sequence[Change], converged: str) -> ResourceResult:
    """Fold one resource's per-item changes into the row the composite prints.

    Each change is rendered as it is folded, so the reader sees what drifted and
    then the summary of it. Drift rather than Issue whatever the mix: a machine
    differing from its declaration is what `apply` is for, and only a checker that
    could not answer is an Issue.

    An item nobody could measure is neither. Nothing about it differs — that is
    the claim there is no evidence for — and no checker crashed, so it is counted
    and named rather than rendered as a row and rather than moving the exit code.
    The alternative was measured on a cold release cache: every declared release
    is unmeasurable until something refreshes it, which would print a screen of
    rows and exit non-zero on a machine with nothing wrong with it.
    """
    unmeasured = [change for change in changes if change.verdict is ItemVerdict.UNKNOWN and change.repair is Repair.NONE]
    drifted = [change for change in changes if change.drifted and change not in unmeasured]
    for change in drifted:
        render_change(change)

    gap = f', {len(unmeasured)} unmeasurable' if unmeasured else ''
    if not drifted:
        return ResourceResult(address, Verdict.CONVERGED, converged + gap)

    by_hand = sum(1 for change in drifted if change.repair is Repair.BY_HAND)
    detail = f'{len(drifted)} item(s) differ from the declaration'
    if by_hand:
        detail += f', {by_hand} of them repairable only by hand'
    return ResourceResult(address, Verdict.DRIFT, detail + gap)


Checker = Callable[[Session], ResourceResult]
"""Every checker takes the session, so the walk needs no special case for the ones
that read the declaration."""


CHECKERS: dict[str, Checker] = {
    'packages': check_packages,
    'toolchains': check_toolchains,
    'plugins': check_plugins,
    'symlinks': check_symlinks,
    'env': check_env,
    'system': check_system,
    'identity': check_identity,
}
"""Keyed by address and ordered as the machine converges — see `vocabulary.RESOURCES`."""


def check_machine(skip: frozenset[str] = frozenset(), machine: str | None = None, *, refresh: bool = False) -> list[ResourceResult]:
    """Validate the declaration, then walk every resource that was not skipped.

    A skipped address is absent from the results rather than present as a fourth
    verdict: it was not examined, so it has nothing to report, and inventing a
    row for it would put something in `--json` that no checker produced.
    """
    session = Session.resolve(machine, refresh=refresh)
    results = [] if 'machines' in skip else [check_declaration()]
    results.extend(CHECKERS[address](session) for address in vocabulary.RESOURCES if address not in skip)
    return results


def exit_code(results: list[ResourceResult]) -> ExitCode:
    """One number from many verdicts. An Issue outranks drift."""
    verdicts = {result.verdict for result in results}
    if Verdict.ISSUE in verdicts:
        return ExitCode.ISSUE
    if Verdict.DRIFT in verdicts:
        return ExitCode.DRIFT
    return ExitCode.CONVERGED
