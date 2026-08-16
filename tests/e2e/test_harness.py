"""The rig itself, tested without starting anything.

The tier that was missing, and its absence cost two thirty-minute container
installs to answer questions about a fixture. Everything here runs in
milliseconds and is what a change to `harness.py` should be checked against
first; the container tiers exist to catch what only a real machine can show.

Nothing here is marked, so it runs in the default suite. It needs no Docker.
"""

from __future__ import annotations

import dataclasses as dc
import subprocess
from pathlib import Path

import harness
import pytest
from harness import ARCHLINUX
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
from harness import copies_script
from harness import declared_items
from harness import exec_script
from harness import measured_network
from harness import probe_of
from harness import probe_script
from harness import reachable_probes
from harness import shadow_source
from harness import shell_path

from dotfiles import machine as machines
from dotfiles import network
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Precondition
from dotfiles.resolve import Reason
from dotfiles.resolve import Stage

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
    assert any(host.endswith('githubusercontent.com') for host in blocked), (
        'blackholing the CDN a download redirects to is how a path-scoped block becomes a host rule'
    )


OLD_FORMAT_RESULTS = """\
    | SECTION           | NAME                    | TARGET                          | REACH
------------------------------------------------------------------------------
NO  | github_asset      | release asset download  | https://github.com/o/r/releases/download/v1/x| download
YES | git_clone         | dotfiles                | https://github.com/datapointchris/dotfiles.git| clone
------------------------------------------------------------------------------
"""
"""A results file as it was written before the LANDED column, hand-built because
nothing produces this shape any more. The committed file is one of these until the
work box is next behind its own firewall to regenerate it."""


def network_against(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    results = tmp_path / 'connectivity-results.txt'
    results.write_text(text)
    monkeypatch.setattr(harness, 'CONNECTIVITY_RESULTS', results)
    return measured_network()


def test_a_file_without_the_landed_column_still_blackholes_the_asset_cdns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The fallback, and it is load-bearing rather than tidy.

    Deriving from the rows alone would contribute nothing here — the asset row names
    github.com, which is reachable through the clone row, so the both-verdicts rule
    strips it. The firewalled containers would blackhole an empty set and go on
    reporting green while rehearsing no firewall at all.
    """
    blocked, _ = network_against(monkeypatch, tmp_path, OLD_FORMAT_RESULTS)

    assert set(ASSET_CDN_HOSTS) <= set(blocked)


def test_a_file_with_the_landed_column_derives_the_cdn_instead(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Rendered rather than hand-written, because the header is the format marker and
    only `network.render` writes it — a hand-built file here would keep passing after
    the real one stopped saying what this reads."""
    asset = network.ProbeResult(
        network.Probe('github_asset', 'release asset download', 'https://github.com/o/r/releases/download/v1/x'),
        False,
        'release-assets.githubusercontent.com',
    )
    clone = network.ProbeResult(network.Probe('git_clone', 'dotfiles', network.DOTFILES_REPO, network.Reach.CLONE), True)
    written = network.render(
        machines.load('wsl-work-workstation'),
        network.Measurement((asset, clone), ()),
        when='w',
        system='s',
    )

    blocked, _ = network_against(monkeypatch, tmp_path, written)

    assert 'release-assets.githubusercontent.com' in blocked
    assert 'github.com' not in blocked, 'the entry host is reachable through the clone row'
    assert not set(ASSET_CDN_HOSTS) - {'release-assets.githubusercontent.com'} & set(blocked), (
        'the hardcoded names are not added once the file says where the probe landed'
    )


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
    and a run as root passes the sudo-gated stages for the wrong reason. A WSL
    rootfs ships with no login user at all, which is why one is committed into
    the image rather than created per-container."""
    assert environment.user != 'root'
    assert environment.home.endswith(environment.user)


def test_the_environments_are_distinct_machines() -> None:
    """Two sharing a container name would fight over one container."""
    names = [environment.name for environment in ENVIRONMENTS]
    assert len(names) == len(set(names))


def test_asking_for_one_environment_collects_only_that_one() -> None:
    """`-k` reads as environment selection and is not, which cost a running install.

    `-k offline` matches `test_the_offline_run_never_resolved_a_version_online`
    too, so it selected all four; the run then started a container over the name
    the Arch install in another process was using, and `docker rm -f` killed it at
    137 — indistinguishable from an OOM in the log. Collection is checked in a
    subprocess because the option and the deselection are pytest's, not the rig's.
    """
    from dotfiles import paths

    collected = subprocess.run(
        # `-o addopts=` drops the repo's `-vv`, which makes `--collect-only` print
        # a node tree rather than the ids this reads.
        ['uv', 'run', 'pytest', 'tests/e2e', '--docker', '--environment', 'offline', '--collect-only', '-q', '-o', 'addopts='],
        cwd=paths.REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # This module's own parametrization is over environment *definitions*, which
    # start nothing and are deliberately left alone; only what asks for a
    # container is filtered.
    selected = [line for line in collected.stdout.splitlines() if '::' in line and 'test_harness.py' not in line]

    assert selected, collected.stdout[-2000:]
    others = [name for name in ('archlinux', 'wsl', 'restricted') if any(f'[{name}]' in line for line in selected)]
    assert not others, f'asking for offline also collected {others}'
    assert any('[offline]' in line for line in selected)


def test_the_set_tier_is_not_collected_when_nothing_may_install() -> None:
    """`--installed` means assert against the install already there, and a set
    test cannot honour it — `over_base` starts a container and installs into it.

    Collected anyway they were the whole difference between the tier the ladder
    documents and the one it delivered: nine minutes against the seconds that
    make it the rung most fixes land on.
    """
    from dotfiles import paths

    def collect(*flags: str) -> list[str]:
        completed = subprocess.run(
            [
                'uv',
                'run',
                'pytest',
                'tests/e2e',
                '--docker',
                '--environment',
                'archlinux',
                *flags,
                '--collect-only',
                '-q',
                '-o',
                'addopts=',
            ],
            cwd=paths.REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return [line for line in completed.stdout.splitlines() if '::' in line]

    assert any('test_set.py' in line for line in collect()), 'the set tier is gone from the default selection'
    assert not [line for line in collect('--installed') if 'test_set.py' in line]


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
    """An install needs `bash`, `git` and `tar`, which live in none of the above."""
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
# Which flags an environment installs under
# ─────────────────────────────────────────────────────────────────────────────


def test_only_the_bundled_environment_installs_offline() -> None:
    """`offline` is what decides it, not `firewalled` — `restricted` is firewalled
    and carries no bundle, so passing it `--offline` would point every installer at
    a bundle that is not there and stop the downloads from failing, which is the
    only thing that environment is for."""
    assert harness.OFFLINE.offline_flag == ' --offline'
    assert [environment.offline_flag for environment in (harness.ARCHLINUX, harness.WSL, harness.RESTRICTED)] == ['', '', '']


def test_both_halves_of_an_offline_install_are_told_it() -> None:
    """`install.sh` decides where uv and the wheels come from and the apply decides
    where every tool does, so a flag on one half only produces a machine that is
    half bundled — and the bootstrap's own `--offline` is settled before a CLI
    exists to be told anything."""
    command = harness.install_command(harness.OFFLINE)

    assert command.count('--offline') == 2
    assert './install.sh' in command.split('&&')[1]
    assert '--offline' in command.split('&&')[1]
    assert '--offline' in command.split('&&')[2]


def test_an_online_environment_is_told_nothing_about_bundles() -> None:
    assert '--offline' not in harness.install_command(harness.ARCHLINUX)


def test_an_install_pins_its_own_record_alongside_its_log_and_status() -> None:
    """Three artifacts, or the rung that reuses an install answers about two runs.

    `dotfiles/latest` moves under the next apply and the next apply is a test in
    `test_machine.py`, so a record read from there describes the second apply while
    the status beside it still describes the install."""
    command = harness.install_command(harness.WSL)

    assert harness.INSTALL_LOG in command
    assert harness.INSTALL_STATUS in command
    assert f'cp {harness.LATEST_RECORD} ' in command
    assert command.index(harness.INSTALL_STATUS) < command.index(harness.INSTALL_RECORD), (
        'the status is read off PIPESTATUS, so anything between it and the pipeline overwrites it'
    )


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
    """uv scanning PATH for an interpreter is expected; anything else calling
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


class TestGithubCredential:
    """A container's API calls share the host's public IP, so its 60 anonymous
    requests an hour are the host's too. One full install spends most of them."""

    def test_the_token_is_passed_by_name_so_it_stays_out_of_the_argument_list(self, monkeypatch) -> None:
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_pretend')

        arguments = harness.github_token_args()

        assert arguments == ['--env', 'GITHUB_TOKEN']
        assert not any('ghp_pretend' in argument for argument in arguments)

    def test_the_environment_wins_over_gh(self, monkeypatch) -> None:
        """How a caller points a run at a different account without logging out."""
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_from_the_environment')
        monkeypatch.setattr(harness.subprocess, 'run', _never_called)

        assert harness.github_token() == 'ghp_from_the_environment'

    def test_gh_answers_when_the_environment_does_not(self, monkeypatch) -> None:
        monkeypatch.delenv('GITHUB_TOKEN', raising=False)
        monkeypatch.setattr(harness.subprocess, 'run', _answering('ghp_from_gh\n'))

        assert harness.github_token() == 'ghp_from_gh'

    def test_no_credential_anywhere_degrades_rather_than_raising(self, monkeypatch) -> None:
        """An anonymous run is worth having — it is the rate limit that is not worth
        mistaking for a broken installer, which the session header names instead."""
        monkeypatch.delenv('GITHUB_TOKEN', raising=False)
        monkeypatch.setattr(harness.subprocess, 'run', _answering('', returncode=1))

        assert harness.github_token() == ''
        assert harness.github_token_args() == []

    def test_the_container_is_started_with_it(self, monkeypatch) -> None:
        """The whole point: `docker run` carries it, so every `docker exec` after
        inherits it and the install's release lookups are authenticated."""
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_pretend')
        started: list[tuple[str, ...]] = []
        monkeypatch.setattr(harness, 'docker', lambda *args, **kwargs: started.append(args))

        harness.start(ARCHLINUX, 'dotfiles-e2e-pretend')

        assert '--env' in started[0] and 'GITHUB_TOKEN' in started[0]


class TestBaseImage:
    """One image per distinct base, and the digest is the whole of what makes two
    bases distinct. Environments differing only in how the install is *run*
    against the base — firewalled, carrying a bundle — share the one it produces.
    """

    @staticmethod
    def _identified(monkeypatch: pytest.MonkeyPatch) -> None:
        """`docker image inspect` answered from the image name it was asked about,
        so a shared source image yields one id the way a real shared one does and
        two different images stay two."""
        monkeypatch.setattr(harness, 'docker', lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, f'sha256:{args[-1]}\n', ''))

    def test_offline_and_restricted_are_one_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same source image and same manifest, so the plan through the base stage
        is the same plan. The environment name in the tag was the only thing making
        them two, and what it bought was building and storing the base twice."""
        self._identified(monkeypatch)

        assert harness.base_tag(harness.OFFLINE) == harness.base_tag(harness.RESTRICTED)

    def test_a_different_source_image_is_a_different_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`wsl-ubuntu:26.04` is Microsoft's published rootfs, which is why that
        environment does not install onto `ubuntu:26.04` — so the same manifest
        over each is two machines, however alike the declaration."""
        self._identified(monkeypatch)

        assert harness.base_tag(harness.WSL) != harness.base_tag(harness.OFFLINE)

    def test_a_different_manifest_is_a_different_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Held against the same source image, so it is the declaration under test
        and not the two facts moving together."""
        self._identified(monkeypatch)
        elsewhere = dc.replace(harness.OFFLINE, name='pretend', manifest='archlinux-personal-workstation')

        assert harness.base_tag(elsewhere) != harness.base_tag(harness.OFFLINE)

    def test_the_tag_names_no_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """What the sharing rests on: a tag two environments both reach cannot
        carry either name, and one that did would read as an ownership the ledger
        deliberately declines to record."""
        self._identified(monkeypatch)

        for environment in ENVIRONMENTS:
            assert environment.name not in harness.base_tag(environment)


def _never_called(*args: object, **kwargs: object) -> object:
    raise AssertionError('gh was asked for a token the environment already had')


def _answering(stdout: str, returncode: int = 0):
    return lambda *args, **kwargs: subprocess.CompletedProcess(args, returncode, stdout, '')


class TestGitCredential:
    """A private-repo tag fetch needs git authenticated, not just the API.

    `git_uv_tools` pins to a release tag, so uv runs `git fetch` — which prompts
    for a username, finds prompts disabled, and fails. On a real machine
    `gh auth setup-git` has already written a helper; a container has neither.
    """

    def test_the_helper_reads_the_token_at_call_time_rather_than_embedding_it(self, monkeypatch) -> None:
        """So the token stays in the environment and never lands in a config file,
        a command line, or an image layer."""
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_pretend')
        ran: list[str] = []
        monkeypatch.setattr(harness.Machine, 'exec', lambda self, command, **kwargs: ran.append(command))

        harness.authenticate_git(harness.Machine(environment=ARCHLINUX, container='pretend'))

        assert len(ran) == 1
        assert 'credential."https://github.com".helper' in ran[0]
        assert '$GITHUB_TOKEN' in ran[0], 'the helper must read the token, not carry it'
        assert 'ghp_pretend' not in ran[0]

    def test_no_credential_configures_nothing(self, monkeypatch) -> None:
        monkeypatch.delenv('GITHUB_TOKEN', raising=False)
        monkeypatch.setattr(harness.subprocess, 'run', _answering('', returncode=1))
        ran: list[str] = []
        monkeypatch.setattr(harness.Machine, 'exec', lambda self, command, **kwargs: ran.append(command))

        harness.authenticate_git(harness.Machine(environment=ARCHLINUX, container='pretend'))

        assert ran == []


def test_the_container_gets_the_checkout_the_tests_came_from() -> None:
    """`paths.REPO_ROOT` honours `$DOTFILES_DIR`, which `.zshenv` exports to
    ~/dotfiles — so an e2e run from a git worktree mounted the wrong repo and
    installed main's code while reporting on the branch.

    Both directions were wrong and neither was visible: a fix made on the branch
    showed as still broken, and a break on main showed as the branch's.
    """
    assert all((harness.UNDER_TEST / marker).exists() for marker in harness.MARKERS)
    assert (harness.UNDER_TEST / 'src' / 'dotfiles').is_dir()


def test_the_repo_under_test_ignores_the_environment_the_product_reads(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DOTFILES_DIR', str(tmp_path))
    import importlib

    assert tmp_path != importlib.reload(harness).UNDER_TEST


def test_the_checkout_is_found_by_its_markers_rather_than_by_depth(tmp_path) -> None:
    """A `parents[n]` count is a claim about where this file sits in the tree, so
    moving it one directory silently answers `tests/` — which every fixture then
    mounts as the repo."""
    checkout = tmp_path / 'somewhere' / 'dotfiles'
    (checkout / 'tests' / 'e2e').mkdir(parents=True)
    (checkout / 'install.sh').write_text('#!/bin/sh\n')
    (checkout / 'tests' / 'e2e' / 'harness.py').write_text('')
    buried = checkout / 'tests' / 'e2e' / 'deeper' / 'still'
    buried.mkdir(parents=True)

    assert harness.repo_under_test(buried / 'anything.py') == checkout


def test_a_path_in_no_checkout_says_so_rather_than_guessing(tmp_path) -> None:
    with pytest.raises(RuntimeError) as refused:
        harness.repo_under_test(tmp_path / 'nowhere' / 'file.py')

    assert 'install.sh' in str(refused.value)


class TestContainerName:
    """Two checkouts of this repo must not be able to name the same container.

    Every fixture owning one begins by removing it, so a shared name is not a
    queue, it is one run destroying another's install mid-flight.
    """

    def test_the_main_checkout_keeps_the_bare_name(self, monkeypatch) -> None:
        """The containers already on the box stay reachable, and the common case
        stays readable in `docker ps`."""
        monkeypatch.setattr(harness, 'CHECKOUT', None)

        assert harness.container_name('archlinux') == 'dotfiles-e2e-archlinux'
        assert harness.container_name('set', 'wsl') == 'dotfiles-e2e-set-wsl'

    def test_a_worktree_takes_its_own_name(self, monkeypatch) -> None:
        monkeypatch.setattr(harness, 'CHECKOUT', 'convert-the-wsl-scripts')

        assert harness.container_name('archlinux') == 'dotfiles-e2e-archlinux-convert-the-wsl-scripts'

    def test_a_branch_shaped_name_is_made_legal_for_docker(self, monkeypatch) -> None:
        """A worktree may be named for a branch, and docker accepts only
        `[a-zA-Z0-9_.-]` after the first character."""
        monkeypatch.setattr(harness, 'CHECKOUT', 'feature/wsl scripts')

        assert harness.container_name('wsl') == 'dotfiles-e2e-wsl-feature-wsl-scripts'

    def test_the_main_worktree_is_recognised_by_git_rather_than_by_path(self, monkeypatch) -> None:
        monkeypatch.setattr(harness.subprocess, 'run', _answering('.git\n'))

        assert harness.linked_worktree(Path('/anywhere')) is None

    def test_a_linked_worktree_is_named_by_its_git_dir(self, monkeypatch) -> None:
        monkeypatch.setattr(harness.subprocess, 'run', _answering('/home/c/dotfiles/.git/worktrees/some-branch\n'))

        assert harness.linked_worktree(Path('/anywhere')) == 'some-branch'

    def test_no_git_at_all_is_the_main_checkout(self, monkeypatch) -> None:
        """An unpacked tarball is one checkout on the box, which is the case the
        bare name is for — not a reason to fail collection."""
        monkeypatch.setattr(harness.subprocess, 'run', _answering('', returncode=128))

        assert harness.linked_worktree(Path('/anywhere')) is None


# ─────────────────────────────────────────────────────────────────────────────
# The verification sweep, derived without a machine
# ─────────────────────────────────────────────────────────────────────────────
#
# The same split `measured_network` gets: what a probe *is* is decided here and
# asserted in a tenth of a second, and only running it needs a container. The
# shell script this replaced could be checked no other way than by installing a
# machine and reading its transcript.


def desired(**overrides) -> DesiredItem:
    fields = {
        'section': 'go_tools',
        'provider': 'go',
        'resource': 'packages',
        'stage': Stage.TOOLS,
        'name': 'task',
        'executable': 'task',
        'evidence_path': '',
        'precondition': Precondition.NONE,
        'entry': None,
        'reason': Reason('go_tools', 'named'),
    }
    return DesiredItem(**{**fields, **overrides})


def test_a_binary_is_looked_for_on_path() -> None:
    assert probe_of(desired()) == 'command -v task'


def test_a_declared_path_is_looked_for_on_disk() -> None:
    """`bashselfupdate` is a sourced library and puts nothing on PATH, so the
    checkout it lands in is the only evidence there is."""
    probe = probe_of(desired(executable='', evidence_path='~/.local/share/bashselfupdate'))

    assert probe.startswith('[ -e ')
    assert '"$HOME"/' in probe


def test_a_declared_path_beats_a_binary_of_the_same_name() -> None:
    """The same precedence `Provider.evidence` applies: an entry saying where it
    lands is more specific than a rule about how its neighbours are found."""
    assert probe_of(desired(evidence_path='/opt/task')).startswith('[ -e ')


def test_an_item_with_nothing_to_look_for_gets_no_probe() -> None:
    """A macOS default, a systemd unit, a group membership. Each is real and none
    is a file — and a probe that answered anyway would be a green tick for
    something nobody examined."""
    assert probe_of(desired(executable='', evidence_path='')) == ''


def test_a_home_relative_path_expands_rather_than_quoting_the_tilde() -> None:
    """`shlex.quote('~/x')` produces a literal directory named `~`, because the
    shell expands the tilde before quoting and not after. Every path-evidenced
    item then reads as missing on a machine carrying it."""
    assert shell_path('~/.local/bin/ya') == '"$HOME"/.local/bin/ya'
    assert shell_path('~/Application Support/x') == '"$HOME"/\'Application Support/x\''


def test_a_path_that_is_not_home_relative_is_quoted_whole() -> None:
    assert shell_path('/opt/a directory/tool') == "'/opt/a directory/tool'"


def test_the_sweep_asks_after_every_item_it_can_and_no_others() -> None:
    """One `docker exec` for the lot. Two hundred of them is half a minute per
    environment spent starting processes, before the first assertion runs."""
    items = [desired(name='task'), desired(name='sesh', executable='sesh'), desired(name='xcode', executable='', evidence_path='')]

    lines = probe_script(items).splitlines()

    assert len(lines) == 2
    assert all(line.startswith('printf ') for line in lines)
    assert ' go/task ' in lines[0] and ' go/sesh ' in lines[1]


def test_the_copies_sweep_asks_once_per_binary() -> None:
    """Two entries can name one binary — a section declaring `awscli` beside a
    system package of the same name — and asking twice buys nothing."""
    items = [
        desired(name='ripgrep', executable='rg'),
        desired(name='ripgrep-all', executable='rg'),
        desired(name='sesh', executable='sesh'),
    ]

    assert len(copies_script(items).splitlines()) == 2


def test_every_environment_resolves_the_items_it_will_be_asked_about() -> None:
    """The manifest is the checklist, so a tool added or removed changes what is
    verified with nothing here to update. An environment resolving to nothing
    would collect no nodes and report a green run having asked no questions."""
    for environment in ENVIRONMENTS:
        items = declared_items(environment)
        assert items, environment.name
        assert [item.address for item in items] == sorted(item.address for item in items)


def test_every_item_node_is_paired_with_the_container_that_declares_it() -> None:
    """The cross product is generated and then cut back, so this is what says the
    cut happened. Left unfiltered it would ask an Arch machine for wsl's
    `win32yank` — a red line about the pairing wearing the costume of a missing
    tool, on the tier where finding that out costs half an hour.

    Collection in a subprocess for the same reason as the `--environment` test
    above: the deselection is pytest's, not the rig's.
    """
    from dotfiles import paths

    collected = subprocess.run(
        ['uv', 'run', 'pytest', 'tests/e2e/test_verification.py', '--docker', '--collect-only', '-q', '-o', 'addopts='],
        cwd=paths.REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    nodes = [line for line in collected.stdout.splitlines() if 'test_the_machine_carries_what_it_declares[' in line]
    assert nodes, collected.stdout[-2000:]

    declared = {environment.name: {item.address for item in declared_items(environment)} for environment in ENVIRONMENTS}
    for node in nodes:
        # `[<container>-<declared>-<address>]`: pytest composes the id from both
        # parametrizations, and the two naming the same environment is the whole
        # claim. No environment name carries a hyphen; every address may.
        container, _, rest = node.partition('[')[2].rstrip(']').partition('-')
        declaring, _, address = rest.partition('-')

        assert container == declaring, f'{node} asks a {container} machine about a {declaring} item'
        assert address in declared[declaring], f'{declaring} does not declare {address}'

    assert len(nodes) == sum(len(addresses) for addresses in declared.values())


def test_the_replayed_probe_carries_the_fallback_the_measurement_used() -> None:
    """A replay that drops the fallback blames the container for a refusal that
    happens on any network.

    `network.measure` tries HEAD and then a ranged GET, because S3 and some CDNs
    reject HEAD. This replayed only the first, so `terraform-ls` — recorded
    reachable through the fallback — came back unreachable in every container and
    read as a firewall that was stricter than work's.

    `releases.hashicorp.com` answers HEAD with 405 for a named agent and 200 for
    curl's default, which is why the agent is part of the recorded request too.
    """
    from dotfiles import network

    downloads = [probe for probe in harness.measured_probes() if not probe.cloned]
    assert downloads, 'no download probe recorded, so this would pass vacuously'

    for probe in downloads:
        replayed = probe.command()
        assert '--head' in replayed, f'{probe.name} no longer replays the method the measurement tried first'
        assert '-r 0-0' in replayed, f'{probe.name} drops the fallback that recorded it reachable'

    recorded = network.Probe(section='github_releases', name='x', target='https://example.invalid/')
    assert '-r' in (recorded.fallback_command() or ()), 'the measurement no longer has a fallback to mirror'


def test_a_clone_probe_has_no_fallback_to_replay() -> None:
    """`git ls-remote` is the only way to ask the question, so there is no second
    method — which is why `network.Probe.fallback_command` answers None for one."""
    clones = [probe for probe in harness.measured_probes() if probe.cloned]
    assert clones

    for probe in clones:
        assert 'ls-remote' in probe.command()
        assert '||' not in probe.command()
