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
from enum import StrEnum
from urllib.parse import urlsplit

from dotfiles import catalog
from dotfiles import coordinates
from dotfiles import diagnose
from dotfiles import effects
from dotfiles import machine as machines
from dotfiles import plan as planning
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

REPORT_LANDING = ('-o', '/dev/null', '-w', '%{url_effective}')
"""Make curl say where the chain ended, since `-L` means it often is not the target.

Three sources redirect to a host the requested URL does not name — the uv and
claude-code installers, and every GitHub release asset. The verdict was always
right, because `-L` follows through and the final fetch is what succeeds or fails;
the *host* was not, and that is what the firewalled containers blackhole.

Part of the request rather than added at the call site so `as_shell` keeps
rendering what actually ran. It changes only where output goes: same method, same
URL, same agent, which is the property a replay depends on. curl writes this even
when `-f` makes it exit non-zero, so a refused probe still names the host that
refused it."""

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
        return ('curl', '-fsSL', '--head', '-A', PROBE_AGENT, '--connect-timeout', str(TIMEOUT_SECONDS), *REPORT_LANDING, self.target)

    def fallback_command(self) -> tuple[str, ...] | None:
        if self.cloned:
            return None
        return ('curl', '-fsSL', '-A', PROBE_AGENT, '--connect-timeout', str(TIMEOUT_SECONDS), '-r', '0-0', *REPORT_LANDING, self.target)

    def as_shell(self) -> str:
        """The probe as a copyable one-liner, for a container to replay.

        Replaying the recorded request rather than synthesizing `https://<host>/`
        is the whole point: the method, the URL and the agent have each changed a
        verdict at least once, and a probe that differs from the recorded one is
        measuring a different question and calling the answer a firewall.
        """
        rendered = shlex.join(self.command())
        return f'GIT_TERMINAL_PROMPT=0 {rendered}' if self.cloned else rendered


class Refusal(StrEnum):
    """What kind of no a probe got, where that is known.

    Three kinds and not a sentence, because the caller acts on the kind: an
    `INTERCEPTED` host is reachable and needs a CA, a `BLOCKED` one needs an offline
    bundle, and `REPORTED` carries whatever the transport said without claiming to
    have classified it.
    """

    NONE = 'none'
    """No reason established, which is the common answer for a reachable host and
    for a refusal already fully described by the NO beside it."""

    INTERCEPTED = 'intercepted'
    BLOCKED = 'blocked'
    REPORTED = 'reported'


@dc.dataclass(frozen=True, slots=True)
class ProbeResult:
    probe: Probe
    reachable: bool

    landed: str = ''
    """The host the request ended on, when that is not the one it started on.

    Empty is the common answer and means "the target's own host", so a reader and
    the harness both see a redirect only where there was one. Defaulted because it
    is a later addition and the constructions that predate it are still correct."""

    refusal: Refusal = Refusal.NONE
    """Why this probe said no, as a value rather than a sentence.

    **A blocked host and an untrusted certificate were one answer, and they need
    opposite responses.** A firewall that drops the connection is what an offline
    bundle exists for; a TLS-intercepting proxy is reachable and needs its CA
    installed, and a bundle built for it is hours spent on a two-minute fix. Every
    non-zero curl status collapsed to `NO` in the same column, so an intercepted
    machine read as a blackholed one, with curl's exit 60 reported as a block.

    A member and not the prose it renders as. The closing hint in `network check`
    fires on `INTERCEPTED`, and it tested a substring of an English sentence written
    out in two modules — so rewording either one silently stopped the hint, with
    nothing asserting it.

    Deliberately not a column in the committed results file. `tests/e2e/harness.py`
    parses that file by splitting on its pipes to decide which hosts to blackhole, so
    its grammar is an interface; this rides on the terminal report and the debug
    stream instead."""

    detail: str = ''
    """What the transport actually said, where a member cannot carry it.

    A clone's refusal is git's own last line, which is unbounded prose and belongs
    beside the member rather than inside it."""


@dc.dataclass(frozen=True, slots=True)
class Derived:
    """What the declaration says to probe, and what it could not answer for.

    `unprobed` is carried as data rather than warned about in passing, and ends up
    in the results file. The question a reader has is whether a row is absent
    because nothing needed probing or because the probe could not be built, and a
    warning on stderr answers that for whoever was
    watching the run and for nobody afterwards.
    """

    probes: tuple[Probe, ...]
    unprobed: tuple[str, ...]


@dc.dataclass(frozen=True, slots=True)
class Measurement:
    verdicts: tuple[ProbeResult, ...]
    unprobed: tuple[str, ...]


def derive(machine: machines.Machine) -> Derived:
    """Every source this machine's plan would reach, in the order they are tried.

    Derived from `resolve.resolve` rather than from `packages.yml` directly, so a
    row this machine does not subscribe to is not probed and a NO always names
    something this machine would really have failed to get.

    Pure: no request is made here, which is what lets the derivation be tested
    without a network and what keeps `unprobed` a statement about the declaration
    rather than about today's connectivity.
    """
    plan = resolve.resolve(catalog.load(), machine)
    installers, unprobed = _custom_installer_probes(plan, coordinates.target_for(machine.coordinates))
    return Derived(
        probes=(
            *_release_probes(plan),
            *_clone_probes(plan),
            *installers,
            *_runtime_probes(),
            *_registry_probes(plan),
        ),
        unprobed=unprobed,
    )


def _entries[E: catalog.Entry](plan: planning.Plan, kind: type[E]) -> tuple[E, ...]:
    """Every declaration row of one type the plan resolved, deduplicated by name.

    A tool can enter the plan more than once — a runtime is pulled in by each tool
    that needs it — and probing one URL twice reports a host as two rows without
    measuring anything the first did not.

    Generic in `kind`, so a caller asking for `GithubRelease` rows gets rows it can
    read `repo` off. Returning the base would hand every caller an `Entry` and put
    the narrowing this already did back on them.
    """
    seen: dict[str, E] = {}
    for item in plan.items:
        if isinstance(item.entry, kind) and item.entry.name not in seen:
            seen[item.entry.name] = item.entry
    return tuple(seen.values())


def _release_probes(plan: planning.Plan) -> tuple[Probe, ...]:
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


def _clone_probes(plan: planning.Plan) -> tuple[Probe, ...]:
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


def _custom_installer_probes(plan: planning.Plan, target: Target) -> tuple[tuple[Probe, ...], tuple[str, ...]]:
    """Whatever each installer says it reaches, asked of the installer.

    `providers.custom.sources` is the answer rather than a `source_type` word here,
    for the reason asset naming is code: a word could express "a github_clone needs
    github.com" and nothing else — not that `theme` also fetches its script from
    raw.githubusercontent.com, not that `bats` needs three repos, not that `awscli`
    names a different zip per architecture.

    An installer with no sources on this platform installs the tool from somewhere
    else — awscli from Homebrew, mount-s3 not at all — and is left out rather than
    probed, because a probe of nothing is a block that does not exist. It is named
    in the second return value, because "nothing to probe" and "probed and fine"
    are different answers and the row's absence cannot tell them apart.
    """
    found, unprobed = [], []
    for entry in _entries(plan, catalog.CustomInstaller):
        sources = custom.sources(entry, target)
        if not sources:
            unprobed.append(f'{entry.name}: installs from nothing on this platform')
            continue
        for source in sources:
            found.append(Probe('custom_installer', entry.name, source.url, source.reach))
    return tuple(found), tuple(unprobed)


def _runtime_probes() -> tuple[Probe, ...]:
    """Where the language runtimes come from, imported rather than retyped.

    The installer's own constant is the one that decides where a real install
    goes, so a probe holding its own copy can measure a URL nothing uses.
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


def _registry_probes(plan: planning.Plan) -> tuple[Probe, ...]:
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


def measure(probe: Probe) -> ProbeResult:
    """Whether this source answered, and which host answered, through `effects`.

    The range GET runs only when HEAD fails, so a host that accepts HEAD costs one
    request rather than two — which matters against `api.github.com`, where the
    probe run shares the machine's hourly budget with everything else.

    The landing is taken from whichever attempt ran last, because that is the one
    the verdict describes. A HEAD refused by a CDN and a range GET refused by the
    same CDN land identically; a HEAD refused at the entry host and a range GET
    that got further do not, and the second is the truer answer.
    """
    environment = {'GIT_TERMINAL_PROMPT': '0'} if probe.cloned else None
    answered = effects.run(probe.command(), env=environment, output=effects.Output.QUIET)
    if answered.ok:
        return ProbeResult(probe, True, _landing(probe, answered.stdout))

    fallback = probe.fallback_command()
    if fallback is None:
        return ProbeResult(probe, False, _landing(probe, answered.stdout), *_refusal(probe, answered))
    retried = effects.run(fallback, output=effects.Output.QUIET)
    if retried.ok:
        return ProbeResult(probe, True, _landing(probe, retried.stdout))
    return ProbeResult(probe, False, _landing(probe, retried.stdout or answered.stdout), *_refusal(probe, retried))


def _refusal(probe: Probe, answered: effects.Completed) -> tuple[Refusal, str]:
    """Why one probe said no, from what the command exited with and printed.

    The transcript's own words win over the exit status, because git has no code for
    this and curl's is one number for a condition the text states exactly. A clone is
    the case that forces it: `git ls-remote` exits 128 for a certificate it will not
    verify and for a repository that does not exist, and only the message separates
    them.

    `NONE` for a plain refusal, which is the common answer and already fully described
    by the NO beside it. A reason invented for every failure is a reason nobody reads.
    """
    if any(marker in answered.transcript for marker in diagnose.INTERCEPTED):
        return Refusal.INTERCEPTED, diagnose.INTERCEPTED_CAUSE
    if probe.cloned:
        said = answered.transcript.strip().splitlines()
        return (Refusal.REPORTED, said[-1].strip()) if said else (Refusal.NONE, '')
    if cause := diagnose.curl_cause(answered.returncode):
        return Refusal.BLOCKED, cause
    return Refusal.NONE, ''


def _landing(probe: Probe, written: str) -> str:
    """The host curl ended on, where that is not the host it started on.

    The host and not the effective URL, though curl reports the URL: the host is
    all any reader of this wants, and a release asset's effective URL is 900-odd
    characters of signed CDN query string carrying a SAS signature and a JWT. That
    is unreadable in a file whose reason for being committed is that it gets read
    and diffed, and it is a short-lived credential nobody needs in git.

    A clone has no chain to report and `git ls-remote` writes refs on the same
    stream, so it is answered before anything is parsed rather than after — a ref
    line happens not to look like a URL, which is luck and not a check.
    """
    if probe.cloned:
        return ''
    landed = written.strip()
    if '//' not in landed:
        return ''
    host = urlsplit(landed).netloc
    return host if host != probe.host else ''


def asset_probe(machine: machines.Machine) -> tuple[Probe | None, str]:
    """A real release asset, discovered from the API rather than synthesized.

    Discovered and not derived: the asset host is a redirect target, and which
    host it is has changed upstream. Asking here rather than in `derive` keeps
    that one pure, and puts the live lookup in the path that was always going to
    make requests.

    Never a NO when it cannot be built. A blocked API already has its own row, so
    inferring a second failure from it reports one block as two — but the reason
    is returned rather than dropped, because a reader otherwise cannot tell an
    unprobed asset row from a machine that has no releases to probe.
    """
    releases = _entries(resolve.resolve(catalog.load(), machine), catalog.GithubRelease)
    if not releases:
        return None, ''

    repo = releases[0].repo
    latest = f'https://api.github.com/repos/{repo}/releases/latest'
    answered = effects.run(
        ('curl', '-fsSL', '-A', PROBE_AGENT, '--connect-timeout', str(TIMEOUT_SECONDS), latest),
        output=effects.Output.QUIET,
    )
    if not answered.ok:
        return None, f'release asset delivery: {repo} did not answer, so no asset URL could be resolved'
    try:
        assets = json.loads(answered.stdout).get('assets') or []
    except json.JSONDecodeError:
        return None, f'release asset delivery: {repo} answered with something that is not JSON'
    if not assets:
        url = None
    else:
        url = assets[0].get('browser_download_url')
    if not url:
        return None, f'release asset delivery: the newest {repo} release publishes no asset'
    return Probe('github_asset', 'release asset download', url), ''


RESULTS_HEADER = 'Dotfiles Connectivity Test Results'
RULE = '-' * 78

LANDED_COLUMN = 'LANDED'
"""The header word that says a file records where each probe ended.

The header and not the rows, because the column is written only where a row
redirected: a file where nothing redirected and one written before the column
existed have identically shaped rows and mean opposite things. Named here because
the code that writes the column is what should say how to recognise it."""


def _row(verdict: ProbeResult) -> str:
    """One measured row, ending at REACH unless there is a landing to add.

    The trailing separator is omitted rather than emitted empty, so a row carries a
    sixth field only when it has one to carry. `rstrip` cannot do it: it takes the
    padding off and leaves the pipe, which splits to an empty sixth field and is the
    thing being avoided.
    """
    head = f'{"YES" if verdict.reachable else "NO":<4}| {verdict.probe.section:<18}| {verdict.probe.name:<24}| {verdict.probe.target:<64}| '
    if not verdict.landed:
        return f'{head}{verdict.probe.reach}'
    return f'{head}{verdict.probe.reach:<9}| {verdict.landed}'


def render(machine: machines.Machine, measurement: Measurement, *, when: str, system: str) -> str:
    """The measurement as the committed results file.

    The column layout is load-bearing rather than decorative: `tests/e2e/harness.py`
    parses this file to decide which hosts the firewalled containers blackhole, and
    it splits on the pipes. The environment facts are arguments rather than read
    here so the render is pure and one call can be diffed against another.

    **The header names the manifest and the kernel, and neither the hostname nor
    the account.** This file is committed, and the one machine whose measurement it
    carries is behind an employer's firewall — where `socket.gethostname()` is an
    asset tag and `getpass.getuser()` is a work account. Neither is needed to read
    a row: what a reader has to know to interpret a block is which manifest was
    resolved and which OS asked, and the manifest name already says which box.

    REACH is a fifth column because the four before it cannot carry it. Whoever
    replays a row has to know whether it was a clone or a download, and a replay
    that differs from the recorded request measures a different question — the trap
    `Probe.as_shell` documents. The only other source is the section name, which
    cannot answer it: a custom installer's section is `custom_installer` whether it
    clones or downloads, and three of them clone.

    LANDED is sixth, holds a host rather than a URL, and is written only where a row
    redirected off its own host — three rows in forty-odd. Always writing it would
    repeat TARGET on every other line, in a file whose reason for being committed is
    that a human reads it and diffs it. The absent value is why the *header* is what
    says whether a file carries the column at all: "nothing redirected" and "written
    before the column existed" are different facts, and the rows cannot tell them
    apart.
    """
    rows = '\n'.join(_row(verdict) for verdict in measurement.verdicts)
    reachable = sum(1 for verdict in measurement.verdicts if verdict.reachable)
    unprobed = (
        ['', 'Unprobed - nothing to ask, rather than asked and blocked:', *(f'  {reason}' for reason in measurement.unprobed)]
        if measurement.unprobed
        else []
    )
    return '\n'.join(
        (
            '=' * 38,
            RESULTS_HEADER,
            '=' * 38,
            f'Date: {when}',
            f'Manifest: {machine.name}',
            f'OS: {system}',
            '',
            f'Summary: {reachable} reachable, {len(measurement.verdicts) - reachable} blocked',
            '',
            f'{"":<4}| {"SECTION":<18}| {"NAME":<24}| {"TARGET":<64}| {"REACH":<9}| {LANDED_COLUMN}',
            RULE,
            rows,
            RULE,
            *unprobed,
            '',
            'Legend: YES = reachable, NO = blocked or unreachable',
            '',
        )
    )


def measure_all(machine: machines.Machine) -> Measurement:
    """Every derived probe, plus the one asset row that has to be discovered."""
    derived = derive(machine)
    found = list(derived.probes)
    unprobed = list(derived.unprobed)

    asset, why = asset_probe(machine)
    if asset is not None:
        found.append(asset)
    elif why:
        unprobed.append(why)

    return Measurement(tuple(measure(probe) for probe in found), tuple(unprobed))
