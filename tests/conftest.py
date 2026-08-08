"""Shared test fixtures.

Modules under `install/` are importable by name — `pythonpath` in pyproject.toml
names their directories. Apps are not: a command is `aws-profiles`, not
`aws_profiles.py`, and a filename with a hyphen and no extension is not a module
name. `load_app` loads one by path so its functions can still be called directly
rather than only exercised through a subprocess.
"""

import importlib.machinery
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

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
    parser.addoption('--keep', action='store_true', default=False, help='leave e2e containers running afterwards')
    parser.addoption('--reuse', action='store_true', default=False, help='reuse a kept container and any built bundle')


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
