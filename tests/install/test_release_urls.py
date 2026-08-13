"""Every declared GitHub release publishes the asset this repo asks it for.

This was the gate that let the 23 installer scripts be replaced by Python: it
resolved a URL from each script and from `providers/releases.py` and asserted
the two agreed, for every tool on every platform declared rather than the one
the developer happened to be sitting at. That parity pass has done its job — the
scripts are gone, and asking a deleted file what it would download is not a
weaker test, it is no test. What remains is the same corpus asked of the code
that ships.

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
import tempfile
from collections.abc import Callable
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx2
import pytest

from dotfiles import catalog
from dotfiles import github_release
from dotfiles import machine as machines
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import ghrelease
from dotfiles.providers import releases as providers

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_YML = REPO_ROOT / 'install' / 'packages.yml'

# The architectures each OS family serves. Writing the pairing out is the point:
# macOS is the one OS serving two, so a tool that spells only one of them is
# invisible from whichever Mac runs the suite. Keyed on the coordinate rather
# than on a `platform:` string, because the loader answers in coordinates and a
# manifest naming its axes directly has no platform label at all.
OS_TARGETS = {
    OSFamily.DARWIN: (('darwin', 'arm64'), ('darwin', 'x86_64')),
    OSFamily.LINUX: (('linux', 'x86_64'),),
}

Case = tuple[str, str, str]

LINUX = Target(OSFamily.LINUX, Arch.X86_64)
"""Enough to ask an asset function whether it has companions — the answer does
not vary by target for any of them, and every declared tool covers this one."""


def declared_releases() -> set[str]:
    return {entry.name for entry in catalog.load().section('github_releases')}


def build_corpus() -> list[Case]:
    """Every (tool, os, arch) any manifest actually asks for, deduplicated.

    Asked of `machine.load` and `Subscription.wants` rather than of the manifest
    files, because what a manifest asks for is not what its `github_releases:`
    key literally contains — `true` means the whole section, absent means none,
    and a list means membership. Re-reading the key here would be a second copy
    of that grammar, and it is the copy that would be wrong the first time a
    machine spells its subscription the other way.
    """
    declared = catalog.load()
    cases: set[Case] = set()
    for name in machines.names(REPO_ROOT):
        machine = machines.load(name, REPO_ROOT)
        for entry in declared.section('github_releases'):
            if machine.subscription('github_releases').wants(entry):
                cases.update((entry.name, *target) for target in OS_TARGETS[machine.coordinates.os_family])
    return sorted(cases)


CORPUS = build_corpus()


def resolve_url(tool: str, os_name: str, arch: str) -> tuple[str, str, str]:
    """What this repo would download for one tool on one platform."""
    entry = catalog.load(PACKAGES_YML).find('github_releases', tool)
    assert isinstance(entry, catalog.GithubRelease)

    tag = ghrelease.resolve_tag(entry)
    if tag is None:
        raise AssertionError(ghrelease.unresolved(entry, offline=False))

    asset = providers.ASSETS[tool](tag, Target(OSFamily(os_name), Arch(arch)))
    return tool, tag, providers.asset_url(entry.repo, tag, asset)


@pytest.fixture(scope='session')
def resolved_urls() -> dict[Case, tuple[str, str, str] | Exception]:
    """Resolve the whole matrix once, concurrently.

    Each entry costs a release API call, and a tool declared on three platforms
    resolves its version three times, so the matrix is network-bound rather than
    CPU-bound. A failure is returned rather than raised so it lands on the case
    that owns it instead of taking the fixture, and the rest of the matrix down
    with it.
    """

    def resolve(case: Case) -> tuple[str, str, str] | Exception:
        try:
            return resolve_url(*case)
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

    def test_every_declared_release_has_an_asset_function_to_ask(self):
        assert set(providers.ASSETS) == declared_releases()


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
def test_the_resolved_url_serves_the_asset(tool, os_name, arch, resolved_urls, repo_is_private, http):
    repo, _, url = asset_under_test((tool, os_name, arch), resolved_urls)

    status = http.head(url).status_code
    if status == 404 and repo_is_private(repo):
        pytest.skip(f'{repo} is private: the browser URL 404s whatever token is presented, and only the asset endpoint serves it')
    assert status == 200, f'{url} answered {status}'


@pytest.mark.e2e
@pytest.mark.parametrize(('tool', 'os_name', 'arch'), CORPUS)
def test_the_release_publishes_the_asset_asked_for(tool, os_name, arch, resolved_urls, published_assets):
    repo, tag, url = asset_under_test((tool, os_name, arch), resolved_urls)

    asset_name = url.rsplit('/', 1)[-1]
    assets = published_assets(repo, tag)
    assert asset_name in assets, f'{repo} {tag} publishes no {asset_name}; it has {sorted(assets)}'


@pytest.mark.e2e
@pytest.mark.parametrize('tool', sorted(providers.COMPANIONS))
def test_every_companion_resolves_at_its_own_tag(tool, resolved_urls, http):
    """A companion is fetched from the repo tree rather than the release, so it is
    the one download the asset-list check above cannot see.

    Parametrized off `COMPANIONS` directly, which is only possible because a
    companion's name is static and its URL is the half carrying the tag. Reading it
    off an asset function would mean inventing a tag to ask with, and inventing one
    is guessing at what the answer depends on.
    """
    _, tag, _ = asset_under_test((tool, 'linux', 'x86_64'), resolved_urls)

    for companion in providers.COMPANIONS[tool]:
        response = http.get(companion.url(tag))
        assert response.status_code == 200, f'{companion.name} at {tag} answered {response.status_code}'
        assert response.text.startswith('#!'), f'{companion.name} did not come back as a script'


# ─────────────────────────────────────────────────────────────────────────────
# Which install scripts this fleet fetches and executes
# ─────────────────────────────────────────────────────────────────────────────


def _fleet_install_urls() -> list[tuple[str, str]]:
    """Every `custom_installers` entry whose install script comes from a repo here.

    Off the declaration rather than a list, because the whole property being
    guarded is that nobody adds a fifth one on a branch ref. A list would pass
    while the new entry went unmeasured.

    Scoped to `raw.githubusercontent.com/datapointchris/` on purpose. A vendor URL
    like `https://claude.ai/install.sh` carries no ref this repo could pin — the
    vendor decides what that path serves, and pretending otherwise would fail the
    test for something no commit here can fix.
    """
    entries = catalog.load(PACKAGES_YML).section('custom_installers')
    prefix = 'https://raw.githubusercontent.com/datapointchris/'
    return sorted((entry.name, entry.install_url) for entry in entries if entry.install_url.startswith(prefix))


@pytest.mark.parametrize(('name', 'url'), _fleet_install_urls())
def test_an_install_script_is_fetched_from_a_tag_rather_than_a_branch(name, url):
    """`providers/custom.py` downloads this URL and executes it, which is the
    widest reach anything in the install engine has.

    standards/dependencies.md § "Classify a dependency by what it can reach" puts
    repo code at "reputable registries and taps, pinned". A `main` ref met the
    first half and not the second: two machines converging a day apart executed
    whatever had been pushed in between, and neither run could say what it ran.

    No network, because the fault is visible in the declaration. This is the test
    that catches the fifth entry being added on a branch — the e2e one below only
    proves the tag that *is* written resolves.
    """
    ref = url.removeprefix('https://raw.githubusercontent.com/datapointchris/').split('/')[1]

    assert ref != 'main', f'{name} fetches its installer from main; name a release tag'
    assert ref.startswith('v'), f'{name} fetches from {ref!r}, which is not a release tag'


@pytest.mark.e2e
@pytest.mark.parametrize(('name', 'url'), _fleet_install_urls())
def test_the_pinned_install_script_still_resolves(name, url, http):
    """A tag deleted or renamed upstream breaks a fresh machine build and nothing
    else, so without this it surfaces on a rebuild rather than in CI.

    Asserting it comes back as a script, not merely as 200: raw.githubusercontent
    answers 200 with an HTML error page for some ref shapes, and a bundle staging
    that page would hand `bash` an install that fails halfway through.
    """
    response = http.get(url)

    assert response.status_code == 200, f'{name}: {url} answered {response.status_code}'
    assert response.text.startswith('#!'), f'{name}: {url} did not come back as a script'


# ─────────────────────────────────────────────────────────────────────────────
# Which releases can be checksum-verified at all
# ─────────────────────────────────────────────────────────────────────────────
#
# `checksum: required` is the default, so the entries that cannot satisfy it say
# so in `packages.yml` rather than being discovered by a broken install. This
# compares each declaration against what the release actually publishes today,
# and fails in *both* directions: a project that starts publishing checksums must
# stop being an exception, and one that stops must be caught before an install
# refuses it.
#
# The lists live in the declaration and are read from it here rather than
# restated. A second copy is a copy that rots, and it is the copy a reader trusts
# — the version this replaced named hadolint and tenv, which both verify, and
# missed shellcheck, win32yank and zk, which cannot.

STATE_FOR_DECLARATION = {
    catalog.CHECKSUM_REQUIRED: 'VERIFIABLE',
    catalog.CHECKSUM_UNPUBLISHED: 'UNPUBLISHED',
    catalog.CHECKSUM_UNLISTED: 'NO-ENTRY',
}
"""What each declared value claims a live release will turn out to be."""


def declared_checksum_states() -> dict[str, str]:
    return {entry.name: entry.checksum for entry in catalog.load(PACKAGES_YML).section('github_releases')}


def checksum_state(repo: str, tag: str, asset_name: str, assets: dict[str, int]) -> str:
    """What verification would find, without downloading the asset to hash it."""
    checksum_asset = github_release.select_checksum_asset(sorted(assets), asset_name)
    if checksum_asset is None:
        return 'UNPUBLISHED'

    destination = Path(tempfile.mkstemp(prefix='checksums-')[1])
    try:
        browser_url = f'https://github.com/{repo}/releases/download/{tag}/{checksum_asset}'
        if not github_release.download_asset(browser_url, destination, repo, tag, checksum_asset):
            return 'UNREACHABLE'
        from_sidecar = checksum_asset.endswith(github_release.CHECKSUM_SIDECAR_SUFFIXES)
        found = github_release.checksum_for_asset(destination.read_text(), asset_name, from_sidecar)
    finally:
        destination.unlink(missing_ok=True)

    return 'VERIFIABLE' if found else 'NO-ENTRY'


@pytest.mark.e2e
@pytest.mark.parametrize(('tool', 'os_name', 'arch'), CORPUS)
def test_a_release_verifies_exactly_as_its_entry_declares(tool, os_name, arch, resolved_urls, published_assets):
    repo, tag, url = asset_under_test((tool, os_name, arch), resolved_urls)
    asset_name = url.rsplit('/', 1)[-1]

    declared = declared_checksum_states()[tool]
    expected = STATE_FOR_DECLARATION[declared]
    state = checksum_state(repo, tag, asset_name, published_assets(repo, tag))

    assert state == expected, (
        f'{tool} declares checksum: {declared}, which claims {expected}, but {repo} {tag} answers {state} — change the declaration'
    )


def test_every_declared_checksum_state_is_one_the_engine_acts_on():
    """No network. A value the catalog accepts and the install engine has no
    branch for would install unverified while reading as declared."""
    assert set(STATE_FOR_DECLARATION) == catalog.CHECKSUM_STATES


# ─────────────────────────────────────────────────────────────────────────────
# The bundled sections: cargo and go name their assets from data, not code
# ─────────────────────────────────────────────────────────────────────────────


def bundled_entries() -> list[tuple[str, str]]:
    """Every `cargo_packages`/`go_tools` entry a bundle can stage, by section.

    These are the sections whose asset naming is `binary_pattern` in
    `packages.yml` rather than a function in `providers/releases.py`, which is
    why the corpus above never covered them — and why `watchexec-cli` spelled
    `{version}` where cargo-dist publishes the bare number, 404ing every bundle
    build for as long as nothing asked.
    """
    declared = catalog.load()
    found = []
    for section in ('cargo_packages', 'go_tools'):
        for entry in declared.section(section):
            if getattr(entry, 'github_repo', '') and getattr(entry, 'binary_pattern', ''):
                found.append((section, entry.name))
    return sorted(found)


BUNDLED = bundled_entries()


@pytest.mark.e2e
@pytest.mark.parametrize(('section', 'name'), BUNDLED, ids=lambda value: value if isinstance(value, str) else str(value))
def test_a_bundled_pattern_names_an_asset_the_release_publishes(section, name, published_assets, http):
    """Asked of the same function that installs from the bundle.

    `cargo.stage`/`gotool.stage` are what name the file on both sides, so this
    covers the expansion rather than re-deriving it — the mistake the release
    corpus above records as its own reason for existing.

    Linux x86_64 only: unlike the release entries, a bundle is built for the one
    machine that needs it, and the offline manifest is `wsl-work-workstation`.
    """
    from dotfiles.providers import cargo
    from dotfiles.providers import gotool

    entry = catalog.load().find(section, name)
    # `latest_version`, which is what the bundler calls — not `latest_tag`. A
    # workspace repo tags its subcrates too, and the newest tag in `BurntSushi/
    # ripgrep` is `ignore-0.4.33`, a crate release carrying no assets at all.
    tag = github_release.latest_version(entry.github_repo)
    if not tag:
        pytest.skip(f'{entry.github_repo} answered with no release')

    target = Target(OSFamily('linux'), Arch('x86_64'))
    staged = (cargo.stage if section == 'cargo_packages' else gotool.stage)(entry, tag, target)

    assert staged in published_assets(entry.github_repo, tag), (
        f'{name} asks for {staged!r}, which {entry.github_repo} {tag} does not publish — '
        f'check {{version}} against {{version_num}} in its binary_pattern'
    )
