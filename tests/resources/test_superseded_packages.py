"""A declared package the machine cannot install, because an older name is still there.

The case it pins down: `packages.yml` moves an entry from `aur: sioyek` to
`aur: sioyek-git` because upstream deleted the first, and the machine still
carries the package the superseded name built. `sioyek-git` declares
`Conflicts With: sioyek`, so pacman has to remove one to install the other, and
the installers run `--noconfirm` — which takes the default answer to the removal
prompt, and that default is no.

The install can therefore never succeed, while the three verbs each say something
different about it:

    check   converged, because a missing package is drift rather than a fault
    plan    `missing`, which promises an apply will install it
    apply   a long rebuild, then `yay -S exited 1`

Each is right about what it measured, and all three are wrong together, because
nothing measures the thing that decides the outcome — that a package standing in
the way is installed. These tests measure it.
"""

from __future__ import annotations

from dotfiles import catalog
from dotfiles import evidence as ev
from dotfiles.reconcile import sift
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Precondition
from dotfiles.resolve import Preconditions
from dotfiles.resolve import Reason
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import advice_for
from dotfiles.resources import repair_for

MET = Preconditions(github_auth=True, amd_gpu=True)


def item(*, supersedes: tuple[str, ...] = ()) -> DesiredItem:
    """The sioyek entry, as `packages.yml` declares it under the newer name."""
    return DesiredItem(
        section='system_packages',
        provider='syspkg',
        resource='system',
        stage=Stage.SYSTEM,
        name='sioyek',
        executable='sioyek',
        evidence_path='',
        precondition=Precondition.NONE,
        entry=catalog.SystemPackage(name='sioyek', aur='sioyek-git', supersedes=supersedes),
        reason=Reason('system_packages', 'test'),
    )


def change_for(desired: DesiredItem, found: ev.Evidence) -> Change:
    """One item's `Change`, built the way `resources.system` builds it."""
    repair = repair_for(desired, found.verdict, MET, found.blocked_by)
    return Change(
        'system',
        Stage.SYSTEM,
        desired.address,
        found.verdict,
        repair=repair,
        detail=found.detail,
        advice=advice_for(desired, repair, found.blocked_by),
        desired=desired,
    )


def test_a_missing_package_with_nothing_in_its_way_stays_applys_to_fix() -> None:
    """The ordinary case, and the one that must not regress. Every other package
    in `packages.yml` reaches this branch, so a blocker that reported itself too
    eagerly would take the whole install path down with it."""
    found = ev.by_registry(item(supersedes=('sioyek',)), {'pacman': frozenset({'git', 'ripgrep'})})

    assert found.verdict is Verdict.MISSING
    assert found.blocked_by is None
    assert change_for(item(), found).actionable


def test_a_superseded_package_still_installed_is_named_as_the_blocker() -> None:
    """The measurement that was missing. `sioyek` is in the inventory under the
    name this entry replaced, so the install `plan` was about to promise cannot
    happen."""
    found = ev.by_registry(item(supersedes=('sioyek',)), {'pacman': frozenset({'sioyek', 'git'})})

    assert found.verdict is Verdict.MISSING
    assert found.blocked_by is not None
    assert found.blocked_by.package == 'sioyek'


def test_a_blocked_package_is_not_applys_to_repair() -> None:
    """`BY_HAND` rather than `AUTOMATIC`, which is what stops apply attempting a
    build whose outcome is already decided."""
    found = ev.by_registry(item(supersedes=('sioyek',)), {'pacman': frozenset({'sioyek'})})

    assert repair_for(item(supersedes=('sioyek',)), found.verdict, MET, found.blocked_by) is Repair.BY_HAND


def test_the_advice_names_the_package_to_remove_and_the_command() -> None:
    """`yay -S exited 1` sent a reader to the transcript to find the conflict.
    The next step belongs on the row that reports the problem."""
    found = ev.by_registry(item(supersedes=('sioyek',)), {'pacman': frozenset({'sioyek'})})
    advice = advice_for(item(supersedes=('sioyek',)), Repair.BY_HAND, found.blocked_by)

    assert 'sioyek' in advice
    assert 'pacman -R' in advice


def test_check_reports_a_blocked_package_that_plan_and_apply_leave_alone() -> None:
    """The whole finding, in the terms the three verbs are folded through.

    `sift` is what `plan`, `check` and `apply` each read: plan renders `pending`,
    check renders `attention`, and apply acts on `pending` and reports
    `attention` without counting it as a failure. A blocked package belongs in
    exactly one of them.
    """
    found = ev.by_registry(item(supersedes=('sioyek',)), {'pacman': frozenset({'sioyek'})})
    pending, attention, unmeasured = sift([change_for(item(supersedes=('sioyek',)), found)])

    assert not pending, 'plan promised an install that could never happen'
    assert len(attention) == 1, 'check stayed converged while apply was going to fail'
    assert not unmeasured


def test_supersedes_naming_this_entrys_own_package_is_a_declaration_error() -> None:
    """A package does not supersede itself, and an entry saying so would report
    itself permanently blocked by its own installation."""
    entry = catalog.SystemPackage(name='sioyek', aur='sioyek-git', supersedes=('sioyek-git',))

    assert any('supersedes' in problem for problem in entry.problems())
