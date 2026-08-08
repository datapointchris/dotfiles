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

`install/phases.sh` still holds the same registry for `update.sh`, and
`tests/cli/test_phase_registry.py` asserts the two name the same phases — the one
thing that keeps the halves from drifting while both exist.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dotfiles import deploy
from dotfiles import failure_report
from dotfiles import parse_packages
from dotfiles import paths
from dotfiles.effects import Completed
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import err_console
from dotfiles.output import heading
from dotfiles.output import hint
from dotfiles.output import warn
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
unless it is named: go-tools needs the Go toolchain, node.sh needs fnm from the
cargo phase, npm-globals needs the Node that node.sh links as fnm's default alias.
Order mirrors `.zshenv` so a phase resolves the same binary an interactive shell
would. `install/tool-path.sh` says the same thing to `update.sh`, and
`tests/cli/test_phase_registry.py` asserts the two agree.
"""


@dataclass(frozen=True)
class Run:
    """One `apply`, and everything its phases need to answer a question.

    `packages` and `manifest` are parsed once and passed down. That is the whole
    difference between this and the bash it replaces, which asked the same two
    files 28 separate times through 28 separate interpreters.
    """

    machine: str
    platform: str
    packages: dict
    manifest: dict
    reinstall: bool = False
    offline: bool = False
    owner: str | None = None
    failures_log: Path = paths.REPO_ROOT / 'unused'

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

        The platform comes from the manifest and never from `uname`. A fresh
        machine has no `~/.env` to read it from, and detecting it instead is how a
        wsl manifest once deployed the linux shell overlay for a whole install.
        """
        name = machine or os.environ.get('MACHINE') or ''
        if not name:
            raise Declaration('no machine named, and MACHINE is not set in the environment')

        manifest_file = paths.MANIFESTS_DIR / f'{name}.yml'
        if not manifest_file.is_file():
            available = ', '.join(sorted(path.stem for path in paths.MANIFESTS_DIR.glob('*.yml')))
            raise Declaration(f'no manifest named {name!r}. Available: {available}')

        manifest = parse_packages.load_manifest(name)
        platform = manifest.get('platform')
        if not platform:
            raise Declaration(f'{manifest_file} declares no platform')

        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
        return cls(
            machine=name,
            platform=platform,
            packages=parse_packages.load_packages(),
            manifest=manifest,
            reinstall=reinstall,
            offline=offline,
            owner=owner,
            failures_log=Path(tempfile.gettempdir()) / f'dotfiles-install-failures-{stamp}.txt',
        )

    @property
    def system_tier(self) -> str:
        """ "core", "workstation", or "" when the phase is off for this machine.

        A bare `true` still means the full set: manifests predating the tier said
        so that way, and reading it as "" would silently install no system
        packages on a machine whose declaration asks for all of them.
        """
        declared = self.manifest.get('system_packages')
        if declared is None or declared is False:
            return ''
        if declared is True:
            return 'workstation'
        return str(declared)

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
    'go': parse_packages.filter_go_packages_by_manifest,
    'cargo': parse_packages.filter_cargo_packages_by_manifest,
    'npm': parse_packages.filter_npm_packages_by_manifest,
    'uv': parse_packages.filter_uv_packages_by_manifest,
    'git_uv': parse_packages.filter_git_uv_packages_by_manifest,
    'github': parse_packages.filter_github_releases_by_manifest,
    'custom': parse_packages.filter_custom_installers_by_manifest,
}


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


def _run_scripts(context: Run, scripts: list[Path], *, tier: str = '') -> bool:
    """Run several scripts in order, reporting whether all of them succeeded.

    Every one runs even after a failure: a broken cask must not stop the Xcode
    licence or the Docker configuration that follow it, and the report at the end
    is what names all of them at once.
    """
    environment = {'SYSTEM_PACKAGE_TIER': tier} if tier else None
    return all([run_installer(context, script, script.stem, env=environment) for script in scripts])


def _run_directory_phase(context: Run, kind: str, directory: Path, title: str) -> bool:
    """The phases that are a directory of per-tool scripts rather than one script."""
    tools = context.declared(kind)
    if not tools:
        return True
    heading(title)
    return all([run_installer(context, directory / f'{tool}.sh', tool) for tool in tools])


# ─────────────────────────────────────────────────────────────────────────────
# The phases
# ─────────────────────────────────────────────────────────────────────────────

COMMON = paths.INSTALL_DIR / 'common'

SYSTEM_SCRIPTS = {
    'macos': ('homebrew.sh', 'system-packages.sh', 'casks.sh', 'configure-docker.sh', 'mas-apps.sh', 'xcode.sh', 'preferences.sh'),
    'wsl': ('system-packages.sh',),
    'archlinux': ('system-packages.sh',),
    'linux': ('system-packages.sh',),
}


def _system_packages(context: Run) -> bool:
    """The OS package manager, plus whatever else that platform configures.

    The tier gates only the package payload. Everything beside it — fontconfig on
    WSL, `system-config.sh` on Arch, preferences and the Xcode licence on macOS —
    runs whether or not this machine wants packages, because it is configuration
    rather than payload.
    """
    if context.platform not in SYSTEM_SCRIPTS:
        raise Declaration(f'unsupported platform: {context.platform}')

    platform_dir = paths.INSTALL_DIR / context.platform
    heading(f'System packages ({context.platform})')

    scripts = [platform_dir / name for name in SYSTEM_SCRIPTS[context.platform]] if context.system_tier else []
    # macOS's list is the payload *and* the configuration, and only the first
    # entry of it is gated. Splitting it here rather than in the table keeps the
    # table readable as "what this platform runs".
    if context.platform == 'macos' and not context.system_tier:
        scripts = [platform_dir / name for name in SYSTEM_SCRIPTS['macos'][1:]]

    if context.platform == 'wsl':
        scripts.append(platform_dir / 'fontconfig-setup.sh')
    if context.platform == 'archlinux':
        if context.wants('flatpak'):
            scripts.append(platform_dir / 'flatpak.sh')
        scripts.append(platform_dir / 'system-config.sh')

    return _run_scripts(context, scripts, tier=context.system_tier or 'workstation')


def _go_toolchain(context: Run) -> bool:
    if not context.declared('go'):
        return True
    heading('Go toolchain')
    return run_installer(context, COMMON / 'language-managers' / 'go.sh', 'go')


def _rust_toolchain(context: Run) -> bool:
    if not context.declared('cargo'):
        return True
    heading('Rust toolchain')
    return all(
        [
            run_installer(context, COMMON / 'language-managers' / 'rust.sh', 'rust'),
            run_installer(context, COMMON / 'language-tools' / 'cargo-binstall.sh', 'cargo-binstall'),
        ]
    )


def _uv_toolchain(context: Run) -> bool:
    """Ungated, unlike every other toolchain.

    A manifest with empty uv lists still needs uv, because the tools that come
    later resolve through it — and before this CLI existed, the symlink phase
    itself shelled out to `uv run` and died with exit 127 on `linux-lxc-server`.
    """
    heading('uv')
    return run_installer(context, COMMON / 'language-managers' / 'uv.sh', 'uv')


def _go_tools(context: Run) -> bool:
    if not context.declared('go'):
        return True
    heading('Go tools')
    return run_installer(context, COMMON / 'language-tools' / 'go-tools.sh', 'go-tools')


def _github_releases(context: Run) -> bool:
    return _run_directory_phase(context, 'github', COMMON / 'github-releases', 'GitHub release tools')


def _custom_installers(context: Run) -> bool:
    return _run_directory_phase(context, 'custom', COMMON / 'custom-installers', 'Custom distribution tools')


def _cargo_packages(context: Run) -> bool:
    if not context.declared('cargo'):
        return True
    heading('Rust/cargo tools')
    return run_installer(context, COMMON / 'language-tools' / 'cargo-tools.sh', 'cargo-tools')


def _node_toolchain(context: Run) -> bool:
    if not context.declared('npm'):
        return True
    heading('Node toolchain')
    return run_installer(context, COMMON / 'language-managers' / 'node.sh', 'node')


def _npm_globals(context: Run) -> bool:
    if not context.declared('npm'):
        return True
    heading('npm globals')
    return run_installer(context, COMMON / 'language-tools' / 'npm-install-globals.sh', 'npm-globals')


def _uv_tools(context: Run) -> bool:
    if not context.declared('uv') and not context.declared('git_uv'):
        return True
    heading('Python tools (uv)')
    return run_installer(context, COMMON / 'language-tools' / 'uv-tools.sh', 'uv-tools')


def _shell_plugins(context: Run) -> bool:
    if not context.wants('shell_plugins'):
        return True
    heading('Shell plugins')
    return run_installer(context, COMMON / 'plugins' / 'shell-plugins.sh', 'shell-plugins')


def _symlinks(context: Run) -> bool:
    heading('Symlinking dotfiles')
    return deploy.relink(context.platform)


def _tmux_plugins(context: Run) -> bool:
    if not context.wants('tmux_plugins'):
        return True
    heading('tmux plugins')
    return all(
        [
            run_installer(context, COMMON / 'plugins' / 'tpm.sh', 'tpm'),
            run_installer(context, COMMON / 'plugins' / 'tmux-plugins.sh', 'tmux-plugins'),
        ]
    )


def _nvim_plugins(context: Run) -> bool:
    if not context.wants('nvim_plugins'):
        return True
    heading('Neovim plugins')
    return run_installer(context, COMMON / 'plugins' / 'nvim-plugins.sh', 'nvim-plugins')


def _zsh_config(context: Run) -> bool:
    """Point the system zshenv at the XDG config, and make zsh the login shell.

    Both sudo calls sit here rather than in a `privilege.py` because that module
    is a design with a shape — declared privilege, one authorisation up front, a
    keepalive for `pacman -Syu` — and writing it around these two would be a
    different thing wearing the name. Step 6 builds it with the system resource.

    Every state check is an unprivileged read, so a machine already configured
    never prompts for a password.
    """
    if not context.wants('configure_zsh'):
        return True
    heading('Shell configuration')
    return _ensure_zdotdir() and _ensure_login_shell()


def _ensure_zdotdir() -> bool:
    """Without this `~/.config/zsh/.zshrc` never loads at all, on any platform."""
    zshenv = Path('/etc/zsh/zshenv') if Path('/etc/zsh').is_dir() else Path('/etc/zshenv')

    if zshenv.is_file() and 'ZDOTDIR' in zshenv.read_text():
        err_console.print(f'ZDOTDIR already configured in {zshenv}')
        return True

    # $HOME has to expand when zsh reads the file, not now.
    line = 'export ZDOTDIR="$HOME/.config/zsh"'
    if not zshenv.parent.is_dir() and not run(['sudo', 'mkdir', '-p', str(zshenv.parent)]).ok:
        return False
    if not run(['sudo', 'sh', '-c', f'printf "%s\\n" {line!r} >> {zshenv}'], output=Output.QUIET).ok:
        warn(f'could not write ZDOTDIR into {zshenv}')
        return False
    err_console.print(f'ZDOTDIR configured in {zshenv}')
    return True


def _ensure_login_shell() -> bool:
    """A no-op, and no sudo, where zsh is already the login shell — always on macOS.

    Two shell idioms that do not survive translation into subprocess calls, and
    both were here: `command -v` is a builtin no `exec` can find, and `$USER` is
    unset in any context without a login shell — `docker exec`, a systemd timer,
    cron — where `chsh -s zsh ""` then fails with `user "" does not exist`.
    """
    if 'zsh' in os.environ.get('SHELL', ''):
        err_console.print('Default shell is already zsh')
        return True

    zsh = shutil.which('zsh')
    if not zsh:
        warn('zsh is not installed, so it cannot be made the login shell')
        return False

    if not run(['sudo', 'chsh', '-s', zsh, _current_user()]).ok:
        return False
    err_console.print('Default shell changed to zsh (effective at next login)')
    return True


def _current_user() -> str:
    """Whose login shell this is, from the uid rather than the environment."""
    import pwd

    return pwd.getpwuid(os.getuid()).pw_name


# ─────────────────────────────────────────────────────────────────────────────
# The registry
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Phase:
    name: str
    """The address a row prints and `--skip` takes."""

    resource: str
    """Which CLI resource owns it, so `dotfiles packages apply` selects a subset."""

    owner_aware: bool
    """Whether its contents can be traced to a GitHub owner.

    A phase driven by a registry instead — apt, npm, PyPI — has no owner, and is
    skipped under `--owner` rather than silently running in full.
    """

    run: Callable[[Run], bool]


REGISTRY = (
    Phase('system-packages', 'system', False, _system_packages),
    Phase('go-toolchain', 'toolchains', False, _go_toolchain),
    Phase('rust-toolchain', 'toolchains', False, _rust_toolchain),
    Phase('uv', 'toolchains', False, _uv_toolchain),
    Phase('go-tools', 'packages', True, _go_tools),
    Phase('github-releases', 'packages', True, _github_releases),
    Phase('custom-installers', 'packages', True, _custom_installers),
    Phase('cargo', 'packages', True, _cargo_packages),
    Phase('node-toolchain', 'toolchains', False, _node_toolchain),
    Phase('npm-globals', 'packages', False, _npm_globals),
    Phase('uv-tools', 'packages', True, _uv_tools),
    Phase('shell-plugins', 'plugins', False, _shell_plugins),
    Phase('symlinks', 'symlinks', False, _symlinks),
    Phase('tmux-plugins', 'plugins', False, _tmux_plugins),
    Phase('nvim-plugins', 'plugins', False, _nvim_plugins),
    Phase('zsh-config', 'system', False, _zsh_config),
)


def select(skip: frozenset[str] = frozenset(), only: frozenset[str] | None = None, owner: str | None = None) -> list[Phase]:
    """Which phases a run covers, in registry order.

    Pure, and separate from running them, so "what would this do" is answerable
    without doing it. `only` is how a resource sub-app narrows to its own subtree;
    `skip` is the subtraction the composite offers and the noun form cannot say.
    """
    return [
        phase
        for phase in REGISTRY
        if phase.resource not in skip and (only is None or phase.resource in only) and (owner is None or phase.owner_aware)
    ]


def apply_machine(
    skip: frozenset[str] = frozenset(),
    only: frozenset[str] | None = None,
    machine: str | None = None,
    *,
    reinstall: bool = False,
    offline: bool = False,
    owner: str | None = None,
) -> ExitCode:
    """Run the selected phases and report whether the machine converged."""
    try:
        context = Run.resolve(machine, reinstall=reinstall, offline=offline, owner=owner)
    except Declaration as problem:
        warn(str(problem))
        return ExitCode.USAGE

    phases = select(skip, only, owner)
    if not phases:
        warn('nothing selected')
        return ExitCode.USAGE

    if offline and not paths.BUNDLE_DIR.is_dir():
        warn(f'offline needs a staged bundle at {paths.BUNDLE_DIR}, and there is none')
        hint('stage one with: ./install.sh --machine <name> --offline')
        return ExitCode.ISSUE

    err_console.rule(f'[bold]dotfiles apply[/]  {context.machine} ({context.platform})', align='left')

    # Before the phases, so the run and every later shell agree on what this
    # machine is. Nothing is read back: the platform and the flags come from the
    # manifest above, which is the file ~/.env is generated from.
    from dotfiles import bridge

    if not bridge.ops('env', 'sync', '--machine', context.machine).ok:
        warn('could not sync ~/.env — continuing with the existing file')

    failed = [phase.name for phase in phases if not phase.run(context)]

    if failed:
        err_console.rule('[bold red]failed[/]', align='left')
        warn(f'{len(failed)} of {len(phases)} phases reported a failure: {", ".join(failed)}')
        hint(f'the full report is in {context.failures_log}')
        return ExitCode.ISSUE

    err_console.rule(f'[bold green]converged[/]  {context.machine}', align='left')
    return ExitCode.CONVERGED
