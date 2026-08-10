"""The connectivity measurement: what gets probed, and how.

Everything here is the *derivation*, which is pure — no probe is run. That is the
half worth pinning, because the failure this replaced was never a bad request; it
was a hand-maintained URL list that had drifted from the declaration in both
directions at once.
"""

from __future__ import annotations

from dotfiles import catalog
from dotfiles import machine as machines
from dotfiles import network
from dotfiles import resolve
from dotfiles.providers.custom import Reach

WSL = 'wsl-work-workstation'
ARCHLINUX = 'archlinux-personal-workstation'


def probes_for(name: str) -> tuple[network.Probe, ...]:
    return network.probes(machines.load(name))


def test_two_machines_are_probed_differently() -> None:
    """The point of deriving: a manifest that installs more is probed for more.

    Equal counts would mean the manifest was not consulted and every machine was
    being measured against one list, which is the defect this replaced.
    """
    assert len(probes_for(ARCHLINUX)) > len(probes_for(WSL))


def test_every_probed_tool_is_one_the_machine_declares() -> None:
    """A NO has to name something this machine would really have failed to get.

    The inverse of the drift above: probing a tool the manifest does not subscribe
    to reports a block that costs this machine nothing, and a result nobody can act
    on is one nobody reads.
    """
    plan = resolve.resolve(catalog.load(), machines.load(WSL))
    declared = {item.entry.name for item in plan.items if item.entry is not None}

    named = {probe.name for probe in probes_for(WSL) if probe.section in {'github_release', 'custom_installer'}}
    assert named <= declared


def test_a_registry_is_probed_once_however_many_sections_reach_it() -> None:
    """`uv_tools` and `git_uv_tools` both install from pypi.org.

    Two identical rows measure one thing and report it as two, which inflates the
    blocked count and makes the summary line wrong.
    """
    registries = [probe.target for probe in probes_for(ARCHLINUX) if probe.section == 'registry']
    assert len(registries) == len(set(registries))


def test_a_registry_nothing_installs_from_is_not_probed() -> None:
    """Gated on the plan actually resolving tools of that type.

    A machine with no cargo tools has nothing to lose to a blocked crates.io, and
    saying otherwise is what would send someone bundling nine tools for nothing.
    """
    bare = machines.load(WSL)
    plan = resolve.resolve(catalog.load(), bare)
    installs_go = bool([item for item in plan.items if isinstance(item.entry, catalog.GoTool)])
    probed_go = any(probe.name == 'proxy.golang.org' for probe in network.probes(bare))

    assert probed_go == installs_go


def test_a_clone_is_probed_as_a_clone() -> None:
    """`git ls-remote` against a repo, never a GET of its web page.

    A firewall that serves github.com over HTTPS while blocking the git transport
    would otherwise report every plugin and git-installed tool as reachable, and
    they are the ones that come down that way.
    """
    clones = [probe for probe in probes_for(WSL) if probe.reach is Reach.CLONE]

    assert clones, 'a machine installing shell plugins clones something'
    assert all(probe.command()[:2] == ('git', 'ls-remote') for probe in clones)
    assert all('GIT_TERMINAL_PROMPT=0' in probe.as_shell() for probe in clones)


def test_every_download_probe_sends_the_agent() -> None:
    """crates.io answers curl's default agent with 403.

    A run that omitted it recorded crates.io as a firewall block, which would have
    meant bundling all nine cargo tools for nothing. Both the HEAD and the range
    GET fallback have to carry it, or the fallback re-earns the same wrong answer.
    """
    downloads = [probe for probe in probes_for(ARCHLINUX) if probe.reach is Reach.DOWNLOAD]

    assert all(network.PROBE_AGENT in probe.command() for probe in downloads)
    assert all(network.PROBE_AGENT in (probe.fallback_command() or ()) for probe in downloads)


def test_the_head_comes_first_and_the_range_get_is_the_fallback() -> None:
    """HEAD downloads nothing; the range GET exists for hosts that reject it,
    which S3 and some CDNs do. Reversing them would pull a byte from every host
    on a run that is meant to cost nothing."""
    probe = next(probe for probe in probes_for(WSL) if probe.reach is Reach.DOWNLOAD)

    assert '--head' in probe.command()
    assert '--head' not in (probe.fallback_command() or ())
    assert '-r' in (probe.fallback_command() or ())


def test_the_runtime_urls_are_the_installers_own() -> None:
    """Imported rather than retyped, so there is one place a runtime's home is
    written and the probe cannot measure a URL no install would use."""
    from dotfiles.providers import toolchain

    targets = {probe.target for probe in probes_for(WSL) if probe.section == 'language_manager'}

    assert targets == {toolchain.UV_INSTALL_URL, toolchain.GO_VERSION_URL, toolchain.RUSTUP_URL}


def test_the_results_file_is_the_shape_the_harness_parses() -> None:
    """`tests/e2e/harness.py` splits this file on pipes to decide which hosts the
    firewalled containers blackhole, so the column layout is an interface and not
    a presentation choice."""
    machine = machines.load(WSL)
    verdicts = (
        network.Verdict(network.Probe('registry', 'crates.io', 'https://crates.io/api/v1/crates/bat'), True),
        network.Verdict(network.Probe('git_clone', 'forgit', 'https://github.com/wfxr/forgit.git', Reach.CLONE), False),
    )

    rows = [
        [cell.strip() for cell in line.split('|')]
        for line in network.render(machine, verdicts, host='h', when='w', user='u', system='s').splitlines()
        if line.split('|')[0].strip() in {'YES', 'NO'}
    ]

    assert rows == [
        ['YES', 'registry', 'crates.io', 'https://crates.io/api/v1/crates/bat'],
        ['NO', 'git_clone', 'forgit', 'https://github.com/wfxr/forgit.git'],
    ]


def test_the_summary_counts_what_the_rows_say() -> None:
    """A summary line derived from a second walk is a second chance to disagree
    with the table under it."""
    verdicts = tuple(network.Verdict(network.Probe('registry', str(index), f'https://h/{index}'), index % 2 == 0) for index in range(5))

    written = network.render(machines.load(WSL), verdicts, host='h', when='w', user='u', system='s')

    assert 'Summary: 3 reachable, 2 blocked' in written
