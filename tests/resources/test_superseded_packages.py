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
from dotfiles.plan import DesiredItem
from dotfiles.plan import Precondition
from dotfiles.plan import Preconditions
from dotfiles.plan import Reason
from dotfiles.plan import Stage
from dotfiles.reconcile import sift
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


# ─────────────────────────────────────────────────────────────────────────────
# The same shape one mechanism over: a release taking over from a package
# ─────────────────────────────────────────────────────────────────────────────
#
# syncthing is `syncthing` under pacman and under Homebrew, and the fleet's one
# install path for it is the GitHub release. The blocker is not the binary — the
# release binary would install perfectly well beside the package's — it is the
# service: both of those ship one, so a machine carrying two runs two daemons over
# one config directory and one port.
#
# Which is why this one clears under `--force` where the sioyek case above never
# does. There the manager is the thing refusing, and authorising this repo to
# replace what it did not create says nothing to pacman.


def release(*, supersedes: tuple[str, ...] = ()) -> DesiredItem:
    """The syncthing entry, as `packages.yml` declares it."""
    return DesiredItem(
        section='github_releases',
        provider='ghrelease',
        resource='packages',
        stage=Stage.TOOLS,
        name='syncthing',
        executable='syncthing',
        evidence_path='',
        precondition=Precondition.NONE,
        entry=catalog.GithubRelease(name='syncthing', repo='syncthing/syncthing', supersedes=supersedes),
        reason=Reason('github_releases', 'test'),
    )


def test_a_release_whose_name_no_manager_holds_has_nothing_in_its_way() -> None:
    """Every other release entry reaches this branch, so a blocker reporting itself
    too eagerly would take the whole install path down with it."""
    assert ev.superseded(release(supersedes=('syncthing',)), {'brew': frozenset({'git', 'ripgrep'})}) is None


def test_a_release_is_asked_of_every_manager_rather_than_the_ones_it_names() -> None:
    """`by_registry` asks about the installers the entry declares a name under. A
    release declares none — no package manager installing it is what makes it a
    release — so the question goes to whichever manager answered."""
    blocking = ev.superseded(release(supersedes=('syncthing',)), {'brew': frozenset({'syncthing'})})

    assert blocking is not None
    assert blocking.package == 'syncthing'
    assert blocking.manager == 'brew'


def test_the_removal_named_is_the_one_that_manager_takes() -> None:
    """Homebrew's uninstall, not pacman's, on the machine Homebrew answered for."""
    blocking = ev.superseded(release(supersedes=('syncthing',)), {'brew': frozenset({'syncthing'})})

    assert blocking is not None
    assert blocking.removal == 'brew uninstall syncthing'


def test_a_blocked_release_is_refused_rather_than_installed_beside_the_package() -> None:
    """Installing over it is what makes the machine worse than either state alone,
    so the refusal is the safe answer and the flag is the deliberate one."""
    blocking = ev.superseded(release(supersedes=('syncthing',)), {'pacman': frozenset({'syncthing'})})

    assert repair_for(release(), Verdict.MISSING, MET, blocking) is Repair.BY_HAND


def test_the_advice_names_the_command_that_removes_it_and_the_one_that_migrates() -> None:
    """Two next steps because there are two, and the second is what an apply does.
    `standards/help.md` § "An error is the help screen for the failure in hand"."""
    blocking = ev.superseded(release(supersedes=('syncthing',)), {'pacman': frozenset({'syncthing'})})
    advice = advice_for(release(), Repair.BY_HAND, blocking)

    assert 'pacman -R syncthing' in advice
    assert 'dotfiles packages apply --package syncthing --force' in advice


def test_force_clears_the_blocker_so_apply_can_act_on_it() -> None:
    """The flag `symlinks apply` already spells this way: authorisation to replace
    what this repo did not create."""
    blocking = ev.superseded(release(supersedes=('syncthing',)), {'pacman': frozenset({'syncthing'})})

    assert blocking is not None
    assert blocking.standing(force=True) is None
    assert blocking.standing(force=False) is blocking


def test_force_does_not_clear_a_superseded_system_package() -> None:
    """The asymmetry, and it is deliberate. Nothing here removes a package to make
    `yay -S` succeed, so a flag that promised to would turn a clear refusal into a
    long build and a failed transaction."""
    found = ev.by_registry(item(supersedes=('sioyek',)), {'pacman': frozenset({'sioyek'})})

    assert found.blocked_by is not None
    assert found.blocked_by.standing(force=True) is found.blocked_by
