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


def pytest_addoption(parser):
    parser.addoption('--e2e', action='store_true', default=False, help='also run tests that reach the real network')


def pytest_collection_modifyitems(config, items):
    """Deselect the e2e tier unless it is asked for.

    Here rather than in `addopts`, which forge owns: a deselection written there
    is erased by the next sync-pyproject run.
    """
    if config.getoption('--e2e'):
        return
    skip = pytest.mark.skip(reason='reaches the real network; pass --e2e to run')
    for item in items:
        if 'e2e' in item.keywords:
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
