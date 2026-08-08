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
from dataclasses import dataclass
from enum import StrEnum

from dotfiles import bridge
from dotfiles import vocabulary
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.vocabulary import ExitCode


class Verdict(StrEnum):
    """What one resource had to say.

    `DRIFT` and `ISSUE` are different kinds, not degrees. Drift is expected and
    benign — the machine differs from its declaration, which is what `apply` is
    for. An Issue is something wrong: a checker crashed, a declaration is
    invalid, a required file is absent. Collapsing them is what would make an
    exit code meaningless and the shell nudge not worth having.
    """

    CONVERGED = 'converged'
    DRIFT = 'drift'
    ISSUE = 'issue'
    PENDING = 'pending'


@dataclass(frozen=True)
class ResourceResult:
    address: str
    verdict: Verdict
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {'address': self.address, 'verdict': str(self.verdict), 'detail': self.detail}


PENDING_DETAIL = 'no checker yet; apply still installs it'


def _from_status(address: str, status: int, converged: str, drifted: str) -> ResourceResult:
    """Read a shelled-out checker's exit status as a verdict.

    Anything above 1 is an Issue rather than worse drift: the scripts behind this
    use 1 for "found something" and reserve the rest for their own failures, so a
    2 means the checker itself could not answer.
    """
    if status == 0:
        return ResourceResult(address, Verdict.CONVERGED, converged)
    if status == 1:
        return ResourceResult(address, Verdict.DRIFT, drifted)
    return ResourceResult(address, Verdict.ISSUE, f'the checker exited {status} and could not answer')


def check_packages(machine: str | None = None) -> ResourceResult:
    arguments = ['missing', *(('--machine', machine) if machine else ())]
    status = bridge.catalog(*arguments, output=Output.STREAM)
    return _from_status(
        'packages',
        status,
        'every declared package is installed',
        "declared packages are missing — 'dotfiles packages apply' installs them",
    )


def check_symlinks() -> ResourceResult:
    """In-process, and read-only.

    The script this replaced ran `symlinks check`, whose `--auto-fix` defaults to
    true — a read verb whose default was to delete files. Reading is what `check`
    does; removing the broken ones is what `symlinks apply` does.
    """
    from dotfiles import deploy

    healthy = deploy.check()
    return _from_status('symlinks', 0 if healthy else 1, 'symlinks are healthy', 'symlinks are broken or missing')


def check_env(machine: str | None = None) -> ResourceResult:
    arguments = ['check', *(('--machine', machine) if machine else ())]
    status = bridge.ops('env', *arguments).returncode
    return _from_status(
        'env',
        status,
        '~/.env matches the manifest and the declared flags',
        "~/.env has drifted — 'dotfiles env apply' rewrites it",
    )


def check_identity() -> ResourceResult:
    """Ask now rather than at the first commit, mid-work.

    The repo ships no identity and sets `user.useConfigOnly`, so a machine
    without one discovers it when git refuses a commit. `--global` rather than a
    plain `--get`, so a repo-local override cannot mask an unset machine.
    """
    name = run(['git', 'config', '--global', '--get', 'user.name'], output=Output.QUIET)
    email = run(['git', 'config', '--global', '--get', 'user.email'], output=Output.QUIET)

    if name.ok and email.ok:
        who = f'{name.transcript.strip()} <{email.transcript.strip()}>'
        return ResourceResult('identity', Verdict.CONVERGED, who)

    return ResourceResult(
        'identity',
        Verdict.DRIFT,
        "no git identity — commits will be refused; set one with 'git config --global user.email <address>'",
    )


def check_declaration() -> ResourceResult:
    """Validate `packages.yml` against the manifests and the installer scripts.

    An Issue rather than drift whatever it finds, and first in the walk: a
    machine checked against an invalid declaration produces a verdict that means
    nothing. This is what `packages verify` does today, reached through
    `machines check` in the new grammar.
    """
    status = bridge.catalog('verify', output=Output.STREAM)
    if status == 0:
        return ResourceResult('machines', Verdict.CONVERGED, 'packages.yml matches the manifests and installer scripts')
    return ResourceResult('machines', Verdict.ISSUE, "the declaration is invalid — 'dotfiles machines check' lists why")


Checker = Callable[[str | None], ResourceResult]
"""Every checker takes the machine, so the walk needs no special case for the one
that uses it. The discarding lambdas below are the honest way to say "not this one"
— the alternative was an `if address == 'env'` branch in the walk, which is where a
second machine-aware resource would have had to be remembered and would not be.
"""


def _pending(address: str) -> Checker:
    return lambda _machine: ResourceResult(address, Verdict.PENDING, PENDING_DETAIL)


CHECKERS: dict[str, Checker] = {
    'packages': check_packages,
    'toolchains': _pending('toolchains'),
    'plugins': _pending('plugins'),
    'symlinks': lambda _machine: check_symlinks(),
    'env': check_env,
    'system': _pending('system'),
    'identity': lambda _machine: check_identity(),
}
"""Keyed by address and ordered as the machine converges — see `vocabulary.RESOURCES`."""


def check_machine(skip: frozenset[str] = frozenset(), machine: str | None = None) -> list[ResourceResult]:
    """Validate the declaration, then walk every resource that was not skipped.

    A skipped address is absent from the results rather than present as a fourth
    verdict: it was not examined, so it has nothing to report, and inventing a
    row for it would put something in `--json` that no checker produced.
    """
    results = [] if 'machines' in skip else [check_declaration()]
    results.extend(CHECKERS[address](machine) for address in vocabulary.RESOURCES if address not in skip)
    return results


def exit_code(results: list[ResourceResult]) -> ExitCode:
    """One number from many verdicts. Issue outranks drift; pending counts for nothing."""
    verdicts = {result.verdict for result in results}
    if Verdict.ISSUE in verdicts:
        return ExitCode.ISSUE
    if Verdict.DRIFT in verdicts:
        return ExitCode.DRIFT
    return ExitCode.CONVERGED
