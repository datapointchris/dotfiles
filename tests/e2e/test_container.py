"""The container rig, before anything is installed.

Seconds rather than half an hour, because nothing here runs `install.sh`. These
are the questions that used to require a full install to answer — is the repo
really in there, does a command see the PATH a login shell would, is the network
the one the work box reported — and every one of them is a way the harness can be
wrong while the code under test is fine.

Run these after touching `harness.py` or `conftest.py`; run `test_machine.py`
after touching what actually installs a machine.

    uv run pytest tests/e2e/test_container.py --docker
"""

from __future__ import annotations

import pytest
from harness import SHADOW_BIN
from harness import SHADOW_REFUSAL
from harness import Machine
from harness import measured_network
from harness import reachable_probes
from harness import shadow_calls

pytestmark = pytest.mark.docker


def test_the_container_is_running_as_the_installing_user(container: Machine) -> None:
    """Root would pass the sudo-gated phases for the wrong reason, and would write
    into `/root` rather than the home the real machine uses."""
    assert container.read('id -un') == container.environment.user


def test_home_is_the_installing_user_s_home(container: Machine) -> None:
    assert container.read('echo $HOME') == container.environment.home


def test_the_repo_arrived_and_is_a_git_checkout(container: Machine) -> None:
    """`install.sh` resolves the repo with `git rev-parse --show-toplevel`, so a
    copy that is not a checkout fails at its first line."""
    home = container.environment.home
    assert container.succeeds(f'test -x {home}/dotfiles/install.sh')
    assert container.read(f'cd {home}/dotfiles && git rev-parse --show-toplevel') == f'{home}/dotfiles'


def test_the_repo_is_writable_by_the_installing_user(container: Machine) -> None:
    """The bind mount is read-only on purpose — an install must never be able to
    write back into the working tree it was launched from."""
    home = container.environment.home
    assert container.succeeds(f'touch {home}/dotfiles/.writable-probe && rm {home}/dotfiles/.writable-probe')
    assert not container.succeeds('touch /dotfiles-src/.writable-probe')


def test_the_copy_left_the_host_git_directory_behind(container: Machine) -> None:
    """Copying `.git` would carry the host's branch, remotes and hooks into the
    container, and `git init` would then be a no-op over someone else's history."""
    home = container.environment.home
    assert container.read(f'cd {home}/dotfiles && git log --oneline -1 2>&1 | head -1') != container.read(
        'cd /dotfiles-src && git log --oneline -1 2>&1 | head -1'
    )


def test_a_command_sees_the_path_a_login_shell_would(container: Machine) -> None:
    """The failure this catches is invisible in a log: a tool reported missing on
    a machine that is carrying it, because the exec forgot `~/.local/bin`."""
    path = container.read('echo $PATH').split(':')
    home = container.environment.home
    assert f'{home}/.local/bin' in path
    assert path.index(f'{home}/.local/bin') < path.index('/usr/bin')


def test_the_bootstrap_has_what_install_sh_requires(container: Machine) -> None:
    """`install.sh` checks for exactly these and then stops, so a missing one is a
    prepared-container problem rather than an install failure."""
    for tool in ('git', 'tar'):
        assert container.succeeds(f'command -v {tool}'), tool


def test_the_system_python_is_shadowed_rather_than_absent(container: Machine) -> None:
    """The stub has to win the PATH lookup, or the install it is meant to break
    runs against the real interpreter and passes for the wrong reason.

    Absence is the weaker property and only one image can express it: Arch ships
    no python, so asserting `command -v python3` fails there proves that Arch is
    Arch, and the same assertion on a Mac fails against Xcode's.
    """
    home = container.environment.home
    assert container.read('command -v python3') == f'{home}/{SHADOW_BIN}/python3'

    refused = container.exec('python3 --version')
    assert refused.returncode == 1
    assert SHADOW_REFUSAL in refused.stderr


def test_the_shadow_names_whoever_called_it(container: Machine) -> None:
    """The log is the diagnosis when an install dies, and a log that records the
    call without the caller answers the wrong half of the question."""
    container.exec('python3 -c pass')
    called = [call for call in shadow_calls(container) if 'python3' in call.argv]
    assert called, 'the stub ran and recorded nothing'
    assert all(call.caller for call in called)


def test_the_machine_declares_itself_before_anything_runs(container: Machine) -> None:
    """`~/.env` either was written here or is deliberately absent so `install.sh`
    generates it — and generating it is the step being rehearsed."""
    home = container.environment.home
    exists = container.succeeds(f'test -f {home}/.env')
    assert exists == (container.environment.env_file is not None)


def test_the_network_is_the_one_the_work_box_measured(container: Machine) -> None:
    """Both directions, because only one of them was ever asserted.

    Blocking too little proves nothing. Blocking too much manufactures failures no
    machine has, and they read as real ones in a log — which is how clone-based
    installers came to look broken on a network where they install fine.
    """
    if not container.environment.firewalled:
        pytest.skip('only a firewalled environment models the work network')

    blocked, _ = measured_network()
    still_reachable = [host for host in blocked if container.succeeds(f'curl -fsS --connect-timeout 5 https://{host}/')]
    assert not still_reachable, f'blocked at work but reachable here: {still_reachable}'

    # Each recorded probe re-run exactly as the measurement ran it — same method,
    # same URL, same agent. Synthesizing `https://<host>/` instead reported
    # crates.io blocked, because it answers a default curl agent with 403; that is
    # the trap `test-connectivity.sh` documents and works around, and this test
    # walked into it on its first run.
    unreachable = [probe.name for probe in reachable_probes() if not container.succeeds(probe.command())]
    assert not unreachable, f'reachable at work but not here — the container is stricter than the firewall: {unreachable}'


def test_an_online_environment_has_no_firewall(container: Machine) -> None:
    """The inverse mistake: an online run that cannot reach GitHub would report
    the online path broken when only the container was."""
    if container.environment.firewalled:
        pytest.skip('a firewalled environment blackholes hosts on purpose')
    assert container.succeeds('curl -fsS --connect-timeout 10 https://github.com/')
