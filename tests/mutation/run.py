"""Plant every site in a target, run the tests that reach it, and say which bugs nobody noticed.

**Never the working tree.** `configs/`, `shell/` and `apps/` are symlinked live into `$HOME` here and the CLI is installed editable against
`src/`, so a mutation written in place is a mutated `dotfiles` deployed on the machine until the harness gets around to restoring it
— and an interrupted run never does. Each worker gets its own copy of `src/` in a temporary directory and shadows the checkout with
`PYTHONPATH=<copy>/src`, which precedes the editable install's `.pth` entry on `sys.path`, so `import dotfiles` resolves to the copy
and the checkout is only ever read.

**The control run is the reason a score can be believed.** Before anything is planted, the chosen subset runs against an unmutated
round trip of the target through `ast.unparse`. Without it a bad pytest flag makes every mutant look killed: the first run of the
prototype passed `--timeout`, which is not installed here, so pytest exited 4 on every mutant and reported 100%.

**A crash is not a kill.** Exit 1 means tests failed, and that is the only exit code that kills. 2, 3, 4 and 5 are interrupted,
internal error, usage error and nothing collected — harness faults, reported separately and never scored. A run recording killers
reads one part of exit 4 differently, and only because it can tell the two apart by attribution; `UNCOLLECTABLE` is why.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import dataclasses
import datetime as dt
import os
import queue
import re
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from collections.abc import Sequence
from pathlib import Path

from dotfiles import paths
from mutation import classify
from mutation import planter
from mutation import score
from mutation import subset
from mutation import targets as target_list

MARKERS = ('pyproject.toml', 'install/packages.yml')
"""What identifies the checkout.

Anchored on files rather than on `paths.REPO_ROOT`, which honours `$DOTFILES_DIR` — pinned to ~/dotfiles in `.zshenv`, so a harness
reading it would measure `main` while reporting on a worktree. `tests/e2e/harness.py` was fixed for exactly this.
"""

PYTEST_PREFIX = ('uv', 'run', '--frozen', 'pytest')

QUIET = ('-q', '--no-header', '-p', 'no:randomly', '-p', 'no:cacheprovider', '--no-cov')
"""`no:cacheprovider` because parallel workers share a checkout and would otherwise race on `.pytest_cache`."""

TIMEOUT_FLOOR = 60.0
TIMEOUT_FACTOR = 3.0
"""A hung mutant has to be told from a slow one, and only the control knows how slow the subset is.

Three times the control plus the floor, because a flipped loop condition hangs forever while a mutant that merely takes a slower
path takes tens of percent longer, not three times.
"""

HUNK = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')

NOT_FOUND = re.compile(r'^ERROR: not found: (\S+)')
"""pytest saying a node id it was handed does not exist, which after a mutation means the id moved rather than the test."""

NO_BYTECODE = '1'
"""Why a mutant worker refuses the bytecode cache, and why its copy starts without one.

A `.pyc` is revalidated against the source's size and its mtime **in whole seconds**, and mutants are written to the same path in
rapid succession. Two of equal length inside one second are indistinguishable to that check, so the second one imports the first
one's bytecode. Both directions were measured on the toy in `test_redundancy.py`: `LIMIT = 3` -> `4` is the same length as the
original and survived without ever running, and `'under'` -> `'under-mutant'` is the same length as the `'over'` mutant that
preceded it in the same worker, so it was reported killed by a test that never executes the branch.

Refusing to write is only half of it — an existing `.pyc` is still read — so `Workers` also declines to copy `__pycache__` into
the worker's tree. Together there is no bytecode for the shadowed source at any point, which no timing window can defeat. Measured
at no cost: the checkout's own `tests/` cache is untouched and still warm, and only the copied `src/` recompiles.
"""

SUMMARY = ('-rfE', '--continue-on-collection-errors')
"""What makes pytest name the tests that failed, rather than only counting them.

`-rfE` is asked for explicitly rather than relied on. pytest's default `reportchars` already covers failures and errors, and a run
whose attribution silently emptied would read as a mutant nothing killed — the one direction `redundancy.py` cannot survive.

`--continue-on-collection-errors` is the half that turns a whole class of mutant from unusable into measured. A mutation to a
module constant can break import: `'darwin'` -> `'darwin-mutant'` in `coordinates.py` makes the catalog refuse a manifest, and
pytest abandons the session at exit 4 with one file named. That reads as a harness fault, which blocks every proof over the file.
With the flag the session continues, every file that could not be collected is named, and the rest of the room still runs — so
the mutant is attributed to the tests that really failed instead of to nobody.
"""

SUMMARY_WIDTH = '200'
"""`COLUMNS` for a summary run.

pytest fits the crash message to the terminal width and falls back to 80 columns off a tty. The node id itself is never truncated,
but a wide terminal keeps the whole line readable in a saved log.
"""

UNATTRIBUTED = 'pytest exited 1 and its summary named no test the subset was handed'
"""Why a kill nobody can be attributed to is reported as a harness fault rather than as a kill.

A kill with an empty killer set is indistinguishable from a mutant every test tolerated, and `redundancy.py` would read it as one
more mutant that blocks nothing — proving a test redundant on the strength of a measurement that failed.
"""

UNCOLLECTABLE = 'the mutant stopped a test module being collected, so pytest exited on arguments that no longer resolve'
"""Why a killer-recording run reads some of exit 4 as a kill, where the scoring run never does.

A mutation to a module constant can break import — `'darwin'` -> `'darwin-mutant'` in `coordinates.py` makes the catalog refuse
every manifest — and a subset naming node ids inside that module then names arguments pytest cannot resolve, which is a usage
error. The suite noticed the bug in the loudest way available to it, and the summary says which file, so the tests the subset
holds there are the killers.

**The attribution is what decides it, which is what keeps the original guard intact.** A genuine usage error — the `--timeout`
flag that is not installed, and made the first prototype report a perfect score — produces no summary at all, so there are no
killers and the result stays a harness fault. Only exit 4 that names files the subset holds becomes a kill.
"""


def say(line: str) -> None:
    """Progress, flushed.

    A run takes minutes and stdout is block-buffered the moment it is redirected to a file, so an unflushed `print` leaves a live run
    looking hung until it finishes.
    """
    print(line, flush=True)


def repo_root() -> Path:
    found = Path(__file__).resolve().parents[2]
    if all((found / marker).exists() for marker in MARKERS):
        return found
    raise RuntimeError(f'{found} does not look like the dotfiles checkout')


@dataclasses.dataclass(frozen=True)
class Plan:
    """Everything the harness needs that is not a target, so its own tests can drive it against a toy tree."""

    repo: Path
    source_root: Path
    cache_dir: Path
    pytest_prefix: tuple[str, ...] = PYTEST_PREFIX
    context_args: tuple[str, ...] = ()
    jobs: int = 4
    trees: tuple[str, ...] = ('src', 'tests')
    record_killers: bool = False
    """Whether a killed mutant carries the tests that killed it.

    Off by default because it costs the `-x` saving on every kill: the subset has to run to the end before the summary can name
    more than the first failure. `redundancy.py` is what turns it on, and it is the only thing that reads the field.
    """


@dataclasses.dataclass(frozen=True)
class Planned:
    """One site, its bucket and the tests that execute its line."""

    relative: str
    site: planter.Site
    verdict: classify.Verdict
    tests: tuple[str, ...]


def plan_target(relative: str, source: str, path: Path, contexts: subset.Contexts) -> list[Planned]:
    """Every site in a target, classified and given its subset, before anything runs."""
    tree = ast.parse(source)
    verdicts = classify.annotate(tree, path)
    found: list[Planned] = []
    for site, (held, _, _, _) in zip(planter.sites(tree), planter.mutable(tree), strict=True):
        verdict = verdicts.get(id(held.node), classify.DEFAULT)
        found.append(Planned(relative, site, verdict, contexts.for_line(relative, site.lineno)))
    return found


def explain(path: Path, repo: Path) -> list[Planned]:
    """Every site with its bucket and the rule that assigned it, and no pytest anywhere near it.

    An empty context map, because the audit question is what the classifier decided and that needs no measurement at all.
    """
    relative = str(path.resolve().relative_to(repo.resolve()))
    return plan_target(relative, path.read_text(), path, subset.Contexts(tests=(), lines={}))


def outcome_for(code: int | None) -> tuple[str, str]:
    """pytest's exit code as a verdict about the mutant, and a reason where it is not one."""
    if code is None:
        return score.TIMED_OUT, 'no result before the timeout'
    if code == 0:
        return score.SURVIVED, ''
    if code == 1:
        return score.KILLED, ''
    if code == 5:
        return score.HARNESS_ERROR, 'pytest collected nothing: the subset named tests that do not exist'
    if code in (2, 3, 4):
        return score.HARNESS_ERROR, f'pytest exited {code}: interrupted, internal error or usage error'
    return score.HARNESS_ERROR, f'pytest exited {code}'


def killers_in(output: str, tests: Sequence[str]) -> tuple[str, ...]:
    """Which of the tests pytest was handed appear in its short summary as a failure or an error.

    Matched against the subset rather than parsed out of the line. A node id and the message after it are separated by ` - `, which
    a parametrised id is free to contain, and `tests/x.py::test_a` is a prefix of `tests/x.py::test_ab` — so the id is recognised by
    equality against something already known rather than cut out of prose.
    """
    reported = [line[len(word) :] for line in output.splitlines() for word in ('FAILED ', 'ERROR ') if line.startswith(word)]
    found = {test for test in tests for line in reported if line == test or line.startswith(f'{test} ')}
    # A collection error names the file rather than a node, and a file that cannot be collected runs none of its tests — so every
    # test the subset holds in it failed, which is what the mutant did to them.
    uncollected = {line.split(' ')[0] for line in reported if '::' not in line.split(' ')[0]}
    return tuple(sorted(found | {test for test in tests if test.split('::')[0] in uncollected}))


def vanished_in(output: str, tests: Sequence[str]) -> tuple[str, ...]:
    """Which of the subset's node ids the mutant made unresolvable.

    A mutation to a value a test is parametrised over renames the case: `'apt'` -> `'apt-mutant'` turns
    `test_every_package_manager_names_an_installer_family[apt]` into a node id nothing answers to, pytest exits 4 having run
    nothing, and the whole subset comes back unmeasured over one renamed argument. Naming them lets the mutant be re-run against
    everyone still addressable, so the loss is the handful of tests whose identity moved rather than the module.
    """
    named = [match.group(1) for line in output.splitlines() if (match := NOT_FOUND.match(line))]
    return tuple(sorted({test for test in tests for absolute in named if absolute.endswith(test)}))


def _pytest(
    plan: Plan, shadow: Path, tests: Sequence[str], *, stop_early: bool, timeout: float, basetemp: Path, summary: bool = False
) -> tuple[int | None, float, str]:
    argv = [
        *plan.pytest_prefix,
        *QUIET,
        f'--basetemp={basetemp}',
        *(('-x',) if stop_early else ()),
        *(SUMMARY if summary else ()),
        *tests,
    ]
    environment = dict(os.environ, PYTHONPATH=subset.pythonpath(shadow, plan.source_root), PYTHONDONTWRITEBYTECODE=NO_BYTECODE)
    if summary:
        environment['COLUMNS'] = SUMMARY_WIDTH
    began = time.perf_counter()
    with subprocess.Popen(
        argv, cwd=plan.repo, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True
    ) as process:
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.communicate()
            return None, time.perf_counter() - began, ''
    return process.returncode, time.perf_counter() - began, output or ''


class Workers:
    """One copy of the source tree per worker, handed out and handed back.

    A copy per worker rather than per mutant: copying `src/` costs more than most mutant runs, and a worker only ever holds one
    mutant at a time.
    """

    def __init__(self, plan: Plan, scratch: Path) -> None:
        self.available: queue.Queue[tuple[Path, Path]] = queue.Queue()
        for index in range(plan.jobs):
            room = scratch / f'worker-{index}'
            shutil.copytree(plan.source_root, room / plan.source_root.name, ignore=shutil.ignore_patterns('__pycache__'))
            (room / 'basetemp').mkdir(parents=True, exist_ok=True)
            self.available.put((room / plan.source_root.name, room / 'basetemp'))

    def take(self) -> tuple[Path, Path]:
        return self.available.get()

    def give_back(self, room: tuple[Path, Path]) -> None:
        self.available.put(room)


def _write_into(shadow: Path, source_root: Path, relative: str, text: str) -> None:
    (shadow / Path(relative).relative_to(source_root.name)).write_text(text)


def control(plan: Plan, shadow: Path, basetemp: Path, relative: str, source: str, tests: Sequence[str]) -> float:
    """The round trip, unmutated, against the union of every subset. Returns how long it took."""
    _write_into(shadow, plan.source_root, relative, planter.round_trip(source))
    code, seconds, output = _pytest(plan, shadow, tests, stop_early=False, timeout=1800.0, basetemp=basetemp)
    if code != 0:
        raise RuntimeError(f'the control run exited {code}, so no mutant can be attributed to its own bug\n{output[-2000:]}')
    return seconds


def _execute(plan: Plan, workers: Workers, sources: dict[str, str], planned: Planned, timeout: float) -> score.SiteResult:
    shadow, basetemp = workers.take()
    try:
        text = planter.plant(sources[planned.relative], planned.site.index)
    except SyntaxError as unparseable:
        workers.give_back((shadow, basetemp))
        return _result(planned, score.SKIPPED, detail=f'{planter.UNPARSEABLE}: {unparseable}')
    except Exception as broken:
        # A site the planner recognised and the planter cannot perform is a fault
        # in the harness, not a property of the source. Recorded as a skip it left
        # the denominator, so a half-added operator raised the score rather than
        # failing — which `Tally.scored` excluding SKIPPED is what makes silent.
        workers.give_back((shadow, basetemp))
        return _result(planned, score.HARNESS_ERROR, detail=f'planting failed: {type(broken).__name__}: {broken}')
    try:
        _write_into(shadow, plan.source_root, planned.relative, text)
        # Attribution needs every failure, and `-x` stops at the first one. A killer-recording run therefore forgoes the saving
        # rather than paying for a second pass, which also makes the survivor confirmation below unnecessary.
        early = not plan.record_killers
        code, seconds, output = _pytest(
            plan, shadow, planned.tests, stop_early=early, timeout=timeout, basetemp=basetemp, summary=plan.record_killers
        )
        status, detail = outcome_for(code)
        if status == score.SURVIVED and early:
            confirmed, _, _ = _pytest(plan, shadow, planned.tests, stop_early=False, timeout=timeout, basetemp=basetemp)
            if confirmed == 1:
                status, detail = score.KILLED, 'killed only without -x, which means the subset ordering hid it'
        subsetted: tuple[str, ...] = planned.tests
        unmeasured: tuple[str, ...] = ()
        if plan.record_killers and status == score.HARNESS_ERROR and (gone := vanished_in(output, planned.tests)):
            subsetted = tuple(name for name in planned.tests if name not in set(gone))
            if subsetted:
                unmeasured = gone
                code, seconds, output = _pytest(plan, shadow, subsetted, stop_early=False, timeout=timeout, basetemp=basetemp, summary=True)
                status, detail = outcome_for(code)
        killers = killers_in(output, subsetted) if plan.record_killers else ()
        if plan.record_killers and killers and status == score.HARNESS_ERROR:
            status, detail = score.KILLED, UNCOLLECTABLE
        elif plan.record_killers and status == score.KILLED and not killers:
            status, detail = score.HARNESS_ERROR, UNATTRIBUTED
        if status == score.HARNESS_ERROR:
            detail = f'{detail}\n{output[-400:]}'.strip()
        return _result(planned, status, seconds=seconds, detail=detail, killers=killers, unmeasured=unmeasured)
    finally:
        _write_into(shadow, plan.source_root, planned.relative, sources[planned.relative])
        workers.give_back((shadow, basetemp))


def _result(
    planned: Planned,
    status: str,
    seconds: float = 0.0,
    detail: str = '',
    killers: tuple[str, ...] = (),
    unmeasured: tuple[str, ...] = (),
) -> score.SiteResult:
    return score.SiteResult(
        file=planned.relative,
        line=planned.site.lineno,
        col=planned.site.col,
        kind=planned.site.kind,
        bucket=planned.verdict.bucket,
        rule=planned.verdict.rule,
        description=planned.site.description,
        status=status,
        tests=len(planned.tests),
        seconds=round(seconds, 2),
        detail=detail,
        killers=killers,
        unmeasured=unmeasured,
    )


def measure(
    plan: Plan,
    relatives: Sequence[str],
    contexts: subset.Contexts,
    *,
    limit: int | None = None,
    lines: dict[str, set[int]] | None = None,
    announce: Callable[[str], None] = say,
) -> score.Run:
    """The whole run: classify, answer the free question, plant the rest, and record what happened."""
    started = dt.datetime.now(dt.UTC)
    sources = {relative: (plan.repo / relative).read_text() for relative in relatives}
    everything: list[Planned] = []
    for relative in relatives:
        found = plan_target(relative, sources[relative], plan.repo / relative, contexts)
        if lines is not None:
            found = [item for item in found if item.site.lineno in lines.get(relative, set())]
        everything.extend(found)

    skipped = [_result(item, score.SKIPPED, detail=item.site.skipped) for item in everything if item.site.skipped]
    unreached = [_result(item, score.UNREACHED) for item in everything if not item.site.skipped and not item.tests]
    results: list[score.SiteResult] = [*skipped, *unreached]
    runnable = [item for item in everything if not item.site.skipped and item.tests]
    if limit is not None:
        runnable = runnable[:limit]

    announce(f'{len(everything)} sites: {len(runnable)} to plant, {len(unreached)} unreached, {len(skipped)} skipped')

    control_seconds = 0.0
    # Per target, because a mutant runs one target's subset. Summed, the budget
    # is as many times too long as there are targets — with `--all` that is 85,
    # so a flipped loop condition hangs for half an hour instead of being killed.
    per_target: dict[str, float] = {}
    if runnable:
        with tempfile.TemporaryDirectory(prefix='dotfiles-mutation-') as scratch:
            workers = Workers(plan, Path(scratch))
            shadow, basetemp = workers.take()
            for relative in relatives:
                # An empty subset would hand pytest no arguments at all, which is `testpaths` and therefore the whole suite.
                chosen = subset.union(item.tests for item in runnable if item.relative == relative)
                if not chosen:
                    continue
                taken = control(plan, shadow, basetemp, relative, sources[relative], chosen)
                per_target[relative] = max(TIMEOUT_FLOOR, taken * TIMEOUT_FACTOR)
                control_seconds += taken
                _write_into(shadow, plan.source_root, relative, sources[relative])
            workers.give_back((shadow, basetemp))
            longest = max(per_target.values(), default=TIMEOUT_FLOOR)
            announce(f'control passed in {control_seconds:.1f}s; longest per-mutant timeout {longest:.0f}s')

            done = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=plan.jobs) as pool:
                futures = {
                    pool.submit(_execute, plan, workers, sources, item, per_target.get(item.relative, TIMEOUT_FLOOR)): item
                    for item in runnable
                }
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    results.append(result)
                    done += 1
                    if result.status in (score.SURVIVED, score.HARNESS_ERROR, score.TIMED_OUT) or done % 10 == 0:
                        announce(f'  [{done}/{len(runnable)}] {result.status:9} {result.address} {result.description}')

    return score.Run(
        started_at=score.stamp(started),
        finished_at=score.stamp(dt.datetime.now(dt.UTC)),
        machine=_machine_id(),
        targets=tuple(relatives),
        results=tuple(sorted(results, key=lambda item: (item.file, item.line, item.col))),
        control_seconds=round(control_seconds, 2),
        timeout_seconds=round(max(per_target.values(), default=TIMEOUT_FLOOR), 1),
    )


def _machine_id() -> str:
    return paths.MACHINE_ID


def changed_lines(repo: Path, since: str) -> dict[str, set[int]]:
    """The lines a branch added or touched, from `git diff -U0`, so a diff run plants only what moved."""
    revision = subprocess.run(['git', 'rev-parse', '--verify', '--quiet', since], cwd=repo, capture_output=True, text=True)
    if revision.returncode != 0:
        raise RuntimeError(f'{since} does not resolve to a commit in {repo}')
    diff = subprocess.run(
        ['git', 'diff', '-U0', f'{since}...HEAD', '--', 'src/dotfiles'], cwd=repo, capture_output=True, text=True, check=True
    )
    found: dict[str, set[int]] = {}
    current = ''
    for line in diff.stdout.splitlines():
        if line.startswith('diff --git '):
            current = ''
        elif line.startswith('+++ b/'):
            current = line[len('+++ b/') :]
            found.setdefault(current, set())
        elif (hunk := HUNK.match(line)) and current:
            start, span = int(hunk.group(1)), int(hunk.group(2) or 1)
            found[current].update(range(start, start + span))
    return {path: lines for path, lines in found.items() if lines}


def gate_lines(run: score.Run, comparison: score.Comparison | None, *, floored: bool) -> list[str]:
    """What the gate refuses, in the words it refuses with."""
    said: list[str] = []
    counts = run.tally()
    if floored and counts.score < target_list.THRESHOLD:
        said.append(f'score {counts.score:.0%} is below the committed floor of {target_list.THRESHOLD:.0%}')
    if comparison is not None and comparison.new_prose_pinned:
        said.append(f'{len(comparison.new_prose_pinned)} rendering mutants died that did not before: a test is newly asserting on prose')
    return said


def gate(run: score.Run, comparison: score.Comparison | None, *, floored: bool) -> int:
    """The exit code, decided apart from the run that produced the numbers.

    Its own function because the composition around it — record, select this
    box's own history, compare, refuse — is the half `main` could not be tested
    through, and a whole mutation pass is too expensive to make a test of.

    **The floor applies only to the declared targets.** A module is added to
    `DEFAULT_TARGETS` after somebody has run it and looked at the survivors, so
    that first exploratory run is against a module nobody has aimed a test at
    and is below the floor by construction. Refusing there reports the command
    as failed for doing exactly what it is for.
    """
    return 1 if gate_lines(run, comparison, floored=floored) else 0


def main(argv: Sequence[str] | None = None) -> int:
    repo = repo_root()
    parser = argparse.ArgumentParser(description='Plant one bug at a time and count the ones nothing noticed')
    parser.add_argument('target', nargs='*', help='Repo-relative modules (default: tests/mutation/targets.py)')
    parser.add_argument(
        '--explain', type=Path, default=None, help='Print every site with its bucket and the rule that assigned it, and run nothing'
    )
    parser.add_argument('--since', default=None, help='Mutate only the lines this branch changed against a ref, e.g. origin/main')
    parser.add_argument('--all', action='store_true', help='Every module under src/dotfiles')
    parser.add_argument('--jobs', type=int, default=max(2, (os.cpu_count() or 4) - 1))
    parser.add_argument('--limit', type=int, default=None, help='Plant at most this many mutants, for a smoke run')
    parser.add_argument('--refresh-contexts', action='store_true', help='Re-measure which tests execute which line')
    parser.add_argument('--runs-dir', type=Path, default=None, help='Where to record this run (default: the XDG state directory)')
    parser.add_argument('--machine', default=None, help='Record and compare under this box name (default: this machine)')
    parsed = parser.parse_args(argv)

    if parsed.explain is not None:
        for item in explain(parsed.explain if parsed.explain.is_absolute() else repo / parsed.explain, repo):
            reason = f' skipped:{item.site.skipped}' if item.site.skipped else ''
            where = f'{item.relative}:{item.site.lineno}:{item.site.col}'
            print(f'{where}  {item.site.kind:18} {item.verdict.bucket:9} {item.verdict.rule:22} {item.site.description}{reason}')
        return 0

    # The context pass is one whole-suite run and is distributed; the mutant runs are not, because each is already one worker of many.
    plan = Plan(
        repo=repo,
        source_root=repo / 'src',
        cache_dir=subset.cache_for(paths.cache_home() / 'mutation', repo),
        jobs=parsed.jobs,
        context_args=('-n', str(max(2, (os.cpu_count() or 4) - 1))),
    )
    lines = changed_lines(repo, parsed.since) if parsed.since else None
    chosen = sorted(lines) if lines is not None else target_list.resolve(repo, parsed.target, parsed.all)
    if not chosen:
        say(f'nothing changed under src/dotfiles since {parsed.since}')
        return 0

    contexts, cached, measured = subset.load(
        repo,
        plan.source_root,
        plan.cache_dir,
        pytest_prefix=plan.pytest_prefix,
        pytest_args=plan.context_args,
        trees=plan.trees,
        refresh=parsed.refresh_contexts,
    )
    say(f'contexts {"measured" if measured else "cached"}: {cached}')

    run = measure(plan, chosen, contexts, limit=parsed.limit, lines=lines)
    directory = parsed.runs_dir if parsed.runs_dir is not None else paths.STATE_HOME / 'mutation-runs'
    machine = parsed.machine or paths.MACHINE_ID
    written = score.record(run, directory, machine)
    # This box's own history and nobody else's. The state directory is a
    # Syncthing folder, so the newest file in it is usually another machine's
    # measurement of another commit, and the gate below follows the comparison.
    earlier = [path for path in score.recorded(directory, machine) if path != written]
    comparison = score.compare(run, score.read(earlier[0])) if earlier else None
    for line in score.render(run, comparison):
        say(line)
    say(f'recorded {written}')

    for line in gate_lines(run, comparison, floored=chosen == target_list.DEFAULT_TARGETS):
        say(line)
    return gate(run, comparison, floored=chosen == target_list.DEFAULT_TARGETS)


if __name__ == '__main__':
    raise SystemExit(main())
