"""Whether the finished machine is carrying what its manifest declares.

Two properties are what make this readable, and both are easy to lose:

**One node per tool.** A single check counting its own assertions returns one exit
code, so a failure is `returncode == 0` and four thousand characters of transcript.
A missing tool is a named red line here —
`test_the_machine_carries_what_it_declares[wsl-…-go/sesh]` — and the tools that
*are* fine stay quiet.

**The declaration decides what is checked.** A hand-written list at the bottom of
the file goes on asserting tools long after they are deleted, and never checks the
ones added since — a check covering less than it claims to. `resolve.resolve`
answers for the whole plan.

**The observation stays independent.** Expectations come from the resolver;
whether something is *there* is asked of the container in shell, and nothing here
runs `dotfiles check`. A verification that read the product's own evidence would
agree with the installer whenever they were wrong together, which is the one
failure it exists to catch.
"""

from __future__ import annotations

import pytest
from harness import Declared
from harness import Machine
from harness import Sweep
from harness import declared_items
from harness import declared_links
from harness import deployed_script
from harness import probed
from harness import recorded_as
from harness import refusals
from harness import registry_names
from harness import unexplained_copies

pytestmark = pytest.mark.docker


@pytest.fixture(scope='session')
def present(machine: Machine) -> Sweep:
    """What the machine answered about every declared item, from one sweep.

    Session-scoped and taken off `machine` rather than `converged_machine`: it is
    a measurement of the container, and which environments are *expected* to have
    converged is the individual test's question. Function scope would put two
    hundred `docker exec` calls where one belongs.
    """
    return probed(machine, declared_items(machine.environment))


@pytest.fixture(scope='session')
def refused(machine: Machine) -> dict[str, str]:
    """What this machine's own install reached, wrote nothing for, and explained.

    Read from the record the install pinned rather than from a list here, so it
    cannot disagree with what the run did and so an installer that stops refusing
    something starts being required with nothing here to update.

    Every way of failing to read one leaves this empty, which requires *every*
    declared item. A record this cannot find has to make the check stricter, never
    more forgiving — the opposite turns a broken CLI into a green verification.
    """
    try:
        return refusals(machine)
    except AssertionError:
        return {}


def test_the_machine_carries_what_it_declares(
    converged_machine: Machine, declared_item: Declared, present: Sweep, refused: dict[str, str]
) -> None:
    """One declared item, one node.

    Three ways to be excused, and each is about the machine rather than the item:
    the run reached it and explained writing nothing, a declared precondition does
    not hold here, or there is nothing on this machine that could have been asked.
    Everything else is a red line naming the item.

    A skip is not a pass, which is the distinction the summary this replaced could
    not make — it counted its own checks, so an item nobody examined and an item
    found present were one number.
    """
    item = declared_item.item

    if (excused := recorded_as(item)) in refused:
        pytest.skip(f'the install refused it: {refused[excused]}')

    observed = present.observed(item)
    if observed is None:
        pytest.skip(
            f'nothing on this machine can be asked about {item.address} ({item.provider}, precondition {item.precondition or "none"})'
        )

    assert observed, (
        f'{item.address} declares {item.executable or item.evidence_path or ", ".join(sorted(registry_names(item)))} '
        f'and the machine has none; the run neither refused it nor explained it'
    )


def test_the_offline_machine_is_where_a_refusal_actually_happens(converged_machine: Machine, refused: dict[str, str]) -> None:
    """The excuse the per-item nodes accept has to be one something really produces.

    A refusal suppresses a red line, so the mechanism is only safe while it stays
    rare and real. Offline is where it is neither optional nor incidental: there
    is no go.dev to fetch a toolchain from and no rustup.rs to run, the bundle
    stages those tools prebuilt instead, and the run says so rather than failing.
    An offline install that refused *nothing* means either the bundle stopped
    standing in for the network or the refusals stopped being recorded, and each
    of those turns every skip above into an unexamined pass.

    Only asserted in that direction. A converging online machine still refuses the
    odd item for a reason that is about the box — a container has no `/dev/kfd`,
    so ROCm's precondition does not hold — and demanding an empty set there would
    be a red line about the hardware.
    """
    if not converged_machine.environment.offline:
        pytest.skip('a refusal is incidental here; offline is where the mechanism is load-bearing')

    assert refused, 'the offline install refused nothing, so nothing stood in for the network it cannot reach'


def test_every_declared_symlink_is_deployed(converged_machine: Machine) -> None:
    """The config half of the machine, which no tool check reaches.

    Not parametrized, unlike the items above: a link is one `test -e` and the
    diagnosis a reader wants is the whole list of what is missing at once, where a
    tool wants its own red line and its own name.

    Derived, never a hand-picked list: a list picked once is never revisited, so a
    config added since goes unexamined and one deleted is still asserted.
    """
    targets = declared_links(converged_machine.environment)
    assert targets, 'nothing declared any links, so this asked the machine nothing'

    swept = converged_machine.exec(deployed_script(targets))
    missing = [line.strip() for line in swept.stdout.splitlines() if line.strip()]

    assert not missing, f'{len(missing)} of {len(targets)} declared links are not on the machine: {missing[:20]}'


def test_nothing_declared_is_installed_twice(converged_machine: Machine) -> None:
    """Two copies means the one that runs is decided by PATH order, not the manifest.

    Asked independently of `dotfiles check`, which grew the same row in the same
    commit — the point of a second opinion is that it is second. What it shares is
    the *explanation*, which is declaration and not evidence: a copy an OS package
    manager attributes to a package this manifest declares is the bootstrap the
    declaration asked for, and pacman's `nodejs` under fnm's node is exactly that.

    Asserted on what the check *reports*, never on its exit status: a detector that
    prints its findings and still exits 0 makes a return-code assertion one that
    can never fail.
    """
    found = unexplained_copies(converged_machine, declared_items(converged_machine.environment))

    assert not found, f'declared tools answering to more than one copy nothing explains: {found}'


def test_a_login_shell_on_the_finished_machine_reports_nothing(converged_machine: Machine) -> None:
    """A converged machine's shell has nothing left to complain about.

    `tests/shell/test_zshrc_startup.py` asks the same question against a home
    assembled by hand, which is fast and is where the rule is stated. This asks it
    of a machine that actually converged, where the plugins are installed and the
    flags are the manifest's rather than a fixture's approximation of them — so a
    config that reports something only a real install can produce is caught here
    and nowhere else.

    Measured 2026-08-16 on scheduler-lxc: every shell wrote `broot not found`,
    because the manifest omits a tool `.zshrc` assumed. Nothing in this matrix ran
    that manifest, and nothing at any level started a shell and read stderr.
    """
    started = converged_machine.exec("zsh -i -c true 2>&1 >/dev/null | grep -F '❌' || true")
    reported = [line.strip() for line in started.stdout.splitlines() if line.strip()]

    assert not reported, 'a shell on the finished machine reported:\n' + '\n'.join(reported)
