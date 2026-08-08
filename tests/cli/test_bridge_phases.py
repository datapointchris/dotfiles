"""`RESOURCE_PHASES` must account for every phase `install/phases.sh` registers.

The mapping is a literal in Python while the registry is an array in bash, and
nothing about editing one brings you into contact with the other. Left
unasserted, a phase added to the registry simply stops being reachable through
the resource that should own it — `dotfiles packages apply` would quietly install
less than it used to, and the run would still exit 0.

The registry is read by *sourcing* phases.sh and asking bash to print the array,
never by parsing the file. Regex over structured data is how the two drift apart
a second time.

Step 4 deletes both sides of this: the registry becomes Python and the mapping
becomes the resource definitions themselves.
"""

from __future__ import annotations

import subprocess

import pytest

from dotfiles import paths
from dotfiles.bridge import RESOURCE_PHASES


def registered_phases() -> list[tuple[str, str]]:
    """Every (phase, group) bash declares, straight from the sourced array."""
    script = f'PHASE_VERB=install; source "{paths.INSTALL_DIR}/phases.sh"; printf "%s\\n" "${{PHASE_REGISTRY[@]}}"'
    result = subprocess.run(
        ['bash', '-c', script],
        capture_output=True,
        text=True,
        env={'DOTFILES_DIR': str(paths.REPO_ROOT), 'PATH': '/usr/bin:/bin', 'TERM': 'dumb'},
        check=True,
    )
    entries = []
    for line in result.stdout.splitlines():
        name, group, *_ = line.split('|')
        entries.append((name, group))
    return entries


REGISTERED = registered_phases()


def test_the_registry_was_actually_read() -> None:
    """Sourcing a script that fails silently would make every test below vacuous."""
    assert len(REGISTERED) > 10


@pytest.mark.parametrize('phase', [name for name, _ in REGISTERED])
def test_every_registered_phase_is_claimed(phase: str) -> None:
    owners = [resource for resource, phases in RESOURCE_PHASES.items() if phase in phases]
    assert owners, (
        f'phase {phase!r} is in install/phases.sh but no resource claims it, so '
        f'`dotfiles <resource> apply` will never run it. Add it to RESOURCE_PHASES.'
    )
    assert len(owners) == 1, f'phase {phase!r} is claimed by {owners}; two resources would run it twice'


def test_no_resource_claims_a_phase_that_does_not_exist() -> None:
    """A phase renamed in bash leaves `install.sh <old-name>` failing as a bad selector."""
    registered = {name for name, _ in REGISTERED}
    for resource, phases in RESOURCE_PHASES.items():
        unknown = set(phases) - registered
        assert not unknown, f'{resource} claims phases that install/phases.sh does not register: {sorted(unknown)}'


def test_apply_covers_the_whole_registry() -> None:
    """`dotfiles apply` with nothing skipped must be the same work as a full install.sh."""
    claimed = {phase for phases in RESOURCE_PHASES.values() for phase in phases}
    assert claimed == {name for name, _ in REGISTERED}
