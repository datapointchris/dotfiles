"""Whether this network can reach the sources a machine installs from.

Every probe is derived from the resolved plan, never typed here. A hand-maintained
URL list is what made the January 2026 results wrong in both directions: pinned
versions (neovim v0.10.0, lazygit v0.44.1) 404'd and were recorded as firewall
blocks, while bashselfupdate was on the manifest and never probed at all. A URL
written into a test is true only on the day it is written.

What a NO means depends on the section, which is why the section is on every row:
a blocked registry kills a whole install method, a blocked single repo kills one
tool. `create_bundle` reads the result to decide what an offline bundle carries.

This is a measurement, not a reconciliation — nothing here writes to the machine,
and there is no desired state to converge on. It answers the question that decides
whether a bundle is needed at all, which is why it sits beside the bundler rather
than among the resources.
"""

from __future__ import annotations

import dataclasses as dc
import json
import shlex
from urllib.parse import urlsplit

from dotfiles import catalog
from dotfiles import coordinates
from dotfiles import effects
from dotfiles import machine as machines
from dotfiles import resolve
from dotfiles.coordinates import Target
from dotfiles.providers import custom
from dotfiles.providers import toolchain
from dotfiles.providers.custom import Reach

PROBE_AGENT = 'dotfiles-connectivity-test (+https://github.com/datapointchris/dotfiles)'
"""The agent every probe sends, and not cosmetic.

crates.io answers curl's default agent with 403. A run that omitted this recorded
crates.io as a firewall block, which would have meant bundling all nine cargo
tools for nothing.
"""

TIMEOUT_SECONDS = 10

DOTFILES_REPO = 'https://github.com/datapointchris/dotfiles.git'
"""Probed as its own row because the install starts by cloning it.

Not derived: no manifest declares the repo it was itself read from, and a machine
that cannot clone this has no install to plan.
"""


@dc.dataclass(frozen=True, slots=True)
class Probe:
    """One thing to try, and what a failure would cost."""

    section: str
    name: str
    target: str
    reach: Reach = Reach.DOWNLOAD

    @property
    def host(self) -> str:
        return urlsplit(self.target if '//' in self.target else f'https://{self.target}').netloc

    @property
    def cloned(self) -> bool:
        return self.reach is Reach.CLONE

    def command(self) -> tuple[str, ...]:
        """The request to make, as argv.

        A HEAD downloads nothing, and the range GET is the fallback for hosts that
        reject HEAD, which S3 and some CDNs do. `measure` runs the second only when
        the first fails, so this returns the one that is tried first and
        `fallback_command` returns the other — two commands rather than a shell
        `||`, because `effects.run` takes argv and the point of going through it is
        that every request lands in the event stream individually.
        """
        if self.cloned:
            return ('git', 'ls-remote', '--quiet', self.target, 'HEAD')
        return ('curl', '-fsSL', '--head', '-A', PROBE_AGENT, '--connect-timeout', str(TIMEOUT_SECONDS), self.target)

    def fallback_command(self) -> tuple[str, ...] | None:
        if self.cloned:
            return None
        return ('curl', '-fsSL', '-A', PROBE_AGENT, '--connect-timeout', str(TIMEOUT_SECONDS), '-r', '0-0', self.target)

    def as_shell(self) -> str:
        """The probe as a copyable one-liner, for a container to replay.

        Replaying the recorded request rather than synthesizing `https://<host>/`
        is the whole point: the method, the URL and the agent have each changed a
        verdict at least once, and a probe that differs from the recorded one is
        measuring a different question and calling the answer a firewall.
        """
        rendered = shlex.join(self.command())
        return f'GIT_TERMINAL_PROMPT=0 {rendered}' if self.cloned else rendered


@dc.dataclass(frozen=True, slots=True)
class Verdict:
    probe: Probe
    reachable: bool


def probes(machine: machines.Machine) -> tuple[Probe, ...]:
    """Every source this machine's plan would reach, in the order they are tried.

    Derived from `resolve.resolve` rather than from `packages.yml` directly, so a
    row this machine does not subscribe to is not probed and a NO always names
    something this machine would really have failed to get.
    """
    plan = resolve.resolve(catalog.load(), machine)
    return (
        *_release_probes(plan),
        *_clone_probes(plan),
        *_custom_installer_probes(plan, coordinates.target_for(machine.coordinates)),
        *_runtime_probes(),
        *_registry_probes(plan),
    )


def _entries(plan: resolve.Plan, kind: type[catalog.Entry]) -> tuple[catalog.Entry, ...]:
    """Every declaration row of one type the plan resolved, deduplicated by name.

    A tool can enter the plan more than once — a runtime is pulled in by each tool
    that needs it — and probing one URL twice reports a host as two rows without
    measuring anything the first did not.
    """
    seen: dict[str, catalog.Entry] = {}
    for item in plan.items:
        if isinstance(item.entry, kind) and item.entry.name not in seen:
            seen[item.entry.name] = item.entry
    return tuple(seen.values())


def _release_probes(plan: resolve.Plan) -> tuple[Probe, ...]:
    """`/releases/latest` per tool, then the API and an asset off the first one.

    Release pages live on github.com but assets redirect to a separate host, so a
    reachable `/releases/latest` does not prove a release can be downloaded. The
    API row is the same distinction again: a firewall that allows the web UI and
    blocks `api.github.com` breaks every release install while looking fine.

    `/releases/latest` redirects to the newest tag, so there is no version to pin —
    which is what stopped the pinned-version 404s being read as blocks.
    """
    releases = _entries(plan, catalog.GithubRelease)
    found = tuple(Probe('github_release', entry.name, f'https://github.com/{entry.repo}/releases/latest') for entry in releases)
    if not releases:
        return found

    first = releases[0]
    return (
        *found,
        Probe('github_api', 'api.github.com', f'https://api.github.com/repos/{first.repo}/releases/latest'),
    )


def _clone_probes(plan: resolve.Plan) -> tuple[Probe, ...]:
    """This repo, then every tool and plugin installed by cloning one.

    Kept separate from the release rows even though both name github.com: at the
    work firewall the clone path is reachable while parts of the release path are
    not, so collapsing them to one host would report a machine as able to install
    tools it cannot.
    """
    cloned = (
        Probe('git_clone', 'dotfiles', DOTFILES_REPO, Reach.CLONE),
        *(Probe('git_clone', entry.name, entry.repo, Reach.CLONE) for entry in _entries(plan, catalog.GitUvTool)),
        *(Probe('git_clone', entry.name, entry.repo, Reach.CLONE) for entry in _entries(plan, catalog.ShellPlugin)),
    )
    return cloned


def _custom_installer_probes(plan: resolve.Plan, target: Target) -> tuple[Probe, ...]:
    """Whatever each installer says it reaches, asked of the installer.

    `providers.custom.sources` is the answer rather than a `source_type` word here,
    for the reason asset naming is code: a word could express "a github_clone needs
    github.com" and nothing else — not that `theme` also fetches its script from
    raw.githubusercontent.com, not that `bats` needs three repos, not that `awscli`
    names a different zip per architecture.

    An installer with no sources on this platform installs the tool from somewhere
    else — awscli from Homebrew, mount-s3 not at all — and is left out rather than
    probed, because a probe of nothing is a block that does not exist.
    """
    found = []
    for entry in _entries(plan, catalog.CustomInstaller):
        for source in custom.sources(entry, target):
            found.append(Probe('custom_installer', entry.name, source.url, source.reach))
    return tuple(found)


def _runtime_probes() -> tuple[Probe, ...]:
    """Where the language runtimes come from, imported rather than retyped.

    These three URLs were spelled out in the shell script beside the constants the
    installers actually use, which is two copies of one fact; the installer's copy
    is the one that decides where a real install goes.
    """
    return (
        Probe('language_manager', 'uv installer', toolchain.UV_INSTALL_URL),
        Probe('language_manager', 'go.dev', toolchain.GO_VERSION_URL),
        Probe('language_manager', 'rustup', toolchain.RUSTUP_URL),
    )


REGISTRY_PROBES: tuple[tuple[type[catalog.Entry], str, str], ...] = (
    (catalog.GoTool, 'proxy.golang.org', 'https://proxy.golang.org/github.com/go-task/task/v3/@latest'),
    (catalog.NpmGlobal, 'registry.npmjs.org', 'https://registry.npmjs.org/typescript/latest'),
    (catalog.UvTool, 'pypi.org', 'https://pypi.org/simple/ruff/'),
    (catalog.GitUvTool, 'pypi.org', 'https://pypi.org/simple/ruff/'),
    # cargo binstall resolves a crate's version through the crates.io API before
    # fetching the binary from GitHub, so a blocked crates.io fails the whole
    # section even though every byte it installs comes from a reachable host.
    (catalog.CargoPackage, 'crates.io', 'https://crates.io/api/v1/crates/bat'),
)
"""One registry probe per entry type that reaches it, and the URL that tests it.

A well-known package is fetched rather than the registry root, because several of
these answer a bare `GET /` with a redirect to a marketing page that a firewall
would happily serve.
"""


def _registry_probes(plan: resolve.Plan) -> tuple[Probe, ...]:
    """A registry is probed only where the plan actually resolved tools using it.

    `git_uv_tools` and `uv_tools` both reach pypi.org, so the same URL can be
    claimed twice; the first claim wins and the second is dropped, because two
    identical rows measure one thing and report it as two.
    """
    found: dict[str, Probe] = {}
    for kind, name, url in REGISTRY_PROBES:
        if _entries(plan, kind) and url not in found:
            found[url] = Probe('registry', name, url)
    return tuple(found.values())


def measure(probe: Probe) -> bool:
    """Whether this source answered, through `effects` like every other subprocess.

    The range GET runs only when HEAD fails, so a host that accepts HEAD costs one
    request rather than two — which matters against `api.github.com`, where the
    probe run shares the machine's hourly budget with everything else.
    """
    environment = {'GIT_TERMINAL_PROMPT': '0'} if probe.cloned else None
    if effects.run(probe.command(), env=environment, output=effects.Output.QUIET).ok:
        return True
    fallback = probe.fallback_command()
    return bool(fallback and effects.run(fallback, output=effects.Output.QUIET).ok)


def asset_probe(machine: machines.Machine) -> Probe | None:
    """A real release asset, discovered from the API rather than synthesized.

    Added here and not in `probes` because it is the one row whose target cannot be
    derived: the asset host is a redirect target, and which host it is has changed
    upstream. Asking keeps `probes` pure, which is what lets it be tested without a
    network, and puts the one live lookup in the function that was always going to
    make requests.

    None where the API could not be asked or the release publishes no asset — an
    unprobed row, exactly as the shell reported it, and never a NO. A blocked API
    already has its own row, so inferring a second failure from it would report one
    block as two.
    """
    releases = _entries(resolve.resolve(catalog.load(), machine), catalog.GithubRelease)
    if not releases:
        return None

    latest = f'https://api.github.com/repos/{releases[0].repo}/releases/latest'
    answered = effects.run(
        ('curl', '-fsSL', '-A', PROBE_AGENT, '--connect-timeout', str(TIMEOUT_SECONDS), latest),
        output=effects.Output.QUIET,
    )
    if not answered.ok:
        return None
    try:
        assets = json.loads(answered.stdout).get('assets') or []
    except json.JSONDecodeError:
        return None
    url = assets[0].get('browser_download_url') if assets else None
    return Probe('github_asset', 'release asset download', url) if url else None


RESULTS_HEADER = 'Dotfiles Connectivity Test Results'
RULE = '-' * 70


def render(machine: machines.Machine, verdicts: tuple[Verdict, ...], *, host: str, when: str, user: str, system: str) -> str:
    """The measurement as the committed results file.

    The column layout is load-bearing rather than decorative: `tests/e2e/harness.py`
    parses this file to decide which hosts the firewalled containers blackhole, and
    it splits on the pipes. The environment facts are arguments rather than read
    here so the render is pure and one call can be diffed against another.
    """
    rows = '\n'.join(
        f'{"YES" if verdict.reachable else "NO":<4}| {verdict.probe.section:<18}| {verdict.probe.name:<24}| {verdict.probe.target}'
        for verdict in verdicts
    )
    reachable = sum(1 for verdict in verdicts if verdict.reachable)
    return '\n'.join(
        (
            '=' * 38,
            RESULTS_HEADER,
            '=' * 38,
            f'Host: {host}',
            f'Date: {when}',
            f'User: {user}',
            f'Manifest: {machine.name}',
            f'OS: {system}',
            '',
            f'Summary: {reachable} reachable, {len(verdicts) - reachable} blocked',
            '',
            f'{"":<4}| {"SECTION":<18}| {"NAME":<24}| TARGET',
            RULE,
            rows,
            RULE,
            '',
            'Legend: YES = reachable, NO = blocked or unreachable',
            '',
        )
    )


def measure_all(machine: machines.Machine) -> tuple[Verdict, ...]:
    """Every derived probe, plus the one asset row that has to be discovered."""
    found = list(probes(machine))
    if (asset := asset_probe(machine)) is not None:
        found.append(asset)
    return tuple(Verdict(probe, measure(probe)) for probe in found)
