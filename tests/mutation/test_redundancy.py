"""A prover nobody has seen fail is not evidence, so this drives one against a suite whose answer is known by construction.

The toy holds a test of each kind the prover has to tell apart: one that alone executes a line, one that alone catches a bug, two
that catch exactly the same bugs as each other, one whose only assertion no operator can violate. Deleting the ones it calls
redundant leaves the toy's mutation score unchanged, and that is the property being measured — the report is only how it is read.

The seams around the proof get their own tables. Attribution is where a proof silently empties, so the shapes that used to be
ambiguous — a parametrized id carrying ` - `, one node id that is another's prefix, a class, a file that will not import — are
driven against a real pytest rather than a fixture imitating one. And a kill nothing can be attributed to is driven through a stub
pytest that exits 1 in silence, because that is the failure the whole proof rests on not happening quietly.
"""

from __future__ import annotations

import ast
import dataclasses
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from mutation import classify
from mutation import failures
from mutation import planter
from mutation import redundancy
from mutation import run as harness
from mutation import score
from mutation import subset
from mutation.toys import site
from mutation.toys import toy_run
from mutation.toys import toy_tree as build_toy

# ─────────────────────────────────────────────────────────────────────────────
# The cheap condition
# ─────────────────────────────────────────────────────────────────────────────


def contexts_from(rows: dict[str, dict[int, tuple[int, ...]]], tests: tuple[str, ...]) -> subset.Contexts:
    return subset.Contexts(tests=tests, lines=rows)


def test_a_test_alone_on_a_line_is_necessary_and_the_line_is_named() -> None:
    found = redundancy.survey(contexts_from({'src/a.py': {1: (0, 1), 2: (0,)}}, ('t::one', 't::two')))
    assert found.necessary == {'t::one': ('src/a.py', 2)}
    assert found.candidates == ('t::two',)


def test_a_line_nobody_ran_makes_nobody_necessary() -> None:
    """An import-time line carries an empty context set, which belongs to no test and cannot prove one indispensable."""
    found = redundancy.survey(contexts_from({'src/a.py': {1: (), 2: (0, 1)}}, ('t::one', 't::two')))
    assert found.necessary == {}
    assert found.candidates == ('t::one', 't::two')


def test_a_footprint_is_the_files_a_test_executes() -> None:
    found = redundancy.footprints(contexts_from({'src/a.py': {1: (0,)}, 'src/b.py': {4: (0, 1)}}, ('t::one', 't::two')))
    assert found['t::one'].files == frozenset({'src/a.py', 'src/b.py'})
    assert found['t::two'].files == frozenset({'src/b.py'})


def test_the_scope_is_the_union_of_what_the_chosen_tests_execute() -> None:
    found = redundancy.footprints(contexts_from({'src/a.py': {1: (0,)}, 'src/b.py': {4: (1,)}}, ('t::one', 't::two')))
    assert redundancy.scope_of(found, ['t::one']) == ('src/a.py',)
    assert redundancy.scope_of(found, ['t::one', 't::two']) == ('src/a.py', 'src/b.py')


def test_a_candidate_reaching_outside_the_scope_is_not_within_it() -> None:
    found = redundancy.footprints(contexts_from({'src/a.py': {1: (0, 1)}, 'src/b.py': {4: (1,)}}, ('t::one', 't::two')))
    assert redundancy.within(found, ['t::one', 't::two'], ['src/a.py']) == ('t::one',)


# ─────────────────────────────────────────────────────────────────────────────
# Attribution
# ─────────────────────────────────────────────────────────────────────────────

RECORDED = [
    (
        'a file that could not be collected takes every test the subset holds in it',
        ('tests/x.py',),
        ('tests/x.py::test_a', 'tests/x.py::test_b', 'tests/y.py::test_c'),
        ('tests/x.py::test_a', 'tests/x.py::test_b'),
    ),
    ('a run that recorded nothing names nobody', (), ('tests/x.py::test_a',), ()),
    ('a test outside the subset is ignored', ('tests/y.py::test_z',), ('tests/x.py::test_a',), ()),
]


@pytest.mark.parametrize(('name', 'reported', 'subsetted', 'expected'), RECORDED, ids=[row[0] for row in RECORDED])
def test_attribution_intersects_what_was_recorded_with_what_was_handed(
    name: str, reported: tuple[str, ...], subsetted: tuple[str, ...], expected: tuple[str, ...]
) -> None:
    """Only the collection rule is a rule. The rest is a set intersection, which is the point of recording node ids rather than
    reading them back out of a sentence."""
    assert harness.killers_in(reported, subsetted) == expected


@pytest.mark.replants
def test_pytest_records_the_ids_it_was_handed_however_they_are_shaped(tmp_path: Path) -> None:
    """The shapes that made a prefix scrape ambiguous, asserted against real pytest rather than a fixture imitating it.

    A parametrized id may contain ` - `, which used to be the separator between an id and its message. `test_a` is a prefix of
    `test_ab`. A class adds a third `::` component. A file that will not import is named on its own.
    """
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests' / 'test_shapes.py').write_text(SHAPES)
    (tmp_path / 'tests' / 'test_broken.py').write_text('import nothing_at_all  # noqa: F401\n\n\ndef test_never_runs():\n    pass\n')
    handed = [
        'tests/test_shapes.py::test_a',
        'tests/test_shapes.py::test_ab',
        'tests/test_shapes.py::test_parametrized[a - b]',
        'tests/test_shapes.py::TestGrouped::test_inside',
    ]
    setup = dataclasses.replace(toy_tree(tmp_path / 'tree'), repo=tmp_path, pytest_prefix=(sys.executable, '-m', 'pytest'))

    _, _, _, reported = harness.run_pytest(
        setup, tmp_path, handed, stop_early=False, timeout=120.0, basetemp=tmp_path / 'bt', attributed=True
    )

    assert harness.killers_in(reported, handed) == (
        'tests/test_shapes.py::TestGrouped::test_inside',
        'tests/test_shapes.py::test_ab',
        'tests/test_shapes.py::test_parametrized[a - b]',
    )

    _, _, _, broke = harness.run_pytest(
        setup,
        tmp_path,
        ['tests/test_broken.py::test_never_runs'],
        stop_early=False,
        timeout=120.0,
        basetemp=tmp_path / 'bt',
        attributed=True,
    )
    assert harness.killers_in(broke, ['tests/test_broken.py::test_never_runs']) == ('tests/test_broken.py::test_never_runs',)


SHAPES = """\
import pytest


def test_a():
    assert True


def test_ab():
    assert False


@pytest.mark.parametrize('value', ['a - b'])
def test_parametrized(value):
    assert False


class TestGrouped:
    def test_inside(self):
        assert False
"""


VANISHED = 'ERROR: not found: /repo/tests/x.py::test_a[apt]\n(no match in any of [<Module x.py>])\n'


def test_a_node_id_the_mutant_renamed_is_recognized_by_the_suffix_it_still_shares() -> None:
    """pytest prints the absolute path, and a prefix match would take `test_ab` for `test_a`."""
    subsetted = ('tests/x.py::test_a[apt]', 'tests/x.py::test_ab[apt]', 'tests/x.py::test_b')
    assert harness.vanished_in(VANISHED, subsetted) == ('tests/x.py::test_a[apt]',)


def test_nothing_vanishes_from_an_ordinary_failure_summary() -> None:
    assert harness.vanished_in('FAILED tests/x.py::test_a - assert False', ('tests/x.py::test_a',)) == ()


def test_a_test_whose_id_a_mutant_destroyed_is_unprovable_and_the_rest_are_not() -> None:
    """Blocking the whole module for this cost 715 of 718 proofs, for six mutants that renamed a parametrized case."""
    run = toy_run([site(score.KILLED, killers=('t::one', 't::two'), unmeasured=('t::gone',))])
    footprint = one_file(['t::one', 't::two', 't::gone'])
    verdicts = redundancy.prove(run, ['t::two', 't::gone'], footprint, ['src/dotfiles/x.py'], run_set=['t::one', 't::two'])
    assert [proof.test for proof in verdicts.redundant] == ['t::two']
    assert verdicts.unprovable == (('t::gone', redundancy.UNADDRESSABLE),)


def test_a_survivor_carrying_unmeasured_tests_blocks_them_too() -> None:
    """A mutant nothing killed blocks nobody, so a test it never ran against would be judged on a measurement missing it."""
    run = toy_run([site(score.KILLED, killers=('t::one', 't::two')), site(score.SURVIVED, line=2, unmeasured=('t::two',))])
    verdicts = redundancy.prove(run, ['t::two'], one_file(['t::one', 't::two']), ['src/dotfiles/x.py'], run_set=['t::one', 't::two'])
    assert verdicts.unprovable == (('t::two', redundancy.UNADDRESSABLE),)


def test_a_timed_out_mutant_blocks_its_file_rather_than_counting_as_killed_by_nobody() -> None:
    """Both readings of an unattributable kill make a test look more redundant than it is, so the file is refused instead."""
    run = toy_run([site(score.KILLED, killers=('t::one',)), site(score.TIMED_OUT, line=9)])
    found, blocked = redundancy.mutants(run)
    assert [item.address for item in found] == ['src/dotfiles/x.py:1:0']
    assert blocked == ('src/dotfiles/x.py',)


def test_a_harness_error_blocks_its_file_too() -> None:
    run = toy_run([site(score.KILLED, killers=('t::one',)), site(score.HARNESS_ERROR, line=9)])
    assert redundancy.mutants(run)[1] == ('src/dotfiles/x.py',)


def test_two_mutants_at_one_address_are_refused_rather_than_merged() -> None:
    """Merging them would union their killers, which weakens every proof resting on either."""
    run = toy_run([site(score.KILLED, killers=('t::one',)), site(score.KILLED, killers=('t::two',))])
    assert redundancy.mutants(run)[1] == ('src/dotfiles/x.py',)


# ─────────────────────────────────────────────────────────────────────────────
# The proof
# ─────────────────────────────────────────────────────────────────────────────


def one_file(tests: list[str], file: str = 'src/dotfiles/x.py') -> dict[str, redundancy.Footprint]:
    return {name: redundancy.Footprint(files=frozenset({file}), unique=()) for name in tests}


def test_a_test_holding_one_kill_alone_is_load_bearing_and_the_mutant_is_named() -> None:
    run = toy_run([site(score.KILLED, line=1, killers=('t::one', 't::two')), site(score.KILLED, line=2, killers=('t::one',))])
    verdicts = redundancy.prove(run, ['t::one'], one_file(['t::one', 't::two']), ['src/dotfiles/x.py'])
    assert verdicts.redundant == ()
    assert [proof.test for proof in verdicts.load_bearing] == ['t::one']
    assert verdicts.load_bearing[0].sole_owner == ('src/dotfiles/x.py:2:0', 'a -> b')


def test_a_test_whose_every_kill_is_shared_is_redundant_and_the_sharer_is_named() -> None:
    run = toy_run([site(score.KILLED, line=1, killers=('t::one', 't::two')), site(score.KILLED, line=2, killers=('t::one', 't::two'))])
    verdicts = redundancy.prove(run, ['t::two'], one_file(['t::one', 't::two']), ['src/dotfiles/x.py'])
    assert [(proof.test, proof.subsumed_by, proof.killed) for proof in verdicts.redundant] == [('t::two', ('t::one',), 2)]


def test_no_single_test_covering_the_whole_kill_set_is_still_a_proof_by_a_group() -> None:
    run = toy_run([site(score.KILLED, line=1, killers=('t::one', 't::two')), site(score.KILLED, line=2, killers=('t::one', 't::three'))])
    verdicts = redundancy.prove(run, ['t::one'], one_file(['t::one', 't::two', 't::three']), ['src/dotfiles/x.py'])
    assert verdicts.redundant[0].subsumed_by == ('t::three', 't::two')


def test_a_test_that_kills_nothing_is_unprovable_rather_than_deletable() -> None:
    """The operators cannot express an exception type, an ordering, an argv or a file not written, so silence is not a verdict."""
    run = toy_run([site(score.KILLED, line=1, killers=('t::one',))])
    verdicts = redundancy.prove(run, ['t::two'], one_file(['t::one', 't::two']), ['src/dotfiles/x.py'])
    assert verdicts.redundant == ()
    assert verdicts.unprovable == (('t::two', redundancy.NO_KILLS),)


def test_a_test_reaching_a_module_the_run_never_mutated_is_unprovable() -> None:
    footprint = {'t::one': redundancy.Footprint(files=frozenset({'src/dotfiles/x.py', 'src/dotfiles/y.py'}), unique=())}
    verdicts = redundancy.prove(toy_run([site(score.KILLED, killers=('t::one',))]), ['t::one'], footprint, ['src/dotfiles/x.py'])
    assert verdicts.redundant == ()
    assert redundancy.OUTSIDE_SCOPE in verdicts.unprovable[0][1]


def test_a_test_dropped_by_the_screen_is_unprovable_rather_than_deletable() -> None:
    """It failed against every mutant and against none, so nothing it did is evidence about anything."""
    run = toy_run([site(score.KILLED, killers=('t::one', 't::two'))])
    verdicts = redundancy.prove(run, ['t::two'], one_file(['t::one', 't::two']), ['src/dotfiles/x.py'], dropped=['t::two'])
    assert verdicts.unprovable == (('t::two', redundancy.UNSHADOWABLE),)
    assert verdicts.dropped == ('t::two',)


def test_a_blocked_file_makes_every_test_that_executes_it_unprovable() -> None:
    run = toy_run([site(score.KILLED, line=1, killers=('t::one', 't::two')), site(score.TIMED_OUT, line=9)])
    verdicts = redundancy.prove(run, ['t::two'], one_file(['t::one', 't::two']), ['src/dotfiles/x.py'])
    assert verdicts.redundant == ()
    assert redundancy.BLOCKED in verdicts.unprovable[0][1]


def test_two_tests_that_only_cover_each_other_yield_one_deletion_rather_than_two() -> None:
    """Both are redundant against the suite as it stands, and deleting both would take the mutant's last killer with them."""
    run = toy_run([site(score.KILLED, line=1, killers=('t::one', 't::two'))])
    verdicts = redundancy.prove(
        run, ['t::one', 't::two'], one_file(['t::one', 't::two']), ['src/dotfiles/x.py'], run_set=['t::one', 't::two']
    )
    assert len(verdicts.redundant) == 2
    assert [proof.test for proof in verdicts.redundant if proof.together] == ['t::two']


def test_a_test_covered_by_something_nobody_is_deleting_goes_in_the_joint_answer() -> None:
    run = toy_run([site(score.KILLED, line=1, killers=('t::one', 't::keeper'))])
    footprint = one_file(['t::one', 't::keeper'])
    verdicts = redundancy.prove(run, ['t::one'], footprint, ['src/dotfiles/x.py'], run_set=['t::one', 't::keeper'])
    assert [proof.test for proof in verdicts.redundant if proof.together] == ['t::one']


def test_the_redundancy_payload_carries_the_counts_rather_than_a_verdict_sentence() -> None:
    run = toy_run([site(score.KILLED, line=1, killers=('t::one', 't::two'))])
    found = redundancy.survey(contexts_from({'src/dotfiles/x.py': {1: (0, 1)}}, ('t::one', 't::two')))
    verdicts = redundancy.prove(run, ['t::two'], one_file(['t::one', 't::two']), ['src/dotfiles/x.py'], run_set=['t::one', 't::two'])
    payload = redundancy.as_payload(found, verdicts)

    assert len(payload['redundant']) == 1
    assert payload['deletable'] == ['t::two']


# ─────────────────────────────────────────────────────────────────────────────
# The whole thing, against a toy whose answer is known by construction
# ─────────────────────────────────────────────────────────────────────────────

TOY_SOURCE = '''\
"""A toy."""

LIMIT = 3


def over(count):
    return count > LIMIT


def label(count):
    return 'over' if over(count) else 'under'


def counted(items):
    return len(items) + 1


def even(number):
    return number % 2 == 0
'''

TOY_TESTS = """\
from toy import thing


def test_over_high():
    assert thing.over(4) is True


def test_over_high_again():
    assert thing.over(4) is True


def test_over_low():
    assert thing.over(3) is False


def test_label_says_over():
    assert thing.label(4) == 'over'


def test_label_returns_a_string():
    assert isinstance(thing.label(4), str)


def test_counted_is_the_length_plus_one():
    assert thing.counted([1, 2]) == 3


def test_two_is_even():
    assert thing.even(2) is True


def test_four_is_even():
    assert thing.even(4) is True
"""
"""The toy, and every kind of test the prover has to tell apart.

`test_two_is_even` and `test_four_is_even` are the mutual pair. Every mutant in `even` — the comparison, the modulus and the
zero — is killed by exactly those two and by nothing else, so each is redundant against the other and deleting both costs three
kills. They are what makes the joint answer visible from the outside rather than only in a hand-built killer table.
"""


def toy_tree(tmp_path: Path) -> harness.Setup:
    """This file's toy, recording killers, because that is what a redundancy proof reads."""
    return build_toy(tmp_path, TOY_SOURCE, TOY_TESTS, record_killers=True)


@pytest.fixture(scope='module')
def proved(tmp_path_factory: pytest.TempPathFactory) -> tuple[redundancy.Survey, redundancy.Verdicts]:
    """One real end-to-end, shared because it costs a coverage pass and a pytest run per planted site."""
    setup = toy_tree(tmp_path_factory.mktemp('redundancy'))
    contexts, _, measured = subset.load(setup.repo, setup.source_root, setup.cache_dir, pytest_prefix=setup.pytest_prefix)
    assert measured
    return redundancy.measure(setup, contexts, ['tests/test_thing.py'], announce=lambda _: None)


def test_the_only_test_calling_a_function_is_proven_necessary(proved: tuple[redundancy.Survey, redundancy.Verdicts]) -> None:
    """`counted` has one caller, so its body is a line that test holds alone — and nothing else needs measuring."""
    assert 'tests/test_thing.py::test_counted_is_the_length_plus_one' in proved[0].necessary
    assert proved[0].necessary['tests/test_thing.py::test_counted_is_the_length_plus_one'][0] == 'src/toy/thing.py'


def test_a_verbatim_duplicate_is_proven_redundant_by_the_test_it_duplicates(
    proved: tuple[redundancy.Survey, redundancy.Verdicts],
) -> None:
    proofs = {proof.test: proof for proof in proved[1].redundant}
    duplicate = proofs['tests/test_thing.py::test_over_high_again']
    assert duplicate.killed > 0
    assert 'tests/test_thing.py::test_over_high' in duplicate.subsumed_by


def test_the_test_holding_the_only_assertion_on_a_string_is_load_bearing(
    proved: tuple[redundancy.Survey, redundancy.Verdicts],
) -> None:
    """Nothing else reads `label`'s return value, so the mutant on `'over'` has exactly one killer."""
    holding = {proof.test: proof for proof in proved[1].load_bearing}
    assert 'tests/test_thing.py::test_label_says_over' in holding
    assert holding['tests/test_thing.py::test_label_says_over'].sole_owner is not None


def test_a_test_no_operator_can_break_is_unprovable_rather_than_redundant(
    proved: tuple[redundancy.Survey, redundancy.Verdicts],
) -> None:
    """`isinstance(..., str)` survives every string mutation, which is silence rather than evidence of worthlessness."""
    reasons = dict(proved[1].unprovable)
    assert reasons['tests/test_thing.py::test_label_returns_a_string'] == redundancy.NO_KILLS


def test_no_test_is_both_redundant_and_load_bearing(proved: tuple[redundancy.Survey, redundancy.Verdicts]) -> None:
    verdicts = proved[1]
    assert not {proof.test for proof in verdicts.redundant} & {proof.test for proof in verdicts.load_bearing}
    assert not {proof.test for proof in verdicts.redundant} & set(proved[0].necessary)


def kills(tmp_path: Path, dropped: Sequence[str] = ()) -> int:
    """How many logic mutants the toy's suite kills, with the named tests taken out of it."""
    setup = toy_tree(tmp_path)
    suite = tmp_path / 'tests' / 'test_thing.py'
    for name in dropped:
        source = suite.read_text()
        kept = source.replace(f'def {name}():', f'def _dropped_{name}():')
        assert kept != source, name
        suite.write_text(kept)
    contexts, _, _ = subset.load(setup.repo, setup.source_root, setup.cache_dir, pytest_prefix=setup.pytest_prefix)
    return harness.measure(setup, ['src/toy/thing.py'], contexts, announce=lambda _: None).tally().killed


def named(test: str) -> str:
    return test.rsplit('::', 1)[1]


def test_deleting_any_test_it_proved_redundant_leaves_the_kills_unchanged(
    proved: tuple[redundancy.Survey, redundancy.Verdicts], tmp_path: Path
) -> None:
    """The claim itself, measured rather than argued: a proof the deletion does not survive is not a proof.

    The baseline is measured here too, so this asserts "unchanged" rather than restating a number that would need editing the
    first time the toy grows a line. Deleted one at a time, because every proof is stated against the suite as it stands — two
    tests that duplicate each other are both redundant, and neither is once the other has gone.
    """
    baseline = kills(tmp_path / 'baseline')
    assert baseline > 0
    for proof in proved[1].redundant:
        assert kills(tmp_path / named(proof.test), dropped=[named(proof.test)]) == baseline, proof.test


@pytest.mark.replants
def test_the_verification_pass_replants_the_scope_and_finds_nothing_lost(tmp_path: Path) -> None:
    """The prover checking its own answer, end to end and against the real thing rather than against its bookkeeping."""
    setup = toy_tree(tmp_path)
    contexts, _, _ = subset.load(setup.repo, setup.source_root, setup.cache_dir, pytest_prefix=setup.pytest_prefix)
    _, verdicts = redundancy.measure(setup, contexts, ['tests/test_thing.py'], verified=True, announce=lambda _: None)
    assert verdicts.verified is not None
    assert verdicts.verified.holds
    assert verdicts.verified.deleted == len(verdicts.deletable)


@pytest.mark.replants
def test_the_verification_pass_reports_the_kill_a_wrong_deletion_would_cost(tmp_path: Path) -> None:
    """Deleting a whole mutual cluster is exactly the mistake the joint answer exists to prevent, so it is measured failing."""
    setup = toy_tree(tmp_path)
    contexts, _, _ = subset.load(setup.repo, setup.source_root, setup.cache_dir, pytest_prefix=setup.pytest_prefix)
    _, verdicts = redundancy.measure(setup, contexts, ['tests/test_thing.py'], announce=lambda _: None)
    everything = [proof.test for proof in verdicts.redundant]
    run = harness.measure(
        setup, ['src/toy/thing.py'], redundancy.forced_contexts(['src/toy/thing.py'], verdicts.run_set, setup.repo), announce=lambda _: None
    )
    checked = redundancy.verify(setup, ['src/toy/thing.py'], verdicts.run_set, everything, run, lambda _: None)
    assert not checked.holds
    assert checked.killed_after < checked.killed_before


def test_deleting_the_whole_joint_set_in_one_act_leaves_the_kills_unchanged(
    proved: tuple[redundancy.Survey, redundancy.Verdicts], tmp_path: Path
) -> None:
    """The claim a person acts on, which the per-test proof does not make on its own."""
    joint = [named(proof.test) for proof in proved[1].redundant if proof.together]
    assert joint
    assert kills(tmp_path / 'joint', dropped=joint) == kills(tmp_path / 'baseline')


def test_deleting_every_redundant_test_at_once_would_cost_a_kill(
    proved: tuple[redundancy.Survey, redundancy.Verdicts], tmp_path: Path
) -> None:
    """Why the joint answer exists at all: the per-test list is not a list of deletions, and this is the toy proving it."""
    everything = [named(proof.test) for proof in proved[1].redundant]
    assert kills(tmp_path / 'all', dropped=everything) < kills(tmp_path / 'baseline')


def test_dropping_a_load_bearing_test_does_cost_a_kill(proved: tuple[redundancy.Survey, redundancy.Verdicts], tmp_path: Path) -> None:
    """The other direction, without which the assertion above would pass for a prover that called everything redundant."""
    baseline = kills(tmp_path / 'baseline')
    for proof in proved[1].load_bearing:
        assert kills(tmp_path / named(proof.test), dropped=[named(proof.test)]) < baseline, proof.test


# ─────────────────────────────────────────────────────────────────────────────
# The seam the whole proof rests on
# ─────────────────────────────────────────────────────────────────────────────


def stub_pytest(tmp_path: Path, body: str) -> Path:
    stub = tmp_path / 'stub_pytest.py'
    stub.write_text(body)
    return stub


def stub_recording(tmp_path: Path, recorded: Sequence[str], code: int) -> Path:
    """A stub pytest that writes what the real plugin would have, then exits.

    The record is the plugin's whole contract, so a stub standing in for pytest has to honor it or it is testing an interface
    nothing has.
    """
    body = f'import json, os, sys\nopen(os.environ[{failures.WHERE!r}], "w").write(json.dumps({list(recorded)!r}))\nsys.exit({code})\n'
    return stub_pytest(tmp_path, body)


@pytest.mark.replants
def test_a_kill_the_summary_cannot_attribute_is_a_harness_error_rather_than_a_kill(tmp_path: Path) -> None:
    """Exit 1 with nothing named would otherwise be a mutant with no killers, which blocks no proof and licenses a false one."""
    setup = dataclasses.replace(
        toy_tree(tmp_path / 'tree'), pytest_prefix=(sys.executable, str(stub_pytest(tmp_path, 'import sys\nsys.exit(1)\n')))
    )
    result = executed(setup, ('tests/test_thing.py::test_over_high',), tmp_path / 'scratch')
    assert result.status == score.HARNESS_ERROR
    assert harness.UNATTRIBUTED in result.detail
    assert result.killers == ()


def executed(setup: harness.Setup, tests: tuple[str, ...], scratch: Path) -> score.SiteResult:
    workers = harness.Workers(setup, scratch)
    planned = harness.Planned(
        relative='src/toy/thing.py', site=planter.sites(ast.parse(TOY_SOURCE))[0], verdict=classify.DEFAULT, tests=tests
    )
    return harness._execute(setup, workers, {'src/toy/thing.py': TOY_SOURCE}, planned, 60.0)


@pytest.mark.replants
def test_a_mutant_that_stops_a_module_being_collected_is_a_kill_by_the_tests_in_it(tmp_path: Path) -> None:
    """Exit 4 because the named node ids stopped resolving is the suite noticing in the loudest way it has."""
    stub = stub_recording(tmp_path, ['tests/test_thing.py'], code=4)
    setup = dataclasses.replace(toy_tree(tmp_path / 'tree'), pytest_prefix=(sys.executable, str(stub)))
    result = executed(setup, ('tests/test_thing.py::test_over_high', 'tests/other.py::test_z'), tmp_path / 'scratch')
    assert result.status == score.KILLED
    assert result.killers == ('tests/test_thing.py::test_over_high',)
    assert harness.UNCOLLECTABLE in result.detail


@pytest.mark.replants
def test_exit_four_that_names_nothing_stays_a_harness_error(tmp_path: Path) -> None:
    """The guard the harness was built around: a flag that is not installed made the first prototype report a perfect score."""
    body = 'import sys\nprint("ERROR: unrecognized arguments: --timeout")\nsys.exit(4)\n'
    setup = dataclasses.replace(toy_tree(tmp_path / 'tree'), pytest_prefix=(sys.executable, str(stub_pytest(tmp_path, body))))
    result = executed(setup, ('tests/test_thing.py::test_over_high',), tmp_path / 'scratch')
    assert result.status == score.HARNESS_ERROR
    assert result.killers == ()


@pytest.mark.replants
def test_the_collection_flag_is_asked_for_only_when_the_killers_are_wanted(tmp_path: Path) -> None:
    """It decides what an uncollectable mutant scores — exit 4 is a harness fault and exit 1 is a kill — so a run that is not
    recording killers keeps the stricter reading."""
    setup = dataclasses.replace(
        toy_tree(tmp_path / 'tree'),
        pytest_prefix=(
            sys.executable,
            str(stub_pytest(tmp_path, f'import sys, pathlib\npathlib.Path({str(tmp_path / "argv")!r}).write_text("\\n".join(sys.argv))\n')),
        ),
    )
    for wanted in (False, True):
        harness.run_pytest(setup, tmp_path, ['tests/test_thing.py'], stop_early=False, timeout=60.0, basetemp=tmp_path, attributed=wanted)
        argv = (tmp_path / 'argv').read_text().splitlines()
        assert (harness.ATTRIBUTED[0] in argv) is wanted
        assert ('mutation.failures' in argv) is wanted


UNSHADOWABLE_TEST = """\
from pathlib import Path

import toy


def test_a_marker_beside_the_package():
    assert (Path(toy.__file__).parent.parent.parent / 'pyproject.toml').is_file()
"""


@pytest.mark.replants
def test_a_test_anchored_outside_the_package_is_dropped_and_named(tmp_path: Path) -> None:
    """The real shape, reproduced: the worker's copy holds `src/` and nothing beside it, so such a test fails against every mutant.

    Left in the room it would be everybody's subsumer, which is the one failure that turns a proof into its opposite.
    """
    setup = toy_tree(tmp_path / 'tree')
    (setup.repo / 'tests' / 'test_anchored.py').write_text(UNSHADOWABLE_TEST)
    room = ['tests/test_thing.py::test_over_high', 'tests/test_anchored.py::test_a_marker_beside_the_package']
    kept, dropped = redundancy.screen(setup, room, tmp_path / 'scratch')
    assert kept == ('tests/test_thing.py::test_over_high',)
    assert dropped == ('tests/test_anchored.py::test_a_marker_beside_the_package',)


@pytest.mark.replants
def test_a_room_screened_down_to_nothing_is_refused_rather_than_run(tmp_path: Path) -> None:
    """Dropping is for a test the harness cannot host, never a way to reach a green room by attrition.

    The empty list is the trap worth refusing loudly: pytest handed no arguments runs `testpaths`, so a room screened to nothing
    would quietly become the whole suite.
    """
    setup = toy_tree(tmp_path / 'tree')
    (setup.repo / 'tests' / 'test_broken.py').write_text('def test_one():\n    assert False\n\n\ndef test_two():\n    assert False\n')
    with pytest.raises(RuntimeError, match='nothing left to prove'):
        redundancy.screen(setup, ['tests/test_broken.py::test_one', 'tests/test_broken.py::test_two'], tmp_path / 'scratch')


def test_forcing_the_contexts_puts_the_whole_room_on_every_line(tmp_path: Path) -> None:
    """Selecting by the measured map would skip a site coverage attributes to the line a statement starts on."""
    (tmp_path / 'src' / 'toy').mkdir(parents=True)
    (tmp_path / 'src' / 'toy' / 'thing.py').write_text(TOY_SOURCE)
    forced = redundancy.forced_contexts(['src/toy/thing.py'], ['t::one', 't::two'], tmp_path)
    assert forced.for_line('src/toy/thing.py', 1) == ('t::one', 't::two')
    assert forced.for_line('src/toy/thing.py', len(TOY_SOURCE.splitlines())) == ('t::one', 't::two')


def test_an_ordinary_run_records_no_killers_at_all() -> None:
    """The field is empty because nobody asked, never because nobody killed — `-x` stops at the first failure."""
    assert harness.Setup(repo=Path('/'), source_root=Path('/'), cache_dir=Path('/')).record_killers is False


def test_a_mutant_the_same_length_as_the_last_one_is_still_imported(tmp_path: Path) -> None:
    """Attribution is worth nothing on top of a stale import, so the property that makes it trustworthy is pinned here.

    Both readings were measured before `run.NO_BYTECODE`. `LIMIT = 3` -> `4` is byte-for-byte the same length as the original, so
    it survived without the interpreter ever compiling it. `'under'` -> `'under-mutant'` is the same length as the `'over'` mutant
    that ran before it in the same worker, so it was reported killed by a test that never reaches the branch it changed.
    """
    setup = toy_tree(tmp_path)
    contexts, _, _ = subset.load(setup.repo, setup.source_root, setup.cache_dir, pytest_prefix=setup.pytest_prefix)
    run = harness.measure(setup, ['src/toy/thing.py'], contexts, announce=lambda _: None)
    verdicts = {result.description: result.status for result in run.results}
    assert verdicts['3 -> 4'] == score.KILLED
    assert verdicts["'under' -> 'under-mutant'"] == score.SURVIVED
