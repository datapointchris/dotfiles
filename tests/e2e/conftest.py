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

Run it without the flag when `install.sh`, a provider or a package list
changes. Run it with the flag when a test, an assertion or a verification script
changes, which is most of the time.

    uv run pytest tests/e2e --docker --environment archlinux   # one environment
    uv run pytest tests/e2e --docker --keep           # leave the containers up
    uv run pytest tests/e2e --docker --reuse          # reuse the OS state, install again
    uv run pytest tests/e2e --docker --installed      # reuse the install too

The four environments are independent containers and no longer share a name with
another checkout's — `harness.container_name` suffixes a linked worktree's. What
that buys is a second checkout running the cheap rungs while the first holds a
container, not four full installs at once: an install is twenty to thirty minutes
of one box's CPU and disk, and running them concurrently makes the box unusable
for the duration. One full install at a time; parallelism belongs at the rungs
that cost seconds.

Pick an environment with `--environment`, never `-k`. `-k` filters on test names
as well as parameter ids, so `-k offline` also matches
`test_the_offline_run_never_resolved_a_version_online[archlinux]` and quietly
selects every environment — which within one checkout is still a container
another of its own runs is using, and `docker rm -f` then kills that install.
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Iterator

import levels
import pytest
from harness import ARCHLINUX
from harness import ENVIRONMENTS
from harness import UNDER_TEST
from harness import Environment
from harness import Machine
from harness import authenticate_git
from harness import build_base
from harness import clear_shadow_calls
from harness import container_name
from harness import copy_repo
from harness import docker
from harness import github_token
from harness import github_token_args
from harness import image_exists
from harness import install_age
from harness import install_command
from harness import install_record
from harness import plant_python_shadow
from harness import stage_bundle
from harness import start


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


def _narrow_to_level(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep only the rung that was asked for.

    Read off each test's `fixturenames` rather than a list of modules, so a test
    moved between files lands at the level its fixtures put it at and a new file
    needs nothing here. `levels.level_of` owns the ordering the nesting requires.

    Exactly the rung, never up to it: the runner walks the ladder itself, so an
    invocation that also ran every level below would run the unit suite five
    times and the container tier four. Asking for `container` therefore drops the
    1,600 unmarked tests too, which is the whole point of asking for a rung.
    """
    if not (wanted := str(config.getoption('--level')).strip()):
        return

    level = levels.resolve(wanted)
    installed = bool(config.getoption('--installed'))
    dropping = [
        item
        for item in items
        if levels.level_of(
            getattr(item, 'fixturenames', ()),
            docker=item.get_closest_marker('docker') is not None,
            installed=installed,
        )
        is not level
    ]
    if dropping:
        config.hook.pytest_deselected(items=dropping)
        items[:] = [item for item in items if item not in dropping]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Honour `--environment`, and drop what `--installed` cannot mean.

    Only items carrying a `container` parameter are narrowed by environment, so
    nothing outside the container tiers is affected by asking for one.

    `--installed` additionally deselects the set tier, which is the difference
    between the rung the ladder documents and the one it delivered: `--installed`
    says assert against the install that is already there, and a set test cannot
    honour that — `over_base` starts a fresh container and installs a section
    into it. Collected anyway, they made `tests/e2e --installed` take nine
    minutes where the tier is meant to answer in seconds, which is what pushes a
    question back up to the half-hour rung.
    """
    if config.getoption('--installed'):
        installing = [item for item in items if 'over_base' in getattr(item, 'fixturenames', ())]
        if installing:
            config.hook.pytest_deselected(items=installing)
            items[:] = [item for item in items if item not in installing]

    _narrow_to_level(config, items)

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


def _purpose(config: pytest.Config) -> str:
    """What the container this run wants is *for*, which is its name's middle.

    `machine` when no level was named, because a bare `pytest tests/e2e --docker`
    is the full run — and because `--installed` has to find the container the
    full run left, which is the one case where two levels must agree on a name.
    """
    wanted = str(config.getoption('--level')).strip()
    return (levels.resolve(wanted).purpose or 'probe') if wanted else 'machine'


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
        subprocess.run(environment.build_image, check=True, cwd=UNDER_TEST)

    name = container_name(_purpose(request.config), environment.name)
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

            # Inside the guard with `prepare`, and for the same reason: this is
            # setup for a container nothing has installed into. Written over a
            # reused container it destroys the `~/.env` the install generated —
            # a 45-byte stub naming no MACHINE replacing the manifest-derived
            # file — and `--installed` then fails three tests that read it, with
            # "~/.env does not declare this machine" against a machine that
            # declared itself correctly half an hour earlier.
            if environment.env_file:
                subject.exec(f'printf %s {shlex.quote(environment.env_file)} > {environment.home}/.env', check=True)

        copy_repo(subject)
        authenticate_git(subject)
        plant_python_shadow(subject)

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
    recorded rather than asserted here: `dotfiles apply` exits 3 when a stage
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


@pytest.fixture
def fresh_container(container: Machine, request: pytest.FixtureRequest) -> Machine:
    """`container` narrowed to a run that started it empty.

    Under `--reuse` or `--installed` the container is one a previous run installed
    into, so a question about the state *before* an install is being put to a
    machine that is after one. `~/.env` is the case that made this necessary: it
    is present because the last install wrote it, not because the rig planted it,
    and the assertion reads as a rig failure.

    Skipping rather than adapting, because there is no version of "before the
    install" that a already-installed container can answer.
    """
    if reusing_containers(request.config):
        pytest.skip('--reuse/--installed: asks about a container before an install, and this one is after one')
    return container


@pytest.fixture
def fresh_install(machine: Machine, request: pytest.FixtureRequest) -> Machine:
    """`machine` narrowed to a run that performed the install itself.

    `--installed` returns the container without going through the install fixture,
    and `clear_shadow_calls` lives there — so the shadow log is not this install's
    record but everything since the last one, including the assertions of the run
    reading it. A test asking what the install did has nothing to read.

    Distinct from `fresh_container`, which turns on `--reuse` too: `--reuse` does
    perform an install, so anything reading what an install did is answerable
    under it.
    """
    if request.config.getoption('--installed'):
        pytest.skip('--installed: reads what the install did, and this run did not perform one')
    return machine


@pytest.fixture(scope='session')
def base(container_environment: Environment) -> str:
    """The base image for this environment: system packages and nothing above them.

    Built once and reused across runs while its digest and its age hold, because
    the packages are the part that costs ten minutes and changes least. Everything
    a set test then installs sits on top of a machine that already has curl, git,
    unzip and a package manager — which is exactly the state a set's own
    prerequisites are declared against.

    Which environment comes from `container_environment` rather than being decided
    again here. Decided twice, the two disagreed: `--environment wsl` reached this
    fixture as an unparametrised request, so it fell back to Arch and handed
    `over_base` an Arch image to run with wsl's user and home. The container then
    failed at `chown -R ubuntu` — an image with no such user — which reads as a
    broken copy step rather than as the wrong base.
    """
    if docker('info').returncode != 0:
        pytest.skip('Docker is not running')
    if not image_exists(container_environment.image):
        pytest.skip(f'image {container_environment.image} is absent')

    return build_base(container_environment)


@pytest.fixture
def over_base(base: str, container_environment: Environment) -> Iterator[Machine]:
    """A throwaway machine from the base image, with this checkout's code in it.

    Function-scoped and not session-scoped, unlike `container` and `machine`: a set
    installs into the machine, so two sets sharing one would make the second's
    result depend on the first's. Starting from an image costs about a second,
    which is what makes per-test isolation affordable here and not there.
    """
    name = container_name('section', container_environment.name)
    docker('rm', '-f', name)
    docker(
        'run',
        '-d',
        '--name',
        name,
        '--env',
        'DOTFILES_DOCKER_TEST=true',
        *github_token_args(),
        '--mount',
        f'type=bind,source={UNDER_TEST},target=/dotfiles-src,readonly',
        base,
        'sleep',
        'infinity',
        check=True,
    )
    subject = Machine(environment=container_environment, container=name)
    try:
        copy_repo(subject)
        authenticate_git(subject)
        yield subject
    finally:
        docker('rm', '-f', name)


@pytest.fixture(scope='session')
def container_environment(request: pytest.FixtureRequest) -> Environment:
    """Which environment the set tier runs against.

    One rather than all four: a set test asks whether a section installs, and the
    answer is the same shape on every environment while the base costs multiple GB
    each. `--environment` still picks it.
    """
    wanted = str(request.config.getoption('--environment')).strip()
    named = {environment.name: environment for environment in ENVIRONMENTS}
    return named.get(wanted.split(',')[0], ARCHLINUX)
