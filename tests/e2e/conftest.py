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

**Four tiers, and reach for the cheapest one that can answer the question.**
Running a whole machine install to find out whether a fixture is right costs half
an hour and answers nothing an install can uniquely answer; that mistake is what
the first tiers exist to stop.

    uv run pytest tests/e2e/test_harness.py             # 0.1s, no Docker at all
    uv run pytest tests/e2e/test_container.py --docker  # ~25s per environment
    uv run pytest tests/e2e --docker --installed        # seconds: assert, do not install
    uv run pytest tests/e2e --docker                    # the full installs

`test_harness.py` covers everything decidable without starting anything: the
network derivation, the environment definitions, the exec script. `test_container.py`
starts a container and copies the repo but installs nothing, which is where the
rig's own failures live — a wrong PATH, a missing bootstrap tool, a firewall that
does not match the measurement. `test_machine.py` needs an installed machine, and
`--installed` is how to keep asking it questions without paying for one twice.

**`--installed` is the tier that was missing**, and its absence is most of what
today cost: a container died and thirty minutes went with it, then an assertion
added after a run started needed another thirty to answer. The install writes its
exit status and log into the container, so a later run reads them back instead of
producing them again. It re-copies the repo first, so the verification scripts and
the editable CLI are current even though the install is not — what is stale is
exactly `install_status` and `install_log`, and the flag's name says so.

Run it without the flag when `install.sh`, a phase script or a package list
changes. Run it with the flag when a test, an assertion or a verification script
changes, which is most of the time.

    uv run pytest tests/e2e --docker --environment archlinux   # one environment
    uv run pytest tests/e2e --docker --keep           # leave the containers up
    uv run pytest tests/e2e --docker --reuse          # reuse the OS state, install again
    uv run pytest tests/e2e --docker --installed      # reuse the install too

The four environments are independent containers, so four shells running one
`--environment` each finish in the time of the slowest rather than the sum.

Pick an environment with `--environment`, never `-k`. `-k` filters on test names
as well as parameter ids, so `-k offline` also matches
`test_the_offline_run_never_resolved_a_version_online[archlinux]` and quietly
selects every environment — which starts a container whose name another running
process is already using, and `docker rm -f` then kills that install.
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Iterator

import pytest
from harness import ENVIRONMENTS
from harness import Environment
from harness import Machine
from harness import authenticate_git
from harness import clear_shadow_calls
from harness import copy_repo
from harness import docker
from harness import github_token
from harness import image_exists
from harness import install_age
from harness import install_command
from harness import install_record
from harness import plant_python_shadow
from harness import stage_bundle
from harness import start

from dotfiles import paths


def reusing_containers(config: pytest.Config) -> bool:
    """`--keep` is deliberately not here: it says leave this one running, not
    install into whatever is already there."""
    return bool(config.getoption('--reuse') or config.getoption('--installed'))


def keeping_containers(config: pytest.Config) -> bool:
    """Asking to reuse a container implies keeping it, or the next run finds
    nothing to reuse and silently pays for a whole install again."""
    return bool(config.getoption('--keep') or reusing_containers(config))


def pytest_report_header(config: pytest.Config) -> str:
    """Say whether a container run is authenticated, before anything installs.

    Anonymous GitHub API calls are 60 an hour per public IP and a full install
    spends most of them, so an unauthenticated run fails on every release tool with
    "did not answer with a release" — which reads exactly like a broken installer.
    Naming it in the header is what keeps a red run from being argued about: either
    the line says the calls are authenticated, or the failures are suspect.
    """
    if not config.getoption('--docker'):
        return ''
    return (
        'github: authenticated' if github_token() else 'github: ANONYMOUS — 60 API calls/hour, release failures are suspect (gh auth login)'
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Honour `--environment`, which is the only safe way to run one of these.

    Only items carrying a `container` parameter are touched, so nothing outside
    the container tiers is affected by asking for one environment.
    """
    wanted = str(config.getoption('--environment')).strip()
    if not wanted:
        return

    names = {name.strip() for name in wanted.split(',') if name.strip()}
    known = {environment.name for environment in ENVIRONMENTS}
    if unknown := names - known:
        raise pytest.UsageError(f'--environment: no such environment {sorted(unknown)}; known are {sorted(known)}')

    keeping: list[pytest.Item] = []
    dropping: list[pytest.Item] = []
    for item in items:
        callspec = getattr(item, 'callspec', None)
        environment = callspec.params.get('container') if callspec else None
        (dropping if environment is not None and environment.name not in names else keeping).append(item)

    if dropping:
        config.hook.pytest_deselected(items=dropping)
        items[:] = keeping


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
    reusing = reusing_containers(request.config) and docker('container', 'inspect', name).returncode == 0
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
        authenticate_git(subject)
        plant_python_shadow(subject)

        if environment.env_file:
            subject.exec(f'printf %s {shlex.quote(environment.env_file)} > {environment.home}/.env', check=True)

        yield subject
    finally:
        if keeping_containers(request.config):
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

    `--installed` goes further and skips the install entirely, reading the record
    the last one left in the container. Session scope only stops a question being
    asked twice inside one run; changing an assertion still cost a fresh half
    hour, which is what made two of today's runs pure waiting.
    """
    environment = container.environment

    if request.config.getoption('--installed'):
        kept = install_record(container)
        if kept is None:
            raise pytest.UsageError(f'--installed: {container.container} has no install record — run once without it first')
        print(f'\n--installed: asserting against the install from {install_age(container)}, not running one')
        container.install_status, container.install_log = kept
        return container

    if environment.offline:
        # `--reuse` means "reuse the expensive artifacts", and the bundle is one:
        # half a gigabyte and several minutes. Rebuilt by default so a change to
        # the bundle format cannot ship against a bundle in the old layout.
        stage_bundle(container, reuse=request.config.getoption('--reuse'))

    # Truncated here rather than at planting time, so the log covers the install
    # and nothing else: the container tier probes the shadow deliberately to
    # prove it works, and those probes are not the run under test.
    clear_shadow_calls(container)

    container.exec(install_command(environment))
    recorded = install_record(container)
    if recorded is None:
        raise AssertionError('the install left no exit status behind, so nothing here can say what it did')
    container.install_status, container.install_log = recorded
    return container
