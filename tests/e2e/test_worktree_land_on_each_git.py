"""The landing suite, run inside a container against that image's own git.

`land` needs `git merge-tree --write-tree`, which arrived in git 2.38, and every
other command it runs has to mean the same on the oldest git a machine carries.
Debian 12's 2.39 is that floor, and Arch tracks the newest release. So each of
those two containers runs `tests/apps/test_worktree_land.py` from its copy of the
repo, on the git its image installed.

The images carry git and no uv, and `worktree` starts under `uv run --script`. The
host's uv binary is copied in rather than added to the images, because the images
model a machine before anything installs. Everything the run downloads lands in one
directory of the container's home, removed afterwards, so the session's other tests
find the container as they would have.

`wsl` runs nothing here, because CI on ubuntu-26.04 already runs the suite on that
apt git, and `offline` and `restricted` share its image.

    uv run pytest tests/e2e/test_worktree_land_on_each_git.py --docker --level empty-container --environment archlinux,server
"""

from __future__ import annotations

import re
import shutil

import pytest
from harness import ARCHLINUX
from harness import SERVER
from harness import UNDER_TEST
from harness import Machine
from harness import docker

pytestmark = pytest.mark.docker

ON_THEIR_OWN_GIT = (ARCHLINUX.name, SERVER.name)
SUITE = 'tests/apps/test_worktree_land.py'
SCRATCH = 'worktree-land-run'


def locked_pytest() -> str:
    """The pytest the project's lock resolves, so a container runs the same one."""
    found = re.search(r'^name = "pytest"\nversion = "([^"]+)"', (UNDER_TEST / 'uv.lock').read_text(), re.MULTILINE)
    assert found, 'uv.lock resolves no pytest'
    return found[1]


def test_the_landing_suite_passes_on_the_containers_own_git(container: Machine) -> None:
    if container.environment.name not in ON_THEIR_OWN_GIT:
        pytest.skip(f'{container.environment.name} shares the git CI already runs the suite on')
    uv = shutil.which('uv')
    assert uv, 'the host has no uv to copy in'

    home = container.environment.home
    scratch = f'{home}/{SCRATCH}'
    container.exec(f'mkdir -p {scratch}/bin', check=True)
    docker('cp', uv, f'{container.container}:{scratch}/bin/uv', check=True)
    try:
        ran = container.exec(
            f'export PATH="{scratch}/bin:$PATH" UV_CACHE_DIR={scratch}/cache UV_PYTHON_INSTALL_DIR={scratch}/python; '
            f'git --version && cd {home}/dotfiles && '
            f'uv run --no-project --no-config --python 3.13 --with pytest=={locked_pytest()} '
            f'pytest -p no:cacheprovider --confcutdir tests/apps -q {SUITE}'
        )
    finally:
        container.exec(f'rm -rf {scratch}', user='root')

    assert ran.returncode == 0, f'{ran.stdout}\n{ran.stderr}'
