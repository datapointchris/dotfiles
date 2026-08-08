"""
Tests for parse_packages.py

Run with: pytest tests/install/test_parse_packages.py
Or from project root: python -m pytest tests/install/
"""

from pathlib import Path

import pytest
import yaml

from dotfiles import parse_packages

PACKAGES_YML = Path(__file__).parent.parent.parent / 'install' / 'packages.yml'
MANIFESTS_DIR = Path(__file__).parent.parent.parent / 'install' / 'manifests'


@pytest.fixture
def real_packages_data():
    """Load actual packages.yml for tests that validate live configuration."""
    with open(PACKAGES_YML) as f:
        return yaml.safe_load(f)


@pytest.fixture
def sample_packages_data():
    """Sample packages.yml data for testing."""
    return {
        'runtimes': {'node': {'version': '22'}, 'python': {'version': '3.12'}},
        'system_packages': [
            {'apt': 'curl', 'brew': 'curl', 'pacman': 'curl'},
            {'apt': 'git', 'brew': 'git', 'pacman': 'git'},
            {'apt': 'build-essential', 'pacman': 'base-devel'},
        ],
        'cargo_packages': [{'name': 'ripgrep'}, {'name': 'fd-find'}],
        'npm_globals': {
            'formatters': [{'name': 'prettier'}, {'name': 'markdownlint-cli'}],
            'language_servers': [{'name': 'typescript-language-server'}],
        },
        'uv_tools': {'formatters': [{'name': 'black'}, {'name': 'isort'}]},
        'go_tools': [
            {'package': 'github.com/jesseduffield/lazydocker@latest'},
            {'package': 'github.com/rhysd/actionlint/cmd/actionlint@latest'},
        ],
        'mas_apps': [{'id': 937984704, 'name': 'Amphetamine'}, {'id': 1352778147, 'name': 'Bitwarden'}],
        'github_releases': [
            {'name': 'neovim', 'repo': 'neovim/neovim', 'min_version': '0.9.0'},
            {'name': 'lazygit', 'repo': 'jesseduffield/lazygit'},
        ],
        'shell_plugins': [
            {'name': 'zsh-autosuggestions', 'repo': 'zsh-users/zsh-autosuggestions'},
            {'name': 'fast-syntax-highlighting', 'repo': 'zdharma-continuum/fast-syntax-highlighting'},
        ],
        'macos_taps': ['homebrew/cask-fonts'],
        'flatpak_apps': [{'flatpak_id': 'com.slack.Slack'}, {'flatpak_id': 'us.zoom.Zoom'}],
        'macos_casks': [{'name': 'alfred'}, {'name': 'bettertouchtool'}],
    }


def test_get_value_simple(sample_packages_data):
    """Test getting simple nested value."""
    value = parse_packages.get_value(sample_packages_data, 'runtimes.node.version')
    assert value == '22'


def test_get_value_deep_nesting(sample_packages_data):
    """Test getting deeply nested value."""
    value = parse_packages.get_value(sample_packages_data, 'runtimes.python.version')
    assert value == '3.12'


def test_get_system_packages_apt(sample_packages_data):
    """Test extracting apt packages."""
    packages = parse_packages.get_system_packages(sample_packages_data, 'apt')
    assert packages == ['curl', 'git', 'build-essential']


def test_get_system_packages_brew(sample_packages_data):
    """Test extracting brew packages."""
    packages = parse_packages.get_system_packages(sample_packages_data, 'brew')
    assert packages == ['curl', 'git']


def test_get_system_packages_pacman(sample_packages_data):
    """Test extracting pacman packages."""
    packages = parse_packages.get_system_packages(sample_packages_data, 'pacman')
    assert packages == ['curl', 'git', 'base-devel']


def test_get_cargo_packages(sample_packages_data):
    """Test extracting cargo package names."""
    packages = parse_packages.get_cargo_packages(sample_packages_data)
    assert packages == ['ripgrep', 'fd-find']


def test_get_npm_packages(sample_packages_data):
    """Test extracting npm package names from all categories."""
    packages = parse_packages.get_npm_packages(sample_packages_data)
    assert packages == ['prettier', 'markdownlint-cli', 'typescript-language-server']


def test_get_uv_packages(sample_packages_data):
    """Test extracting uv tool names."""
    packages = parse_packages.get_uv_packages(sample_packages_data)
    assert packages == ['black', 'isort']


def test_get_git_uv_packages_defaults_to_release_mode():
    """A git uv tool is installed pinned to its newest release unless told otherwise.

    The ref mode travels to the shell because it decides the install: pinning is
    what lets a tool's own updater run on it, and what stops `uv tool upgrade`
    re-resolving a pin to the same commit and calling it current forever.
    """
    data = {'git_uv_tools': [{'name': 'syncer', 'repo': 'https://github.com/datapointchris/syncer.git'}]}

    assert parse_packages.get_git_uv_packages(data) == ['syncer|https://github.com/datapointchris/syncer.git|release']


def test_get_git_uv_packages_marks_a_branch_tracking_tool():
    """`tracks_branch` is for a repo publishing no releases, so there is no tag to pin."""
    data = {
        'git_uv_tools': [
            {
                'name': 'keymap-align',
                'repo': 'https://github.com/datapointchris/keymap-align.git',
                'tracks_branch': True,
            }
        ]
    }

    assert parse_packages.get_git_uv_packages(data) == ['keymap-align|https://github.com/datapointchris/keymap-align.git|branch']


def test_get_git_uv_packages_is_pipe_delimited(real_packages_data):
    """Pipe, not colon: a clone URL contains colons, so the shell cannot split on them."""
    for entry in parse_packages.get_git_uv_packages(real_packages_data):
        name, repo, ref_mode = entry.split('|')
        assert name
        assert repo.startswith('https://')
        assert ref_mode in ('release', 'branch')


def test_get_go_packages(sample_packages_data):
    """Test extracting go tool package paths."""
    packages = parse_packages.get_go_packages(sample_packages_data)
    assert packages == ['github.com/jesseduffield/lazydocker@latest', 'github.com/rhysd/actionlint/cmd/actionlint@latest']


def test_get_mas_apps(sample_packages_data):
    """Test extracting Mac App Store app IDs."""
    packages = parse_packages.get_mas_apps(sample_packages_data)
    assert packages == ['937984704', '1352778147']


def test_get_github_packages(sample_packages_data):
    """Test extracting GitHub release package names."""
    packages = parse_packages.get_github_packages(sample_packages_data)
    assert packages == ['neovim', 'lazygit']


def test_get_shell_plugins_names(sample_packages_data):
    """Test extracting shell plugin names."""
    packages = parse_packages.get_shell_plugins(sample_packages_data, output_format='names')
    assert packages == ['zsh-autosuggestions', 'fast-syntax-highlighting']


def test_get_shell_plugins_name_repo(sample_packages_data):
    """Test extracting shell plugin name|repo pairs."""
    packages = parse_packages.get_shell_plugins(sample_packages_data, output_format='name_repo')
    assert packages == [
        'zsh-autosuggestions|zsh-users/zsh-autosuggestions',
        'fast-syntax-highlighting|zdharma-continuum/fast-syntax-highlighting',
    ]


def test_get_github_release_field(sample_packages_data):
    """Test getting field from GitHub release."""
    value = parse_packages.get_github_release_field(sample_packages_data, 'neovim', 'min_version')
    assert value == '0.9.0'

    value = parse_packages.get_github_release_field(sample_packages_data, 'neovim', 'repo')
    assert value == 'neovim/neovim'


def test_get_github_release_field_not_found(sample_packages_data):
    """Test getting field from non-existent release."""
    value = parse_packages.get_github_release_field(sample_packages_data, 'nonexistent', 'repo')
    assert value is None


def test_get_macos_taps(sample_packages_data):
    """Test extracting macOS Homebrew taps."""
    taps = parse_packages.get_macos_taps(sample_packages_data)
    assert taps == ['homebrew/cask-fonts']


def test_get_flatpak_apps(sample_packages_data):
    """Test extracting Flatpak app IDs."""
    apps = parse_packages.get_flatpak_apps(sample_packages_data)
    assert apps == ['com.slack.Slack', 'us.zoom.Zoom']


def test_get_macos_casks(sample_packages_data):
    """Test extracting macOS cask names."""
    casks = parse_packages.get_macos_casks(sample_packages_data)
    assert casks == ['alfred', 'bettertouchtool']


def test_get_cargo_packages_empty():
    """Test with no cargo packages."""
    data = {}
    packages = parse_packages.get_cargo_packages(data)
    assert packages == []


def test_get_system_packages_empty():
    """Test with no system packages."""
    data = {}
    packages = parse_packages.get_system_packages(data, 'apt')
    assert packages == []


# ================================================================
# Live packages.yml validation: cargo binary_pattern
# ================================================================
# broot has burned us twice with non-standard release format.
# These tests pin the known-good patterns so regressions are caught
# before the offline bundle is built, not after install on WSL.


def test_broot_uses_version_pattern_not_target(real_packages_data):
    """broot releases a fat zip named by version (broot_1.56.2.zip), NOT by
    target triple (broot_x86_64-unknown-linux-gnu.zip). Using {target} causes
    a 404 on every bundle build. This test pins the correct placeholder."""
    cargo_packages = real_packages_data.get('cargo_packages', [])
    broot = next((p for p in cargo_packages if p.get('name') == 'broot'), None)

    assert broot is not None, 'broot must be present in cargo_packages'
    pattern = broot.get('binary_pattern', '')

    assert pattern, 'broot must have a binary_pattern field'
    assert '{target}' not in pattern, (
        f'broot binary_pattern must NOT use {{target}} — broot ships a fat zip with all platforms, named only by version. Got: {pattern!r}'
    )
    assert '{version_num}' in pattern or '{version}' in pattern, f'broot binary_pattern must use a version placeholder. Got: {pattern!r}'


def test_fnm_overrides_both_target_triples(real_packages_data):
    """fnm names its assets after the OS word (fnm-linux.zip, fnm-macos.zip), so the
    bare {target} triple 404s on every bundle build. Both overrides must be present:
    a linux-only override leaves the macOS bundle broken and vice versa."""
    cargo_packages = real_packages_data.get('cargo_packages', [])
    fnm = next((p for p in cargo_packages if p.get('name') == 'fnm'), None)

    assert fnm is not None, 'fnm must be present in cargo_packages'
    assert fnm.get('linux_target') == 'linux', f'fnm must override linux_target to the OS word. Got: {fnm.get("linux_target")!r}'
    assert fnm.get('darwin_target') == 'macos', f'fnm must override darwin_target to the OS word. Got: {fnm.get("darwin_target")!r}'


def test_manifests_installing_npm_globals_also_install_fnm():
    """The node phase runs whenever a manifest has npm globals, and it aborts if fnm
    is missing — which is how a WSL offline install died with `fnm not found`. Read
    from disk rather than a list so a new manifest is covered the day it is added."""
    for manifest_path in sorted(MANIFESTS_DIR.glob('*.yml')):
        manifest = yaml.safe_load(manifest_path.read_text())
        if not manifest.get('npm_globals'):
            continue
        cargo = manifest.get('cargo_packages')
        assert cargo is True or 'fnm' in cargo, f'{manifest_path.name} installs npm globals but no fnm; the node phase will abort'


def test_cargo_packages_with_binary_pattern_have_github_repo(real_packages_data):
    """Any cargo package with a binary_pattern must also have a github_repo,
    since the pattern is only used to construct a GitHub release download URL."""
    cargo_packages = real_packages_data.get('cargo_packages', [])
    for pkg in cargo_packages:
        if 'binary_pattern' in pkg:
            assert 'github_repo' in pkg, (
                f'Cargo package {pkg["name"]!r} has binary_pattern but no github_repo. binary_pattern is only used for GitHub release URLs.'
            )


# ================================================================
# Unit tests: filter_custom_installers_by_manifest
# ================================================================
# The offline bundler runs --type=custom --filter=bundle_install_script
# --manifest=<machine> to pick up only the install scripts that the target
# machine actually uses AND that have a downloadable script worth caching.
# Both predicates must compose correctly or the bundle will either be missing
# scripts (broken offline install) or carrying scripts the machine never runs.
#
# Each parametrize row encodes one mutation defense: invert the membership
# check, drop the True branch, swallow filter_field, etc. Together they pin
# every branch of the filter without requiring manual mutation testing.


@pytest.fixture
def custom_installers_sample():
    """Realistic sample mirroring the structure of packages.yml custom_installers."""
    return {
        'custom_installers': [
            {'name': 'claude-code', 'bundle_install_script': True},
            {'name': 'theme', 'bundle_install_script': True},
            {'name': 'font', 'bundle_install_script': True},
            {'name': 'awscli'},
            {'name': 'terraform-ls'},
        ]
    }


@pytest.mark.parametrize(
    'case_id, manifest, filter_field, expected',
    [
        # Intersection: list of names returns only names present in BOTH manifest and packages.yml.
        # Mutation it catches: inverting `in` to `not in` flips intersection to complement.
        ('list_intersection', {'custom_installers': ['claude-code', 'awscli']}, None, ['claude-code', 'awscli']),
        # True branch returns every entry in declaration order.
        # Mutation it catches: True branch returning [] or filtered list.
        ('true_returns_all', {'custom_installers': True}, None, ['claude-code', 'theme', 'font', 'awscli', 'terraform-ls']),
        # Missing field defaults to [], not all.
        # Mutation it catches: `manifest.get('custom_installers', True)` (wrong default).
        ('missing_field_returns_empty', {}, None, []),
        # Empty list returns []. Note this is distinct from True — falsy list must NOT fall
        # through to the True branch.
        # Mutation it catches: `if not manifest_installers` placed BEFORE the `is True` check.
        ('empty_list_returns_empty', {'custom_installers': []}, None, []),
        # filter_field ANDs with manifest membership. terraform-ls and awscli are in the
        # manifest but lack bundle_install_script; only claude-code survives both predicates.
        # Mutation it catches: dropping the filter_field clause (would return all 3).
        (
            'filter_field_ands_with_manifest',
            {'custom_installers': ['claude-code', 'awscli', 'terraform-ls']},
            'bundle_install_script',
            ['claude-code'],
        ),
        # filter_field still applies when manifest_installers is True.
        # Mutation it catches: filter_field clause skipped on the True branch only.
        ('filter_field_with_true_manifest', {'custom_installers': True}, 'bundle_install_script', ['claude-code', 'theme', 'font']),
        # filter_field with manifest containing only un-flagged names yields []. Catches the
        # case where manifest says "yes install awscli" but the bundle has no script for it.
        # Mutation it catches: filter_field treated as OR (would return both names).
        ('filter_field_excludes_all_unflagged', {'custom_installers': ['awscli', 'terraform-ls']}, 'bundle_install_script', []),
        # Stale manifest names (no matching packages.yml entry) are silently dropped, not errors.
        # Mutation it catches: emitting manifest names verbatim instead of intersecting.
        (
            'unknown_manifest_names_dropped',
            {'custom_installers': ['claude-code', 'ghost-installer', 'another-ghost']},
            None,
            ['claude-code'],
        ),
        # filter_field with missing manifest field still returns [] (not "all where flag").
        # Mutation it catches: filter_field path bypassing the manifest check entirely.
        ('filter_field_with_missing_manifest', {}, 'bundle_install_script', []),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_filter_custom_installers_by_manifest(custom_installers_sample, case_id, manifest, filter_field, expected):
    """Parametrized contract for filter_custom_installers_by_manifest. See the case
    comments above for the specific mutation each row defends against."""
    result = parse_packages.filter_custom_installers_by_manifest(custom_installers_sample, manifest, filter_field=filter_field)
    assert result == expected, f'case={case_id!r}: expected {expected}, got {result}'


# ================================================================
# Live-config invariants: cargo bundle composition by manifest
# ================================================================
# webviewrs is the regression: it depends on WebKitGTK + GStreamer at runtime
# (packages.yml:562-568) so it ships only on archlinux-personal-workstation.
# The offline bundler used to fetch all cargo_packages indiscriminately, which
# 404'd on webviewrs and broke WSL bundles.
#
# This parametrized test runs the same assertion across every machine manifest
# we ship. It's the strongest defense against two specific regression classes:
#
#   1. Filter goes back to "fetch everything" — webviewrs leaks into wsl/mac.
#   2. Someone hardcodes `if name == 'webviewrs': skip` — the arch row breaks.


@pytest.mark.parametrize(
    'manifest_name, must_include, must_exclude',
    [
        # WSL work: the manifest that triggered the bug. fnm is required on every
        # manifest with npm_globals — the node phase aborts without it.
        ('wsl-work-workstation', ['fnm', 'bat', 'fd', 'eza', 'zoxide', 'delta', 'oxker', 'broot'], ['webviewrs']),
        # macOS personal: same cargo set as WSL, also no webviewrs.
        ('macos-personal-workstation', ['fnm', 'bat', 'fd', 'eza', 'zoxide', 'delta', 'oxker', 'broot'], ['webviewrs']),
        # Arch personal: the only machine that actually installs webviewrs.
        # Proves the filter is data-driven, not a hardcoded skip.
        ('archlinux-personal-workstation', ['fnm', 'bat', 'fd', 'eza', 'zoxide', 'delta', 'oxker', 'broot', 'webviewrs'], []),
        # Minimal LXC server: lean cargo set — no broot, no webviewrs, and no fnm
        # since it installs no npm globals. Catches mutations that hardcode-include
        # workstation cargo tools for all Linux.
        ('linux-lxc-server', ['bat', 'fd', 'eza', 'zoxide', 'delta', 'oxker'], ['broot', 'webviewrs', 'fnm']),
    ],
)
def test_cargo_bundle_composition_by_manifest(real_packages_data, manifest_name, must_include, must_exclude):
    """Each machine's cargo bundle must contain its manifest's packages and nothing else.
    Names compared are commands (binary_info first column), since fd-find→fd, git-delta→delta."""
    manifest = parse_packages.load_manifest(manifest_name)
    result = parse_packages.filter_cargo_packages_by_manifest(real_packages_data, manifest, output_format='binary_info')
    names = {line.split('|', 1)[0] for line in result}
    missing = [n for n in must_include if n not in names]
    leaked = [n for n in must_exclude if n in names]
    assert not missing, f'{manifest_name}: missing required cargo entries {missing}; got {sorted(names)}'
    assert not leaked, f'{manifest_name}: cargo bundle leaked {leaked}; got {sorted(names)}'


# ================================================================
# System-package tiering (core vs workstation)
# ================================================================
# The minimal LXC/server profile installs `system_packages: core`, which must
# be a strict subset of the full workstation set. These guard the split so a
# heavy workstation-only package (docker, ffmpeg, ...) can never leak onto a
# minimal server, and a core-tagged base tool is never dropped from it.


def test_system_core_is_subset_of_workstation(real_packages_data):
    """The core tier must be a strict subset of the workstation tier for apt."""
    core = set(parse_packages.get_system_packages(real_packages_data, 'apt', 'core'))
    workstation = set(parse_packages.get_system_packages(real_packages_data, 'apt', 'workstation'))
    assert core, 'core tier unexpectedly empty'
    assert core < workstation, 'core must be a strict subset of workstation'


def test_system_core_excludes_workstation_only_packages(real_packages_data):
    """Heavy workstation-only packages must never appear in the core tier."""
    core = set(parse_packages.get_system_packages(real_packages_data, 'apt', 'core'))
    for pkg in ['docker-ce', 'ffmpeg', 'imagemagick', 'mpv', 'graphviz']:
        assert pkg not in core, f'{pkg} leaked into the core (server) tier'


def test_system_core_includes_essential_base(real_packages_data):
    """Bootstrap and everyday base tools must be present in the core tier.

    ripgrep is intentionally absent here: it moved to cargo_packages (installed
    via cargo binstall's prebuilt binaries). Its "reaches every machine including
    servers" guarantee now lives in test_ripgrep_reaches_servers_via_cargo.
    """
    core = set(parse_packages.get_system_packages(real_packages_data, 'apt', 'core'))
    for pkg in ['git', 'zsh', 'tmux', 'python3-yaml', 'curl']:
        assert pkg in core, f'{pkg} missing from the core (server) tier'


def test_ripgrep_reaches_servers_via_cargo(real_packages_data):
    """ripgrep must still land on minimal servers, now through the cargo path.

    It ships prebuilt release binaries, so cargo binstall installs it without
    compiling — the reason it can move off system_packages yet still serve the
    core (LXC server) tier that has no heavy build toolchain.
    """
    cargo_names = {pkg['name'] for pkg in real_packages_data.get('cargo_packages', [])}
    assert 'ripgrep' in cargo_names, 'ripgrep must be in cargo_packages'

    server_manifest = yaml.safe_load((MANIFESTS_DIR / 'linux-lxc-server.yml').read_text())
    assert 'ripgrep' in server_manifest.get('cargo_packages', []), (
        'ripgrep must be in the linux-lxc-server cargo list so servers still get it'
    )


def test_system_default_tier_is_workstation(real_packages_data):
    """Callers that omit a tier get the full workstation set (backward compatible)."""
    default = parse_packages.get_system_packages(real_packages_data, 'apt')
    workstation = parse_packages.get_system_packages(real_packages_data, 'apt', 'workstation')
    assert default == workstation


# ================================================================
# Owner filtering (drives `update.sh --mine`)
# ================================================================


@pytest.mark.parametrize(
    'entry,expected',
    [
        ({'repo': 'datapointchris/ichrisbirch'}, 'datapointchris'),
        ({'repo': 'https://github.com/datapointchris/indy.git'}, 'datapointchris'),
        ({'repo': 'https://github.com/datapointchris/indy'}, 'datapointchris'),
        ({'github_repo': 'datapointchris/todoui'}, 'datapointchris'),
        ({'package': 'github.com/datapointchris/forge'}, 'datapointchris'),
        ({'package': 'github.com/joshmedeski/sesh/v2'}, 'joshmedeski'),
        ({'apt': 'curl', 'brew': 'curl'}, None),
        ({'name': 'ruff'}, None),
    ],
)
def test_extract_owner_handles_every_field_shape(entry, expected):
    """Sections disagree on which field carries the owner and in what form."""
    assert parse_packages.extract_owner(entry) == expected


def test_owner_filter_spans_every_install_method(real_packages_data):
    """--mine must reach Chris's tools however they happen to be installed.

    Regression guard for the reason owner-derivation was chosen over a `personal`
    tag: a tag has to be remembered on each new tool, and silently excludes what
    it misses.

    Each section is checked by representative rather than by exact set. An exact
    set turns "a new tool was added" into a test failure, which teaches you to
    edit the assertion instead of reading it — and the assertion is not an
    inventory, it is proof that owner-derivation reaches that section at all.
    The negative direction is test_owner_filter_excludes_third_party.
    """
    owned = parse_packages.filter_packages_by_owner(real_packages_data, 'datapointchris')

    representatives = {
        'github_releases': {'icb', 'learning', 'nomad', 'meso'},
        'custom_installers': {'theme', 'font', 'bashselfupdate'},
        'go_tools': {'todoui', 'forge', 'toolbox'},
        'git_uv_tools': {'indy'},
        'cargo_packages': {'webviewrs'},
    }
    for section, expected in representatives.items():
        assert expected <= {i['name'] for i in owned[section]}, section


def test_owner_filter_excludes_third_party(real_packages_data):
    """Third-party tools must not survive the owner filter."""
    owned = parse_packages.filter_packages_by_owner(real_packages_data, 'datapointchris')

    assert 'terraform-ls' not in {i['name'] for i in owned['custom_installers']}
    assert 'sesh' not in {i['name'] for i in owned['go_tools']}
    assert 'neovim' not in {i['name'] for i in owned['github_releases']}


def test_owner_filter_empties_ownerless_sections(real_packages_data):
    """Registry-sourced sections have no GitHub owner and must match nothing."""
    owned = parse_packages.filter_packages_by_owner(real_packages_data, 'datapointchris')

    assert owned['system_packages'] == []
    # npm_globals and uv_tools nest their lists one level deeper, under categories
    assert all(not entries for entries in owned['npm_globals'].values())
    assert all(not entries for entries in owned['uv_tools'].values())


def test_owner_filter_preserves_section_structure(real_packages_data):
    """Getters run against the filtered data, so every section must still exist."""
    owned = parse_packages.filter_packages_by_owner(real_packages_data, 'datapointchris')
    assert set(owned) == set(real_packages_data)


def test_owner_filter_is_empty_for_unknown_owner(real_packages_data):
    """An owner with nothing in packages.yml yields no packages, not an error."""
    owned = parse_packages.filter_packages_by_owner(real_packages_data, 'nobody-at-all')
    assert parse_packages.get_github_packages(owned) == []
    assert parse_packages.get_custom_installers(owned) == []
