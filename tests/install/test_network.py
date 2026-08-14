"""The connectivity measurement: what gets probed, and how.

Everything here is the *derivation*, which is pure — no probe is run. That is the
half worth pinning, because the failure this replaced was never a bad request; it
was a hand-maintained URL list that had drifted from the declaration in both
directions at once.
"""

from __future__ import annotations

import pytest

from dotfiles import catalog
from dotfiles import machine as machines
from dotfiles import network
from dotfiles import resolve
from dotfiles.providers.custom import Reach

WSL = 'wsl-work-workstation'
ARCHLINUX = 'archlinux-personal-workstation'


LXC = 'linux-lxc-server'

REACH_COLUMN = 4
"""Indexed rather than taken from the end: LANDED follows it, and only where a row
redirected — so `[-1]` reads REACH on most rows and something else on the three
that matter."""


def probes_for(name: str) -> tuple[network.Probe, ...]:
    return network.derive(machines.load(name)).probes


def rendered_rows(measurement: network.Measurement) -> list[list[str]]:
    written = network.render(machines.load(WSL), measurement, host='h', when='w', user='u', system='s')
    return [[cell.strip() for cell in line.split('|')] for line in written.splitlines() if line.split('|')[0].strip() in {'YES', 'NO'}]


def test_two_machines_are_probed_differently() -> None:
    """The point of deriving: a manifest that installs more is probed for more.

    Equal counts would mean the manifest was not consulted and every machine was
    being measured against one list.
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
    """Both directions, against two manifests that genuinely differ.

    `linux-lxc-server` declares no npm globals and `wsl-work-workstation` declares
    eleven, so the branch this is named for actually executes. Asserting
    `probed == declared` against one manifest that declares some passes with both
    sides True and never runs the not-probed case at all.

    It matters because a machine with nothing to lose to a blocked registry should
    not be told it is blocked — that is what would send someone bundling tools for
    nothing.
    """
    assert any(probe.name == 'registry.npmjs.org' for probe in probes_for(WSL))
    assert not any(probe.name == 'registry.npmjs.org' for probe in probes_for(LXC))


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
    measurement = network.Measurement(
        (
            network.ProbeResult(network.Probe('registry', 'crates.io', 'https://crates.io/api/v1/crates/bat'), True),
            network.ProbeResult(network.Probe('git_clone', 'forgit', 'https://github.com/wfxr/forgit.git', Reach.CLONE), False),
        ),
        (),
    )

    rows = [
        [cell.strip() for cell in line.split('|')]
        for line in network.render(machine, measurement, host='h', when='w', user='u', system='s').splitlines()
        if line.split('|')[0].strip() in {'YES', 'NO'}
    ]

    assert rows == [
        ['YES', 'registry', 'crates.io', 'https://crates.io/api/v1/crates/bat', 'download'],
        ['NO', 'git_clone', 'forgit', 'https://github.com/wfxr/forgit.git', 'clone'],
    ]


def test_the_recorded_reach_survives_the_file() -> None:
    """The column the harness replays from, and the reason it exists.

    A custom installer's section is `custom_installer` whether it clones or
    downloads, so a reader deriving reach from the section name gets every one of
    those wrong — and replays a `.git` URL as `curl --head`, which GitHub answers,
    so it passes for the wrong reason while a blocked git transport reads as
    reachable.
    """
    cloned = network.Probe('custom_installer', 'theme', 'https://github.com/datapointchris/theme.git', Reach.CLONE)
    measurement = network.Measurement((network.ProbeResult(cloned, True),), ())

    written = network.render(machines.load(WSL), measurement, host='h', when='w', user='u', system='s')
    row = next(line for line in written.splitlines() if line.startswith('YES'))

    assert row.split('|')[REACH_COLUMN].strip() == 'clone'
    assert not row.split('|')[1].strip().endswith('clone'), 'the section cannot answer it, which is the point'


def measured_through(monkeypatch: pytest.MonkeyPatch, probe: network.Probe, *, ok: bool, written: str) -> network.ProbeResult:
    """`measure` with curl replaced by what a real run would have printed.

    Both attempts answer the same way, because what is under test is the reading of
    the output rather than which attempt produced it.
    """
    completed = network.effects.Completed(command=(), returncode=0 if ok else 1, transcript=written, stdout=written)
    monkeypatch.setattr(network.effects, 'run', lambda *_, **__: completed)
    return network.measure(probe)


def test_a_probe_that_moved_hosts_records_where_it_ended(monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole point: `claude.ai` answers a 302 and `downloads.claude.ai` serves
    the bytes, so a firewall built from the requested host blocks a host the work
    box reaches and leaves the one that refuses resolvable."""
    probe = network.Probe('custom_installer', 'claude-code', 'https://claude.ai/install.sh')

    verdict = measured_through(monkeypatch, probe, ok=True, written='https://downloads.claude.ai/claude-code-releases/bootstrap.sh')

    assert verdict.reachable
    assert verdict.landed == 'downloads.claude.ai'


def test_a_probe_that_stayed_put_records_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty is the common answer, and writing it anyway would repeat TARGET on
    forty-odd of the file's rows to say nothing."""
    probe = network.Probe('registry', 'crates.io', 'https://crates.io/api/v1/crates/bat')

    verdict = measured_through(monkeypatch, probe, ok=True, written='https://crates.io/api/v1/crates/bat')

    assert verdict.landed == ''


def test_a_refused_probe_still_names_the_host_that_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """curl writes `-w` output whatever the exit status, and the failing case is the
    one the firewall is built from — a NO whose landing is unknown is the bug."""
    probe = network.Probe('github_asset', 'release asset download', 'https://github.com/neovim/neovim/releases/download/v1/x')
    signed = 'https://release-assets.githubusercontent.com/neovim/x?sig=SECRET&jwt=SECRET'

    verdict = measured_through(monkeypatch, probe, ok=False, written=signed)

    assert not verdict.reachable
    assert verdict.landed == 'release-assets.githubusercontent.com', 'the host, so no signed query string reaches git'


def test_a_clone_never_claims_a_landing(monkeypatch: pytest.MonkeyPatch) -> None:
    """`git ls-remote` writes refs on the same stream curl writes the URL on, so the
    answer is the reach and not a guess at whether a line looks like a URL."""
    probe = network.Probe('git_clone', 'forgit', 'https://github.com/wfxr/forgit.git', Reach.CLONE)

    verdict = measured_through(monkeypatch, probe, ok=True, written='deadbeef\tHEAD')

    assert verdict.landed == ''


def test_a_landing_reaches_the_results_file_and_an_absent_one_adds_no_column() -> None:
    """The harness splits on pipes, so where the value sits is an interface.

    The absent case is why `records_landings` reads the header: these two rows are
    indistinguishable from a file written before the column existed.
    """
    moved = network.ProbeResult(
        network.Probe('language_manager', 'uv installer', 'https://astral.sh/uv/install.sh'),
        True,
        'releases.astral.sh',
    )
    stayed = network.ProbeResult(network.Probe('registry', 'crates.io', 'https://crates.io/api/v1/crates/bat'), True)

    rows = rendered_rows(network.Measurement((moved, stayed), ()))

    assert rows[0][5] == 'releases.astral.sh'
    assert len(rows[1]) == 5, 'a row that did not redirect ends at REACH'
    assert rows[1][REACH_COLUMN] == 'download'


def test_an_installer_with_nothing_to_probe_is_named_rather_than_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """ "Nothing to probe" and "probed and fine" are different answers, and the
    row's absence cannot tell them apart.

    Driven through a stubbed `sources` rather than through whichever declared
    installer happens to reach nothing today. awscli on a Mac was that example
    until it stopped being planned there at all, which left this asserting a
    coincidence of the declaration rather than the behaviour.
    """
    monkeypatch.setattr(network.custom, 'sources', lambda entry, target: ())

    derived = network.derive(machines.load('macos-personal-workstation'))

    assert derived.unprobed
    assert all('installs from nothing' in reason for reason in derived.unprobed)
    assert not any(probe.section == 'custom_installer' for probe in derived.probes)


def test_the_summary_counts_what_the_rows_say() -> None:
    """A summary line derived from a second walk is a second chance to disagree
    with the table under it."""
    verdicts = tuple(network.ProbeResult(network.Probe('registry', str(index), f'https://h/{index}'), index % 2 == 0) for index in range(5))

    written = network.render(machines.load(WSL), network.Measurement(verdicts, ()), host='h', when='w', user='u', system='s')

    assert 'Summary: 3 reachable, 2 blocked' in written
