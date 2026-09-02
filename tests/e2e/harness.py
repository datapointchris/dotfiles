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

import datetime as dt
import hashlib
import json
import os
import shlex
import subprocess
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from urllib.parse import urlsplit

from dotfiles import catalog
from dotfiles import engine
from dotfiles import evidence as ev
from dotfiles import machine as machines
from dotfiles import network
from dotfiles import paths
from dotfiles import resolve
from dotfiles.plan import DesiredItem
from dotfiles.plan import Precondition
from dotfiles.providers import clone
from dotfiles.providers import toolchain
from dotfiles.resources import symlinks
from dotfiles.session import Session

MARKERS = ('install.sh', 'tests/e2e/harness.py')
"""Files that together identify a dotfiles checkout and nothing else."""


def repo_under_test(start: Path | None = None) -> Path:
    """The checkout these tests came from, found by what is in it.

    Not `paths.REPO_ROOT`, which honors `$DOTFILES_DIR` — correct for the product,
    because the CLI must deploy the machine's repo from wherever it is invoked, and
    exactly wrong for a harness. `.zshenv` exports that variable to `~/dotfiles`, so
    an e2e run from a git worktree mounted `~/dotfiles` and installed *main's* code
    while reporting on the branch: a fix made on the branch showed as still broken,
    and a break on main showed as the branch's.

    Anchored on marker files rather than counting `parents[n]`, because a count is
    a claim about where this file sits in the tree — move it one directory and the
    answer silently becomes `tests/`, which every fixture then mounts as the repo.
    """
    for candidate in (start or Path(__file__).resolve()).parents:
        if all((candidate / marker).exists() for marker in MARKERS):
            return candidate
    raise RuntimeError(f'no dotfiles checkout above {start or __file__}: none of its parents holds {", ".join(MARKERS)}')


UNDER_TEST = repo_under_test()


def linked_worktree(checkout: Path) -> str | None:
    """The worktree's own name, or `None` for the checkout git calls the main one.

    Asked of git rather than of the path, because "is this a worktree" is a fact
    git holds: `--git-dir` answers `.git` for the main checkout and
    `<common>/worktrees/<name>` for a linked one.
    """
    completed = subprocess.run(('git', '-C', str(checkout), 'rev-parse', '--git-dir'), capture_output=True, text=True)
    if completed.returncode != 0:
        return None
    git_dir = Path(completed.stdout.strip())
    return git_dir.name if git_dir.parent.name == 'worktrees' else None


CHECKOUT = linked_worktree(UNDER_TEST)


def container_name(*parts: str) -> str:
    """A container name no other checkout of this repo can claim.

    Every name here was global — `dotfiles-e2e-archlinux` and two siblings — and
    every fixture that owns one begins by `docker rm -f`-ing it. Two checkouts
    running the same environment therefore did not queue, they destroyed each
    other: a `rm -f` at one run's exit killed the other's install at exit 137,
    which reads as an OOM. Naming them apart is what makes a second checkout safe
    to run in rather than a rule to remember.

    The main checkout keeps the bare name, so the containers already on the box
    stay reachable and the common case stays readable. Only a linked worktree
    takes a suffix, and it is that worktree's name because that is what says
    whose container it is in `docker ps`.
    """
    suffix = (
        () if CHECKOUT is None else (''.join(character if character.isalnum() or character in '_.-' else '-' for character in CHECKOUT),)
    )
    return '-'.join(('dotfiles-e2e', *parts, *suffix))


DOCKER_DIR = UNDER_TEST / 'tests' / 'install' / 'docker'

RESTRICTED_MANIFEST = 'wsl-work-workstation'
"""Whose plan the restricted rehearsal resolves, and the only thing read off a machine.

The manifest names the tools, so `network.derive` builds every URL an install
would reach from the declaration itself. Nothing here records what any real
network answered, which is the property that matters: a recorded verdict can only
be re-taken from the network it describes, so it goes stale between runs and the
rehearsal drifts from the declaration it is supposed to be testing.
"""

BLOCKED_HOSTS = (
    'awscli.amazonaws.com',
    'proxy.golang.org',
    'objects.githubusercontent.com',
    'release-assets.githubusercontent.com',
    'github-releases.githubusercontent.com',
)
"""The hosts this rig's firewall blackholes — a scenario, not a measurement.

Chosen for the install paths each one closes, because that is what the rehearsal
is for. A blocked registry kills a whole section and is what makes `go_tools`
prove the bundle path. A blocked vendor host kills one custom installer while its
neighbors keep working — `awscli` plays that part, and terraform-ls or mount-s3
would do as well, each being a custom installer with a vendor host to itself. What
the part needs is any one of those three; theme, font and bashselfupdate cannot
take it, since they share `raw.githubusercontent.com` and blocking it fails all
three at once. The three CDNs are the case a host blocklist otherwise
cannot express: github.com has to stay reachable for clones and the API, so the
only way to rehearse a refused release download is to take down the hosts an
asset redirects to.

github.com is deliberately absent, and that is the whole reason the CDNs are
named. Blackholing it takes theme, font, bashselfupdate and all four zsh plugins
with it, which manufactures failures and reads as a real firewall in a log.
"""

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
CONTAINER_PATH_DIRS = ('$HOME/' + SHADOW_BIN, *toolchain.TOOL_PATH_DIRS, *SYSTEM_PATH_DIRS)


# ─────────────────────────────────────────────────────────────────────────────
# The measured network
# ─────────────────────────────────────────────────────────────────────────────


# The agent the measurement used, and not cosmetic: crates.io answers curl's
# default agent with 403. `dotfiles.network` carries the same
# constant and the reason — a run that omitted it recorded crates.io as a firewall
# block, which would have meant bundling all nine cargo tools for nothing. A
# container re-probe that synthesizes its own request walks into it again, which
# is why `probe_command` replays the recorded one instead.
PROBE_AGENT = 'dotfiles-connectivity-test (+https://github.com/datapointchris/dotfiles)'


@dataclass(frozen=True)
class Probe:
    """One source an install reaches, and this rig's verdict on it."""

    verdict: str
    section: str
    name: str
    target: str
    reach: str = ''

    @property
    def host(self) -> str:
        return urlsplit(self.target if '//' in self.target else f'https://{self.target}').netloc

    @property
    def reachable(self) -> bool:
        return self.verdict == 'YES'

    @property
    def cloned(self) -> bool:
        """Whether this source is reached by cloning, which decides how it replays.

        Taken from REACH rather than from the section name, which is wrong for
        exactly the rows that matter: a custom installer is `custom_installer`
        whether it clones or downloads, and theme, font and bashselfupdate all
        clone. Read off the section, every one of them replayed as `curl --head`
        against a `.git` URL, which GitHub answers — so it passed for the wrong
        reason and a blocked git transport would have read as reachable.
        """
        return self.reach == 'clone'

    def command(self) -> str:
        """The same request the measurement made, to re-run inside a container.

        Re-running it rather than synthesizing `https://<host>/` is the whole
        point: the method, the URL and the agent all changed a verdict at least
        once, and a probe that differs from the recorded one is measuring a
        different question and calling the answer a firewall.

        **Including the fallback, which this dropped and which cost exactly what
        the paragraph above predicts.** `network.measure` tries HEAD and then a
        ranged GET, because S3 and some CDNs reject HEAD; this replayed only the
        first. `releases.hashicorp.com` answers HEAD with 405 — but only for a
        named agent, since curl's default gets a 200 — so `terraform-ls` was
        recorded reachable through the fallback and then re-probed without it.
        The container was blamed for a refusal that happens on any network,
        including this desk's.

        A shell `||` rather than two argv, which is the one place that is right:
        `network.measure` keeps them separate so each lands in the event stream
        on its own, and this is a single command string handed to a container.
        """
        if self.cloned:
            return f'GIT_TERMINAL_PROMPT=0 git ls-remote --quiet {shlex.quote(self.target)} HEAD'
        agent = shlex.quote(PROBE_AGENT)
        target = shlex.quote(self.target)
        head = f'curl -fsSL --head -A {agent} --connect-timeout 10 {target}'
        ranged = f'curl -fsSL -A {agent} --connect-timeout 10 -r 0-0 {target}'
        return f'{head} || {ranged}'


def measured_probes() -> tuple[Probe, ...]:
    """Every source the restricted manifest's plan reaches, verdict included.

    Resolved from the declaration through `network.derive`, which is the same
    function `dotfiles network check` builds its requests from — so a tool added
    to the manifest is rehearsed without anyone regenerating a file. A recorded
    measurement could only ever be re-taken behind the firewall it described, and
    went stale between every one of those runs.

    The verdict is this rig's, from `BLOCKED_HOSTS`. A container that blocks more
    than intended manufactures failures no machine has, and they read as real ones
    in a log — clone-based installers dying is the shape it takes, since theme,
    font, bashselfupdate and every zsh plugin come down that way.
    """
    derived = network.derive(machines.load(RESTRICTED_MANIFEST))
    return tuple(
        Probe(
            verdict='NO' if probe.host in BLOCKED_HOSTS else 'YES',
            section=probe.section,
            name=probe.name,
            target=probe.target,
            reach=str(probe.reach),
        )
        for probe in derived.probes
    )


def measured_network() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """`(blocked, reachable)` hosts, for building the container's `--add-host` set.

    The blocklist is declared and the reachable set is everything else the plan
    names, which is the direction that cannot go wrong: a host nobody chose to
    block stays resolvable, and a typo in `BLOCKED_HOSTS` blackholes nothing
    rather than blackholing something the rig depends on.

    Subtracted rather than intersected, so a blocked host never also arrives as an
    `--add-host` pair pointing at the real address.
    """
    reachable = {probe.host for probe in measured_probes() if probe.host} - set(BLOCKED_HOSTS)
    return tuple(sorted(BLOCKED_HOSTS)), tuple(sorted(reachable))


def reachable_probes() -> tuple[Probe, ...]:
    """One probe per reachable host *per method*.

    Per host alone would be cheaper and would silently drop every clone: the
    release rows come first and claim `github.com`, so the git path — the one
    carrying theme, font, bashselfupdate and all four zsh plugins — would never be
    re-probed at all. Two probes for that host, forty-odd rows collapsed to a
    dozen.
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
    because uv is installed by a later stage and the warning said it was
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

    converges: bool = True
    """Whether a finished install here is expected to have installed everything.

    False for the firewalled environment carrying no bundle, whose downloads are
    *meant* to fail — `test_the_firewall_actually_broke_something` asserts exit 3
    and says a run where nothing failed leaves the reporting untested.

    Declared rather than inferred from `firewalled and not offline`, because the
    two facts are separable: an environment could be arranged to fail for some
    other reason, and a reader of `test_machine.py` should not have to reconstruct
    the intent from a pair of unrelated flags.

    Without it, the four assertions that presume a converged machine were red on
    `restricted` forever, for the reason the environment exists — which is the
    same disease as a false red at any other rung: it makes the level unreadable,
    and an unreadable level is one nobody runs.
    """

    build_image: tuple[str, ...] = field(default_factory=tuple)
    """How to produce the image when it is absent, rather than failing."""

    @property
    def offline_flag(self) -> str:
        """`--offline` where this environment installs from a bundle, else ''.

        A property rather than the conditional written out at each caller, because
        the callers are the install and every later `dotfiles apply` against the
        machine it produced, and those have to agree. They did not: the
        second-apply test omitted it, reached the network this environment exists
        to do without, and installed the two toolchains the install had refused.
        """
        return ' --offline' if self.offline else ''


ARCHLINUX = Environment(
    name='archlinux',
    image='archlinux:latest',
    user='archlinuxuser',
    home='/home/archlinuxuser',
    manifest='archlinux-personal-workstation',
    # git only, and sudo for the stages that need it. No python either, which is
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
    firewalled=True,
    converges=False,
    build_image=('bash', str(DOCKER_DIR / 'build-base.sh')),
)

SCHEDULER = Environment(
    name='scheduler',
    image='debian:12',
    user='scheduleruser',
    home='/home/scheduleruser',
    manifest='scheduler',
    # The only environment here whose manifest is not a workstation, and the only
    # one on apt at `system_packages: core`. Every cargo and github_release entry
    # the profile names has to resolve there, and nothing else in this matrix asks
    # that question — archlinux is pacman, and the other three run the wsl-work
    # manifest.
    #
    # debian:12 rather than ubuntu, because the machine this stands in for is a
    # Proxmox LXC cloned from a Debian 12 template.
    # curl and git because `install.sh` requires them by name and debian:12 ships
    # neither — measured 2026-08-16, where the base image carries `tar` alone out
    # of curl, wget, git, sudo, unzip and xz. The archlinux prepare gets away with
    # `sudo git` because that base image already has the rest, which is what made
    # this the environment that says what a bootstrap actually needs.
    prepare=(
        'apt-get update && apt-get install -y --no-install-recommends sudo git curl ca-certificates',
        'useradd -m -s /bin/bash scheduleruser',
        "printf '%s\\n' 'scheduleruser ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers",
    ),
)

ENVIRONMENTS = (ARCHLINUX, WSL, OFFLINE, RESTRICTED, SCHEDULER)


@dataclass(frozen=True, slots=True)
class Verdict:
    """What to do about a machine level that may not be startable here."""

    action: str
    reason: str = ''


def machine_verdict(*, docker_running: bool, image_present: bool, buildable: bool, required: bool) -> Verdict:
    """Whether a level that needs a container runs, builds, skips, or refuses.

    `required` is the runner's answer, not the machine's, and it is the whole
    point: a workstation running the fast suite should skip what it cannot start,
    while a run that asked for `fresh-install` has already said it wants a
    machine. `tests/conftest.py` § `resolve_interpreters` draws the same line for
    bash, zsh and tmux.

    Measured 2026-08-16: without the refusal, `debian:12` being absent skipped all
    97 cases, pytest exited 0, and `matrix.py` reported
    `pass  fresh-install/scheduler  3.2s` for a rung documented at 20-30 minutes.
    Every environment is exposed — `archlinux:latest` declares no builder either
    and works only because it is already pulled here.

    Docker is asked about first because `docker image inspect` fails for both
    reasons and cannot say which.
    """
    if not docker_running:
        return Verdict('refuse' if required else 'skip', 'Docker is not running')
    if image_present:
        return Verdict('run')
    if buildable:
        return Verdict('build')
    reason = 'image is absent and nothing here builds it'
    return Verdict('refuse' if required else 'skip', reason)


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
    an interpreter is expected, anything else reaching for `python3` is the bug
    this step deleted.
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


LATEST_RECORD = '${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles/latest-$(echo "$HOSTNAME" | cut -d. -f1 | tr "[:upper:]" "[:lower:]")'
"""`paths.LATEST_RUN`, spelled for a shell because it is read inside the container.

The suffix is *derived*, never globbed. `paths.LATEST_RUN` gained a
`-{machine_id}` suffix when the state directory became fleet-shared, and naming
the old path made the `cp` match nothing — so a `latest-*` glob replaced it, and
that is worse in a way the first fault was not. A glob is silent when it matches
nothing and *fatal* when it matches twice: `cp a b file` fails with "target is
not a directory", and every test taking the `machine` fixture then errors after
a converged install.

Which it does, because the base image bakes a record from the build. That build
runs as a machine named `buildkitsandbox`, and its `latest-buildkitsandbox`
lives in the image beside the container's own.

`$HOSTNAME` cut at the first dot and lowercased is `paths.machine_id` in shell,
which reads `socket.gethostname()`. Bash sets that variable itself, so it needs no
binary — `hostname` is absent on the Arch image, where deriving through it
resolved to `latest-` and matched nothing on every environment but Ubuntu.

One box per container, so it resolves to exactly one path or to none at all."""

INSTALL_LOG = '.dotfiles-install-log'
INSTALL_STATUS = '.dotfiles-install-status'
INSTALL_RECORD = '.dotfiles-install-record'
"""The run record *this* install wrote, kept beside its log and status.

`dotfiles/latest` is whatever ran most recently, which stops being this install
the moment anything else applies — and something always does, because
`test_a_second_apply_over_a_converged_machine_changes_nothing` is the next thing
in the file. At the `existing-install` rung that made `run_record` answer with the
second apply while `install_status` and `install_log` still answered with the
install, so `test_the_run_reports_its_own_outcome` compared one run's exit code
against another run's outcomes: a clean second apply hides the install's failures,
and a failing one invents failures for an install that had none.
"""


def install_command(environment: Environment, through: str = '') -> str:
    """`install.sh` and the `dotfiles apply` it hands to, as one recorded run.

    Two commands rather than one since the bootstrap stopped converging the
    machine itself, and the pair is what an install *is* here — a container the
    bootstrap alone touched would answer no question this tier asks. Chained with
    `&&`, so an apply never runs against a machine whose CLI failed to install and
    the recorded status is whichever half ended the run.

    Persisted rather than only returned, because the install is the expensive
    artifact and every question about it gets asked again the moment an assertion
    changes — twice today, once because a container died and once because a test
    was added after the run started. `PIPESTATUS[0]` because `tee` is whose exit
    status the shell would otherwise report, and it always succeeds.

    All three artifacts are copied out, not two. The record is pinned for the same
    reason as the log: `dotfiles/latest` moves under the next apply, and the next
    apply is a test in the same file.
    """
    home = environment.home
    offline = environment.offline_flag
    ceiling = f' --through {through}' if through else ''
    return (
        f'cd {home}/dotfiles && {{ ./install.sh --machine {environment.manifest}{offline} '
        f'&& dotfiles apply --machine {environment.manifest}{offline}{ceiling}; }} 2>&1 '
        f'| tee {home}/{INSTALL_LOG}; echo ${{PIPESTATUS[0]}} > {home}/{INSTALL_STATUS}; '
        f'cp {LATEST_RECORD} {home}/{INSTALL_RECORD} 2>/dev/null || true'
    )


def install_record(machine: Machine) -> tuple[int, str] | None:
    """The status and log of the install in this container, or None if there is none.

    All three artifacts are required to call one present. A container carrying a log
    and a status but no pinned record predates `INSTALL_RECORD`, and reusing it
    would pass `--installed` and then fail every assertion that reads the record —
    a rebuild reported as thirty broken tests.
    """
    status = machine.read(f'cat {machine.environment.home}/{INSTALL_STATUS} 2>/dev/null').strip()
    if not status.isdigit():
        return None
    if not machine.succeeds(f'test -s {machine.environment.home}/{INSTALL_RECORD}'):
        return None
    return int(status), machine.exec(f'cat {machine.environment.home}/{INSTALL_LOG} 2>/dev/null').stdout


def install_record_gap(machine: Machine) -> str:
    """Which of the artifacts is missing, for a caller that has to say why.

    `install_record` collapses two unrelated failures into one `None`: an install
    that never finished, and a finished install whose record was not copied out.
    Reporting the first for the second cost an afternoon — the `LATEST_RECORD`
    path had moved, the `cp` matched nothing, and 249 tests blamed an install
    that had in fact converged.
    """
    home = machine.environment.home
    if not machine.read(f'cat {home}/{INSTALL_STATUS} 2>/dev/null').strip().isdigit():
        return f'{INSTALL_STATUS} is absent or holds no number, so the install did not reach the end of the command{_install_tail(machine)}'
    return (
        f'{INSTALL_STATUS} is present, so the install ran — but {INSTALL_RECORD} is empty, '
        f'so {LATEST_RECORD} matched nothing{_install_tail(machine)}'
    )


def _install_tail(machine: Machine) -> str:
    """The end of the install log, appended to whatever gap is being reported.

    The log is written by `tee` and survives every failure, and the fixture that
    raises this discards it — so the one artifact that says *why* is the one
    nobody sees. Diagnosing a failed install then costs a second run of the
    install, which is forty minutes to learn something already on disk.
    """
    home = machine.environment.home
    tail = machine.read(f'tail -n 40 {home}/{INSTALL_LOG} 2>/dev/null')
    return f'\n\n--- last 40 lines of {INSTALL_LOG} ---\n{tail}' if tail else ''


def install_age(machine: Machine) -> str:
    """When that install ran, so a stale one cannot be mistaken for this run's."""
    return machine.read(f'date -r {machine.environment.home}/{INSTALL_STATUS} 2>/dev/null') or 'an unknown time'


def run_record(machine: Machine) -> dict:
    """What *this install* recorded about itself, as values rather than console text.

    The alternative is grepping `install_log` for a sentence the run printed,
    which pins an English fragment: reword it and the test fails with nothing
    wrong. Every count these assertions want is a field here.

    Read from the copy the install pinned rather than from `dotfiles/latest`, so it
    describes the same run as `install_status` and `install_log` beside it. See
    `INSTALL_RECORD`. A container installed before that copy existed has none, and
    says so rather than answering with whatever ran last.
    """
    pinned = f'{machine.environment.home}/{INSTALL_RECORD}'
    written = machine.read(f'cat {pinned} 2>/dev/null')
    assert written.strip(), (
        f'no run record pinned at {pinned}. An install writes one; a container '
        f'from before it did needs rebuilding without --installed/--reuse.'
    )
    return json.loads(written)


def failed_outcomes(machine: Machine) -> list[str]:
    """Every address the run tried to repair and could not."""
    return [outcome['address'] for outcome in run_record(machine)['outcomes'] if outcome['action'] == 'failed']


def refused_outcomes(machine: Machine) -> list[str]:
    """Every address the run reached, wrote nothing for, and explained.

    Not a failure and not a success: an offline machine has no go.dev to fetch a
    toolchain from, so its run converges with the Go and Rust runtimes refused and
    the tools they would have built taken from the bundle instead.

    Separate from `failed_outcomes` because the exit code separates them, and
    because the verification script has to agree with this list — the tools it
    finds absent are supposed to be exactly the ones named here.
    """
    return [outcome['address'] for outcome in run_record(machine)['outcomes'] if outcome['action'] == 'refused']


def recorded_as(item: DesiredItem) -> str:
    """How a run record spells one item.

    `sinks.py` writes `f'{event.resource}/{change.item}'`, and every resource
    passes `item.address`. This matched two spellings until `toolchains` was the
    last one passing `item.name` — an item addressed `go-toolchain/go` recorded as
    `toolchains/go`, so a caller holding a resolved plan could not look it up
    without knowing which resource had written it.

    Deliberately not the shell script's answer, which keyed on the address's last
    segment because it had no `resource` to hand — and so let anything named
    `awscli` excuse every absent `aws`, whichever provider had refused.
    """
    return f'{item.resource}/{item.address}'


def refusals(machine: Machine) -> dict[str, str]:
    """The same set, keyed by address and carrying the reason each gave.

    Addressed as the record writes them — `packages/go/sesh`, which is
    `f'{item.resource}/{item.address}'` — so a caller matches an item exactly
    rather than on its last segment. Keyed on the segment alone, anything named
    `awscli` excuses every absent `aws`, whichever provider had
    refused.
    """
    return {
        outcome['address']: outcome.get('message') or 'no reason recorded'
        for outcome in run_record(machine)['outcomes']
        if outcome['action'] == 'refused'
    }


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


def github_token() -> str:
    """The host's GitHub credential, or '' where there is none.

    `gh` rather than a checked-in secret or a CI variable: the credential is
    already on this machine and already refreshed, so nothing has to be stored to
    use it. `GITHUB_TOKEN` wins where it is set, which is how a caller points a run
    at a different account without logging `gh` out of this one.
    """
    if existing := os.environ.get('GITHUB_TOKEN'):
        return existing
    found = subprocess.run(['gh', 'auth', 'token'], check=False, capture_output=True, text=True)
    return found.stdout.strip() if found.returncode == 0 else ''


def github_token_args() -> list[str]:
    """`--env GITHUB_TOKEN` for the container, and the export that makes it resolve.

    **An install needs one.** Anonymous GitHub API calls are 60 an hour *per public
    IP*, and the container shares the host's — so one full install spends most of
    that budget and a second inside the hour answers "did not answer with a
    release" for every release tool. That is indistinguishable from a broken
    installer, which is how a red run gets blamed on code that is fine and a real
    break gets waved through as "just the rate limit".

    Passed by name rather than as `GITHUB_TOKEN=<value>`, so the secret is not in
    an argument list that `ps` or a shell history can read. Docker resolves it from
    this process, which is what the export is for; it is still in the container's
    own environment afterwards, which is the point of sending it.

    Empty where there is no credential rather than raising: an anonymous run is
    degraded, not impossible, and `conftest` says so once at the top of the session
    so a rate-limited failure is never mistaken for a code one.
    """
    token = github_token()
    if not token:
        return []
    os.environ['GITHUB_TOKEN'] = token
    return ['--env', 'GITHUB_TOKEN']


def authenticate_git(machine: Machine) -> None:
    """Let git reach a private repo, the way this fleet's machines already do.

    A real machine runs `gh auth setup-git`, which writes a credential helper of
    `!gh auth git-credential`. A container has neither `gh` logged in nor a helper,
    so a `git fetch` of a private tag prompts for a username, finds prompts
    disabled, and fails — which is what `git_uv_tools` pinned to a private release
    hits, and it reads as a broken installer rather than a missing credential.

    The helper reads `$GITHUB_TOKEN` at call time rather than embedding it, so the
    token stays in the container's environment and never lands in a config file, a
    command line, or an image layer. Same shape as the host's, one indirection
    further out.
    """
    if not github_token():
        return
    helper = '!f() { echo username=x-access-token; echo "password=$GITHUB_TOKEN"; }; f'
    machine.exec(f'git config --global credential."https://github.com".helper {shlex.quote(helper)}')


def start(environment: Environment, name: str) -> None:
    docker(
        'run',
        '-d',
        '--name',
        name,
        '--env',
        'DOTFILES_DOCKER_TEST=true',
        *github_token_args(),
        *blocked_host_args(environment),
        '--mount',
        f'type=bind,source={UNDER_TEST},target=/dotfiles-src,readonly',
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


# ─────────────────────────────────────────────────────────────────────────────
# The base image: system packages, installed once and reused
# ─────────────────────────────────────────────────────────────────────────────

BASE_STAGE = 'system_upgrade'
"""How far a base container converges.

The last of the three `SYSTEM*` stages, so a base carries the packages, the app
stores built on them, and nothing that depends on a tool. Named as a stage rather
than as a resource because `dotfiles system apply` would also run
`SYSTEM_CONFIG` — group memberships, units, the login shell — which sits at the
*end* of the whole order and needs packages a set installs later.
"""

BASE_REPOSITORY = 'dotfiles-e2e-base'

BASE_LEDGER = 'e2e-bases.json'
"""What each base image was built from, under `$XDG_CACHE_HOME/dotfiles`.

The image is the artifact and docker's store is its cache — `docker save` into
this directory would duplicate multiple GB that docker already manages, and
reloading it costs minutes a tag lookup does not. What docker cannot answer is
*which plan* a tag came from, so that is what lives here: enough to report on the
bases, prune the superseded ones, and explain why a rebuild happened.
"""


# ─────────────────────────────────────────────────────────────────────────────
# What the machine should be carrying, and one sweep that asks it
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Declared:
    """One item, and which environment's manifest asked for it.

    The environment travels with the item because `container` is parametrized by
    the fixture's own `params` and pytest refuses to parametrize it twice — so the
    pairing cannot be expressed as one `metafunc.parametrize` over both names.
    What happens instead is the cross product, cut back to the matched pairs in
    `pytest_collection_modifyitems`, and this is what lets that comparison be made.
    """

    environment: str
    item: DesiredItem


def declared_items(environment: Environment) -> tuple[DesiredItem, ...]:
    """Every item this environment's manifest resolves to, in address order.

    The resolver's answer rather than a reading of `packages.yml`, for the same
    reason `base_plan` takes it: a tool added or removed changes what is verified
    with no list here to update. It is also strictly wider than the shell script
    this replaced, which asked a helper that knew only some of the sections — 141
    checks against the 214 items Arch resolves.

    Sorted so the parameter ids a run prints are stable between collections.
    """
    plan = resolve.resolve(catalog.load(), machines.load(environment.manifest))
    return tuple(sorted(plan.items, key=lambda item: item.address))


def shell_path(declared: str) -> str:
    """A declared path as shell that expands, with everything else quoted.

    `~` is expanded by the shell before quoting and not after, so the obvious
    `shlex.quote('~/.local/bin/x')` produces a literal directory named `~` and
    every path-evidenced item reads as missing.
    """
    if declared.startswith('~/'):
        return f'"$HOME"/{shlex.quote(declared[2:])}'
    return shlex.quote(declared)


def probe_of(item: DesiredItem) -> str:
    """The shell that answers where one item is, or '' for one asked another way.

    **Its own observation, deliberately, and not `dotfiles check`.** The tier
    exists to say whether the install worked, and a checker that agreed with the
    installer because they share the code that decides what "installed" means
    would answer that question by assuming it.

    A plugin is a checkout and puts nothing on PATH, so `clone.destination` is
    asked where it belongs — the declaration's answer, which TPM is separately
    *told*, and not a directory named here. Without this the zsh plugins, TPM and
    tmux-fzf would be silently unexamined, which is coverage the shell script had.
    Asked home-relative and left that way: `exec_script` exports the container's
    `HOME`, so `"$HOME"` is the one spelling that is right in every environment
    and this stays a pure function of the item.

    **Empty for a registry package, which PATH cannot answer for.** `command -v
    7zip` fails on Arch against a `7zip` that is installed and working, because
    the package ships `7z`; `build-essential` and `libssl-dev` name no binary at
    all. Asking PATH about system packages fails a large share of them, so those
    are `registry_names`' question instead.

    Empty too for an item with no evidence of any kind — a macOS default, a
    systemd unit, a group membership. Each is real and is somebody else's
    assertion; what none of them is, is a file this can look for.
    """
    if registry_names(item):
        return ''
    if item.evidence_path:
        target = item.evidence_path
    elif isinstance(item.entry, catalog.ShellPlugin | catalog.TmuxPlugin | catalog.YaziPlugin):
        target = str(clone.destination(item, Path('~')))
    elif item.executable:
        return f'command -v {shlex.quote(item.executable)}'
    else:
        return ''
    return f'[ -e {shell_path(target)} ] && printf %s {shell_path(target)}'


def registry_names(item: DesiredItem) -> dict[str, list[str]]:
    """Query name → the names this entry goes by there, for a package a manager owns.

    `evidence.declared_names` is the declaration's own table — the entry is
    `7zip` and the package is `p7zip-full` on apt and `7zip` on pacman — and
    reusing it is reusing the declaration, not the evidence. `INSTALLER_QUERIES`
    is what collapses `aur` onto pacman's query, an AUR package being a pacman
    package once it is installed.
    """
    named: dict[str, list[str]] = {}
    for installer, names in ev.declared_names(item).items():
        named.setdefault(ev.INSTALLER_QUERIES[installer], []).extend(names)
    return named


PRECONDITION_PROBES: dict[Precondition, str] = {
    Precondition.AMD_GPU: '[ -e /dev/kfd ]',
    Precondition.GITHUB_AUTH: '[ -n "${GITHUB_TOKEN:-}" ]',
}
"""How to ask the container whether a declared precondition holds there.

Measured rather than assumed, and measured *here* rather than through
`evidence.measured_preconditions`, which would ask the host. An item whose
precondition fails was never installable, so `repair_for` makes it `BY_HAND`,
`apply` never attempts it, and **nothing is recorded** — not a refusal either. So
a run record cannot excuse it and this is the only thing that can: ollama declares
`requires_amd_gpu`, no container has a `/dev/kfd`, and it failed here as a missing
package on a machine that was right not to have it.
"""


def probe_script(items: Sequence[DesiredItem]) -> str:
    """One script asking after every item, rather than one `exec` each.

    Two hundred `docker exec` calls is half a minute per environment spent on
    process startup, and the per-item nodes this feeds want the answer before the
    first of them runs. The same lesson as `Inventories`: ask the machine once,
    and ask each package manager once rather than once per package.

    Three kinds of line, tagged, because a tab cannot appear in a path, a package
    name or a manager's name — where a space appears in all three.
    """
    lines = [
        f'printf \'held\\t%s\\t%s\\n\' {precondition} "$({probe} && echo yes || true)"'
        for precondition, probe in PRECONDITION_PROBES.items()
        if any(item.precondition is precondition for item in items)
    ]
    # Guarded on the binary existing, and that guard is the whole point: a manager
    # this machine does not have must leave *no* line, so an apt-only package on
    # Arch is unaskable rather than reported absent. Piping a missing command
    # through `tr` succeeds with empty output, which reads identically to a
    # manager that answered and listed nothing.
    lines += [
        f'command -v {ev.QUERIES[query][0]} >/dev/null 2>&1 && '
        f"printf 'listed\\t%s\\t%s\\n' {query} \"$({shlex.join(ev.QUERIES[query])} 2>/dev/null | tr '\\n' ' ')\""
        for query in sorted({query for item in items for query in registry_names(item)})
        if query in ev.QUERIES
    ]
    lines += [
        f'printf \'found\\t%s\\t%s\\n\' {shlex.quote(item.address)} "$({probe} 2>/dev/null || true)"'
        for item in items
        if (probe := probe_of(item))
    ]
    return '\n'.join(lines)


@dataclass(frozen=True)
class Sweep:
    """What one run of `probe_script` found, as three answers rather than one.

    `listed` holding no entry for a manager and holding an empty set for it are
    different facts, and the difference decides a skip against a failure: apt on
    Arch cannot be asked, while pacman answering with nothing means the package is
    not there.
    """

    found: dict[str, str]
    """Address → where the machine has it, '' where it looked and found nothing."""

    listed: dict[str, frozenset[str]]
    """Query name → what that manager says it has, for the ones that answered."""

    held: frozenset[Precondition]
    """Which declared preconditions this machine actually meets."""

    def observed(self, item: DesiredItem) -> bool | None:
        """Whether the machine has one item, or None where nothing could ask.

        None is not a pass. It is what the per-item test skips on, and the reason
        is always the machine rather than the item: no manager that could answer,
        or an item whose evidence is not a file, a binary or a package.
        """
        if item.precondition is not Precondition.NONE and item.precondition not in self.held:
            return None
        if names := registry_names(item):
            answerable = {query: found for query, found in names.items() if query in self.listed}
            if not answerable:
                return None
            return any(name in self.listed[query] for query, found in answerable.items() for name in found)
        if item.address in self.found:
            return bool(self.found[item.address])
        return None


def probed(machine: Machine, items: Sequence[DesiredItem]) -> Sweep:
    """Run the sweep and read its three kinds of line back."""
    answered = machine.exec(probe_script(items))

    found: dict[str, str] = {}
    listed: dict[str, frozenset[str]] = {}
    held: set[Precondition] = set()
    for line in answered.stdout.splitlines():
        kind, tab, rest = line.partition('\t')
        subject, tab, value = rest.partition('\t')
        if not tab:
            continue
        if kind == 'found':
            found[subject] = value.strip()
        elif kind == 'listed':
            listed[subject] = frozenset(value.split())
        elif kind == 'held' and value.strip() == 'yes':
            held.add(Precondition(subject))

    return Sweep(found=found, listed=listed, held=frozenset(held))


def declared_links(environment: Environment) -> tuple[Path, ...]:
    """Every path the symlink manager says this machine should have, sorted.

    `resources.symlinks.declared` is a walk of the repo and reads no `$HOME`, so
    the host can answer for the container: same checkout, and the targets are
    built under the container's home rather than this one's.

    Derived rather than listed, which is the whole difference from the script this
    replaces — that one named `zshrc`, `tmux.conf`, `gitconfig` and `init.lua`,
    four of the several hundred, chosen once and never revisited.
    """
    machine = machines.load(environment.manifest)
    session = Session(machine_name=environment.manifest, repo=UNDER_TEST, home=Path(environment.home))
    return tuple(sorted(link.target for link in symlinks.declared(session, machine.coordinates)))


def deployed_script(targets: Sequence[Path]) -> str:
    """One `test -e` per declared link, in a single script.

    `-e` and not `-L`: what matters is that the path resolves to something, and a
    machine where safekeep restored a real file over a link is a different finding
    from one where the pass never ran.
    """
    return '\n'.join(f"[ -e {shlex.quote(str(target))} ] || printf '%s\\n' {shlex.quote(str(target))}" for target in targets)


def unexplained_copies(machine: Machine, items: Sequence[DesiredItem]) -> dict[str, tuple[str, ...]]:
    """Declared binaries the machine answers to more than once, minus the explained.

    The same two explanations `resources.packages._shadowing` applies, reached
    independently: a copy the OS package manager attributes to a package this
    manifest declares, and a copy owned by a package installed to satisfy
    something else. Both are declaration questions rather than evidence ones,
    which is why sharing them costs no independence — what is not shared is
    anything that decides whether a thing is installed.

    Two `exec` calls and only when the first finds something, because on a
    converged machine it usually finds nothing.
    """
    swept = machine.exec(copies_script(items))
    duplicated = {
        binary: tuple(found.split())
        for binary, tab, found in (line.partition('\t') for line in swept.stdout.splitlines())
        if tab and len(found.split()) > 1
    }
    if not duplicated:
        return {}

    declared = {
        name
        for item in items
        if isinstance(item.entry, catalog.SystemPackage)
        for installer in ('apt', 'pacman', 'aur', 'brew')
        if (name := item.entry.package_for(installer))
    }
    every = [path for paths in duplicated.values() for path in paths]
    answered = machine.exec(ownership_script(every))

    explained = set()
    for line in answered.stdout.splitlines():
        path, tab, owner = line.partition('\t')
        if tab and owner.strip() and (owner.strip() in declared or owner.strip().startswith('unchosen:')):
            explained.add(path)

    return {
        binary: remaining for binary, paths in duplicated.items() if len(remaining := tuple(p for p in paths if p not in explained)) > 1
    }


def ownership_script(paths: Sequence[str]) -> str:
    """Who put each of these here, and whether anybody asked for it.

    `unchosen:` prefixes a package the manager installed to satisfy something
    else — yay needs a compiler, so pacman's Go sits under the tarball's on every
    machine that builds an AUR package, and nobody can be told to remove it.
    """
    return '\n'.join(
        f'owner="$(pacman -Qoq {shlex.quote(path)} 2>/dev/null || dpkg-query -S {shlex.quote(path)} 2>/dev/null | cut -d: -f1)"; '
        f'if [ -n "$owner" ] && {{ pacman -Qdq "$owner" >/dev/null 2>&1 || apt-mark showauto "$owner" 2>/dev/null | grep -qx "$owner"; }}; '
        f'then owner="unchosen:$owner"; fi; '
        f'printf \'%s\\t%s\\n\' {shlex.quote(path)} "$owner"'
        for path in paths
    )


def copies_script(items: Sequence[DesiredItem]) -> str:
    """Every path each declared binary answers to, resolved through its symlinks.

    `type -aP` rather than `command -v`, which answers with the winner alone —
    the whole question here is how many there are. Resolved in the container
    because a symlink means nothing off the machine it is on, and
    `~/.local/bin/fd` pointing at `/usr/bin/fd` is one installation with two
    names rather than a duplicate.
    """
    lines = [
        f"printf '%s\\t%s\\n' {shlex.quote(binary)} "
        f'"$(type -aP {shlex.quote(binary)} 2>/dev/null | while read -r found; do readlink -f "$found"; done | sort -u | tr \'\\n\' \' \')"'
        for binary in dict.fromkeys(item.executable for item in items if item.executable)
    ]
    return '\n'.join(lines)


def base_plan(environment: Environment) -> tuple[str, ...]:
    """Every item a base container is expected to carry, as addresses.

    The resolver's answer rather than a reading of `packages.yml`, because that is
    what the install will do — an item is in the base if and only if the plan puts
    it at or below `BASE_STAGE`.
    """
    ceiling = engine.stage_named(BASE_STAGE)
    plan = resolve.resolve(catalog.load(), machines.load(environment.manifest))
    return tuple(sorted(item.address for item in plan.items if item.stage <= ceiling))


def base_digest(environment: Environment) -> str:
    """What makes one base different from another, and nothing else.

    Content-addressed on the *plan* rather than on `packages.yml`, so a comment
    edit or a reordering does not rebuild multiple GB while a manifest that stops
    subscribing to a package does. The source image id is in it because a base is
    that image plus this plan, and `archlinux:latest` moves under its own tag.

    What it deliberately cannot see is which *versions* the distro shipped —
    correct for a system base, since pacman decides that and nothing here pins it,
    but it means a base can be stale in a way no digest catches. `BASE_MAX_AGE` is
    the answer to that half.
    """
    source = docker('image', 'inspect', '--format', '{{.Id}}', environment.image).stdout.strip()
    material = '\n'.join([source, *base_plan(environment)])
    return hashlib.sha256(material.encode()).hexdigest()[:12]


def base_tag(environment: Environment) -> str:
    """The digest alone, so environments resolving to the same base share one image.

    The environment's name was in front of it, and was the only thing separating
    `offline` from `restricted`: identical source image, identical manifest,
    therefore identical digest and the same multi-GB image built and stored twice.
    What an environment *is* beyond that — firewalled, carrying a bundle, expected
    to converge — decides how the install is run against the base, never what the
    base contains, and `base_digest` already says so in the sentence above.
    """
    return f'{BASE_REPOSITORY}:{base_digest(environment)}'


BASE_MAX_AGE = dt.timedelta(days=14)
"""When a base is rebuilt despite its digest still matching.

The digest covers what this repo declares; it cannot cover what the distro
shipped, so an unchanged plan against a moved archive silently tests two-week-old
packages. Long enough that a base survives a working week of changes to anything
else, short enough that "it passed on the base" keeps meaning something.
"""


def ledger_path() -> Path:
    return paths.cache_home() / BASE_LEDGER


def ledger() -> dict[str, dict[str, object]]:
    """What the recorded bases are, or nothing.

    A missing file is an ordinary first run and says nothing. A *corrupt* one is
    not, and it costs the same multi-GB rebuild every time, so it is warned about
    rather than folded into the same silence.
    """
    path = ledger_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as unreadable:
        warnings.warn(f'the base-image ledger at {path} is unreadable, so every base will be rebuilt: {unreadable}', stacklevel=2)
        return {}


def record_base(tag: str, environment: Environment, built: dt.datetime) -> None:
    """Write what this tag holds, so a later run can explain and prune it.

    What *made* the image, never which environment asked for it. A tag is reached
    by every environment whose digest matches, so recording the one that happened
    to build it first would read as an ownership it does not have — and would be
    wrong the moment the other one reuses it.
    """
    entries = ledger()
    entries[tag] = {
        'source_image': environment.image,
        'manifest': environment.manifest,
        'through': BASE_STAGE,
        'built': built.isoformat(),
        'items': list(base_plan(environment)),
    }
    path = ledger_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries, indent=2, sort_keys=True) + '\n')
    except OSError as unwritable:
        # Loud, because `base_is_fresh` treats an unrecorded tag as stale: a
        # silently unwritable cache means every run rebuilds a multi-GB base, takes
        # ten minutes, and looks exactly like a normal first build.
        warnings.warn(f'could not record the base image in {path}, so it will be rebuilt every run: {unwritable}', stacklevel=2)


def base_is_fresh(tag: str, now: dt.datetime) -> bool:
    """Whether an existing tag is still worth reusing.

    Both halves have to hold: the image is there, and what the ledger says about
    it is recent enough. A tag with no ledger entry is treated as stale rather
    than trusted — it was built by something that did not record what it built.
    """
    if not image_exists(tag):
        return False
    recorded = ledger().get(tag, {}).get('built')
    if not isinstance(recorded, str):
        return False
    try:
        return now - dt.datetime.fromisoformat(recorded) < BASE_MAX_AGE
    except ValueError:
        return False


def build_base(environment: Environment, now: dt.datetime | None = None) -> str:
    """The base image for this environment, built if there is not a fresh one.

    The repo is deliberately *not* baked in. `conftest.py` records what happens
    when a container reuses OS state and the repo together — the Arch harness
    tested whatever code was mounted when the container was created, so a fix made
    since reported as still broken. A base carries OS state; the code arrives on
    every run.

    The builder container is named per environment even though the tag is not, so
    two environments sharing a base and running concurrently cannot `docker rm -f`
    each other's build. They both build it and both commit the same tag, which
    wastes one build and corrupts nothing; sequentially — which is what one pytest
    session does — the second finds the first fresh and skips it.
    """
    tag = base_tag(environment)
    stamp = now or dt.datetime.now(dt.UTC)
    if base_is_fresh(tag, stamp):
        return tag

    builder = container_name('base-build', environment.name)
    docker('rm', '-f', builder)
    start(environment, builder)
    machine = Machine(environment=environment, container=builder)
    try:
        for command in environment.prepare:
            machine.exec(command, user='root', check=True)
        copy_repo(machine)
        authenticate_git(machine)
        plant_python_shadow(machine)
        if environment.env_file:
            machine.exec(f'printf %s {shlex.quote(environment.env_file)} > {environment.home}/.env', check=True)
        machine.exec(install_command(environment, through=BASE_STAGE))

        # The recorded status, never the shell's. `install_command` pipes through
        # `tee` and ends in an `echo`, so the command always exits 0 and a
        # `check=True` here would commit an image whose install had failed — which
        # it did once, producing a 795MB base carrying none of the 99 packages it
        # is named after.
        recorded = install_record(machine)
        if recorded is None or recorded[0] != 0:
            detail = recorded[1][-2000:] if recorded else install_record_gap(machine)
            raise RuntimeError(f'base install for {environment.name} did not converge:\n{detail}')

        # Committed after the repo is removed, so nothing downstream can read a
        # checkout the image froze — the failure mode the note above describes.
        machine.exec(f'rm -rf {environment.home}/dotfiles', check=True)
        shed_caches(machine)
        docker('commit', builder, tag, check=True)
    finally:
        docker('rm', '-f', builder)

    record_base(tag, environment, stamp)
    return tag


CACHE_PATHS = ('/var/cache/pacman/pkg', '/var/cache/apt/archives', '{home}/.cache')
"""Download caches a base has no use for, cleared before it is committed.

Not a micro-optimization: they were 2.4 GB of a 14.4 GB Arch base, and a base is
kept per environment for two weeks on a root volume `.planning/status.md` already
records as too small. What they hold is packages already installed and archives
already unpacked — a set installing over this image re-downloads what *it* needs
and nothing here would have been a hit for it.
"""


def shed_caches(machine: Machine) -> None:
    for path in CACHE_PATHS:
        machine.exec(f'rm -rf {path.format(home=machine.environment.home)}', user='root')
