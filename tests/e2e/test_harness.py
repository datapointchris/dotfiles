"""The rig itself, tested without starting anything.

The tier that was missing, and its absence cost two thirty-minute container
installs to answer questions about a fixture. Everything here runs in
milliseconds and is what a change to `harness.py` should be checked against
first; the container tiers exist to catch what only a real machine can show.

Nothing here is marked, so it runs in the default suite. It needs no Docker.
"""

from __future__ import annotations

import pytest
from harness import ASSET_CDN_HOSTS
from harness import CONNECTIVITY_RESULTS
from harness import CONTAINER_PATH_DIRS
from harness import ENVIRONMENTS
from harness import PROBE_AGENT
from harness import SHADOW_BIN
from harness import SHADOW_LOG
from harness import SHADOW_REFUSAL
from harness import Environment
from harness import ShadowCall
from harness import blocked_host_args
from harness import exec_script
from harness import measured_network
from harness import reachable_probes
from harness import shadow_source

# ─────────────────────────────────────────────────────────────────────────────
# The measured network
# ─────────────────────────────────────────────────────────────────────────────


def test_the_measurement_was_actually_read() -> None:
    """A parse that silently found nothing would make every assertion below
    vacuous, and would blackhole an empty set — a container with no firewall at
    all, passing."""
    blocked, reachable = measured_network()
    assert len(reachable) > 5
    assert len(blocked) >= len(ASSET_CDN_HOSTS)


def test_a_host_is_never_both_blocked_and_reachable() -> None:
    """The two sets drive `--add-host` and an assertion that contradicts it."""
    blocked, reachable = measured_network()
    assert not set(blocked) & set(reachable)


def test_github_stays_reachable_because_its_block_is_path_scoped() -> None:
    """The measurement records a NO against a github.com URL — a release asset —
    while every clone and the API are YES. Taking the host down would take the
    working paths with it, which is what made theme, font and bashselfupdate fail
    in a test of a network where they install fine.
    """
    blocked, reachable = measured_network()
    assert 'github.com' in reachable
    assert 'github.com' not in blocked
    assert set(ASSET_CDN_HOSTS) <= set(blocked)


def test_what_the_work_box_reported_blocked_is_blocked() -> None:
    """Read off the file rather than restated, so this cannot drift from it."""
    rows = [line.split('|') for line in CONNECTIVITY_RESULTS.read_text().splitlines()]
    verdicts = {cells[0].strip() for cells in rows if len(cells) >= 4}
    assert {'YES', 'NO'} <= verdicts, 'the results file has no verdict column any more'

    blocked, _ = measured_network()
    assert 'proxy.golang.org' in blocked, 'the Go proxy is why go_tools are bundled'


def test_only_a_firewalled_environment_blackholes_anything() -> None:
    """An online environment given a firewall would be testing the offline path
    while claiming to test the online one."""
    for environment in ENVIRONMENTS:
        arguments = blocked_host_args(environment)
        assert bool(arguments) == environment.firewalled, environment.name


def test_every_blocked_host_becomes_one_add_host_pair() -> None:
    firewalled = next(environment for environment in ENVIRONMENTS if environment.firewalled)
    blocked, _ = measured_network()
    arguments = blocked_host_args(firewalled)

    assert arguments.count('--add-host') == len(blocked)
    assert all(f'{host}:127.0.0.1' in arguments for host in blocked)


def test_an_offline_environment_is_always_firewalled() -> None:
    """Otherwise it installs from a bundle on a machine that could have reached
    the network anyway, and proves nothing about the machine that cannot."""
    for environment in ENVIRONMENTS:
        if environment.offline:
            assert environment.firewalled, environment.name


def test_one_firewalled_environment_carries_no_bundle() -> None:
    """The failure machinery is only testable where failures are real, and every
    other environment is arranged so that nothing fails. Losing this one would
    leave `tests/e2e/test_failure_reporting.py` skipping in silence."""
    bare = [environment for environment in ENVIRONMENTS if environment.firewalled and not environment.offline]
    assert bare, 'nothing exercises a run whose downloads genuinely fail'


# ─────────────────────────────────────────────────────────────────────────────
# The environments
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('environment', ENVIRONMENTS, ids=lambda environment: environment.name)
def test_every_environment_names_a_manifest_that_exists(environment: Environment) -> None:
    """The name reaches `install.sh --machine`, which validates it itself and
    lists the alternatives — but only after a container has been built."""
    from dotfiles import paths

    assert (paths.MANIFESTS_DIR / f'{environment.manifest}.yml').is_file()


@pytest.mark.parametrize('environment', ENVIRONMENTS, ids=lambda environment: environment.name)
def test_every_environment_installs_as_a_named_user_in_its_own_home(environment: Environment) -> None:
    """Never root, and never `/root`: the real machines install as a sudo user,
    and a run as root passes the sudo-gated phases for the wrong reason. A WSL
    rootfs ships with no login user at all, which is why one is committed into
    the image rather than created per-container."""
    assert environment.user != 'root'
    assert environment.home.endswith(environment.user)


def test_the_environments_are_distinct_machines() -> None:
    """Two sharing a container name would fight over one container."""
    names = [environment.name for environment in ENVIRONMENTS]
    assert len(names) == len(set(names))


# ─────────────────────────────────────────────────────────────────────────────
# What a container command actually runs
# ─────────────────────────────────────────────────────────────────────────────


def test_the_exec_path_leads_with_the_directories_an_install_writes_to() -> None:
    """`~/.local/bin` carries uv and the CLI, `~/.cargo/bin` and `~/go/bin` the
    tools. A command that cannot find `uv` reports the machine broken when only
    the harness was — which is exactly what happened to the duplicate detector,
    in the one bash step that forgot to export a PATH."""
    script = exec_script('command -v uv', '/home/tester')
    assert '$HOME/.local/bin' in script
    assert script.index('$HOME/.local/bin') < script.index('/usr/bin')


def test_the_exec_path_still_carries_the_system_directories() -> None:
    """A phase needs `bash`, `git` and `tar`, which live in none of the above."""
    assert '/usr/bin' in CONTAINER_PATH_DIRS
    assert '/bin' in CONTAINER_PATH_DIRS


def test_home_is_exported_before_the_command_runs() -> None:
    """`docker exec --user` does not set HOME, so every path the command expands
    would resolve against root's home instead of the installing user's."""
    script = exec_script('echo hi', '/home/tester')
    assert script.index('HOME=/home/tester') < script.index('echo hi')


def test_a_home_with_a_space_survives_the_shell() -> None:
    """Quoted rather than interpolated bare, so a path never splits into two words."""
    assert "'/home/a tester'" in exec_script('echo hi', '/home/a tester')


# ─────────────────────────────────────────────────────────────────────────────
# The hostile system python
# ─────────────────────────────────────────────────────────────────────────────


def test_the_shadow_wins_the_path_lookup() -> None:
    """Behind `/usr/bin` it shadows nothing and every assertion built on it is
    vacuous — the install would use the real interpreter and pass."""
    script = exec_script('python3 --version', '/home/tester')
    assert script.index(f'$HOME/{SHADOW_BIN}') < script.index('/usr/bin')


def test_the_shadow_refuses_and_says_why() -> None:
    """Exit 1 rather than 127: a caller that tolerates "not found" would carry on
    to a fallback, and the fallback is the code path being deleted."""
    source = shadow_source('/home/tester')
    assert 'exit 1\n' in source
    assert SHADOW_REFUSAL in source
    assert f'/home/tester/{SHADOW_LOG}' in source


def test_a_uv_probe_is_not_a_stranger() -> None:
    """uv scanning PATH for an interpreter is expected; a phase script calling
    `python3` is the bug. Matched on basename, because `~/.local/share/uv` puts
    the substring in paths that have nothing to do with uv running."""
    assert ShadowCall(caller='/home/tester/.local/bin/uv tool install', argv='python3 -c ...').by_uv
    assert not ShadowCall(caller='bash /home/tester/dotfiles/install/common/thing.sh', argv='python3 x.py').by_uv
    assert not ShadowCall(caller='/home/tester/.local/share/uv/tools/dotfiles/bin/curl', argv='python3').by_uv
    assert not ShadowCall(caller='', argv='python3').by_uv


def test_a_probe_is_replayed_the_way_the_measurement_ran_it() -> None:
    """The method and the agent both changed a verdict at least once.

    A clone was measured with `git ls-remote`, and crates.io answers curl's
    default agent with 403 — recorded as a firewall block in January 2026, which
    would have meant bundling all nine cargo tools for nothing. A container
    re-probe that invents its own request measures a different question and calls
    the answer a firewall.
    """
    commands = {probe.name: probe.command() for probe in reachable_probes()}

    assert 'git ls-remote' in commands['dotfiles'], 'a clone must be probed as a clone'
    assert all(PROBE_AGENT in command for command in commands.values() if command.startswith('curl'))
    assert all(probe.target in probe.command() for probe in reachable_probes()), 'the recorded URL, not a synthesized one'


def test_every_reachable_host_is_probed_once_per_method() -> None:
    """Forty-odd rows collapse to a dozen, covering every reachable host and both
    ways one is reached. Per host alone would drop every clone, because the
    release rows claim `github.com` first."""
    probes = reachable_probes()
    _, reachable = measured_network()

    keys = [(probe.host, probe.cloned) for probe in probes]
    assert len(keys) == len(set(keys))
    assert {probe.host for probe in probes} == set(reachable)
    assert any(probe.cloned for probe in probes), 'the git path is never re-probed'
