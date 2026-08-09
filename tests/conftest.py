"""Shared test fixtures.

Modules under `install/` are importable by name — `pythonpath` in pyproject.toml
names their directories. Apps are not: a command is `aws-profiles`, not
`aws_profiles.py`, and a filename with a hyphen and no extension is not a module
name. `load_app` loads one by path so its functions can still be called directly
rather than only exercised through a subprocess.
"""

import importlib.machinery
import importlib.util
import os
import shutil
import stat
from pathlib import Path
from types import ModuleType

import pytest

from dotfiles.privilege import Escalation
from dotfiles.privilege import Privilege

APPS_DIR = Path(__file__).resolve().parent.parent / 'apps'


# Both opt-in tiers are declared here rather than beside the tests they gate.
# pytest only calls `pytest_addoption` on an *initial* conftest — the rootdir's —
# so the copy that lived in `tests/e2e/conftest.py` registered only when pytest
# was pointed straight at that directory, and `pytest tests/ --docker` failed
# with `unrecognized arguments`.
TIERS = {
    '--e2e': ('e2e', 'also run tests that reach the real network', 'reaches the real network; pass --e2e to run'),
    '--docker': (
        'docker',
        'run the container installs (tens of minutes each)',
        'installs a whole machine in a container; pass --docker to run',
    ),
}


def pytest_addoption(parser):
    for flag, (_, help_text, _reason) in TIERS.items():
        parser.addoption(flag, action='store_true', default=False, help=help_text)
    parser.addoption(
        '--require-interpreters',
        action='store_true',
        default=False,
        help='refuse to run rather than skip when a test needs an interpreter this machine lacks',
    )
    parser.addoption('--keep', action='store_true', default=False, help='leave e2e containers running afterwards')
    parser.addoption('--reuse', action='store_true', default=False, help='reuse a kept container and any built bundle')
    parser.addoption(
        '--installed',
        action='store_true',
        default=False,
        help='assert against the install already in the container instead of running one',
    )
    # Selection by environment cannot be `-k`, which matches test names too:
    # `-k offline` also matched `test_the_offline_run_never_resolved_a_version_online`
    # and so selected all four environments. The run started a second Arch
    # container, `docker rm -f` took the name from the Arch install running in
    # another process, and that install died at 137 looking like an OOM.
    # `tests/e2e/conftest.py` does the deselecting; the option has to be declared
    # here for the same reason the tiers above do.
    parser.addoption('--environment', default='', help='e2e environments to run, comma-separated (default: all)')


def pytest_collection_modifyitems(config, items):
    """Deselect an opt-in tier unless it is asked for.

    Here rather than in `addopts`, which forge owns: a deselection written there
    is erased by the next sync-pyproject run.

    `get_closest_marker` rather than `in item.keywords`: keywords carry every
    ancestor node's name as well as the markers, so the membership test also
    matched every test under a *directory* named `e2e` — silently skipping the
    whole container suite, which is marked `docker` and asked for with `--docker`.
    """
    for flag, (marker, _help, reason) in TIERS.items():
        if config.getoption(flag):
            continue
        skip = pytest.mark.skip(reason=reason)
        for item in items:
            if item.get_closest_marker(marker):
                item.add_marker(skip)

    resolve_interpreters(config, items)


def resolve_interpreters(config, items):
    """Skip what needs a missing interpreter, or refuse the whole run.

    `tests/shell` drives real bash, zsh and tmux. A machine without one should
    skip those cases and still run the rest; CI must do the opposite, because a
    runner image that has no zsh reports green having run a third of that
    directory. Both readings are right for their runner, which is why the marker
    only states the requirement and this decides what it means.

    The enforced set is read back off the collected items rather than written
    down anywhere, so it is exactly what the tests ask for. A workflow step
    proving two named binaries exist is a different claim that only looks like
    this one — it stays green after the last test needing them is deleted, and
    stays green when a new test starts needing a third.
    """
    required = {marker.args[0] for item in items for marker in item.iter_markers('interpreter')}
    missing = sorted(name for name in required if shutil.which(name) is None)

    if config.getoption('--require-interpreters'):
        if missing:
            raise pytest.UsageError(f'--require-interpreters, but this machine has no {", ".join(missing)}')
        return

    for item in items:
        for marker in item.iter_markers('interpreter'):
            if shutil.which(marker.args[0]) is None:
                item.add_marker(pytest.mark.skip(reason=f'{marker.args[0]} is not installed'))


def load_app(name: str, platform: str = 'common') -> ModuleType:
    """Import an executable from apps/<platform>/ under a usable module name.

    The loader is used directly rather than through spec.loader, which is
    Optional and would need narrowing at every call.
    """
    path = APPS_DIR / platform / name
    module_name = name.lstrip('_').replace('-', '_')

    loader = importlib.machinery.SourceFileLoader(module_name, str(path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    if spec is None:
        raise ImportError(f'could not load {path}')

    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope='session')
def aws_profiles():
    return load_app('_aws-profiles')


@pytest.fixture
def unprivileged() -> Privilege:
    """A `Privilege` that has never been authorized, which is what refuses.

    Every resource but `system` takes one and ignores it — `perform` carries it
    so that `observe` cannot — so a test of one of those wants the object that
    proves nothing escalated rather than a mock that would let it.
    """
    return Privilege()


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A bin directory first on PATH, with the real system dirs still behind it.

    `/usr/bin:/bin` stays, or `git`, `bash` and `install` raise FileNotFoundError
    and a fixture cannot run its own helpers. Shadowing by name rather than
    emptying PATH is what keeps these tests from reading the machine they run on:
    without it, "dpkg-query refuses to answer" holds on Arch for the wrong reason
    and inverts on every Debian CI runner.
    """
    directory = tmp_path / 'bin'
    directory.mkdir()
    monkeypatch.setenv('PATH', f'{directory}{os.pathsep}/usr/bin{os.pathsep}/bin')
    return directory


def _executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """Local to this file on purpose. `tests/conftest.py` and `tests/e2e/conftest.py`
    are both the module `conftest` to an importer, so a `from conftest import ...`
    resolves to whichever one the tool looked at first — which typechecks as the
    wrong file and would run as the wrong one from another working directory.
    Fixtures are injected and have no such problem; a plain helper is copied."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


@pytest.fixture
def granted(fake_bin: Path):
    """An authorized `Privilege` whose sudo runs the command instead of dropping it.

    A fake that logged and exited 0 would let every write test pass without a file
    ever being written, which is the one result they must not be able to produce.
    """
    _executable(fake_bin, 'sudo', '#!/bin/sh\n[ "$1" = "-n" ] && shift\n[ "$1" = "-v" ] && exit 0\nexec "$@"\n')
    privilege = Privilege()
    privilege.authorize((Escalation('a privileged action'),))
    yield privilege
    privilege.stop()
