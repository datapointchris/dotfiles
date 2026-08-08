"""Real installs, in real containers.

The most accurate tier there is: a fresh OS image, the actual `install.sh`, and
whatever the machine looks like afterwards. Docker stays — what moved is the
harness around it, from three ~490-line bash scripts into one rig the
environments parameterize.

They were three copies of one shape, and the copies drifted. Every difference
below was a bug found by running them on 2026-08-08:

- `--reuse` re-copied the repo in the WSL script and not the Arch one, so a
  reused container silently tested the code from whenever it was created.
- Two scripts aborted under `set -e` the moment `install.sh` exited non-zero,
  skipping the verification that decides whether the failure mattered.
- Steps 5 and 7 exported a PATH carrying `~/.local/bin`; step 6 did not, so the
  duplicate detector could not find `uv` and died on a machine where uv was
  installed and working.

The payload each test sends is still shell — the repo's own verification scripts,
and `docker exec … bash -c` around them — because that part genuinely is shell.
What is Python is the lifecycle, the selection, and the assertions.

**Three tiers, and reach for the cheapest one that can answer the question.**
Running a whole machine install to find out whether a fixture is right costs half
an hour and answers nothing an install can uniquely answer; that mistake is what
the first two tiers exist to stop.

    uv run pytest tests/e2e/test_harness.py           # 0.1s, no Docker at all
    uv run pytest tests/e2e/test_container.py --docker  # ~25s per environment
    uv run pytest tests/e2e --docker                  # the full installs

`test_harness.py` covers everything decidable without starting anything: the
network derivation, the environment definitions, the exec script. `test_container.py`
starts a container and copies the repo but installs nothing, which is where the
rig's own failures live — a wrong PATH, a missing bootstrap tool, a firewall that
does not match the measurement. `test_machine.py` is the only tier that needs the
install, so run it when `install.sh`, `apply.py` or a phase script changes.

    uv run pytest tests/e2e --docker -k archlinux     # one environment
    uv run pytest tests/e2e --docker --keep           # leave the containers up
    uv run pytest tests/e2e --docker --keep --reuse   # and reuse them next time
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Iterator

import pytest
from harness import ENVIRONMENTS
from harness import Environment
from harness import Machine
from harness import clear_shadow_calls
from harness import copy_repo
from harness import docker
from harness import image_exists
from harness import plant_python_shadow
from harness import stage_bundle
from harness import start

from dotfiles import paths


@pytest.fixture(scope='session', params=ENVIRONMENTS, ids=lambda environment: environment.name)
def container(request: pytest.FixtureRequest) -> Iterator[Machine]:
    """A started container with the repo in it, and nothing installed.

    The cheap half, deliberately separate from `machine`: proving the rig works —
    the exec environment, the copy, the network model — costs seconds here and
    half an hour if it has to go through an install first. That split is the
    answer to having run two full Arch installs to find out whether a fixture
    was right.
    """
    environment: Environment = request.param

    if docker('info').returncode != 0:
        pytest.skip('Docker is not running')

    if not image_exists(environment.image):
        if not environment.build_image:
            pytest.skip(f'image {environment.image} is absent and nothing here builds it')
        subprocess.run(environment.build_image, check=True, cwd=paths.REPO_ROOT)

    name = f'dotfiles-e2e-{environment.name}'
    # `--reuse` keeps the OS state — an Arch container is 4.5GB of pacman
    # downloads — and never the repo inside it. Reusing both is how the Arch
    # harness came to test whatever code was mounted when the container was
    # created, so a fix made since reported as still broken.
    reusing = request.config.getoption('--reuse') and docker('container', 'inspect', name).returncode == 0
    if reusing:
        docker('start', name)
    else:
        docker('rm', '-f', name)
        start(environment, name)

    subject = Machine(environment=environment, container=name)

    try:
        if not reusing:
            for command in environment.prepare:
                subject.exec(command, user='root', check=True)

        copy_repo(subject)
        plant_python_shadow(subject)

        if environment.env_file:
            subject.exec(f'printf %s {shlex.quote(environment.env_file)} > {environment.home}/.env', check=True)

        yield subject
    finally:
        if request.config.getoption('--keep'):
            print(f'\nkept: docker exec -it --user {environment.user} {name} bash')
        else:
            docker('rm', '-f', name)


@pytest.fixture(scope='session')
def machine(container: Machine, request: pytest.FixtureRequest) -> Machine:
    """The same container, with `install.sh` run against it.

    Session-scoped because the install is the expensive part and every test is a
    different question about the same finished machine. `install_status` is
    recorded rather than asserted here: `dotfiles apply` exits 3 when a phase
    fails, and the tests are what say whether that mattered.
    """
    environment = container.environment

    if environment.offline:
        # `--reuse` means "reuse the expensive artifacts", and the bundle is one:
        # half a gigabyte and several minutes. Rebuilt by default so a change to
        # the bundle format cannot ship against a bundle in the old layout.
        stage_bundle(container, reuse=request.config.getoption('--reuse'))

    # Truncated here rather than at planting time, so the log covers the install
    # and nothing else: the container tier probes the shadow deliberately to
    # prove it works, and those probes are not the run under test.
    clear_shadow_calls(container)

    flags = ' --offline' if environment.offline else ''
    completed = container.exec(f'cd {environment.home}/dotfiles && ./install.sh --machine {environment.manifest}{flags}')
    container.install_status = completed.returncode
    container.install_log = completed.stdout + completed.stderr
    return container
