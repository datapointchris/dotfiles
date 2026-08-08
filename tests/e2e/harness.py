"""The container rig the e2e tests drive.

Beside `conftest.py` rather than inside it so the test module can import these
names: `tests/` is not a package, so `tests.e2e.conftest` is not an importable
path, while pytest puts this directory on `sys.path` for both files. `conftest.py`
keeps only what pytest itself calls.

`Machine.exec` is the one definition of what running a command in the container
means. That matters more than it sounds: the three bash harnesses this replaced
each built their own `docker exec` line, and every difference between them was a
bug — one exported a PATH carrying `~/.local/bin` and another did not, so the
duplicate detector could not find `uv` and reported the machine broken when only
the harness was.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from urllib.parse import urlsplit

from dotfiles import apply
from dotfiles import paths

CONNECTIVITY_RESULTS = paths.INSTALL_DIR / 'offline' / 'connectivity-results.txt'
DOCKER_DIR = paths.REPO_ROOT / 'tests' / 'install' / 'docker'

# The one thing a host blocklist cannot express is that the work firewall filters
# by path: github.com serves clones, /releases/latest and the API while refusing
# /releases/download/. Blackholing the CDNs a download redirects to is how that
# becomes a host rule, and it is why a github.com row measured NO does not become
# a github.com entry.
ASSET_CDN_HOSTS = (
    'objects.githubusercontent.com',
    'release-assets.githubusercontent.com',
    'github-releases.githubusercontent.com',
)

SHADOW_BIN = '.dotfiles-shadow-bin'
"""Where the hostile `python3` lives, first on every PATH the rig hands out."""

SHADOW_LOG = '.dotfiles-shadow-calls'
"""One line per invocation of it: who called, and with what."""


# On a real machine the tool directories are prepended to a PATH that already
# exists; `docker exec` supplies almost nothing, so the system half has to be
# named here. The tool half is imported rather than copied — a fourth list of the
# same directories is how the npm prefix came to be on three of them and not the
# fourth, which reported eleven installed tools as missing.
SYSTEM_PATH_DIRS = ('/usr/local/sbin', '/usr/local/bin', '/usr/sbin', '/usr/bin', '/sbin', '/bin')
CONTAINER_PATH_DIRS = ('$HOME/' + SHADOW_BIN, *apply.TOOL_PATH_DIRS, *SYSTEM_PATH_DIRS)


# ─────────────────────────────────────────────────────────────────────────────
# The measured network
# ─────────────────────────────────────────────────────────────────────────────


# The agent the measurement used, and not cosmetic: crates.io answers curl's
# default agent with 403. `install/offline/test-connectivity.sh` carries the same
# constant and the reason — a run that omitted it recorded crates.io as a firewall
# block, which would have meant bundling all nine cargo tools for nothing. A
# container re-probe that synthesizes its own request walks into it again, which
# is why `probe_command` replays the recorded one instead.
PROBE_AGENT = 'dotfiles-connectivity-test (+https://github.com/datapointchris/dotfiles)'


@dataclass(frozen=True)
class Probe:
    """One row of the measurement: what was tried, and what the work box got."""

    verdict: str
    section: str
    name: str
    target: str

    @property
    def host(self) -> str:
        return urlsplit(self.target if '//' in self.target else f'https://{self.target}').netloc

    @property
    def reachable(self) -> bool:
        return self.verdict == 'YES'

    @property
    def cloned(self) -> bool:
        return self.section.endswith('clone')

    def command(self) -> str:
        """The same request the measurement made, to re-run inside a container.

        Re-running it rather than synthesizing `https://<host>/` is the whole
        point: the method, the URL and the agent all changed a verdict at least
        once, and a probe that differs from the recorded one is measuring a
        different question and calling the answer a firewall.
        """
        if self.cloned:
            return f'GIT_TERMINAL_PROMPT=0 git ls-remote --quiet {shlex.quote(self.target)} HEAD'
        return f'curl -fsSL --head -A {shlex.quote(PROBE_AGENT)} --connect-timeout 10 {shlex.quote(self.target)}'


def measured_probes() -> tuple[Probe, ...]:
    """Every row of `install/offline/connectivity-results.txt`.

    Derived rather than typed: that file is written by
    `install/offline/test-connectivity.sh` from packages.yml and the manifest, and
    is committed precisely so this does not have to be guessed. A container that
    blocks more than the firewall manufactures failures no machine has, and they
    read as real ones in a log — clone-based installers dying is the shape it
    takes, since git clone is reachable at work and theme, font, bashselfupdate
    and every zsh plugin come down that way.
    """
    probes = []
    for line in CONNECTIVITY_RESULTS.read_text().splitlines():
        fields = [cell.strip() for cell in line.split('|')]
        if len(fields) < 4 or fields[0] not in {'YES', 'NO'}:
            continue
        probes.append(Probe(verdict=fields[0], section=fields[1], name=fields[2], target=fields[3]))
    return tuple(probes)


def measured_network() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """`(blocked, reachable)` hosts, for building the container's `--add-host` set."""
    probes = measured_probes()
    reachable = {probe.host for probe in probes if probe.reachable and probe.host}
    blocked = {probe.host for probe in probes if not probe.reachable and probe.host}

    # A host under both verdicts is a path-scoped block; taking the host down
    # would take down the paths that work.
    blocked = {host for host in blocked if host not in reachable}
    blocked |= set(ASSET_CDN_HOSTS)
    return tuple(sorted(blocked)), tuple(sorted(reachable))


def reachable_probes() -> tuple[Probe, ...]:
    """One probe per reachable host *per method*.

    Per host alone would be cheaper and would silently drop every clone: the
    release rows come first in the file and claim `github.com`, so the git path —
    the one carrying theme, font, bashselfupdate and all four zsh plugins — would
    never be re-probed at all. Two probes for that host, forty-odd rows collapsed
    to a dozen.
    """
    seen: set[tuple[str, bool]] = set()
    chosen = []
    for probe in measured_probes():
        key = (probe.host, probe.cloned)
        if probe.reachable and probe.host and key not in seen:
            seen.add(key)
            chosen.append(probe)
    return tuple(chosen)


# ─────────────────────────────────────────────────────────────────────────────
# Environments
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Environment:
    """One machine to install: the image, who installs, and what it declares."""

    name: str
    image: str
    user: str
    home: str
    manifest: str

    prepare: tuple[str, ...] = ()
    """Root commands run in the container before the repo arrives."""

    env_file: str | None = None
    """`~/.env` contents, or None to let install.sh generate it — which is what is
    being rehearsed. Hand-writing a stub hid two bugs at once: `env sync` failed
    because uv is installed by a later phase and the warning said it was
    "continuing with the existing file", meaning the stub; and the stub carried no
    MACHINE, so manifest-derived verification checked 45 things instead of 138 and
    still reported success."""

    firewalled: bool = False
    """Blackhole what the work box reported blocked.

    Separate from `offline` because they are different questions. Firewalled and
    *with* a bundle asks whether the bundle covers what the network cannot reach;
    firewalled and without one asks what a run does when things genuinely fail —
    whether it keeps going, whether every failure lands in one log, whether the
    summary says so. The second is the only test of the failure machinery, and it
    needs the failures to be real.
    """

    offline: bool = False
    """Stage a bundle and pass `--offline`. Implies `firewalled`."""

    build_image: tuple[str, ...] = field(default_factory=tuple)
    """How to produce the image when it is absent, rather than failing."""


ARCHLINUX = Environment(
    name='archlinux',
    image='archlinux:latest',
    user='archlinuxuser',
    home='/home/archlinuxuser',
    manifest='archlinux-personal-workstation',
    # git only, and sudo for the phases that need it. No python either, which is
    # the state the other three images cannot reach — `plant_python_shadow` gives
    # every environment the hostile version of the same question.
    prepare=(
        # -Syu, never -Sy: a partial upgrade is unsupported on Arch, and it broke
        # here the moment gcc-libs split — the new libgcc conflicts on files the
        # un-upgraded gcc-libs still owns.
        'pacman -Syu --noconfirm sudo git',
        'useradd -m -G wheel -s /bin/bash archlinuxuser',
        "printf '%s\\n' 'archlinuxuser ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers",
    ),
    env_file='PLATFORM=archlinux\nDOTFILES_DOCKER_TEST=true\n',
)

WSL = Environment(
    name='wsl',
    image='wsl-ubuntu:26.04',
    user='ubuntu',
    home='/home/ubuntu',
    manifest='wsl-work-workstation',
    prepare=("printf '%s\\n' 'ubuntu ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers",),
    build_image=('bash', str(DOCKER_DIR / 'build-wsl-image.sh'), '26.04'),
)

OFFLINE = Environment(
    name='offline',
    image='dotfiles-test-base:ubuntu-26.04',
    user='testuser',
    home='/home/testuser',
    manifest='wsl-work-workstation',
    env_file='PLATFORM=wsl\n',
    firewalled=True,
    offline=True,
    build_image=('bash', str(DOCKER_DIR / 'build-base.sh')),
)

RESTRICTED = Environment(
    name='restricted',
    image='dotfiles-test-base:ubuntu-26.04',
    user='testuser',
    home='/home/testuser',
    manifest='wsl-work-workstation',
    env_file='PLATFORM=wsl\n',
    firewalled=True,
    build_image=('bash', str(DOCKER_DIR / 'build-base.sh')),
)

ENVIRONMENTS = (ARCHLINUX, WSL, OFFLINE, RESTRICTED)


# ─────────────────────────────────────────────────────────────────────────────
# The container
# ─────────────────────────────────────────────────────────────────────────────


def docker(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['docker', *args], check=check, capture_output=True, text=True)


def image_exists(image: str) -> bool:
    return docker('image', 'inspect', image).returncode == 0


def exec_script(command: str, home: str) -> str:
    """The shell a container command actually runs, with its environment in front.

    A function rather than an expression inside `Machine.exec` so it can be
    asserted without starting anything. The PATH is built here and nowhere else,
    and getting it wrong is not a visible failure — it is a tool reported missing
    on a machine that is carrying it, which reads as a broken install.
    """
    path = ':'.join(CONTAINER_PATH_DIRS)
    return f'export HOME={shlex.quote(home)}; export PATH="{path}"; {command}'


@dataclass
class Machine:
    """A container with the repo in it, and possibly the install already run."""

    environment: Environment
    container: str
    install_status: int = -1
    install_log: str = ''

    def exec(self, command: str, *, user: str | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
        """Run a shell command in the container, as the installing user by default."""
        return docker(
            'exec',
            '--user',
            user or self.environment.user,
            '--env',
            f'HOME={self.environment.home}',
            self.container,
            'bash',
            '-c',
            exec_script(command, self.environment.home),
            check=check,
        )

    def succeeds(self, command: str) -> bool:
        return self.exec(command).returncode == 0

    def read(self, command: str) -> str:
        return self.exec(command).stdout.strip()


# ─────────────────────────────────────────────────────────────────────────────
# The hostile system python
# ─────────────────────────────────────────────────────────────────────────────


SHADOW_REFUSAL = 'the e2e harness shadows the system python'


def shadow_source(home: str) -> str:
    """A `python3` that records who wanted it and then refuses.

    Shadowed rather than absent, because absence is a weaker property and only
    one image can even express it: Arch ships no python, so asserting
    `command -v python3` fails there proves that Arch is Arch, and the same
    assertion on a Mac fails against Xcode's. A stub that is present, first on
    PATH and loud says "nothing reached for it" on every machine.

    The caller comes from `/proc/$PPID/cmdline` because the argv alone does not
    say who ran it, and who ran it is the entire diagnosis — uv probing PATH for
    an interpreter is expected, a phase script calling `python3` is the bug this
    step deleted.
    """
    return (
        '#!/bin/sh\n'
        "caller=$(tr '\\0' ' ' < \"/proc/$PPID/cmdline\" 2>/dev/null || echo unknown)\n"
        f'printf \'%s\\t%s\\n\' "$caller" "$0 $*" >> {home}/{SHADOW_LOG}\n'
        f'echo "{SHADOW_REFUSAL}: nothing may call it by name" >&2\n'
        'exit 1\n'
    )


@dataclass(frozen=True)
class ShadowCall:
    """One invocation of the shadowed interpreter."""

    caller: str
    argv: str

    @property
    def by_uv(self) -> bool:
        """uv scanning PATH for an interpreter, which is uv's business and not ours.

        The offline path passes `--no-python-downloads`, so an interpreter uv can
        find is a documented requirement there; it finds this one first, rejects
        it for exiting 1, and carries on to the real one. Matched on the parent's
        basename rather than a substring, or every path containing `uv` — which
        is most of them once `~/.local/share/uv` exists — would qualify.
        """
        first = self.caller.split()
        return bool(first) and Path(first[0]).name == 'uv'


def plant_python_shadow(machine: Machine) -> None:
    """Put the stub on PATH under every name a caller might reach for."""
    home = machine.environment.home
    machine.exec(
        f'mkdir -p {home}/{SHADOW_BIN} && '
        f'printf %s {shlex.quote(shadow_source(home))} > {home}/{SHADOW_BIN}/python3 && '
        f'chmod +x {home}/{SHADOW_BIN}/python3 && '
        f'ln -sf python3 {home}/{SHADOW_BIN}/python',
        check=True,
    )


def clear_shadow_calls(machine: Machine) -> None:
    machine.exec(f'rm -f {machine.environment.home}/{SHADOW_LOG}', check=True)


def shadow_calls(machine: Machine) -> tuple[ShadowCall, ...]:
    log = machine.read(f'cat {machine.environment.home}/{SHADOW_LOG} 2>/dev/null')
    calls = []
    for line in log.splitlines():
        caller, _, argv = line.partition('\t')
        if line.strip():
            calls.append(ShadowCall(caller=caller.strip(), argv=argv.strip()))
    return tuple(calls)


# ─────────────────────────────────────────────────────────────────────────────
# The install, kept
# ─────────────────────────────────────────────────────────────────────────────


INSTALL_LOG = '.dotfiles-install-log'
INSTALL_STATUS = '.dotfiles-install-status'


def install_command(environment: Environment) -> str:
    """`install.sh`, leaving its output and exit status behind in the container.

    Persisted rather than only returned, because the install is the expensive
    artifact and every question about it gets asked again the moment an assertion
    changes — twice today, once because a container died and once because a test
    was added after the run started. `PIPESTATUS[0]` because `tee` is whose exit
    status the shell would otherwise report, and it always succeeds.
    """
    home = environment.home
    flags = ' --offline' if environment.offline else ''
    return (
        f'cd {home}/dotfiles && ./install.sh --machine {environment.manifest}{flags} 2>&1 '
        f'| tee {home}/{INSTALL_LOG}; echo ${{PIPESTATUS[0]}} > {home}/{INSTALL_STATUS}'
    )


def install_record(machine: Machine) -> tuple[int, str] | None:
    """The status and log of the install in this container, or None if there is none."""
    status = machine.read(f'cat {machine.environment.home}/{INSTALL_STATUS} 2>/dev/null').strip()
    if not status.isdigit():
        return None
    return int(status), machine.exec(f'cat {machine.environment.home}/{INSTALL_LOG} 2>/dev/null').stdout


def install_age(machine: Machine) -> str:
    """When that install ran, so a stale one cannot be mistaken for this run's."""
    return machine.read(f'date -r {machine.environment.home}/{INSTALL_STATUS} 2>/dev/null') or 'an unknown time'


def reaches(machine: Machine, command: str, attempts: int = 3) -> bool:
    """A live network probe, retried before its answer is believed.

    A dozen real requests run in the firewall check, and one transient timeout
    reported the container as stricter than the firewall — a false red that took
    a whole run to disbelieve, on an afternoon when four installs and a
    half-gigabyte bundle download were sharing the connection.

    Retrying does not soften either direction. A blackholed host is 127.0.0.1 and
    refuses immediately every time, so "reachable if any attempt got through" is
    the stricter reading of the blocked list as well as the fairer reading of the
    reachable one.
    """
    return any(machine.succeeds(command) for _ in range(attempts))


def blocked_host_args(environment: Environment) -> list[str]:
    if not environment.firewalled:
        return []
    blocked, _ = measured_network()
    return [argument for host in blocked for argument in ('--add-host', f'{host}:127.0.0.1')]


def start(environment: Environment, name: str) -> None:
    docker(
        'run',
        '-d',
        '--name',
        name,
        '--env',
        'DOTFILES_DOCKER_TEST=true',
        *blocked_host_args(environment),
        '--mount',
        f'type=bind,source={paths.REPO_ROOT},target=/dotfiles-src,readonly',
        environment.image,
        'sleep',
        'infinity',
        check=True,
    )


def copy_repo(machine: Machine) -> None:
    """The repo, writable, without `.git`, as a repo.

    `git init` because `install.sh` resolves the checkout with
    `git rev-parse --show-toplevel` — that is what makes it independent of where
    it was invoked from, and it is the same resolution a real clone gets.
    """
    home = machine.environment.home
    machine.exec(
        f'rm -rf {home}/dotfiles && mkdir -p {home}/dotfiles && shopt -s dotglob && '
        f'for item in /dotfiles-src/*; do '
        f'[ "$(basename "$item")" = .git ] && continue; cp -rp "$item" {home}/dotfiles/; done; '
        f'chown -R {machine.environment.user} {home}/dotfiles',
        user='root',
        check=True,
    )
    machine.exec(f'cd {home}/dotfiles && git init -q', check=True)


def newest_bundle() -> Path | None:
    """The most recent bundle an earlier run left in the repo root, if any."""
    existing = sorted(paths.REPO_ROOT.glob('dotfiles-offline-*-linux-x86_64.tar.gz'), key=lambda path: path.stat().st_mtime)
    return existing[-1] if existing else None


def build_bundle() -> Path:
    """Half a gigabyte and several minutes, on the machine that has the network.

    `--print-path` makes the archive's name the build's return value: it is named
    after the date, the manifest and the target platform, so anything downstream
    would otherwise have to reconstruct a name that changes every build. The log
    goes to stderr, leaving stdout carrying the path alone.
    """
    built = subprocess.run(
        ['uv', 'run', '--project', str(paths.REPO_ROOT), 'dotfiles', 'bundle', 'create', '--platform', 'linux-x86_64', '--print-path'],
        check=True,
        capture_output=True,
        text=True,
        cwd=paths.REPO_ROOT,
    )
    archive = Path(built.stdout.strip())
    if not archive.is_file():
        raise AssertionError(f'bundle build reported {archive}, which is not a file')
    return archive


def stage_bundle(machine: Machine, *, reuse: bool = False) -> Path:
    """Put a bundle where `install.sh --offline` will find it.

    Built on this machine rather than in the container, because building needs
    the network the container does not have — which is the whole point.

    `reuse` takes one an earlier run left behind. Off by default, because a stale
    bundle is exactly what would hide a change to the bundle format: the install
    would pass against the old layout and the format change would ship untested.
    """
    archive = (newest_bundle() if reuse else None) or build_bundle()
    docker('cp', str(archive), f'{machine.container}:{machine.environment.home}/', check=True)
    machine.exec(f'chown {machine.environment.user} {machine.environment.home}/{archive.name}', user='root', check=True)
    return archive
