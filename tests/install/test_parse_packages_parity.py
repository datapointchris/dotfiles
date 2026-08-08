"""The parity corpus: every question the installers ask packages.yml today.

Step 4 replaces parse_packages.py with a resolver, and the only honest proof
that the replacement is faithful is that it answers this whole corpus
identically. That comparison needs both operands, and only one exists yet — so
what this file holds now is the enumeration, the current answers, and the guards
that stop the comparison being vacuous once it lands. Step 4 adds one test
asserting resolve() reproduces `current_answers`, and this file dies with
parse_packages.py at the end of it.

The corpus is derived from the CLI's own choice lists rather than restated here,
so a new --type or --format widens it without anyone remembering to.

Everything runs against one load of packages.yml. That matters: the load costs
~100ms, which is also why the installers spend seconds re-reading the same file
across their 28 separate invocations of this script.
"""

import argparse
import itertools
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

from dotfiles import parse_packages

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_NAMES = sorted(path.stem for path in (REPO_ROOT / 'install' / 'manifests').glob('*.yml'))

# A section whose entries carry no owner cannot answer an owner-filtered query,
# and `custom` is the only one taking --filter. Both are properties of the data,
# so both are read off it below rather than asserted here.
BUNDLE_FILTER = 'bundle_install_script'


class Query(NamedTuple):
    """One question, in both the shapes it gets asked in.

    `as_args` feeds the pure seam and `as_argv` the command line; the CLI test
    below is what keeps the two from drifting apart.
    """

    package_type: str
    manifest: str | None = None
    owner: str | None = None
    manager: str | None = None
    tier: str = 'workstation'
    output_format: str = 'names'
    filter_field: str | None = None

    def as_args(self) -> argparse.Namespace:
        return argparse.Namespace(
            type=self.package_type,
            manager=self.manager,
            tier=self.tier,
            format=self.output_format,
            owner=self.owner,
            filter=self.filter_field,
        )

    def as_argv(self) -> list[str]:
        argv = [f'--type={self.package_type}', f'--tier={self.tier}', f'--format={self.output_format}']
        for flag, value in (
            ('--manager', self.manager),
            ('--manifest', self.manifest),
            ('--owner', self.owner),
            ('--filter', self.filter_field),
        ):
            if value:
                argv.append(f'{flag}={value}')
        return argv


@pytest.fixture(scope='session')
def catalog() -> dict:
    return parse_packages.load_packages()


@pytest.fixture(scope='session')
def manifests() -> dict[str, dict]:
    return {name: parse_packages.load_manifest(name) for name in MANIFEST_NAMES}


@pytest.fixture(scope='session')
def owners(catalog) -> list[str | None]:
    """Every owner packages.yml attributes an entry to, plus the unfiltered view.

    The traversal mirrors filter_packages_by_owner: most sections are lists of
    entries, uv_tools and npm_globals nest one level deeper under categories, and
    macos_taps holds bare strings that own nothing.
    """

    def entries_of(section):
        if isinstance(section, list):
            return section
        if isinstance(section, dict):
            return [entry for group in section.values() if isinstance(group, list) for entry in group]
        return []

    found = {
        parse_packages.extract_owner(entry) for section in catalog.values() for entry in entries_of(section) if isinstance(entry, dict)
    }
    return [None, *sorted(found - {None})]


@pytest.fixture(scope='session')
def corpus(owners) -> list[Query]:
    cases = []
    for manifest, owner in itertools.product([None, *MANIFEST_NAMES], owners):
        for package_type in parse_packages.PACKAGE_TYPES:
            if package_type == 'system':
                for manager, tier in itertools.product(parse_packages.PACKAGE_MANAGERS, parse_packages.SYSTEM_TIERS):
                    cases.append(Query('system', manifest, owner, manager=manager, tier=tier))
            else:
                for output_format in parse_packages.OUTPUT_FORMATS:
                    cases.append(Query(package_type, manifest, owner, output_format=output_format))
        cases.append(Query('custom', manifest, owner, filter_field=BUNDLE_FILTER))
    return cases


@pytest.fixture(scope='session')
def current_answers(corpus, catalog, manifests) -> dict[Query, list[str]]:
    """What parse_packages.py answers today. The baseline resolve() must match."""
    answers = {}
    for query in corpus:
        manifest = manifests[query.manifest] if query.manifest else None
        answers[query] = [str(line) for line in parse_packages.select_packages(catalog, manifest, query.as_args())]
    return answers


class TestCorpusIsNotVacuous:
    def test_it_covers_every_choice_the_cli_offers(self, corpus):
        assert {query.package_type for query in corpus} == set(parse_packages.PACKAGE_TYPES)
        assert {query.output_format for query in corpus} >= set(parse_packages.OUTPUT_FORMATS)
        assert {query.manager for query in corpus if query.manager} == set(parse_packages.PACKAGE_MANAGERS)
        assert {query.tier for query in corpus if query.manager} == set(parse_packages.SYSTEM_TIERS)

    def test_it_covers_every_manifest_and_the_unfiltered_view(self, corpus):
        assert {query.manifest for query in corpus} == {None, *MANIFEST_NAMES}

    def test_every_section_answers_something_for_at_least_one_machine(self, corpus, current_answers):
        answered = {query.package_type for query in corpus if current_answers[query]}
        assert answered == set(parse_packages.PACKAGE_TYPES)

    def test_narrowing_to_a_manifest_never_widens_the_answer(self, corpus, current_answers):
        """A manifest subscribes to a subset of packages.yml, so filtering can
        only remove. A resolver that silently ignored --manifest would still
        pass every count-based check; this is what catches it."""
        unfiltered = {
            (q.package_type, q.owner, q.output_format, q.manager, q.tier, q.filter_field): current_answers[q]
            for q in corpus
            if not q.manifest
        }
        for query in corpus:
            if not query.manifest:
                continue
            key = (query.package_type, query.owner, query.output_format, query.manager, query.tier, query.filter_field)
            assert set(current_answers[query]) <= set(unfiltered[key]), f'{query} answers something no unfiltered query does'


def test_the_command_line_prints_exactly_what_the_pure_seam_returns(current_answers):
    """A sample chosen so every flag as_argv can emit is exercised at least
    once — not a cap on coverage, but the point where a subprocess per case
    stops being worth its ~150ms.

    Run under this interpreter rather than the /usr/bin/python3 the installers
    use: the contract under test is argv to stdout, not which python has PyYAML.
    The installers reach the same module through `-m` with PYTHONPATH pointed at
    src, because there is no distribution installed during a bootstrap.
    """
    sample = [
        Query('cargo'),
        Query('go', MANIFEST_NAMES[0], output_format='name_package'),
        Query('system', manager='apt', tier='core'),
        Query('github', MANIFEST_NAMES[0], owner='datapointchris'),
        Query('custom', filter_field=BUNDLE_FILTER),
    ]
    emitted = {flag.split('=')[0] for query in sample for flag in query.as_argv()}
    assert emitted == {'--type', '--tier', '--format', '--manager', '--manifest', '--owner', '--filter'}

    for query in sample:
        result = subprocess.run(
            [sys.executable, '-m', 'dotfiles.parse_packages', *query.as_argv()],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.splitlines() == current_answers[query], f'{query.as_argv()} printed something the seam did not return'


def test_a_system_query_without_a_manager_is_refused_rather_than_answered(catalog):
    with pytest.raises(parse_packages.QueryError):
        parse_packages.select_packages(catalog, None, Query('system').as_args())
