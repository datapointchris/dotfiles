"""The install phases: what a machine gets, and the order it has to get it in.

This was most of `install.sh`. Sixteen bash functions that each read a manifest
field, printed a header and ran one installer script — dispatch, which is what
this CLI already is. The bash that remains is the per-tool installers under
`install/`, which are genuine sequences of shell commands and which step 5
converts.

Two things fall out of the move rather than being added by it. Every gate used to
cost an interpreter spawn and a re-parse of a 258-entry `packages.yml`; here the
declaration is read once per run and the gates are dictionary lookups. And a run
whose installers failed used to exit 0 — `run_selected_phases` never looked at a
phase's status — so `install.sh && something` chained past a broken install.

Registry order is a dependency chain, not a listing: symlinks must land after the
tools that provide `task` and before tpm reads the tmux config it deploys, and the
node toolchain sits between the cargo phase that ships fnm and the npm globals
that install against what it pins.

This is the only registry. `install/phases.sh` held a second one for `update.sh`
and `tests/cli/test_phase_registry.py` asserted the two agreed, phase for phase.
Both scripts are gone, because reconcile has one verb and `apply` installs what
is missing and upgrades what is behind; the test survives, asserting this
registry's order alone.
"""

from __future__ import annotations

import datetime as dt
import functools
import os
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dotfiles import catalog
from dotfiles import coordinates
from dotfiles import deploy
from dotfiles import engine
from dotfiles import envfile
from dotfiles import evidence as ev
from dotfiles import failure_report
from dotfiles import machine as machines
from dotfiles import parse_packages
from dotfiles import paths
from dotfiles import privilege as privileges
from dotfiles import validate
from dotfiles import versions
from dotfiles.effects import Completed
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import err_console
from dotfiles.output import heading
from dotfiles.output import hint
from dotfiles.output import render_finding
from dotfiles.output import warn
from dotfiles.providers import custom
from dotfiles.providers import ghrelease
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

TOOL_PATH_DIRS = (
    '$HOME/.local/share/fnm/aliases/default/bin',
    '$HOME/.local/share/npm/bin',
    '$HOME/.local/bin',
    '$HOME/.cargo/bin',
    '$HOME/go/bin',
    '/usr/local/go/bin',
    '/usr/local/bin',
)
"""Where a phase finds what an earlier phase installed.

Nothing here reads `.zshenv`, so a tool is invisible to the phase that consumes it
unless it is named: the cargo provider needs `cargo` from rustup, the node
toolchain needs the fnm that arrives as a cargo package, and npm-globals needs the
Node that fnm links as its default alias. The converged providers put what they
install on this process's PATH as well — see `providers/toolchain.put_on_path` —
so this is what the phases that still shell out get, and the two agree.
Order mirrors `.zshenv` so a phase resolves the same binary an interactive shell
would. `install/tool-path.sh` said the same thing to `update.sh` and went with it;
this is the one list now.
"""


@dataclass(frozen=True)
class Run:
    """One `apply`, and everything its phases need to answer a question.

    `packages` and `manifest` are parsed once and passed down. That is the whole
    difference between this and the bash it replaces, which asked the same two
    files 28 separate times through 28 separate interpreters.
    """

    machine: str
    coords: coordinates.Coordinates
    packages: dict
    manifest: dict
    reinstall: bool = False
    offline: bool = False
    owner: str | None = None
    failures_log: Path = paths.REPO_ROOT / 'unused'

    @property
    def platform(self) -> str:
        """The overlay whose package scripts this machine runs.

        Derived from the coordinates rather than read from the manifest, because
        a manifest may declare `coordinates:` *instead of* `platform:` and then
        has no label to read — which is how Arch-on-WSL, the case the coordinate
        split exists for, resolved and checked and then could not be applied.
        """
        return _overlay(self.coords)

    @property
    def target(self) -> coordinates.Target:
        """What this machine's release assets are named for."""
        return coordinates.target_for(self.coords)

    @functools.cached_property
    def declaration(self) -> catalog.Catalog:
        """The typed declaration, beside the raw `packages` dict above.

        Two readings of one file, for the length of the conversion. The dict is
        what the remaining bash phases query through `parse_packages`; the catalog
        is what a converted phase needs, because an installer wants `repo`,
        `checksum` and `release_tag_prefix` as fields rather than as `.get` calls
        that cannot be wrong out loud. Both go when `Run` collapses into `Session`.
        """
        return catalog.load()

    @functools.cached_property
    def session(self) -> Session:
        """The run as the converted resources see it.

        Two objects describing one invocation while the conversion is in flight.
        This one holds what the remaining bash phases need; `Session` holds the
        typed declaration, and `Run` collapses into it when the last phase
        converts.

        Cached because the *Session* is what caches: its catalog, machine and plan
        are `cached_property` on the instance, so a plain property handed every
        reader a fresh one with cold caches. Five phases read this, and one
        `apply --owner` was parsing packages.yml seven times — while the module
        docstring above claimed the declaration is read once per run.

        `refresh` because this is the verb that spends the network, and it is what
        lets a currency question be asked at all. The App Store and Flathub have no
        offline catalogue, so `check` declines those reads and leaves their
        managers UNKNOWN — unrepairable, which would make `mas upgrade` and
        `flatpak update` the two things `update.sh` did that nothing replaced. An
        offline run keeps the refusal, because there is nothing to ask.
        """
        return Session(machine_name=self.machine, offline=self.offline, owner=self.owner, refresh=not self.offline)

    @classmethod
    def resolve(
        cls,
        machine: str | None = None,
        *,
        reinstall: bool = False,
        offline: bool = False,
        owner: str | None = None,
    ) -> Run:
        """Read the declaration for `machine`, or for whatever `~/.env` says this is.

        The coordinates come from the manifest and never from `uname`. A fresh
        machine has no `~/.env` to read them from, and detecting them instead is
        how a wsl manifest once deployed the linux shell overlay for a whole
        install.
        """
        name = machine or os.environ.get('MACHINE') or ''
        if not name:
            raise Declaration('no machine named, and MACHINE is not set in the environment')

        manifest_file = paths.MANIFESTS_DIR / f'{name}.yml'
        if not manifest_file.is_file():
            available = ', '.join(sorted(path.stem for path in paths.MANIFESTS_DIR.glob('*.yml')))
            raise Declaration(f'no manifest named {name!r}. Available: {available}')

        try:
            declared = machines.load(name)
        except machines.MachineError as refused:
            raise Declaration(str(refused)) from refused

        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
        return cls(
            machine=name,
            coords=declared.coordinates,
            packages=parse_packages.load_packages(),
            manifest=parse_packages.load_manifest(name),
            reinstall=reinstall,
            offline=offline,
            owner=owner,
            failures_log=Path(tempfile.gettempdir()) / f'dotfiles-install-failures-{stamp}.txt',
        )

    def wants(self, feature: str) -> bool:
        return self.manifest.get(feature) is True

    def declared(self, kind: str) -> list[str]:
        """What this machine declares of one kind, narrowed by `--owner`.

        Through the same filters `parse_packages` exposes to its own CLI, so a
        gate here and a `--type` query from an installer script cannot disagree
        about what the machine asked for.
        """
        data = parse_packages.filter_packages_by_owner(self.packages, self.owner) if self.owner else self.packages
        return list(_FILTERS[kind](data, self.manifest))

    def environment(self) -> dict[str, str]:
        """What every installer script reads out of its environment.

        `DOTFILES_PYTHON` is the interpreter those scripts use to read
        `packages.yml`; this process is one by construction. `PLATFORM` is
        exported because `detect_platform` honours it and otherwise greps
        `/proc/version`, which is a guess.
        """
        environment = {
            'DOTFILES_DIR': str(paths.REPO_ROOT),
            'DOTFILES_PYTHON': sys.executable,
            'TERM': os.environ.get('TERM') or 'xterm',
            'PATH': os.pathsep.join([os.path.expandvars(entry) for entry in TOOL_PATH_DIRS] + [os.environ['PATH']]),
            'MACHINE': self.machine,
            'PLATFORM': self.platform,
            'FAILURES_LOG': str(self.failures_log),
            'INSTALLER_ACTION': 'installation',
            'FORCE_INSTALL': 'true' if self.reinstall else 'false',
            'OFFLINE_MODE': 'true' if self.offline else 'false',
        }
        if self.owner:
            environment['PACKAGE_OWNER'] = self.owner
        # An installer's own stdout is a pipe, so colors.sh correctly but
        # unhelpfully turns colour off for every one of them. FORCE_COLOR is how
        # the wrapper tells them what it can see and they cannot.
        if sys.stderr.isatty():
            environment['FORCE_COLOR'] = '1'
        return environment


class Declaration(Exception):
    """The machine cannot be resolved, so nothing below can run."""


_FILTERS: dict[str, Callable[[dict, dict], list]] = {
    'github': parse_packages.filter_github_releases_by_manifest,
    'custom': parse_packages.filter_custom_installers_by_manifest,
}
"""What is left of the manifest gates, which is the two phases that still resolve
their own work rather than converging a selection of the plan."""


# ─────────────────────────────────────────────────────────────────────────────
# Running one installer
# ─────────────────────────────────────────────────────────────────────────────


def run_installer(context: Run, script: Path, tool: str, *args: str, env: dict[str, str] | None = None) -> bool:
    """Run one installer, streaming it live and keeping what a report needs.

    Streamed rather than buffered for the reason `install/run-installer.sh`
    recorded before this replaced it: buffering made a long install look hung,
    and capturing stderr alone silently dropped TPM's cause, which it prints on
    stdout. `effects.run` does both, which is why there is no second temp file
    here for the console output — the transcript is the return value.
    """
    if not script.is_file():
        warn(f'no installer script at {script} (machines check should have caught this)')
        return False

    records = Path(tempfile.mkstemp(prefix='dotfiles-records-', suffix='.jsonl')[1])
    try:
        completed = run(
            ['bash', str(script), *args],
            cwd=paths.REPO_ROOT,
            env={**context.environment(), 'FAILURE_RECORDS': str(records), **(env or {})},
            output=Output.STREAM,
        )
        if completed.ok:
            return True
        _record_failure(context, completed, records, script, tool)
        return False
    finally:
        records.unlink(missing_ok=True)


def _record_failure(context: Run, completed: Completed, records: Path, script: Path, tool: str) -> None:
    warn(f'{tool} installation failed (see {context.failures_log})')
    report = failure_report.render_report(
        failure_report.read_records(records),
        completed.transcript,
        str(script),
        tool,
        completed.returncode,
        'installation',
    )
    with context.failures_log.open('a') as log:
        log.write(report)


# ─────────────────────────────────────────────────────────────────────────────
# The phases
# ─────────────────────────────────────────────────────────────────────────────

COMMON = paths.INSTALL_DIR / 'common'


def _overlay(coords: coordinates.Coordinates) -> str:
    """Which `install/<overlay>/` directory these coordinates ask for.

    Keyed on the package manager, with apt split by host — which is the whole of
    what the four platform labels ever distinguished here.

    What is left of it is the `PLATFORM` in `environment()`, which the remaining
    installer scripts read so `detect_platform` does not have to grep
    `/proc/version` and guess. The package scripts it used to select are gone, and
    with them `install/{archlinux,macos,linux}/` — the difference between the
    apt overlays, the docker-ce family, is `excludes_host` in the declaration now.

    So Arch-on-WSL lands on the pacman answer, which is the one a fused `PLATFORM`
    string could not give: it has no row of its own, and every coordinate it needs
    already exists.
    """
    if coords.package_manager is coordinates.PackageManager.BREW:
        return 'macos'
    if coords.package_manager is coordinates.PackageManager.PACMAN:
        return 'archlinux'
    return 'wsl' if coords.host is coordinates.Host.WSL else 'linux'


def _system_packages(context: Run) -> bool:
    """Everything an OS package manager installs, and the app stores built on them.

    One phase over two stages, so `pacman -S` runs before the flatpak apps that
    need the flatpak binary and `brew install` before the casks and the App Store
    apps that need brew and `mas`.

    Nothing here reads the tier or the flatpak flag any more. Both are
    subscriptions, so the resolver has already applied them and a machine that
    declares `system_packages: false` plans no packages to converge — which is
    also what retires the inverted branch this function carried. It gated the
    *bootstrap* on the payload switch, so a manifest with no tier ran `brew
    install` with no brew; the bootstrap belongs to the provider that needs it,
    and casks and App Store apps subscribe to nothing and so cannot be gated by a
    tier at all.
    """
    heading('System packages')
    return _converge(context, engine.Selection.at(Stage.SYSTEM, Stage.SYSTEM_APPS))


def _go_toolchain(context: Run) -> bool:
    heading('Go toolchain')
    return _converge(context, engine.Selection.of('toolchains/go-toolchain'))


def _rust_toolchain(context: Run) -> bool:
    heading('Rust toolchain')
    return _converge(context, engine.Selection.of('toolchains/rust-toolchain'))


def _uv_toolchain(context: Run) -> bool:
    """Ungated, unlike every other toolchain.

    A manifest with empty uv lists still needs uv, because the tools that come
    later resolve through it — and before this CLI existed, the symlink phase
    itself shelled out to `uv run` and died with exit 127 on `linux-lxc-server`.
    """
    heading('uv')
    return _converge(context, engine.Selection.of('toolchains/uv-toolchain'))


def _go_tools(context: Run) -> bool:
    heading('Go tools')
    return _converge(context, engine.Selection.of('packages/go'))


def _have_github_credentials() -> bool:
    """The same question `github_token` in `version-helpers.sh` asks, so the phase
    and the installers it runs cannot disagree about whether to try."""
    return bool(os.environ.get('GITHUB_TOKEN')) or run(['gh', 'auth', 'token'], output=Output.QUIET).ok


def _github_releases(context: Run) -> bool:
    """Every declared release, installed by `providers.ghrelease` rather than by bash.

    A private repo's tool is skipped where there are no credentials for it. Its
    download cannot succeed, so attempting it records a failure for something this
    machine was never able to have, and the run exits 3 for a reason no change to
    this repo can fix. Warned rather than silent: credentials are a state a
    machine can lose, unlike the WSL host `requires_wsl_host` tests for.

    The scripts this replaces had two modes, and which one ran decided whether a
    tool that was present but behind got upgraded: `install.sh` skipped it,
    `update.sh` did not. There is one verb here. `apply` means "make this machine
    match what it declares", latest is what a release entry declares unless it
    pins, and a tool behind latest is drift — the same drift `check` already
    prints as STALE. So it is repaired, and the mode goes away with the scripts.

    The cost is one release lookup per declared tool, where present-means-skip
    cost none. That is the right trade for a verb someone typed on purpose;
    `check` is the one that has to stay cheap, and it reads a cache instead.
    """
    tools = context.declared('github')
    if not _have_github_credentials():
        private = parse_packages.names_requiring_github_auth(context.packages, 'github_releases')
        if skipping := sorted(set(tools) & private):
            warn(f'no GitHub credentials on this machine, so these private-repo tools are skipped: {", ".join(skipping)}')
            tools = [tool for tool in tools if tool not in private]

    if not tools:
        return True
    heading('GitHub release tools')

    try:
        declaration = context.declaration
    except catalog.CatalogError as refused:
        warn(f'cannot read the declaration, so no release can be installed: {refused}')
        return False

    target = context.target
    return all([_install_release(context, declaration, tool, target) for tool in tools])


def _install_release(context: Run, declaration: catalog.Catalog, tool: str, target: coordinates.Target) -> bool:
    """One release, reporting the same way a failed installer script did."""
    entry = declaration.find('github_releases', tool)
    assert isinstance(entry, catalog.GithubRelease)

    tag = ghrelease.resolve_tag(entry, offline=context.offline)
    if tag is None:
        return _install_failed(context, tool, ghrelease.unresolved(entry, offline=context.offline))

    if not context.reinstall and _already_at(entry, tag):
        err_console.print(f'{tool} already at {tag}')
        restored = ghrelease.ensure_companions(entry, target, tag, offline=context.offline)
        return True if restored.ok else _install_failed(context, tool, restored.detail)

    result = ghrelease.install(entry, target, offline=context.offline, tag=tag)
    if result.ok:
        err_console.print(f'[green]✓[/] {result.detail}')
        return True
    return _install_failed(context, tool, result.detail)


def _already_at(entry: catalog.GithubRelease, tag: str) -> bool:
    """Whether the installed binary is the release this run would install.

    Anything unmeasurable answers False, which reinstalls: a binary that will not
    report a version, or reports one nothing can parse, is not a binary known to
    be current. That is the same call `check_if_update_needed` made — "could not
    parse, will reinstall" — and the same rule `Verdict.UNKNOWN` states, except
    that here there is something to do about it.
    """
    reported = ev.reported_version(entry.executable)
    return reported is not None and versions.at_least(reported, tag) is True


def _install_failed(context: Run, tool: str, detail: str) -> bool:
    warn(f'{tool} installation failed: {detail}')
    with context.failures_log.open('a') as log:
        log.write(f'{tool}: {detail}\n')
    return False


def _custom_installers(context: Run) -> bool:
    """The nine vendors that ship themselves, each converged by its own function.

    Every one runs even after a failure, and for the same reason the release phase
    does: nine unrelated vendors are nine independent chances to be having a bad
    day, and a machine that stopped at the first would install none of the eight
    behind it.
    """
    tools = context.declared('custom')
    if not tools:
        return True
    heading('Custom distribution tools')

    try:
        declaration = context.declaration
    except catalog.CatalogError as refused:
        warn(f'cannot read the declaration, so no custom installer can run: {refused}')
        return False

    target = context.target
    return all([_run_custom_installer(context, declaration, tool, target) for tool in tools])


def _run_custom_installer(context: Run, declaration: catalog.Catalog, tool: str, target: coordinates.Target) -> bool:
    entry = declaration.find('custom_installers', tool)
    assert isinstance(entry, catalog.CustomInstaller)

    result = custom.install(entry, target, offline=context.offline, reinstall=context.reinstall)
    if result.ok:
        # The tool's name alone when the vendor streamed its own report, so this
        # confirms the phase considered it without restating what it just said.
        err_console.print(f'[green]✓[/] {result.detail or tool}')
        return True
    return _install_failed(context, tool, result.detail)


def _cargo_packages(context: Run) -> bool:
    """cargo-binstall is not installed here. It is a precondition of the provider,
    which is what makes `packages apply --source cargo_packages` get it too."""
    heading('Rust/cargo tools')
    return _converge(context, engine.Selection.of('packages/cargo'))


def _node_toolchain(context: Run) -> bool:
    heading('Node toolchain')
    return _converge(context, engine.Selection.of('toolchains/node-toolchain'))


def _npm_globals(context: Run) -> bool:
    heading('npm globals')
    return _converge(context, engine.Selection.of('packages/npm'))


def _uv_tools(context: Run) -> bool:
    heading('Python tools (uv)')
    return _converge(context, engine.Selection.of('packages/uv', 'packages/uv-git'))


def _converge(context: Run, selection: engine.Selection) -> bool:
    """One phase's work, through the engine both verbs share.

    Every phase that reached into a resource had grown its own observe/diff/perform
    loop with its own rendering: three of the thirteen copies of the walk, each with
    a different idea of what a refusal looks like. This is the one walk, and what it
    still returns is a bool only because `Phase.run` does.

    Selected rather than observed-then-filtered. The plugins live on opposite sides
    of the symlink pass — TPM has to exist before the pass that deploys the tmux
    config it reads, and the yazi plugins go after it so nothing writes into
    `~/.config/yazi` first — and each is now an address rather than a stage sieve
    over a walk that measured all three.
    """
    session = context.session
    planned = [event for event in engine.assess(session, selection) if isinstance(event.payload, Change)]

    outcomes = [event.payload for event in engine.execute(session, planned, privileges.Privilege())]
    for outcome in outcomes:
        if isinstance(outcome, Outcome) and outcome.ok:
            err_console.print(f'[green]✓[/] {outcome.message or outcome.change.item}')
        elif isinstance(outcome, Outcome):
            _install_failed(context, outcome.change.item, outcome.message)
        else:
            warn(outcome.reason)

    for change in (event.payload for event in planned if isinstance(event.payload, Change)):
        if not change.actionable and change.drifted:
            warn(f'{change.item}: {change.detail}')

    return all(isinstance(outcome, Outcome) and outcome.ok for outcome in outcomes)


def _shell_plugins(context: Run) -> bool:
    heading('Shell plugins')
    return _converge(context, engine.Selection.of('plugins/shell-plugin'))


def _symlinks(context: Run) -> bool:
    heading('Symlinking dotfiles')
    deployed = _converge(context, engine.Selection.of('symlinks'))
    deploy.epilogue(context.session)
    return deployed


def _tmux_plugins(context: Run) -> bool:
    """TPM is a declared clone; the plugins it installs are not.

    Its list is `@plugin` lines in `tmux.conf`, which TPM reads itself, so the
    second half stays a script: there is nothing in `packages.yml` for the
    resolver to plan per plugin.
    """
    heading('tmux plugins')
    if not _converge(context, engine.Selection.of('plugins/tpm')):
        return False
    if not context.wants('tmux_plugins'):
        return True
    return run_installer(context, COMMON / 'plugins' / 'tmux-plugins.sh', 'tmux-plugins')


def _yazi_plugins(context: Run) -> bool:
    """Declared clones, so there is no second half and no script.

    Its own phase rather than riding tmux's: it is a different program's plugins,
    and the two were only ever adjacent. It runs after the symlink pass because
    that is what deploys the config asking for these — and because `ya pkg add`
    running six stages *earlier* is what put two writers on one path.
    """
    heading('yazi plugins')
    return _converge(context, engine.Selection.of('plugins/yazi-plugin'))


def _nvim_plugins(context: Run) -> bool:
    if not context.wants('nvim_plugins'):
        return True
    heading('Neovim plugins')
    return run_installer(context, COMMON / 'plugins' / 'nvim-plugins.sh', 'nvim-plugins')


def _system_config(context: Run) -> bool:
    """Group memberships, unit enablement, files under `/etc`, and the login shell.

    Through the one engine, like every other converted phase, so what this writes
    is exactly what `dotfiles system plan` prints.

    Selected by stage off the registry, which repays the debt A2 took here. This
    briefly observed the whole `system` resource and filtered afterwards, spending
    one package-inventory query per run on rows it was about to discard; the
    providers at this stage are now a selection, so the package half is not in the
    plan this walk is handed and there is nothing to query.

    The password is asked for at the write that needs it, which is now the rule
    everywhere rather than a concession here: keeping a sudo timestamp alive does
    not work on macOS, so a front prompt bought nothing and cost a password on
    machines needing none. `plan` states the count in advance.
    """
    return _converge(context, engine.Selection.at(Stage.SYSTEM_CONFIG))


# ─────────────────────────────────────────────────────────────────────────────
# The registry
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Phase:
    name: str
    """The address a row prints and `--skip` takes."""

    resource: str
    """Which CLI resource owns it, so `dotfiles packages apply` selects a subset."""

    providers: tuple[str, ...]
    """Which of `registry.PROVIDERS` this phase installs, or () for one `--owner`
    can never select: the symlink pass, the Neovim plugins Lazy syncs from its own
    lockfile, and the system configuration, whose rows belong to nobody on GitHub.

    This replaces a hand-maintained `owner_aware` boolean. Ownership is already a
    fact about the entries, so the question "can `--owner` narrow this phase" is
    answered by resolving the plan for that owner and asking which providers it
    left, never by a column someone has to remember to update.
    """

    run: Callable[[Run], bool]


REGISTRY = (
    Phase('system-packages', 'system', ('system', 'cask', 'mas', 'flatpak'), _system_packages),
    Phase('go-toolchain', 'toolchains', ('go-toolchain',), _go_toolchain),
    Phase('rust-toolchain', 'toolchains', ('rust-toolchain',), _rust_toolchain),
    Phase('uv', 'toolchains', ('uv-toolchain',), _uv_toolchain),
    Phase('go-tools', 'packages', ('go',), _go_tools),
    Phase('github-releases', 'packages', ('ghrelease',), _github_releases),
    Phase('custom-installers', 'packages', ('custom',), _custom_installers),
    Phase('cargo', 'packages', ('cargo',), _cargo_packages),
    Phase('node-toolchain', 'toolchains', ('node-toolchain',), _node_toolchain),
    Phase('npm-globals', 'packages', ('npm',), _npm_globals),
    Phase('uv-tools', 'packages', ('uv', 'uv-git'), _uv_tools),
    Phase('shell-plugins', 'plugins', ('shell-plugin',), _shell_plugins),
    Phase('symlinks', 'symlinks', (), _symlinks),
    Phase('tmux-plugins', 'plugins', ('tpm',), _tmux_plugins),
    Phase('yazi-plugins', 'plugins', ('yazi-plugin',), _yazi_plugins),
    Phase('nvim-plugins', 'plugins', (), _nvim_plugins),
    Phase('system-config', 'system', (), _system_config),
)


def select(
    skip: frozenset[str] = frozenset(),
    only: frozenset[str] | None = None,
    providers: frozenset[str] | None = None,
) -> list[Phase]:
    """Which phases a run covers, in registry order.

    Pure, and separate from running them, so "what would this do" is answerable
    without doing it. `only` is how a resource sub-app narrows to its own subtree;
    `skip` is the subtraction the composite offers and the noun form cannot say.

    `providers` is `Plan.providers` — pass it to narrow to the phases that have
    something to install, which is the whole of `--owner`. `None` means no
    narrowing, and is not the same as the empty set: a run whose owner matched
    nothing selects no phases and says so.
    """
    return [
        phase
        for phase in REGISTRY
        if phase.resource not in skip
        and (only is None or phase.resource in only)
        and (providers is None or bool(providers.intersection(phase.providers)))
    ]


def apply_machine(
    skip: frozenset[str] = frozenset(),
    only: frozenset[str] | None = None,
    machine: str | None = None,
    *,
    reinstall: bool = False,
    offline: bool = False,
    owner: str | None = None,
    providers: frozenset[str] | None = None,
) -> ExitCode:
    """Run the selected phases and report whether the machine converged.

    `providers` and `owner` narrow the same way and compose by intersection: one
    says which section was asked for and the other which owner's entries are
    wanted, and a run asking for both means the phases satisfying both.
    """
    # Imported here rather than at module scope: `commands.manage` is a leaf of the
    # CLI and importing it upward would tie this module to the command layer that
    # calls it.
    from dotfiles.commands.manage import report_stray_branch

    report_stray_branch()

    # Before anything is resolved, because everything after this is measured
    # against the declaration: a run against one that will not hold together
    # installs whatever survived the parse and reports success. `check` has always
    # put this first in its walk for the same reason; refusing to *act* on it is
    # what the read-only verb could not do.
    if broken := validate.errors(validate.declaration()):
        warn(f'the declaration has {len(broken)} problem(s), so there is nothing safe to apply')
        for finding in broken:
            render_finding(finding.section, finding.message)
        hint("'dotfiles machines check' lists them, warnings included")
        return ExitCode.ISSUE

    try:
        context = Run.resolve(machine, reinstall=reinstall, offline=offline, owner=owner)
    except Declaration as problem:
        warn(str(problem))
        return ExitCode.USAGE

    # The session already resolves owner-narrowed — `Run.session` hands it the
    # owner — so asking it is the same answer as resolving a second plan, minus
    # the second catalog parse. Ownership stays a property of the entries rather
    # than a column: `shell-plugins` was hand-marked "no owner" when all five of
    # its plugins have one, none of them Chris's.
    try:
        owned = context.session.plan.providers if owner else None
    except (catalog.CatalogError, machines.MachineError) as refused:
        warn(f'cannot narrow to --owner {owner}: {refused}')
        return ExitCode.ISSUE

    narrowed = owned if providers is None else (providers if owned is None else providers & owned)
    phases = select(skip, only, narrowed)
    if not phases:
        warn(f'nothing selected for owner {owner}' if owner else 'nothing selected')
        return ExitCode.USAGE

    if offline and not paths.BUNDLE_DIR.is_dir():
        warn(f'offline needs a staged bundle at {paths.BUNDLE_DIR}, and there is none')
        hint('stage one with: ./install.sh --machine <name> --offline')
        return ExitCode.ISSUE

    err_console.rule(f'[bold]dotfiles apply[/]  {context.machine} ({context.platform})', align='left')

    # Before the phases, so the run and every later shell agree on what this
    # machine is. Nothing is read back: the platform and the flags come from the
    # manifest, which is the file ~/.env is generated from.
    heading('Machine environment')
    try:
        envfile.write(Path.home() / '.env', machines.load(context.machine))
    except (machines.MachineError, OSError) as problem:
        warn(f'could not write ~/.env, continuing with the existing file: {problem}')

    failed = [phase.name for phase in phases if not phase.run(context)]

    if failed:
        err_console.rule('[bold red]failed[/]', align='left')
        warn(f'{len(failed)} of {len(phases)} phases reported a failure: {", ".join(failed)}')
        hint(f'the full report is in {context.failures_log}')
        return ExitCode.ISSUE

    err_console.rule(f'[bold green]converged[/]  {context.machine}', align='left')
    return ExitCode.CONVERGED
