"""Two containers and the shelf between them, so the host never runs the code.

`bundle create` used to run on the host, out of the worktree, through
`uv run --project UNDER_TEST`. That made the test runner the code under test:
editing a source file mid-run changed what was being measured, and the only
defence was not editing. It also meant the one machine in the trip that had a
network was not a machine at all, so nothing about the builder was ever asserted.

So the trip is two containers on one docker network. `BUILDER` has a network and
builds; the offline environment has GitHub blackholed and installs. Neither is
the host, and the host only drives docker.

**The shelf is served over ssh by the builder, and the transport is declared the
way `ifiles` is declared.** dotfiles reads a program name and an argv per
operation out of `[remote.transport]`, so `shelf-transport.sh` implementing the
same six operations puts `src/dotfiles/remote.py` on the trip rather than beside
it — the probe, the one-name-per-line listing contract, and the digest check
around push and pull. Stopping the builder makes the peer genuinely unreachable,
which is the one thing a fake transport cannot be.

The offline container reaching the builder while GitHub stays blocked is not a
compromise in the model. It is the arrangement being rehearsed: the work box
reaches an internal file server and cannot reach GitHub, and `firewalled`
blackholes hosts by name rather than cutting the network.
"""

from __future__ import annotations

import shlex
import tempfile
from pathlib import Path

from harness import DOCKER_DIR
from harness import Environment
from harness import Machine
from harness import container_name
from harness import docker

NETWORK = 'dotfiles-e2e-exchange'
"""The docker network both containers join, so each resolves the other by name."""

SHELF_ROOT = '/srv/shelf'
"""Where the builder keeps what has been published, and the `root` both declare.

Outside either home directory on purpose. A shelf under `~` would be carried by
the repo copy and by the install, and a bundle appearing because something copied
it is exactly the result this is meant to disprove.
"""

TRANSPORT = '/usr/local/bin/shelf-transport'

TRANSPORT_SOURCE = DOCKER_DIR / 'shelf-transport.sh'

KEY = '/home/{user}/.ssh/id_ed25519'

BUILDER = Environment(
    name='builder',
    image='dotfiles-test-base:ubuntu-26.04',
    user='testuser',
    home='/home/testuser',
    manifest='wsl-work-workstation',
    build_image=('bash', str(DOCKER_DIR / 'build-base.sh')),
)
"""The machine with a network, building for the machine without one.

Its manifest is the *target's*, because that is what a bundle is built against —
the builder never installs anything and its own coordinates are never consulted.
Not firewalled, and that is the whole point of it: `bundle create` resolves every
upstream version and downloads every asset, which is what the offline box cannot
do for itself.
"""


def ensure_network() -> None:
    """The docker network, created once and reused.

    `docker network create` fails where it exists, and that failure is not a
    problem to report — a network left by an earlier session is the one wanted.
    """
    if docker('network', 'inspect', NETWORK).returncode != 0:
        docker('network', 'create', NETWORK)


def remove_network() -> None:
    """Removed only when nothing is attached, which docker enforces for us."""
    docker('network', 'rm', NETWORK)


def join(name: str) -> None:
    """Attach a running container to the exchange network.

    Separate from `start` so a container created before this existed, or reused
    across sessions with `--reuse`, still gets connected. Docker refuses a second
    connect, and that refusal is the idempotence.
    """
    docker('network', 'connect', NETWORK, name)


def builder_name(purpose: str) -> str:
    return container_name(purpose, BUILDER.name)


def install_uv(builder: Machine) -> None:
    """Put uv on the builder, which the base image strips on purpose.

    That image removes it so the runtime install proves the bootstrap installs uv
    itself, and a uv already on PATH makes that assertion vacuous. The builder
    never runs the bootstrap and never installs anything, so it needs uv supplied
    rather than earned.
    """
    if builder.succeeds('command -v uv'):
        return
    builder.exec(
        'curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=$HOME/.local/bin UV_NO_MODIFY_PATH=1 sh',
        check=True,
    )


def serve_shelf(builder: Machine) -> None:
    """Start sshd on the builder and give it a shelf to serve.

    The host key is generated per session rather than baked into the image. A key
    in the image is a key in the repo, and `detect private key` is a pre-commit
    hook here for good reason.
    """
    builder.exec('mkdir -p /run/sshd && ssh-keygen -A', user='root', check=True)
    builder.exec('/usr/sbin/sshd', user='root', check=True)
    builder.exec(
        f'mkdir -p {SHELF_ROOT} && chown -R {builder.environment.user} {SHELF_ROOT}',
        user='root',
        check=True,
    )


def authorize(peer: Machine, builder: Machine) -> None:
    """Let one machine reach the builder's shelf without a password.

    Generated in the peer and appended to the builder, rather than a shared key
    planted in both, so the builder authorizes each machine that talks to it and
    a test can revoke one without touching the other.
    """
    user = peer.environment.user
    home = peer.environment.home
    peer.exec(f'mkdir -p {home}/.ssh && chmod 700 {home}/.ssh', check=True)
    peer.exec(f"ssh-keygen -q -t ed25519 -N '' -f {KEY.format(user=user)} <<< y", check=True)
    public = peer.read(f'cat {KEY.format(user=user)}.pub')
    assert public, f'{peer.container} generated no public key'

    builder_home = builder.environment.home
    builder.exec(
        f'mkdir -p {builder_home}/.ssh && chmod 700 {builder_home}/.ssh && '
        f'printf %s\\\\n {shlex.quote(public)} >> {builder_home}/.ssh/authorized_keys && '
        f'chmod 600 {builder_home}/.ssh/authorized_keys',
        check=True,
    )


def declare_transport(machine: Machine, shelf_host: str) -> None:
    """Install the transport script and the config that names it.

    The config is written the way a person writes one, into
    `~/.config/dotfiles/config.toml`, because the ordering trap it carries is
    real: TOML sections are positional, so a key written after
    `[remote.transport]` belongs to that table. A fixture that got this wrong is
    what made the automatic-path tests pass against a machine that had turned
    nothing on.
    """
    home = machine.environment.home
    docker('cp', str(TRANSPORT_SOURCE), f'{machine.container}:{TRANSPORT}', check=True)
    machine.exec(f'chmod 755 {TRANSPORT}', user='root', check=True)

    config = CONFIG.format(root=SHELF_ROOT, program=TRANSPORT)
    machine.exec(f'mkdir -p {home}/.config/dotfiles', check=True)
    machine.exec(f'printf %s {shlex.quote(config)} > {home}/.config/dotfiles/config.toml', check=True)

    # Which peer to reach, in a file rather than the script, so one script serves
    # both machines and the builder reaches its own shelf by the name the peer
    # uses. Not an export: `Machine.exec` runs `bash -c`, which reads no profile.
    machine.exec(f'printf %s {shlex.quote(shelf_host)} > /etc/shelf-host', user='root', check=True)


CONFIG = """\
[remote]
root = "{root}"
keep = 5
fetch_bundle_when_none_is_staged = false
publish_status_after_offline_apply = false

[remote.transport]
program  = "{program}"
probe    = ["probe"]
list     = ["list", "{{dir}}"]
upload   = ["upload", "{{local}}", "{{dir}}"]
download = ["download", "{{remote}}", "{{local}}"]
mkdir    = ["mkdir", "{{dir}}"]
delete   = ["delete", "{{remote}}"]
"""
"""What each machine declares.

`[remote.transport]` last, and every automatic path off. The two flags are the
machine's own opt-in and a test that wants one turns it on explicitly — a
harness that shipped them enabled would be asserting against a machine nobody
configured that way.
"""


def carry(source: Machine, destination: Machine, path: str) -> str:
    """Hand a file from one container to the other, and say where it landed.

    The host is a pipe here and nothing more — `docker cp` twice, through a
    temporary file. That is deliberate for the *first* bundle and only for it: a
    machine installing from a bundle has no dotfiles CLI yet, because the CLI is
    what the bundle installs, so nothing on it could fetch over a transport. Every
    later exchange goes through `remote.py`.
    """
    name = path.rsplit('/', 1)[-1]
    with tempfile.TemporaryDirectory() as workspace:
        staged = Path(workspace) / name
        docker('cp', f'{source.container}:{path}', str(staged), check=True)
        landed = f'{destination.environment.home}/{name}'
        docker('cp', str(staged), f'{destination.container}:{landed}', check=True)
    destination.exec(f'chown {destination.environment.user} {landed}', user='root', check=True)
    return landed


def stage_full_bundle(builder: Machine, machine: Machine) -> str:
    """Build a full bundle on the networked machine and put it on the offline one.

    Where `install.sh --offline` looks, which is the home directory. No transport,
    per `carry` — this is the bundle that arrives before there is anything to run.
    """
    built = build_bundle_in(builder, machine.environment.manifest)
    return carry(builder, machine, built)


def build_bundle_in(builder: Machine, manifest: str, *, against: str | None = None) -> str:
    """Build a bundle inside the builder and return the path it printed.

    `--print-path` makes the archive's name the build's return value. The log
    goes to stderr, leaving stdout carrying the path alone, which is what lets
    this be read rather than reconstructed — the name carries a UTC stamp to the
    second and changes every build.

    The arch is passed because the builder is not the target. Its own CPU happens
    to match today and that is a coincidence of both being x86_64 containers, not
    a fact to rely on.
    """
    against_flag = f' --against {shlex.quote(against)}' if against else ''
    built = builder.exec(
        f'cd {builder.environment.home}/dotfiles && '
        f'uv run dotfiles bundle create --machine {shlex.quote(manifest)} --arch x86_64{against_flag} --print-path',
        check=True,
    )
    path = built.stdout.strip().splitlines()[-1] if built.stdout.strip() else ''
    assert path, f'the builder printed no path: {built.stderr[-2000:]}'
    return path
