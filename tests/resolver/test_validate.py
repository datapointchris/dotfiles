"""Whether the declaration itself holds together, checked against the typed loaders.

These ran as a subprocess against `packages verify --root <tmp>` and asserted on
fragments of its printed report — `'0 errors, 0 warnings' in stdout`, `"names
'ghost-tool'" in stderr`. That tests the wording, which is free to change, rather
than the finding, which is not. The findings are objects now and the assertions
are about them.

Each test builds only the files its check needs. A section absent from `packages`
means no such entries exist in the synthetic world.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import catalog
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import validate
from dotfiles.validate import Severity

LINUX = {'machine': 'test-machine', 'platform': 'linux'}
"""Every manifest needs coordinates to load at all, which is `machine.py`'s rule
and not this module's. A manifest that will not load is reported as such and its
other questions wait for the next run — the same short-circuit the catalog gets,
for the same reason."""


def tree(root: Path, *, packages: dict[str, Any] | None = None, manifests: dict[str, dict[str, Any]] | None = None) -> Path:
    install = root / 'install'
    (install / 'manifests').mkdir(parents=True, exist_ok=True)
    (install / 'packages.yml').write_text(yaml.safe_dump(packages or {}, sort_keys=False))
    for name, content in (manifests or {}).items():
        (install / 'manifests' / f'{name}.yml').write_text(yaml.safe_dump(content, sort_keys=False))
    return root


def messages(findings: tuple[validate.Finding, ...], severity: Severity) -> list[str]:
    return [finding.message for finding in findings if finding.severity is severity]


def test_a_consistent_tree_has_nothing_to_report(tmp_path: Path) -> None:
    root = tree(
        tmp_path,
        packages={
            'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}],
            'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf'}],
            'custom_installers': [{'name': 'theme', 'description': 'Theme installer'}],
        },
        manifests={'test-machine': {**LINUX, 'go_tools': ['task'], 'github_releases': ['fzf'], 'custom_installers': ['theme']}},
    )

    assert validate.declaration(root) == ()


# ─────────────────────────────────────────────────────────────────────────────
# What the loaders refuse reaches the report rather than becoming a traceback
# ─────────────────────────────────────────────────────────────────────────────


def test_an_entry_the_catalog_refuses_is_an_error(tmp_path: Path) -> None:
    """Every per-entry rule is the section's dataclass, tested directly in
    `test_catalog.py`. What is asserted here is that a refusal reaches this
    report — no unit test of the loader can answer that."""
    root = tree(tmp_path, packages={'github_releases': [{'name': 'fzf'}]})

    found = validate.declaration(root)

    assert [finding.severity for finding in found] == [Severity.ERROR]
    assert 'repo' in found[0].message


def test_a_catalog_that_will_not_load_stops_the_rest(tmp_path: Path) -> None:
    """Everything else is measured *against* the catalog, so findings derived from
    a file nobody could parse would describe a declaration that does not exist."""
    root = tree(
        tmp_path,
        packages={'github_releases': [{'name': 'fzf'}]},
        manifests={'test-machine': {**LINUX, 'go_tools': ['ghost']}},
    )

    found = validate.declaration(root)

    assert all(finding.section == 'github_releases' for finding in found)


def test_a_manifest_that_will_not_load_is_reported_and_named(tmp_path: Path) -> None:
    root = tree(tmp_path, manifests={'test-machine': {'machine': 'test-machine'}})

    found = validate.declaration(root)

    assert [finding.section for finding in found] == ['manifest']
    assert found[0].message.startswith('test-machine: ')


@pytest.mark.parametrize('retired', ['go', 'rust', 'nvm', 'uv', 'tenv'])
def test_a_retired_runtime_gate_is_caught_by_the_manifest_loader(tmp_path: Path, retired: str) -> None:
    """This was a second list of retired keys inside `verify`, kept in step with
    `machine.RETIRED_KEYS` by nothing. One list now, and the loader that owns it
    is what catches them."""
    root = tree(tmp_path, manifests={'test-machine': {**LINUX, retired: True}})

    found = validate.declaration(root)

    assert [finding.severity for finding in found] == [Severity.ERROR]
    assert 'name-list' in found[0].message


# ─────────────────────────────────────────────────────────────────────────────
# The three questions no single file can answer about itself
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('section', 'declared', 'named'),
    [
        ('go_tools', [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}], ['task', 'ghost-tool']),
        ('custom_installers', [{'name': 'theme', 'description': 'Theme installer'}], ['theme', 'ghost-tool']),
        ('npm_globals', {'linters': [{'name': 'prettier'}]}, ['prettier', 'ghost-tool']),
    ],
)
def test_a_manifest_naming_an_entry_that_does_not_exist_is_an_error(tmp_path: Path, section: str, declared: Any, named: list[str]) -> None:
    """The check the whole command exists for, and the one the resolver cannot
    make: subscription is a membership test, so a name matching nothing is
    silently dropped rather than refused."""
    root = tree(tmp_path, packages={section: declared}, manifests={'test-machine': {**LINUX, section: named}})

    found = validate.declaration(root)

    assert [(finding.section, finding.severity) for finding in found if 'ghost-tool' in finding.message] == [(section, Severity.ERROR)]


@pytest.mark.parametrize(
    ('section', 'entry', 'module'),
    [
        ('github_releases', {'name': 'nosuchtool', 'repo': 'someone/nosuchtool'}, 'providers/releases.py'),
        ('custom_installers', {'name': 'nosuchtool', 'description': 'invented'}, 'providers/custom.py'),
    ],
)
def test_an_entry_nothing_can_install_is_an_error(tmp_path: Path, section: str, entry: dict, module: str) -> None:
    """One direction only. The reverse — a function naming a tool nothing declares
    — cannot be asked against a synthetic tree, because the functions are code and
    are always the real ones."""
    root = tree(tmp_path, packages={section: [entry]}, manifests={'test-machine': {**LINUX, section: ['nosuchtool']}})

    found = validate.declaration(root)

    assert module in ' '.join(messages(found, Severity.ERROR))


@pytest.mark.parametrize('section', ['cargo_packages', 'go_tools'])
def test_a_pattern_with_no_repo_to_expand_it_against_is_a_warning(tmp_path: Path, section: str) -> None:
    """Both sections carrying the pair, because the check derives them from the
    dataclasses rather than naming one — a version that looked only at cargo would
    pass this for `go_tools` while the field sat unread there too.

    A warning, not an error: the tool installs by whatever its manager does
    without a prebuilt asset, so the declaration is degraded rather than broken.
    """
    entry: dict[str, Any] = {'name': 'ghost', 'binary_pattern': 'ghost-{version}.tar.gz'}
    if section == 'go_tools':
        entry['package'] = 'example.com/ghost'
    root = tree(tmp_path, packages={section: [entry]}, manifests={'test-machine': {**LINUX, section: ['ghost']}})

    found = validate.declaration(root)

    assert messages(found, Severity.WARNING) == ["'ghost' declares binary_pattern but no github_repo, so no asset URL can be built"]
    assert validate.errors(found) == ()


def test_a_pattern_beside_its_repo_reports_nothing(tmp_path: Path) -> None:
    """The pair is the legal shape, and the overwhelmingly common one — a check
    firing on it would bury every real finding under the whole cargo section."""
    root = tree(
        tmp_path,
        packages={'cargo_packages': [{'name': 'ghost', 'github_repo': 'someone/ghost', 'binary_pattern': 'ghost-{version}.tar.gz'}]},
        manifests={'test-machine': {**LINUX, 'cargo_packages': ['ghost']}},
    )

    assert validate.declaration(root) == ()


def test_an_entry_no_manifest_names_is_a_warning_not_an_error(tmp_path: Path) -> None:
    """An entry lands in `packages.yml` before the manifest that wants it, and a
    tool being staged is not a broken declaration."""
    root = tree(
        tmp_path,
        packages={'go_tools': [{'name': 'task', 'package': 'x/task'}, {'name': 'unused', 'package': 'x/unused'}]},
        manifests={'test-machine': {**LINUX, 'go_tools': ['task']}},
    )

    found = validate.declaration(root)

    assert validate.errors(found) == ()
    assert messages(found, Severity.WARNING) == ["'unused' is declared but no manifest names it"]


def test_a_section_some_manifest_takes_wholesale_reports_nothing_unreferenced(tmp_path: Path) -> None:
    """`true` subscribes to every entry, so reporting them all would bury the
    real findings under a section that is referenced by construction."""
    root = tree(
        tmp_path,
        packages={'go_tools': [{'name': 'task', 'package': 'x/task'}, {'name': 'other', 'package': 'x/other'}]},
        manifests={'test-machine': {**LINUX, 'go_tools': True}},
    )

    assert validate.declaration(root) == ()


# ─────────────────────────────────────────────────────────────────────────────
# Severity is what a caller branches on
# ─────────────────────────────────────────────────────────────────────────────


def test_errors_and_warnings_are_reported_together_and_told_apart(tmp_path: Path) -> None:
    """A warning must not hide an error and an error must not suppress a warning:
    one run should say everything that is wrong with the file."""
    root = tree(
        tmp_path,
        packages={'go_tools': [{'name': 'task', 'package': 'x/task'}, {'name': 'unused', 'package': 'x/unused'}]},
        manifests={'test-machine': {**LINUX, 'go_tools': ['task', 'ghost-tool']}},
    )

    found = validate.declaration(root)

    assert len(messages(found, Severity.ERROR)) == 1
    assert len(messages(found, Severity.WARNING)) == 1
    assert len(validate.errors(found)) == 1


def test_the_real_declaration_is_sound() -> None:
    """The gate the pre-commit hook is. Every synthetic test above proves a check
    fires; this proves the repo passes all of them at once."""
    assert validate.errors(validate.declaration()) == ()


# ─────────────────────────────────────────────────────────────────────────────
# Invariants the loader cannot express
#
# `catalog.load` refuses a key no reader consumes, which is a per-entry rule. Each
# of these is a relation — between two fields, or between a manifest and the
# declaration — and none is expressible as a dataclass field, which is why they
# are asserted rather than loaded. Against the real files, because a synthetic
# fixture proves a check works and only the shipped declaration proves the repo
# passes it.
#
# Every read goes through the loader the tool reads with, never `yaml.safe_load`:
# a manifest key is not always its section name and does not always take a list,
# so a test with its own parser is a second copy of a grammar `machine.py` owns.
# ─────────────────────────────────────────────────────────────────────────────


def test_a_manifest_installing_npm_globals_also_installs_fnm() -> None:
    """The node toolchain is planned because npm globals are, and it needs fnm to
    put a node on PATH at all — which is how a WSL offline install died with
    `fnm not found`.

    Asked of every manifest on disk rather than a list of names, so one added
    tomorrow is covered the day it is written, and asked through `subscription`
    because that is the function production narrows with: whether a machine wants
    an entry is a question about coverage, tier and spelling that only the loader
    answers the same way twice.
    """
    declaration = catalog.load(paths.PACKAGES_FILE)
    fnm = declaration.find('cargo_packages', 'fnm')
    assert fnm is not None, 'fnm is the node toolchain; nothing else puts a node on PATH'

    for name in machines.names():
        machine = machines.load(name)
        npm = machine.subscription('npm_globals')
        if not any(npm.wants(entry) for entry in declaration.section('npm_globals')):
            continue
        assert machine.subscription('cargo_packages').wants(fnm), (
            f'{name} installs npm globals but not fnm, so the node toolchain cannot resolve'
        )


def test_fnm_overrides_both_target_triples() -> None:
    """fnm names its assets after the OS word — `fnm-linux.zip`, `fnm-macos.zip` —
    so the bare `{target}` triple 404s on every bundle build.

    Both overrides or neither is the assertion: a linux-only override leaves the
    macOS bundle broken and vice versa, and one of the two going missing is the
    shape that survives a careless edit.
    """
    fnm = catalog.load(paths.PACKAGES_FILE).find('cargo_packages', 'fnm')

    assert fnm is not None, 'fnm is the node toolchain; nothing else puts a node on PATH'
    assert (fnm.linux_target, fnm.darwin_target) == ('linux', 'macos')


def test_no_declared_entry_carries_a_pattern_it_cannot_build_a_url_from() -> None:
    """The real-declaration half of `_unbuildable_assets`, which is a warning and
    so is not covered by `test_the_real_declaration_is_sound` above — that one
    folds to errors alone."""
    unbuildable = [finding for finding in validate.declaration() if 'binary_pattern' in finding.message]

    assert unbuildable == []


# ─────────────────────────────────────────────────────────────────────────────
# The git include scheme, whose two rules git itself cannot enforce
# ─────────────────────────────────────────────────────────────────────────────


def git_tree(root: Path, *, variants: dict[str, str], includes: list[str]) -> Path:
    """A configs/ tree carrying variant gitconfigs and the common file naming them.

    `variants` maps an `<axis>/<value>` directory to the gitconfig basename it
    ships, so a test can put the wrong name in the right place — which is the
    misnaming this check exists to catch and is not otherwise expressible.
    """
    tree(root)
    common = root / 'configs' / 'common' / '.config' / 'git'
    common.mkdir(parents=True, exist_ok=True)
    (common / 'common.gitconfig').write_text('\n'.join(f'[include]\npath = ~/.config/git/{name}' for name in includes))
    for coordinate, filename in variants.items():
        variant = root / 'configs' / coordinate / '.config' / 'git'
        variant.mkdir(parents=True, exist_ok=True)
        (variant / filename).write_text('[core]\nautocrlf = input')
    return root


def test_a_variant_gitconfig_named_for_its_value_and_included_is_silent(tmp_path: Path) -> None:
    root = git_tree(tmp_path, variants={'host/wsl': 'wsl.gitconfig'}, includes=['wsl.gitconfig'])

    assert validate.declaration(root) == ()


def test_a_variant_gitconfig_named_for_its_axis_is_an_error(tmp_path: Path) -> None:
    """The scheme this replaced. A variant named for its axis, deployed to
    `~/.config/git/`, says a side of the trust split was chosen and never which one.

    The expected path is assembled from the coordinate the fixture was handed
    rather than spelled out, so the two cannot disagree — and so the file holds no
    complete literal for a path that deliberately does not exist, which refcheck
    would otherwise read as a reference the rename left behind.
    """
    coordinate, misnamed = 'trust/nonfleet', 'trust.gitconfig'
    root = git_tree(tmp_path, variants={coordinate: misnamed}, includes=[misnamed])

    assert messages(validate.declaration(root), Severity.ERROR) == [
        f'configs/{coordinate}/.config/git/{misnamed} is named for neither its value nor anything else: '
        f"the trust value here is 'nonfleet', so it must be nonfleet.gitconfig"
    ]


def test_a_variant_gitconfig_no_include_names_is_an_error(tmp_path: Path) -> None:
    """The failure the enumeration in `common.gitconfig` introduced, and the whole
    reason this check exists. git ignores an include whose target is absent, so a
    file nothing includes deploys, is never read, and reports nothing."""
    root = git_tree(tmp_path, variants={'host/wsl': 'wsl.gitconfig'}, includes=[])

    assert messages(validate.declaration(root), Severity.ERROR) == [
        'configs/host/wsl/.config/git/wsl.gitconfig is deployed but no include names it, so git never reads it; '
        f'add `{validate.GIT_INCLUDE_PREFIX}wsl.gitconfig` to {validate.COMMON_GITCONFIG}'
    ]


def test_an_include_no_variant_ships_is_a_warning(tmp_path: Path) -> None:
    """Harmless to git and misleading to a reader, which is the warning/error line
    everywhere else in this module."""
    root = git_tree(tmp_path, variants={'host/wsl': 'wsl.gitconfig'}, includes=['wsl.gitconfig', 'native.gitconfig'])

    findings = validate.declaration(root)

    assert messages(findings, Severity.ERROR) == []
    assert messages(findings, Severity.WARNING) == [f"{validate.COMMON_GITCONFIG} includes 'native.gitconfig', which no variant ships"]


def test_a_tree_with_no_git_variants_says_nothing(tmp_path: Path) -> None:
    """Every other test in this module builds a tree with no `configs/` at all, so
    a missing common.gitconfig has to be silent rather than a finding about a
    scheme the tree is not using."""
    assert validate.declaration(tree(tmp_path)) == ()


def configs_tree(root: Path, *, configs: dict[str, str]) -> Path:
    """A configs/ tree whose files are written verbatim.

    `configs` maps a path under `configs/` to the file's whole text. Verbatim
    rather than assembled from a key and a value, because half of what the check
    has to get right is what is *not* a declaration — a commented-out example, an
    empty document — and a helper that only writes real keys cannot express one.
    """
    tree(root)
    for relative, text in configs.items():
        config = root / 'configs' / relative
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(text)
    return root


FLEET_REGISTRY = '~/.local/share/terminal-library-fleet/repos.json'
NONFLEET_REGISTRY = '~/.config/repos.json'


def test_one_registry_per_trust_variant_is_silent(tmp_path: Path) -> None:
    """The shape the fleet actually deploys: every tool in a trust variant naming
    the same file, and the two variants deliberately naming different ones."""
    root = configs_tree(
        tmp_path,
        configs={
            'trust/fleet/.config/indy/config.toml': f'repos_registry = "{FLEET_REGISTRY}"\n',
            'trust/fleet/.config/fleet/config.yml': f'repos_registry: {FLEET_REGISTRY}\n',
            'trust/nonfleet/.config/syncer/config.toml': f'repos_registry = "{NONFLEET_REGISTRY}"\n',
        },
    )

    assert validate.declaration(root) == ()


def test_two_registries_in_one_trust_variant_is_an_error(tmp_path: Path) -> None:
    """The drift a repeated literal invites, and the only thing standing against it.

    Both files deploy to the same machine, so a tool reading the odd one out
    answers about a different set of repos and says nothing about having done so.
    """
    root = configs_tree(
        tmp_path,
        configs={
            'trust/fleet/.config/indy/config.toml': f'repos_registry = "{FLEET_REGISTRY}"\n',
            'trust/fleet/.config/forge/config.yml': 'repos_registry: ~/dev/repos.json\n',
        },
    )

    assert messages(validate.declaration(root), Severity.ERROR) == [
        'the fleet variant names more than one registry — '
        'configs/trust/fleet/.config/forge/config.yml says ~/dev/repos.json; '
        f'configs/trust/fleet/.config/indy/config.toml says {FLEET_REGISTRY}'
    ]


@pytest.mark.parametrize('directory', ['common', 'host/wsl'])
def test_a_registry_named_outside_the_trust_variants_is_an_error(tmp_path: Path, directory: str) -> None:
    """Every directory but `trust/` reaches both trust domains, so one path in one
    cannot be right for both — which is exactly how the fleet's registry came to be
    named in a config the work box also deploys."""
    relative = f'{directory}/.config/syncer/config.toml'
    root = configs_tree(tmp_path, configs={relative: f'repos_registry = "{FLEET_REGISTRY}"\n'})

    assert messages(validate.declaration(root), Severity.ERROR) == [
        f'configs/{relative} names repos_registry outside configs/trust/, so it deploys the same registry '
        f'to both trust domains; move the file into the trust variant that wants it'
    ]


def test_a_commented_out_registry_is_not_a_declaration(tmp_path: Path) -> None:
    """Parsed rather than matched. Every one of these files carries a comment block
    explaining the key, and a check that grepped would read its own documentation as
    a second declaration."""
    root = configs_tree(
        tmp_path,
        configs={
            'common/.config/syncer/config.toml': f'# repos_registry = "{FLEET_REGISTRY}"\ndefault_policy = "standard"\n',
            'common/.config/gh-dash/config.yml': '# repos_registry: somewhere\n',
        },
    )

    assert validate.declaration(root) == ()


def test_a_yaml_config_that_is_not_a_mapping_is_not_a_declaration(tmp_path: Path) -> None:
    """An empty document parses to None and a list parses to a list. Neither
    declares a key, and `.get` on either raises rather than reporting."""
    root = configs_tree(tmp_path, configs={'common/.config/aerc/accounts.yml': '', 'common/.config/zk/tags.yaml': '- one\n- two\n'})

    assert validate.declaration(root) == ()


def test_a_config_that_will_not_parse_is_an_error(tmp_path: Path) -> None:
    """Reported rather than raised, so one unparseable file is a finding beside the
    others instead of a traceback that loses every check after it."""
    root = configs_tree(tmp_path, configs={'trust/fleet/.config/indy/config.toml': 'repos_registry = "unterminated\n'})

    assert [message.split(' — ')[0] for message in messages(validate.declaration(root), Severity.ERROR)] == [
        'configs/trust/fleet/.config/indy/config.toml cannot be read'
    ]


DOTFILES_CONFIG = '.config/dotfiles/config.toml'
REMOTE = """
[remote]
root = "/dotfiles"

[remote.transport]
program = "ifiles"
probe = ["auth", "status"]
list = ["list", "{dir}"]
upload = ["upload", "{local}", "{dir}"]
download = ["download", "{remote}", "{local}"]
"""


def test_the_same_remote_table_in_both_trust_variants_is_silent(tmp_path: Path) -> None:
    """The shape the fleet deploys. A bundle is built on one side of the trust axis
    and collected on the other, so the two copies have to name one server."""
    root = configs_tree(tmp_path, configs={f'trust/fleet/{DOTFILES_CONFIG}': REMOTE, f'trust/nonfleet/{DOTFILES_CONFIG}': REMOTE})

    assert validate.declaration(root) == ()


def test_no_variant_declaring_a_remote_is_silent(tmp_path: Path) -> None:
    """Having no remote is the ordinary state of a machine that never exchanges a
    bundle, so the check is about agreement and never about presence."""
    named = 'repos_registry = "~/.config/repos.json"\n'
    root = configs_tree(tmp_path, configs={f'trust/fleet/{DOTFILES_CONFIG}': named, f'trust/nonfleet/{DOTFILES_CONFIG}': named})

    assert validate.declaration(root) == ()


def test_a_remote_declared_in_one_variant_and_not_the_other_is_an_error(tmp_path: Path) -> None:
    """The likelier half of the drift, and the half a value comparison cannot see.
    One file edited and the other forgotten leaves the declared copies trivially in
    agreement while the forgotten machine has no remote at all."""
    root = configs_tree(
        tmp_path,
        configs={
            f'trust/fleet/{DOTFILES_CONFIG}': REMOTE,
            f'trust/nonfleet/{DOTFILES_CONFIG}': 'repos_registry = "~/.config/repos.json"\n',
        },
    )

    assert messages(validate.declaration(root), Severity.ERROR) == [
        'configs/trust/fleet/.config/dotfiles/config.toml declares a remote table and '
        'configs/trust/nonfleet/.config/dotfiles/config.toml does not, so the machines reading each address different servers'
    ]


def test_two_variants_declaring_different_remote_tables_is_an_error(tmp_path: Path) -> None:
    """An upload onto a shelf the other end never lists succeeds, which reads as a
    handoff that was never built."""
    root = configs_tree(
        tmp_path,
        configs={f'trust/fleet/{DOTFILES_CONFIG}': REMOTE, f'trust/nonfleet/{DOTFILES_CONFIG}': REMOTE.replace('/dotfiles', '/backups')},
    )

    assert messages(validate.declaration(root), Severity.ERROR) == [
        'configs/trust/fleet/.config/dotfiles/config.toml, configs/trust/nonfleet/.config/dotfiles/config.toml '
        'declare different remote tables'
    ]


def test_the_same_table_written_out_differently_is_not_a_difference(tmp_path: Path) -> None:
    """Compared as parsed values, so key order and alignment are not findings — a
    check that diffed the text would report every reformatting as a drifted server."""
    retyped = """
[remote]
root   = "/dotfiles"

[remote.transport]
download = ["download", "{remote}", "{local}"]
upload   = ["upload", "{local}", "{dir}"]
list     = ["list", "{dir}"]
probe    = ["auth", "status"]
program  = "ifiles"
"""
    root = configs_tree(tmp_path, configs={f'trust/fleet/{DOTFILES_CONFIG}': REMOTE, f'trust/nonfleet/{DOTFILES_CONFIG}': retyped})

    assert validate.declaration(root) == ()
