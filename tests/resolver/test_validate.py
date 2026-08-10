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
# declaration — and none is expressible as a dataclass field. They outlived
# `parse_packages`, whose tests were their previous home, and are asserted against
# the real files here for the reason that file did: a synthetic fixture proves the
# check works, and only the real declaration proves the repo passes it.
# ─────────────────────────────────────────────────────────────────────────────


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_a_manifest_installing_npm_globals_also_installs_fnm() -> None:
    """The node toolchain is planned because npm globals are, and it needs fnm to
    put a node on PATH at all — which is how a WSL offline install died with
    `fnm not found`.

    Read off disk rather than from a list of machine names, so a manifest added
    tomorrow is covered the day it is written.
    """
    for manifest in sorted((REPO_ROOT / 'install' / 'manifests').glob('*.yml')):
        declared = yaml.safe_load(manifest.read_text())
        if not declared.get('npm_globals'):
            continue
        cargo = declared.get('cargo_packages')
        assert cargo is True or 'fnm' in (cargo or ()), (
            f'{manifest.name} installs npm globals but no fnm, so the node toolchain cannot resolve'
        )


def test_fnm_overrides_both_target_triples() -> None:
    """fnm names its assets after the OS word — `fnm-linux.zip`, `fnm-macos.zip` —
    so the bare `{target}` triple 404s on every bundle build.

    Both overrides or neither is the assertion: a linux-only override leaves the
    macOS bundle broken and vice versa, and one of the two going missing is the
    shape that survives a careless edit.
    """
    fnm = catalog.load(REPO_ROOT / 'install' / 'packages.yml').find('cargo_packages', 'fnm')

    assert fnm is not None, 'fnm is the node toolchain; nothing else puts node on PATH'
    assert (fnm.linux_target, fnm.darwin_target) == ('linux', 'macos')


def test_a_cargo_binary_pattern_names_the_repo_it_builds_a_url_for() -> None:
    """`binary_pattern` exists only to construct a GitHub release URL, so an entry
    carrying one without a `github_repo` is dead configuration that reads as
    working — the same failure `install_script` was refused for, one relation up
    where the loader cannot see it."""
    declaration = catalog.load(REPO_ROOT / 'install' / 'packages.yml')

    orphaned = [entry.name for entry in declaration.section('cargo_packages') if entry.binary_pattern and not entry.github_repo]

    assert orphaned == []
