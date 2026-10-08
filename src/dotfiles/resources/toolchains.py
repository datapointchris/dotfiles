"""The language runtimes: whether each one this machine needs is there and current.

*Which* of them it needs belongs to the registry, not here: a toolchain is a
provider like every other mechanism, planned by `registry.ToolchainProvider` from
what the tool providers resolved.

What is left is the resource — ask the provider whether each one is there, compare
the versions against the floors the plan carries, and say what differs. Presence
is the provider's answer and never a second `which` here: two independent probes
let a packaged `go` satisfy a toolchain unpacked to a path nothing checked.

uv is ungated and always planned, because everything installed later resolves
through it — the symlink phase included, which shells out to `uv run`. It is also
the one runtime held to a single release rather than a floor: the uv-pre-commit
hook's rev in the repo's own `.pre-commit-config.yaml`.
"""

from __future__ import annotations

import dataclasses as dc

from dotfiles import catalog
from dotfiles import evidence as ev
from dotfiles import paths
from dotfiles import registry
from dotfiles import versions
from dotfiles.plan import DesiredItem
from dotfiles.plan import Plan
from dotfiles.plan import Stage
from dotfiles.privilege import Escalates
from dotfiles.providers import toolchain
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Outcome
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'toolchains'

GO_RUNTIME = 'go'

UV_RUNTIME = 'uv'

GONOSUMDB_VAR = 'GONOSUMDB'

GO_ENV_ITEM = 'go-toolchain/module-env'
"""Addressed apart from `go-toolchain/go` so `perform` can tell the two apart.

One item carrying two changes is the pattern `packages` already uses for a tool
that is both unmeasurable and shadowed. What is different here is that only one
of the two is repaired by installing something, so they cannot share an address.
"""


@dc.dataclass(frozen=True, slots=True)
class Observed:
    reported: dict[str, str]
    """Runtime name → the version string it printed, for those that answered."""

    absent: dict[str, str]
    """Runtime name → why it did not answer.

    The reason rather than a bare set, because "no `go` on PATH" and "a `go` that
    exits non-zero" are different findings and only the first is what a fresh
    machine looks like. A half-extracted tarball leaves the binary in place and
    `which` satisfied by it.
    """

    uv_pin: str = ''
    """The uv release the repo's uv-pre-commit hook pins, or '' with `uv_unpinned` saying why."""

    uv_unpinned: str = ''

    module_env: str | None = None
    """What `go env GONOSUMDB` answers, or None where there is no Go to ask.

    A runtime's *settings* are machine state exactly like its version is, and this
    is the first of them measured rather than assumed. It has to be measured
    because the only writer was a private step inside `install_go`, which runs
    when Go is absent or below its floor and at no other time — so on every
    machine that already had Go, the setting was never written and nothing looked.
    """

    examined: tuple[Examined, ...] = ()
    """Every runtime that answered, keyed by the plan address `diff` uses.

    Built in `observe` rather than derived from `reported`, which is keyed by bare
    name so the summary can read as prose. A row has to carry the same key a
    change does or one runtime appears twice under two spellings, and rebuilding
    the address here would mean a second mapping kept in step with the first.
    """

    @property
    def summary(self) -> str:
        """Names the runtimes rather than counting them: which ones a machine
        needs is derived from its tool lists, so the list itself is the finding."""
        return ', '.join(sorted(self.reported)) or 'none needed'

    @property
    def inventory(self) -> tuple[Examined, ...]:
        """The runtimes that answered, each with the version it printed.

        The version is the part the summary cannot carry. Four runtimes named in
        one sentence is a list crammed into prose, and it drops the one fact
        anybody reads this row for — which Go this machine is actually on.
        """
        return self.examined


class ToolchainsResource:
    name = NAME
    help = 'language runtimes and their version managers'

    def observe(self, session: Session, plan: Plan) -> Observed:
        reported: dict[str, str] = {}
        absent: dict[str, str] = {}
        examined: list[Examined] = []
        go_probe = ''

        for item in plan.for_resource(NAME):
            # Asked of the provider rather than of PATH. A runtime with a fixed
            # home is answered by that path, and `which` is a different question:
            # Arch's `go` package arrived transitively in a container, `which go`
            # found /usr/sbin/go, and this reported the toolchain present while
            # /usr/local/go did not exist — so every Go tool built against a
            # runtime this repo had not installed. The provider already knew; only
            # this second measurement did not ask it.
            found = registry.toolchain_evidence(item, session)
            probe = str(found.binary) if found.binary else item.evidence_path or item.executable
            if found.verdict is not Verdict.MATCHED:
                absent[item.name] = found.detail
            elif (version := ev.reported_version(probe)) is None:
                # Probed where it was found, not by name. For a runtime with a
                # fixed home those are different binaries the moment a package
                # manager put one on PATH, and asking the wrong one is how this
                # came to report a version the machine does not run.
                absent[item.name] = f'{probe} would not report a version'
            else:
                reported[item.name] = version
                examined.append(Examined(item.address, version))
                if item.name == GO_RUNTIME:
                    go_probe = probe

        # The same binary the version came from, so the settings measured belong
        # to the toolchain measured. Resolving a second one here is how the two
        # answers come from two different Go installs on a box carrying both.
        module_env = toolchain.go_env_setting(go_probe, GONOSUMDB_VAR) if go_probe else None

        # The session's checkout, which outside a test is `paths.REPO_ROOT`, so
        # this reads the same file `install_uv` converges to.
        try:
            uv_pin, uv_unpinned = toolchain.pinned_uv(session.repo / paths.PRE_COMMIT_CONFIG.name), ''
        except toolchain.UnpinnedUv as error:
            uv_pin, uv_unpinned = '', str(error)
        return Observed(
            reported=reported,
            absent=absent,
            uv_pin=uv_pin,
            uv_unpinned=uv_unpinned,
            module_env=module_env,
            examined=tuple(examined),
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        changes = []
        for item in plan.for_resource(NAME):
            if item.name in observed.absent:
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        Verdict.MISSING,
                        repair=Repair.AUTOMATIC,
                        detail=observed.absent[item.name],
                        desired=item,
                        privileged=registry.needs_root(item),
                    )
                )
                continue

            reported = observed.reported[item.name]
            if item.name == UV_RUNTIME:
                changes.extend(_against_pin(item, reported, observed))
                continue

            floor = _floor(item)
            if not floor:
                continue

            meets = versions.at_least(reported, floor)
            if meets is None:
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        Verdict.UNKNOWN,
                        repair=Repair.NONE,
                        detail=f'declares a floor of {floor} and reported {reported!r}, which has no version in it',
                        desired=item,
                        observed=reported,
                    )
                )
            elif not meets:
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        Verdict.STALE,
                        repair=Repair.AUTOMATIC,
                        detail=f'below the declared floor of {floor}',
                        desired=item,
                        observed=reported,
                        privileged=registry.needs_root(item),
                    )
                )

        if observed.module_env is not None and observed.module_env != toolchain.GONOSUMDB:
            changes.append(
                Change(
                    NAME,
                    Stage.TOOLCHAIN,
                    GO_ENV_ITEM,
                    Verdict.STALE,
                    repair=Repair.AUTOMATIC,
                    detail=f'{GONOSUMDB_VAR} is {observed.module_env or "unset"}, so a private module in the namespace will not verify',
                    advice=f'`go env -w {GONOSUMDB_VAR}={toolchain.GONOSUMDB}`, which an apply does for you',
                    observed=observed.module_env,
                )
            )
        return tuple(changes)

    def perform(self, session: Session, change: Change, privilege: Escalates) -> Outcome:
        """Whichever version manager planned it installs it, or says why it cannot.

        The module env is the one change here that installs nothing, so it is the
        one `registry.install` cannot answer for.
        """
        if change.item == GO_ENV_ITEM:
            return Outcome.from_result(change, toolchain.set_go_env())
        return registry.install(session, change, privilege)


def _against_pin(item: DesiredItem, reported: str, observed: Observed) -> tuple[Change, ...]:
    """uv against the one release the repo pins, where every other runtime meets a floor.

    A uv above the pin is as wrong as one below, because either writes `uv.lock`
    in its own format revision. uv itself runs at any release, so this STALE row
    is the only report a machine has drifted.
    """
    if observed.uv_unpinned:
        return (Change(NAME, item.stage, item.address, Verdict.UNKNOWN, repair=Repair.NONE, detail=observed.uv_unpinned, desired=item),)

    matches = versions.exactly(reported, observed.uv_pin)
    if matches is None:
        detail = f'pinned to {observed.uv_pin} and reported {reported!r}, which has no version in it'
        return (
            Change(NAME, item.stage, item.address, Verdict.UNKNOWN, repair=Repair.NONE, detail=detail, desired=item, observed=reported),
        )
    if matches:
        return ()
    return (
        Change(
            NAME,
            item.stage,
            item.address,
            Verdict.STALE,
            repair=Repair.AUTOMATIC,
            detail=f'pinned to {observed.uv_pin} by the uv-pre-commit hook, and any other release writes uv.lock in its own format',
            desired=item,
            observed=reported,
        ),
    )


def _floor(item: DesiredItem) -> str:
    """The declared minimum for a runtime, or '' where none is declared.

    Read off the entry the plan carries rather than looked up, because
    `min_version` is a fact about what the tools need and belongs beside them —
    and resolution finishing in the plan is what stops this reaching back into the
    catalog for it.
    """
    entry = item.entry
    if not isinstance(entry, catalog.Runtime):
        return ''
    return entry.min_version or entry.version


RESOURCE = ToolchainsResource()
