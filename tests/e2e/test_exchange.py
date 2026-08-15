"""The two-machine exchange, at the rung below a machine install.

`test_machine.py` runs the whole trip and costs half an hour. Everything here
costs seconds and answers the questions that trip depends on: that the builder
serves a shelf, that a peer reaches it over the network, and that `remote.py`
drives the declared transport rather than the harness driving docker.

That split is the same one `test_container.py` exists for. A rig fault found
after a full install is a rig fault found forty minutes late, and every fault in
this file is one the old harness could not have had — because the old harness ran
the build on the host and moved bundles with `docker cp`.
"""

from __future__ import annotations

import json

import exchange
import pytest
from harness import Machine

pytestmark = pytest.mark.docker


def test_the_builder_has_what_it_needs_to_build(builder: Machine) -> None:
    """uv and the repo, which is all a build needs. Nothing installs here."""
    assert builder.succeeds('command -v uv')
    assert builder.succeeds(f'test -f {builder.environment.home}/dotfiles/install/packages.yml')


def test_the_builder_has_a_network(builder: Machine) -> None:
    """The half the offline machine cannot do for itself, and the reason there are
    two containers rather than one."""
    assert builder.succeeds('curl -sSf -o /dev/null https://api.github.com')


def test_the_shelf_answers_over_the_network(builder: Machine) -> None:
    """sshd up, key authorized, shelf writable. The probe is the operation that
    has to succeed whenever the peer answers, whatever is stored on it."""
    assert builder.succeeds(f'{exchange.TRANSPORT} probe')


def test_the_transport_lists_one_name_per_line(builder: Machine) -> None:
    """The whole contract between dotfiles and whatever moves its bytes. Asserted
    on the script rather than through the CLI, so a failure here is the transport
    and a failure in the next test is `remote.py`."""
    builder.exec(f'{exchange.TRANSPORT} mkdir {exchange.SHELF_ROOT}/probe-dir', check=True)
    builder.exec(f'touch /tmp/alpha && {exchange.TRANSPORT} upload /tmp/alpha {exchange.SHELF_ROOT}/probe-dir', check=True)
    builder.exec(f'touch /tmp/beta && {exchange.TRANSPORT} upload /tmp/beta {exchange.SHELF_ROOT}/probe-dir', check=True)

    listed = builder.read(f'{exchange.TRANSPORT} list {exchange.SHELF_ROOT}/probe-dir')

    assert sorted(listed.splitlines()) == ['alpha', 'beta']


def test_listing_a_directory_that_is_not_there_fails_while_the_probe_still_answers(builder: Machine) -> None:
    """The discrimination the probe exists for. One exit code cannot say whether a
    server is down or a path is absent, which is how a machine comes to download a
    full bundle because a dropped packet hid the status that would have made it
    sparse."""
    assert not builder.succeeds(f'{exchange.TRANSPORT} list {exchange.SHELF_ROOT}/nothing-here')
    assert builder.succeeds(f'{exchange.TRANSPORT} probe')


def test_dotfiles_reports_the_remote_as_reachable(builder: Machine) -> None:
    """`remote.py` driving the declared transport, which is the layer the old
    harness never reached: bundles moved by `docker cp` and the transport was
    exercised only against a fake."""
    ran = builder.exec(f'cd {builder.environment.home}/dotfiles && uv run dotfiles remote check --json')
    reported = json.loads(ran.stdout or '{}')

    assert reported.get('declared') is True, ran.stdout or ran.stderr
    assert reported.get('faults') == 0, ran.stdout
    assert reported.get('root') == exchange.SHELF_ROOT


def test_an_unreachable_peer_is_told_apart_from_an_empty_shelf(builder: Machine) -> None:
    """Pointed at a host that does not exist, the probe fails rather than reporting
    an empty shelf — which is the answer that decides between refusing and building
    a full bundle."""
    builder.exec('printf %s no-such-peer > /etc/shelf-host', user='root', check=True)
    try:
        assert not builder.succeeds(f'{exchange.TRANSPORT} probe')
    finally:
        builder.exec(f'printf %s {builder.container} > /etc/shelf-host', user='root', check=True)

    assert builder.succeeds(f'{exchange.TRANSPORT} probe'), 'the peer was not restored'
