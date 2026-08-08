"""A declared pin is what installs, instead of whatever upstream calls latest.

The capability exists so a machine can hold a known-good release while upstream
is broken, and so an older distro can run an older build than the rest of the
fleet. Vocabulary and the reasoning: .planning/version-constraints.md.

DOTFILES_DIR is the injection point — a real knob every installer already reads,
so a synthetic tree needs no seam added to production code — it carries install/
and src/ because the installers reach the package through PYTHONPATH. The ambient
environment is passed through deliberately: /usr/bin/python3 finds PyYAML via a
relocated PYTHONUSERBASE, so a stripped env cannot read packages.yml at all and
would be testing the wrong failure.

Marked e2e because resolving a bare version to a tag means asking the repo which
tags it published. That is not incidental: the constraint is deliberately a bare
version rather than a tag, because the same release is spelled v0.56.0 by lazygit
and cli/v0.9.0 by the personal CLIs, and only the publisher knows which.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

PINNED_TOOL = 'lazygit'
PINNED_REPO = 'jesseduffield/lazygit'
PINNED_VERSION = '0.56.0'


@pytest.fixture
def pinned_tree(tmp_path: Path) -> Path:
    """A copy of install/ whose lazygit entry declares a pin."""
    root = tmp_path / 'dotfiles'
    shutil.copytree(REPO_ROOT / 'install', root / 'install')
    shutil.copytree(REPO_ROOT / 'src', root / 'src')

    packages = root / 'install' / 'packages.yml'
    declaration = f'  - name: {PINNED_TOOL}\n    repo: {PINNED_REPO}\n'
    text = packages.read_text()
    assert declaration in text, 'the lazygit entry no longer opens with name then repo'
    packages.write_text(text.replace(declaration, f'{declaration}    version: "{PINNED_VERSION}"\n', 1))
    return root


def print_url(root: Path, tool: str) -> tuple[str, str, str]:
    result = subprocess.run(
        ['bash', str(root / 'install' / 'common' / 'github-releases' / f'{tool}.sh'), '--print-url', 'linux', 'x86_64'],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, 'DOTFILES_DIR': str(root)},
    )
    name, version, url = result.stdout.strip().splitlines()[0].split('|')
    return name, version, url


@pytest.mark.e2e
def test_a_pinned_tool_resolves_to_the_pinned_release(pinned_tree):
    _, version, url = print_url(pinned_tree, PINNED_TOOL)

    # The pin is written bare and comes back as the tag the repo publishes.
    assert version == f'v{PINNED_VERSION}'
    assert f'/download/v{PINNED_VERSION}/' in url
    assert PINNED_VERSION in url.rsplit('/', 1)[-1]


@pytest.mark.e2e
def test_an_unpinned_tool_still_resolves_to_latest(pinned_tree):
    """The pin must narrow one entry, not switch the whole catalog into pinned mode."""
    _, pinned, _ = print_url(pinned_tree, PINNED_TOOL)
    _, unpinned, _ = print_url(pinned_tree, 'glow')

    assert pinned == f'v{PINNED_VERSION}'
    assert unpinned and unpinned != f'v{PINNED_VERSION}'


@pytest.mark.e2e
def test_a_pin_no_release_matches_fails_rather_than_installing_latest(tmp_path: Path):
    """Falling through to latest is exactly what the pin exists to prevent, so an
    unmatchable pin has to be loud."""
    root = tmp_path / 'dotfiles'
    shutil.copytree(REPO_ROOT / 'install', root / 'install')
    shutil.copytree(REPO_ROOT / 'src', root / 'src')

    packages = root / 'install' / 'packages.yml'
    declaration = f'  - name: {PINNED_TOOL}\n    repo: {PINNED_REPO}\n'
    packages.write_text(packages.read_text().replace(declaration, f'{declaration}    version: "0.0.0-nope"\n', 1))

    result = subprocess.run(
        ['bash', str(root / 'install' / 'common' / 'github-releases' / f'{PINNED_TOOL}.sh'), '--print-url', 'linux', 'x86_64'],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, 'DOTFILES_DIR': str(root)},
    )
    assert 'publishes no release for' in result.stderr
    assert '/download//' not in result.stdout, 'an unresolved pin leaked an empty version into the URL'


def test_an_unreadable_catalog_fails_rather_than_assuming_nothing_is_pinned(tmp_path: Path):
    """Needs no network, and is the bug this file caught while being written: a
    failed lookup and a declared-nothing lookup both exit 1, so swallowing the
    difference installs latest over a pin nobody can see."""
    root = tmp_path / 'dotfiles'
    shutil.copytree(REPO_ROOT / 'install', root / 'install')
    shutil.copytree(REPO_ROOT / 'src', root / 'src')
    (root / 'install' / 'packages.yml').write_text('github_releases: [unclosed\n')

    result = subprocess.run(
        ['bash', str(root / 'install' / 'common' / 'github-releases' / f'{PINNED_TOOL}.sh'), '--print-url', 'linux', 'x86_64'],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, 'DOTFILES_DIR': str(root)},
    )
    assert 'whether lazygit is pinned is unknown' in result.stderr
    assert 'releases/download' not in result.stdout
