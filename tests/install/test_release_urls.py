"""Every declared GitHub release publishes the asset its installer asks for.

This is the gate that lets the 23 installer scripts be replaced by Python: a URL
builder can only be rewritten safely against proof that the current one is
correct for every tool on every platform that declares it, not just the platform
the developer happens to be sitting at. Run it before deleting a script, and
again after.

Two assertions per case, because they fail independently. The URL has to serve
bytes — the only proof that the host, the path shape and a tag containing a
slash (`cli/v0.9.0`) all survive. And the filename has to be the one the release
actually published, exactly: GitHub resolves asset paths case-insensitively, so
a wrong spelling downloads fine and then silently misses both the asset-id
lookup that private repos need and the checksum entry recorded under the real
name. That is not hypothetical — it is how lazygit came to be fetched as
Linux_x86_64 while every release published linux_x86_64.

Run with: pytest tests/install/test_release_urls.py --e2e
"""

import json
import os
import subprocess
from collections.abc import Callable
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import github_release
import httpx2
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLERS = REPO_ROOT / 'install' / 'common' / 'github-releases'
MANIFESTS = REPO_ROOT / 'install' / 'manifests'
PACKAGES_YML = REPO_ROOT / 'install' / 'packages.yml'

# The (os, arch) pairs each PLATFORM string fuses together. Writing the fusion
# out is the point: macOS is the one platform serving two architectures, so a
# tool that spells only one of them is invisible from whichever Mac runs the
# suite. Coordinates replace this table.
PLATFORM_TARGETS = {
    'macos': (('darwin', 'arm64'), ('darwin', 'x86_64')),
    'archlinux': (('linux', 'x86_64'),),
    'linux': (('linux', 'x86_64'),),
    'wsl': (('linux', 'x86_64'),),
}

Case = tuple[str, str, str]


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def declared_releases() -> set[str]:
    return {entry['name'] for entry in _read_yaml(PACKAGES_YML)['github_releases']}


def build_corpus() -> list[Case]:
    """Every (tool, os, arch) any manifest actually asks for, deduplicated."""
    cases: set[Case] = set()
    for manifest in sorted(MANIFESTS.glob('*.yml')):
        declaration = _read_yaml(manifest)
        for target in PLATFORM_TARGETS[declaration['platform']]:
            for tool in declaration.get('github_releases') or []:
                cases.add((tool, *target))
    return sorted(cases)


CORPUS = build_corpus()


def print_url(tool: str, os_name: str, arch: str) -> tuple[str, str, str]:
    """Ask an installer what it would download, in the mode the bundler uses."""
    result = subprocess.run(
        ['bash', str(INSTALLERS / f'{tool}.sh'), '--print-url', os_name, arch],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, 'DOTFILES_DIR': str(REPO_ROOT)},
    )
    name, version, url = result.stdout.strip().splitlines()[0].split('|')
    return name, version, url


@pytest.fixture(scope='session')
def resolved_urls() -> dict[Case, tuple[str, str, str] | Exception]:
    """Resolve the whole matrix once, concurrently.

    Each invocation costs a release API call, and a tool declared on three
    platforms resolves its version three times, so the matrix is network-bound
    rather than CPU-bound. A failure is returned rather than raised so it lands
    on the case that owns it instead of taking the fixture, and the rest of the
    matrix down with it.
    """

    def resolve(case: Case) -> tuple[str, str, str] | Exception:
        try:
            return print_url(*case)
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(CORPUS, pool.map(resolve, CORPUS), strict=True))


@pytest.fixture(scope='session')
def http() -> Iterator[httpx2.Client]:
    """Unauthenticated on purpose: this is the path a public install takes.

    Redirects are followed because a release download is served by a redirect to
    object storage, and the timeout is raised off the 5s default for the same
    reason.
    """
    with httpx2.Client(
        headers={'User-Agent': github_release.USER_AGENT},
        follow_redirects=True,
        timeout=60,
    ) as client:
        yield client


@pytest.fixture(scope='session')
def repo_is_private() -> Callable[[str], bool]:
    """Asked only when a HEAD fails, so the common case costs no extra call."""
    cache: dict[str, bool] = {}

    def lookup(repo: str) -> bool:
        if repo not in cache:
            cache[repo] = json.loads(github_release.request(f'https://api.github.com/repos/{repo}'))['private']
        return cache[repo]

    return lookup


@pytest.fixture(scope='session')
def published_assets() -> Callable[[str, str], dict[str, int]]:
    """Asset names a release publishes, one API call per (repo, tag)."""
    cache: dict[tuple[str, str], dict[str, int]] = {}

    def lookup(repo: str, tag: str) -> dict[str, int]:
        if (repo, tag) not in cache:
            cache[(repo, tag)] = github_release.release_assets(repo, tag)
        return cache[(repo, tag)]

    return lookup


class TestCorpus:
    """Guards that the matrix below is not vacuously green."""

    def test_every_declared_release_is_claimed_by_a_manifest(self):
        assert {tool for tool, _, _ in CORPUS} == declared_releases()

    def test_both_mac_architectures_and_linux_are_covered(self):
        assert {(os_name, arch) for _, os_name, arch in CORPUS} == {
            ('darwin', 'arm64'),
            ('darwin', 'x86_64'),
            ('linux', 'x86_64'),
        }

    def test_every_declared_release_has_an_installer_to_ask(self):
        assert {path.stem for path in INSTALLERS.glob('*.sh')} == declared_releases()


def asset_under_test(case: Case, resolved_urls) -> tuple[str, str, str]:
    """(repo, tag, asset_name) for a case, failing on the case that owns it."""
    resolved = resolved_urls[case]
    if isinstance(resolved, Exception):
        pytest.fail(f'{case[0]} could not resolve a URL for {case[1]}/{case[2]}: {resolved}')

    _, version, url = resolved
    assert version, f'{case[0]} resolved an empty version for {case[1]}/{case[2]}'

    parsed = github_release.parse_release_url(url)
    assert parsed, f'{case[0]} produced {url}, which is not a GitHub release asset URL'
    return (*parsed, url)


@pytest.mark.e2e
@pytest.mark.parametrize(('tool', 'os_name', 'arch'), CORPUS)
def test_the_installer_url_serves_the_asset(tool, os_name, arch, resolved_urls, repo_is_private, http):
    repo, _, url = asset_under_test((tool, os_name, arch), resolved_urls)

    status = http.head(url).status_code
    if status == 404 and repo_is_private(repo):
        pytest.skip(f'{repo} is private: the browser URL 404s whatever token is presented, and only the asset endpoint serves it')
    assert status == 200, f'{url} answered {status}'


@pytest.mark.e2e
@pytest.mark.parametrize(('tool', 'os_name', 'arch'), CORPUS)
def test_the_release_publishes_the_asset_the_installer_asks_for(tool, os_name, arch, resolved_urls, published_assets):
    repo, tag, url = asset_under_test((tool, os_name, arch), resolved_urls)

    asset_name = url.rsplit('/', 1)[-1]
    assets = published_assets(repo, tag)
    assert asset_name in assets, f'{repo} {tag} publishes no {asset_name}; it has {sorted(assets)}'


@pytest.mark.e2e
def test_the_fzf_tmux_companion_resolves_at_the_same_tag(http):
    """fzf-tmux is a shell script in the repo tree, not a release asset, so it is
    the one download the asset-list check above cannot see."""
    _, version, _ = print_url('fzf', 'linux', 'x86_64')
    response = http.get(f'https://raw.githubusercontent.com/junegunn/fzf/{version}/bin/fzf-tmux')
    assert response.status_code == 200, f'fzf-tmux at {version} answered {response.status_code}'
    assert response.text.startswith('#!'), 'fzf-tmux did not come back as a script'
