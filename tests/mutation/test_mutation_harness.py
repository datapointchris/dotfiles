"""The harness is code, so it is tested.

Three things here are worth more than the rest. The classifier is a table of source snippets against the bucket and the rule they
must land in — adding a rendering position is a row. The exit-code reading is its own table, because "a crash is not a kill" is the
property that made the first prototype report a perfect score against a pytest that never ran. And one end-to-end plants real bugs
in a real toy package and drives a real pytest against it, so the shadowing, the control gate and the survivor confirmation are
measured rather than described.

Nothing here asserts on a printed sentence. `score.render` returns lines and the assertions are on the counts inside them.
"""

from __future__ import annotations

import ast
import dataclasses
import datetime as dt
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from mutation import classify
from mutation import planter
from mutation import run as harness
from mutation import score
from mutation import subset
from mutation import targets


def parsed(source: str) -> ast.Module:
    return ast.parse(textwrap.dedent(source))


# ─────────────────────────────────────────────────────────────────────────────
# The operators, and the walk every module counts sites in
# ─────────────────────────────────────────────────────────────────────────────

OPERATORS = [
    ('x == y', planter.COMPARISON, 'Eq -> NotEq', 'x != y'),
    ('x is None', planter.COMPARISON, 'Is -> IsNot', 'x is not None'),
    ('x in y', planter.COMPARISON, 'In -> NotIn', 'x not in y'),
    ('x and y', planter.BOOLEAN_OPERATOR, 'and -> or', 'x or y'),
    ('x or y', planter.BOOLEAN_OPERATOR, 'or -> and', 'x and y'),
    ('not x', planter.NEGATION, 'drop not', 'x'),
    ('x = True', planter.BOOLEAN, 'True -> False', 'x = False'),
    ('x = 3', planter.INTEGER, '3 -> 4', 'x = 4'),
    ('x = 2.5', planter.FLOATING, '2.5 -> 3.5', 'x = 3.5'),
    ("x = 'ok'", planter.STRING, "'ok' -> 'ok-mutant'", "x = 'ok-mutant'"),
]


@pytest.mark.parametrize(('source', 'kind', 'description', 'planted'), OPERATORS, ids=[row[0] for row in OPERATORS])
def test_each_operator_names_its_kind_and_produces_the_stated_source(source: str, kind: str, description: str, planted: str) -> None:
    found = planter.sites(parsed(source))
    assert [site.kind for site in found] == [kind]
    assert found[0].description == description
    assert planter.plant(source, 0) == planted


def test_a_site_index_names_the_same_node_on_every_re_parse() -> None:
    source = "a = 1\nb = 'two'\nc = a == 1\n"
    assert [planter.plant(source, index) for index in range(len(planter.sites(parsed(source))))] == [
        "a = 2\nb = 'two'\nc = a == 1",
        "a = 1\nb = 'two-mutant'\nc = a == 1",
        "a = 1\nb = 'two'\nc = a != 1",
        "a = 1\nb = 'two'\nc = a == 2",
    ]


def test_planting_one_site_leaves_every_other_site_alone() -> None:
    source = 'a = 1\nb = 2\n'
    assert planter.plant(source, 0) == 'a = 2\nb = 2'
    assert planter.plant(source, 1) == 'a = 1\nb = 3'


def test_a_long_string_is_a_site_rather_than_a_silent_omission() -> None:
    long_enough = 'x' * 80
    found = planter.sites(parsed(f"key = '{long_enough}'"))
    assert [site.kind for site in found] == [planter.STRING]
    assert found[0].skipped == ''
    assert planter.plant(f"key = '{long_enough}'", 0) == f"key = '{long_enough}{planter.MARKER}'"


def test_an_annotation_is_a_counted_site_and_is_never_planted() -> None:
    found = planter.sites(parsed("from typing import Literal\nx: Literal['a'] = 'b'\n"))
    skipped = [site for site in found if site.skipped]
    assert [site.description for site in skipped] == ["'a' -> 'a-mutant'"]
    assert all(site.skipped == planter.ANNOTATION for site in skipped)


def test_a_float_and_a_bool_are_told_apart_from_an_int() -> None:
    found = planter.sites(parsed('a = True\nb = 1\nc = 1.0\n'))
    assert [site.kind for site in found] == [planter.BOOLEAN, planter.INTEGER, planter.FLOATING]


def test_the_round_trip_is_the_source_with_nothing_mutated() -> None:
    source = "def f():\n    '''doc'''\n    return 1 == 1\n"
    assert ast.dump(ast.parse(planter.round_trip(source))) == ast.dump(ast.parse(source))


# ─────────────────────────────────────────────────────────────────────────────
# The classifier: a row per position, which is how a rendering position is added
# ─────────────────────────────────────────────────────────────────────────────

POSITIONS = [
    ('module docstring', "'''prose'''\n", 'prose', classify.RENDERING, classify.RULE_DOCSTRING),
    ('function docstring', "def f():\n    '''prose'''\n", 'prose', classify.RENDERING, classify.RULE_DOCSTRING),
    ('attribute docstring', "LIMIT = 1\n'''prose'''\n", 'prose', classify.RENDERING, classify.RULE_BARE_STRING),
    (
        'help keyword',
        "import typer\nx = typer.Option(False, '--json', help='prose')\n",
        'prose',
        classify.RENDERING,
        classify.RULE_RENDER_KEYWORD,
    ),
    (
        'the flag beside it',
        "import typer\nx = typer.Option(False, '--json', help='prose')\n",
        '--json',
        classify.LOGIC,
        classify.RULE_DEFAULT,
    ),
    ('render function', "from dotfiles.output import error\nerror('prose')\n", 'prose', classify.RENDERING, classify.RULE_RENDER_CALL),
    (
        'render function through the module',
        "from dotfiles import output\noutput.warn('prose')\n",
        'prose',
        classify.RENDERING,
        classify.RULE_RENDER_CALL,
    ),
    (
        'console print',
        "from dotfiles.output import console\nconsole.print('prose')\n",
        'prose',
        classify.RENDERING,
        classify.RULE_RENDER_CALL,
    ),
    (
        'table column',
        "from rich.table import Table\nt = Table()\nt.add_column('prose')\n",
        'prose',
        classify.RENDERING,
        classify.RULE_RENDER_CALL,
    ),
    (
        'f-string inside a render call',
        "from dotfiles.output import warn\nwarn(f'prose {x}')\n",
        'prose ',
        classify.RENDERING,
        classify.RULE_RENDER_CALL,
    ),
    (
        'bad parameter message',
        "import typer\nraise typer.BadParameter('prose')\n",
        'prose',
        classify.RENDERING,
        classify.RULE_EXCEPTION_MESSAGE,
    ),
    ('value error message', "raise ValueError('prose')\n", 'prose', classify.RENDERING, classify.RULE_EXCEPTION_MESSAGE),
    ('style token', "colour = 'red'\n", 'red', classify.RENDERING, classify.RULE_RICH_STYLE),
    (
        'what a comprehension inside a render call reads',
        "from rich.table import Table\nt = Table()\nt.add_row(*(str(row[k]) for k in ('total',)))\n",
        'total',
        classify.LOGIC,
        classify.RULE_DEFAULT,
    ),
    (
        'json payload key',
        "from dotfiles.output import emit_json\nemit_json({'prose': 1})\n",
        'prose',
        classify.LOGIC,
        classify.RULE_JSON_CONTRACT,
    ),
    (
        'command name',
        "import typer\napp = typer.Typer()\n\n@app.command('prose')\ndef f():\n    pass\n",
        'prose',
        classify.LOGIC,
        classify.RULE_DEFAULT,
    ),
    ('dict value on a contract', "def f():\n    return {'outcome': 'prose'}\n", 'prose', classify.LOGIC, classify.RULE_DEFAULT),
    ('file suffix', "x = p.suffix == 'prose'\n", 'prose', classify.LOGIC, classify.RULE_DEFAULT),
    ('env var name', "import os\nx = os.environ.get('prose')\n", 'prose', classify.LOGIC, classify.RULE_DEFAULT),
    (
        'exit code',
        'import typer\nfrom dotfiles.vocabulary import ExitCode\nraise typer.Exit(3)\n',
        3,
        classify.LOGIC,
        classify.RULE_DEFAULT,
    ),
    (
        'structlog event name',
        "from dotfiles import logging\nlog = logging.get_logger(__name__)\nlog.info('prose', at='here')\n",
        'prose',
        classify.LOGIC,
        classify.RULE_EVENT_NAME,
    ),
    (
        'structlog field value',
        "from dotfiles import logging\nlog = logging.get_logger(__name__)\nlog.info('event', at='prose')\n",
        'prose',
        classify.RENDERING,
        classify.RULE_RENDER_CALL,
    ),
]


def verdict_for(source: str, value: object, path: Path = Path('src/dotfiles/somewhere.py')) -> classify.Verdict:
    tree = parsed(source)
    verdicts = classify.annotate(tree, path)
    found = [
        verdicts[id(node)]
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value == value and type(node.value) is type(value)
    ]
    assert found, f'{value!r} is not a constant in that source'
    return found[0]


@pytest.mark.parametrize(('name', 'source', 'value', 'bucket', 'rule'), POSITIONS, ids=[row[0] for row in POSITIONS])
def test_a_constant_is_bucketed_by_the_position_it_sits_in(name: str, source: str, value: object, bucket: str, rule: str) -> None:
    found = verdict_for(source, value)
    assert (found.bucket, found.rule) == (bucket, rule)


def test_every_constant_in_the_render_modules_is_rendering() -> None:
    found = verdict_for("WIDTH = 11\nCOLOUR = 'anything'\n", 11, Path('src/dotfiles/banner.py'))
    assert (found.bucket, found.rule) == (classify.RENDERING, classify.RULE_RENDER_MODULE)


def test_the_status_vocabulary_is_logic_where_it_sits_beside_the_decoration() -> None:
    """`output.py` holds the fleet's verdict words next to its colours. Marked a
    render module it lost `MATCHED` and every `VERDICT_COLOURS` key from the
    score, and a test pinning one landed in PROSE-PINNED, which the gate refuses
    on. Its decoration is still caught, by the rules written for decoration."""
    found = verdict_for("MATCHED = 'matched'\n", 'matched', Path('src/dotfiles/output.py'))

    assert found.bucket == classify.LOGIC


def test_control_flow_is_logic_even_in_a_render_module() -> None:
    tree = parsed('def f(a, b):\n    return a == b\n')
    verdicts = classify.annotate(tree, Path('src/dotfiles/banner.py'))
    compares = [verdicts[id(node)] for node in ast.walk(tree) if isinstance(node, ast.Compare)]
    assert [(found.bucket, found.rule) for found in compares] == [(classify.LOGIC, classify.RULE_CONTROL_FLOW)]


def test_an_unrecognised_position_defaults_to_logic() -> None:
    """The direction that matters: a misclassified logic string surfaces as a survivor, and a misclassified rendering string vanishes."""
    found = verdict_for("x = some_unknown_call('prose')\n", 'prose')
    assert found.bucket == classify.LOGIC


def test_a_style_word_alone_is_not_enough_to_call_a_string_a_style() -> None:
    assert not classify.is_style('on')
    assert not classify.is_style('default')
    assert classify.is_style('bold yellow')


def test_the_import_table_resolves_an_alias_to_its_dotted_name() -> None:
    tree = parsed('from dotfiles import remote as transport\nimport dotfiles.paths\n')
    table = classify.import_table(tree, Path('src/dotfiles/commands/report.py'))
    assert table['transport'] == 'dotfiles.remote'
    assert classify.dotted(ast.parse('transport.reachable', mode='eval').body, table) == 'dotfiles.remote.reachable'


# ─────────────────────────────────────────────────────────────────────────────
# Exit codes: the property the first prototype got wrong
# ─────────────────────────────────────────────────────────────────────────────

EXITS = [
    (0, score.SURVIVED),
    (1, score.KILLED),
    (2, score.HARNESS_ERROR),
    (3, score.HARNESS_ERROR),
    (4, score.HARNESS_ERROR),
    (5, score.HARNESS_ERROR),
    (-11, score.HARNESS_ERROR),
    (None, score.TIMED_OUT),
]


@pytest.mark.parametrize(('code', 'status'), EXITS, ids=[str(row[0]) for row in EXITS])
def test_only_exit_one_is_a_kill(code: int | None, status: str) -> None:
    found, detail = harness.outcome_for(code)
    assert found == status
    assert (detail == '') is (code in (0, 1))


# ─────────────────────────────────────────────────────────────────────────────
# The context map, against a real coverage data file
# ─────────────────────────────────────────────────────────────────────────────


def written_coverage(tmp_path: Path) -> Path:
    """A real `CoverageData`, written through coverage's own API rather than a hand-shaped dict."""
    import coverage

    basename = tmp_path / '.coverage'
    data = coverage.CoverageData(str(basename))
    measured = str(tmp_path / 'src' / 'pkg' / 'thing.py')
    data.set_context('tests/test_a.py::test_one|run')
    data.add_lines({measured: [1, 5]})
    data.set_context('tests/test_b.py::test_two|setup')
    data.add_lines({measured: [5]})
    data.set_context('')
    data.add_lines({measured: [1, 9]})
    data.write()
    return basename


def test_a_line_maps_to_the_tests_that_executed_it(tmp_path: Path) -> None:
    (tmp_path / 'src' / 'pkg').mkdir(parents=True)
    found = subset.read_data(written_coverage(tmp_path), tmp_path, tmp_path / 'src')
    assert found.for_line('src/pkg/thing.py', 5) == ('tests/test_a.py::test_one', 'tests/test_b.py::test_two')


def test_a_line_no_test_reaches_is_empty_rather_than_absent(tmp_path: Path) -> None:
    (tmp_path / 'src' / 'pkg').mkdir(parents=True)
    found = subset.read_data(written_coverage(tmp_path), tmp_path, tmp_path / 'src')
    assert found.for_line('src/pkg/thing.py', 404) == ()
    assert found.measured('src/pkg/thing.py')


def test_an_import_time_line_falls_back_to_every_test_that_touches_the_file(tmp_path: Path) -> None:
    (tmp_path / 'src' / 'pkg').mkdir(parents=True)
    found = subset.read_data(written_coverage(tmp_path), tmp_path, tmp_path / 'src')
    assert found.for_line('src/pkg/thing.py', 9) == ('tests/test_a.py::test_one', 'tests/test_b.py::test_two')


def test_the_phase_suffix_is_stripped_so_pytest_can_address_the_test() -> None:
    assert subset.strip_phase('tests/x.py::test_y|run') == 'tests/x.py::test_y'
    assert subset.strip_phase('tests/x.py::test_y|teardown') == 'tests/x.py::test_y'
    assert subset.strip_phase('tests/x.py::test_y') == 'tests/x.py::test_y'


def test_a_truncated_cache_is_measured_again_rather_than_raising(tmp_path: Path) -> None:
    """A run interrupted mid-write leaves half a map, and half a map produces kills against a subset that is missing rows."""
    plan = toy_tree(tmp_path)
    _, cached, _ = subset.load(plan.repo, plan.source_root, plan.cache_dir, pytest_prefix=plan.pytest_prefix)
    cached.write_text(json.dumps({'tests': ['tests/test_thing.py::test_over']})[:-4])
    found, again, measured = subset.load(plan.repo, plan.source_root, plan.cache_dir, pytest_prefix=plan.pytest_prefix)
    assert (again, measured) == (cached, True)
    assert found.for_line('src/toy/thing.py', 7)


def test_the_fingerprint_moves_when_a_test_file_changes(tmp_path: Path) -> None:
    (tmp_path / 'src').mkdir()
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'src' / 'a.py').write_text('x = 1\n')
    (tmp_path / 'tests' / 'test_a.py').write_text('def test_a():\n    pass\n')
    before = subset.fingerprint(tmp_path)
    (tmp_path / 'tests' / 'test_a.py').write_text('def test_a():\n    assert True\n')
    assert subset.fingerprint(tmp_path) != before


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────


def result(
    status: str, bucket: str = classify.LOGIC, line: int = 1, description: str = 'a -> b', file: str = 'src/dotfiles/x.py'
) -> score.SiteResult:
    return score.SiteResult(file=file, line=line, col=0, kind='string', bucket=bucket, rule='r', description=description, status=status)


def test_unreached_counts_against_the_score_so_deleting_tests_cannot_raise_it() -> None:
    counts = score.tally([result(score.KILLED), result(score.SURVIVED), result(score.UNREACHED)])
    assert (counts.killed, counts.survived, counts.unreached) == (1, 1, 1)
    assert counts.scored == 3
    assert counts.score == pytest.approx(1 / 3)


def test_a_rendering_mutant_is_kept_out_of_the_score_and_counted_when_it_dies() -> None:
    counts = score.tally(
        [result(score.KILLED), result(score.KILLED, bucket=classify.RENDERING), result(score.SURVIVED, bucket=classify.RENDERING)]
    )
    assert counts.scored == 1
    assert counts.score == 1.0
    assert (counts.rendering, counts.prose_pinned) == (2, 1)


def test_a_harness_error_is_never_a_kill() -> None:
    counts = score.tally([result(score.HARNESS_ERROR), result(score.KILLED)])
    assert (counts.harness_errors, counts.killed, counts.scored) == (1, 1, 1)


def test_a_timeout_is_scored_as_a_kill_and_reported_on_its_own() -> None:
    counts = score.tally([result(score.TIMED_OUT), result(score.SURVIVED)])
    assert (counts.timed_out, counts.score) == (1, 0.5)


def toy_run(results: list[score.SiteResult], targets_named: tuple[str, ...] = ('src/dotfiles/x.py',)) -> score.Run:
    return score.Run(
        started_at='20260101T000000Z', finished_at='20260101T000100Z', machine='box', targets=targets_named, results=tuple(results)
    )


def test_a_survivor_that_was_not_there_before_is_named() -> None:
    before = toy_run([result(score.KILLED, line=1), result(score.KILLED, line=2)])
    after = toy_run([result(score.KILLED, line=1), result(score.SURVIVED, line=2)])
    found = score.compare(after, before)
    assert [item.line for item in found.new_survivors] == [2]
    assert found.fixed == ()
    assert (found.score_before, found.score_after) == (1.0, 0.5)


def test_a_survivor_that_is_now_killed_is_named_too() -> None:
    before = toy_run([result(score.SURVIVED, line=2)])
    after = toy_run([result(score.KILLED, line=2)])
    assert [item.line for item in score.compare(after, before).fixed] == [2]


def test_a_rendering_mutant_that_newly_dies_is_named_and_a_standing_one_is_not() -> None:
    """Compared rather than capped: an absolute ceiling would be a committed score, and this direction cannot be gamed."""
    before = toy_run([result(score.KILLED, bucket=classify.RENDERING, line=1)])
    after = toy_run([result(score.KILLED, bucket=classify.RENDERING, line=1), result(score.KILLED, bucket=classify.RENDERING, line=9)])
    found = score.compare(after, before)
    assert [item.line for item in found.new_prose_pinned] == [9]
    assert [item.line for item in score.compare(before, before).new_prose_pinned] == []


def test_a_target_the_previous_run_did_not_measure_is_left_out_of_the_comparison() -> None:
    before = toy_run([result(score.KILLED, file='src/dotfiles/a.py')], targets_named=('src/dotfiles/a.py',))
    after = toy_run(
        [result(score.KILLED, file='src/dotfiles/a.py'), result(score.SURVIVED, file='src/dotfiles/b.py')],
        targets_named=('src/dotfiles/a.py', 'src/dotfiles/b.py'),
    )
    found = score.compare(after, before)
    assert found.shared_targets == ('src/dotfiles/a.py',)
    assert found.new_survivors == ()


def test_a_run_is_recorded_under_the_machine_that_wrote_it(tmp_path: Path) -> None:
    written = score.record(toy_run([result(score.KILLED)]), tmp_path, 'archbox')
    assert written.name == '20260101T000000Z-archbox.json'
    assert score.read(written).results[0].status == score.KILLED
    assert score.recorded(tmp_path, 'archbox') == [written]
    assert score.recorded(tmp_path, 'someone-else') == []


def test_the_report_carries_the_counts_rather_than_a_verdict_sentence() -> None:
    lines = score.render(toy_run([result(score.KILLED), result(score.SURVIVED, line=7)]))
    assert any('50%' in line for line in lines)
    assert any('src/dotfiles/x.py:7:0' in line for line in lines)


def test_a_comparison_over_no_shared_target_is_left_out_rather_than_reported_as_unchanged() -> None:
    """`tally([])` scores 1.0, so an empty intersection would otherwise print a confident `100% -> 100%`."""
    only_a = toy_run([result(score.SURVIVED, file='src/dotfiles/a.py')], targets_named=('src/dotfiles/a.py',))
    only_b = toy_run([result(score.SURVIVED, file='src/dotfiles/b.py')], targets_named=('src/dotfiles/b.py',))
    assert not any('->' in line and '%' in line for line in score.render(only_b, score.compare(only_b, only_a)))


def test_the_report_verb_answers_about_the_directory_it_is_pointed_at(tmp_path: Path) -> None:
    assert score.main(['--runs-dir', str(tmp_path)]) == 1
    score.record(toy_run([result(score.KILLED)]), tmp_path, 'box')
    score.record(
        dataclasses.replace(toy_run([result(score.SURVIVED)]), started_at='20260102T000000Z'),
        tmp_path,
        'box',
    )
    assert score.main(['--runs-dir', str(tmp_path), '--machine', 'box']) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Targets
# ─────────────────────────────────────────────────────────────────────────────


def test_every_default_target_is_a_file_in_the_checkout() -> None:
    """A renamed module drops out of the routine run silently otherwise, which is the failure this file exists to make loud."""
    repo = harness.repo_root()
    assert [name for name in targets.DEFAULT_TARGETS if not (repo / name).is_file()] == []


def test_a_target_that_is_not_a_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        targets.resolve(tmp_path, ['src/dotfiles/nowhere.py'])


def test_discovery_reads_the_tree_rather_than_a_committed_list() -> None:
    repo = harness.repo_root()
    found = list(targets.discover(repo))
    assert 'src/dotfiles/runs.py' in found
    assert len(found) > len(targets.DEFAULT_TARGETS)
    assert targets.resolve(repo, [], everything=True) == found


def test_naming_nothing_measures_what_the_default_targets_name() -> None:
    repo = harness.repo_root()
    assert targets.resolve(repo, []) == list(targets.DEFAULT_TARGETS)


def test_the_explain_verb_classifies_a_real_module_and_runs_no_tests() -> None:
    """The audit surface: every site with the rule that decided it, from an entry point that never reaches pytest."""
    repo = harness.repo_root()
    found = harness.explain(repo / 'src/dotfiles/commands/report.py', repo)
    assert {item.verdict.rule for item in found} >= {classify.RULE_DOCSTRING, classify.RULE_RENDER_CALL, classify.RULE_DEFAULT}
    assert all(item.tests == () for item in found)
    assert harness.main(['--explain', 'src/dotfiles/commands/report.py']) == 0


def test_the_threshold_is_a_floor_a_run_can_actually_clear() -> None:
    assert 0.0 < targets.THRESHOLD < 1.0


# ─────────────────────────────────────────────────────────────────────────────
# The changed-line filter
# ─────────────────────────────────────────────────────────────────────────────


def git_repo(tmp_path: Path) -> Path:
    def git(*argv: str) -> None:
        subprocess.run(['git', *argv], cwd=tmp_path, check=True, capture_output=True)

    (tmp_path / 'src' / 'dotfiles').mkdir(parents=True)
    (tmp_path / 'src' / 'dotfiles' / 'a.py').write_text('one = 1\ntwo = 2\nthree = 3\n')
    git('init', '-q')
    git('config', 'user.email', 'harness@example.invalid')
    git('config', 'user.name', 'harness')
    git('add', '.')
    git('commit', '-qm', 'base')
    git('branch', 'base')
    (tmp_path / 'src' / 'dotfiles' / 'a.py').write_text('one = 1\ntwo = 22\nthree = 3\n')
    git('commit', '-qam', 'change')
    return tmp_path


def test_only_the_lines_a_branch_changed_are_named(tmp_path: Path) -> None:
    assert harness.changed_lines(git_repo(tmp_path), 'base') == {'src/dotfiles/a.py': {2}}


def test_a_ref_that_does_not_resolve_is_refused_rather_than_read_as_no_changes(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        harness.changed_lines(git_repo(tmp_path), 'origin/nowhere')


# ─────────────────────────────────────────────────────────────────────────────
# End to end, against a real toy package and a real pytest
# ─────────────────────────────────────────────────────────────────────────────

TOY_SOURCE = '''\
"""A toy."""

LIMIT = 3


def over(count):
    return count > LIMIT


def label(count):
    return 'over' if over(count) else 'under'


def unreachable(count):
    return count * 2
'''

TOY_TESTS = """\
from toy import thing


def test_over():
    assert thing.over(4) is True
    assert thing.over(3) is False


def test_label():
    assert thing.label(4) == 'over'
"""


def toy_tree(tmp_path: Path) -> harness.Plan:
    (tmp_path / 'src' / 'toy').mkdir(parents=True)
    (tmp_path / 'src' / 'toy' / '__init__.py').write_text('')
    (tmp_path / 'src' / 'toy' / 'thing.py').write_text(TOY_SOURCE)
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests' / 'test_thing.py').write_text(TOY_TESTS)
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    return harness.Plan(
        repo=tmp_path,
        source_root=tmp_path / 'src',
        cache_dir=tmp_path / 'cache',
        pytest_prefix=(sys.executable, '-m', 'pytest'),
        jobs=2,
    )


@pytest.fixture(scope='module')
def toy_result(tmp_path_factory: pytest.TempPathFactory) -> tuple[harness.Plan, score.Run]:
    """One real end-to-end, shared by the assertions below because it costs a coverage pass and several pytest runs."""
    plan = toy_tree(tmp_path_factory.mktemp('toy'))
    contexts, _, measured = subset.load(plan.repo, plan.source_root, plan.cache_dir, pytest_prefix=plan.pytest_prefix)
    assert measured
    return plan, harness.measure(plan, ['src/toy/thing.py'], contexts, announce=lambda _: None)


def test_the_end_to_end_kills_the_comparison_the_toy_asserts_on(toy_result: tuple[harness.Plan, score.Run]) -> None:
    killed = [item for item in toy_result[1].results if item.status == score.KILLED]
    assert ('comparison', 'Gt -> LtE') in {(item.kind, item.description) for item in killed}


def test_the_end_to_end_reports_a_function_no_test_calls_as_unreached(toy_result: tuple[harness.Plan, score.Run]) -> None:
    unreached = [item for item in toy_result[1].results if item.status == score.UNREACHED]
    assert [item.description for item in unreached] == ['2 -> 3']


def test_a_mutant_ran_from_the_copy_and_the_source_tree_was_never_written(toy_result: tuple[harness.Plan, score.Run]) -> None:
    """The property that matters most, and it takes both halves.

    `configs/` and `shell/` are symlinked live into $HOME and the CLI is installed editable against `src/`, so a mutation written in
    place is deployed state. Bugs were planted and killed, *and* the file on disk is byte-identical — which together can only mean
    the mutants ran from the shadow copy.
    """
    plan, run = toy_result
    assert [item for item in run.results if item.status == score.KILLED]
    assert (plan.repo / 'src' / 'toy' / 'thing.py').read_text() == TOY_SOURCE


def test_the_end_to_end_planted_every_site_it_did_not_skip(toy_result: tuple[harness.Plan, score.Run]) -> None:
    run = toy_result[1]
    statuses = {item.status for item in run.results}
    assert score.HARNESS_ERROR not in statuses
    assert run.control_seconds > 0
    assert run.timeout_seconds >= harness.TIMEOUT_FLOOR


def test_a_control_that_fails_stops_the_run_before_anything_is_planted(tmp_path: Path) -> None:
    """Without this gate a bad pytest flag reads as every mutant dying, which is how the prototype first reported 100%."""
    plan = toy_tree(tmp_path)
    contexts, _, _ = subset.load(plan.repo, plan.source_root, plan.cache_dir, pytest_prefix=plan.pytest_prefix)
    (plan.repo / 'tests' / 'test_thing.py').write_text(TOY_TESTS.replace('thing.over(4) is True', 'thing.over(4) is False'))
    with pytest.raises(RuntimeError, match='control run'):
        harness.measure(plan, ['src/toy/thing.py'], contexts, announce=lambda _: None)


def test_the_context_pass_refuses_a_suite_that_is_not_green(tmp_path: Path) -> None:
    plan = toy_tree(tmp_path)
    (plan.repo / 'tests' / 'test_thing.py').write_text('def test_broken():\n    assert False\n')
    with pytest.raises(RuntimeError, match='has to be green'):
        subset.load(plan.repo, plan.source_root, plan.cache_dir, pytest_prefix=plan.pytest_prefix)


def test_the_context_map_is_reused_when_nothing_moved_and_dropped_when_something_does(tmp_path: Path) -> None:
    plan = toy_tree(tmp_path)
    first, cached, measured = subset.load(plan.repo, plan.source_root, plan.cache_dir, pytest_prefix=plan.pytest_prefix)
    assert measured
    _, again, measured_again = subset.load(plan.repo, plan.source_root, plan.cache_dir, pytest_prefix=plan.pytest_prefix)
    assert (again, measured_again) == (cached, False)
    (plan.repo / 'tests' / 'test_thing.py').write_text(TOY_TESTS + '\n\ndef test_extra():\n    assert thing.label(1) == "under"\n')
    _, moved, measured_after = subset.load(plan.repo, plan.source_root, plan.cache_dir, pytest_prefix=plan.pytest_prefix)
    assert moved != cached
    assert measured_after
    assert json.loads(cached.read_text())['tests'] != json.loads(moved.read_text())['tests']
    assert first.for_line('src/toy/thing.py', 7)


# ── The gate, which is the composition `main` could not be tested through ──────


def a_run(*, score_of: float, prose_pinned: int = 0, target: str = 'src/toy/thing.py', stamped: str = '20260817T000000Z') -> score.Run:
    """A run with a chosen score, built rather than measured."""
    killed = int(round(score_of * 10))
    results = [result(score.KILLED, line=index, file=target) for index in range(killed)]
    results += [result(score.SURVIVED, line=100 + index, file=target) for index in range(10 - killed)]
    results += [result(score.KILLED, bucket=classify.RENDERING, line=200 + index, file=target) for index in range(prose_pinned)]
    return score.Run(
        started_at=stamped,
        finished_at=stamped,
        machine='thisbox',
        targets=(target,),
        results=tuple(results),
    )


def test_a_gate_over_a_module_nobody_has_aimed_a_test_at_does_not_report_a_failure() -> None:
    """`DEFAULT_TARGETS` earns a module only after somebody has run it and read
    the survivors, so the first run is below the floor by construction. Refusing
    there reports the command as failed for doing what it is for."""
    poor = a_run(score_of=0.1)

    assert harness.gate(poor, None, floored=False) == 0
    assert harness.gate(poor, None, floored=True) == 1


def test_the_gate_refuses_a_test_that_newly_asserts_on_prose(tmp_path: Path) -> None:
    before = a_run(score_of=1.0)
    after = a_run(score_of=1.0, prose_pinned=1)

    comparison = score.compare(after, before)

    assert comparison.new_prose_pinned
    assert harness.gate(after, comparison, floored=False) == 1
    assert harness.gate(after, None, floored=False) == 0, 'with nothing to compare against there is no new prose'


def test_the_comparison_reads_this_boxs_own_history_and_not_a_peers(tmp_path: Path) -> None:
    """`$XDG_STATE_HOME` is a Syncthing folder, so the newest file in the runs
    directory is usually another machine measuring another commit. Selecting
    without the machine made the gate follow a peer."""
    score.record(a_run(score_of=0.2, stamped='20260817T000000Z'), tmp_path, 'a-peer-box')
    mine = score.record(a_run(score_of=1.0, stamped='20260817T010000Z'), tmp_path, 'thisbox')
    newest_peer = score.record(a_run(score_of=0.2, stamped='20260817T020000Z'), tmp_path, 'a-peer-box')

    assert score.recorded(tmp_path)[0] == newest_peer, 'the peer did write last'
    assert score.recorded(tmp_path, 'thisbox') == [mine]


def test_a_box_named_by_the_tail_of_another_does_not_claim_its_runs(tmp_path: Path) -> None:
    """`scheduler-lxc` is a real hostname here, and a suffix match handed every
    one of its runs to a box called `lxc`."""
    theirs = score.record(a_run(score_of=1.0), tmp_path, 'scheduler-lxc')

    assert score.recorded(tmp_path, 'lxc') == []
    assert score.recorded(tmp_path, 'scheduler-lxc') == [theirs]


def test_a_stamp_carries_no_hyphen_because_the_filename_splits_on_the_first_one() -> None:
    """`record` composes `<stamp>-<machine>` and `recorded` splits it back. A
    machine name carries hyphens of its own, so the stamp is the half that
    cannot, and basic-format ISO 8601 is what makes that true."""
    assert '-' not in score.stamp(dt.datetime(2026, 8, 17, 22, 42, 5, tzinfo=dt.UTC))
