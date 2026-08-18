"""Which tests can be deleted without the suite losing anything it could detect, proved rather than judged.

A test is deletable only when deleting it costs nothing measurable, and "it looks like a duplicate" is not a measurement. Two
conditions decide it, and the second is the proof:

**(a) it uniquely executes no line.** Inverting the `--cov-context=test` map gives, for every line, the tests that ran it. A test
holding a line alone cannot be redundant whatever else is true of it, so this settles a large fraction for the cost of reading a
JSON file. It is a necessary condition and never a sufficient one — executing a line is not constraining it, which is the whole
reason the mutation harness exists.

**(b) every bug it catches, something else catches too.** Each mutant is planted with the whole candidate set in the room and the
tests that failed are recorded, so a mutant carries the set of tests that killed it. A candidate whose every kill is shared is
subsumed; one holding even a single kill alone is load-bearing, and the mutant that proves it is named.

**Only a test inside the scope can be proved, and the scope is the union of the candidates' own footprints.** A mutant nobody
planted is a bug nobody looked for, so a test executing a module outside the scope has an unmeasured half and is reported as such
rather than as redundant. This is the condition that makes the answer small and the reason a run says what it scoped to.

**Every site in scope is planted, not only the ones coverage attributes.** `planter` addresses a site by the line of the node and
coverage records the line a statement starts on, so a constant on the third line of a call is executed and unattributed. Skipping
those would leave a bug unplanted, and an unplanted bug is exactly how a test that catches something reads as catching nothing.

**The per-test list is not a list of deletions.** Condition (b) is stated against the suite as it stands, so two tests that
duplicate each other are *both* redundant and neither is once the other has gone. `together` holds one representative of each such
cluster back, and what is left is deletable in one act — which is the question a person is actually asking.

**`--verify` carries the proof out rather than computing it.** The scope is planted a second time with the deletions taken out of
the room, and any mutant that lost its last killer is named. Bookkeeping over killer sets is only as good as the killer sets.

**Omitting a test from the run under-reports redundancy and never over-reports it.** A test absent from the room can only fail to
be somebody's subsumer, so `--exclude` trades proofs for time and cannot manufacture one. Everything the operators cannot express —
an exception type, an ordering, an argv, a file *not* written — is invisible here and is reported as unprovable rather than as
deletable.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import os
import tempfile
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Sequence
from pathlib import Path

from dotfiles import paths
from mutation import planter
from mutation import run as harness
from mutation import score
from mutation import subset

NO_KILLS = 'kills no mutant the operators can plant'
"""Why a test that killed nothing is unprovable rather than deletable.

The operator set is comparison swaps, boolean swaps, dropped negations and one-step tweaks to ints, floats, bools and strings.
An exception *type*, the order of two effects, a subprocess argv, a resource being cleaned up, a timing bound and a file that must
*not* be written are all outside it. A test pinning one of those kills nothing and is not thereby worthless — it is unmeasured.
"""

OUTSIDE_SCOPE = 'executes a module the run did not mutate'
BLOCKED = 'a mutant in a module it executes could not be attributed'

UNSHADOWABLE = 'fails against an unmutated copy of the source tree, so its failures say nothing about a mutant'
"""Why a test can be in the room on paper and not in it in fact.

The harness runs against a copy of `src/` on `PYTHONPATH`, and a test anchored on something beside the package — `pyproject.toml`,
a marker file, the checkout's own layout — does not find it there. Such a test fails against every mutant and against none, which
would make it everybody's subsumer. The room is screened against the unmutated copy first and anything red is dropped and named.
"""

UNADDRESSABLE = 'some mutant renamed its parametrised case, so at least one mutant never ran against it'
"""Why a test whose node id a mutant destroys cannot be proved, and why only that test is affected.

`'apt'` -> `'apt-mutant'` in `coordinates.py` renames every case parametrised over the package managers, so those node ids stop
existing and pytest exits having run nothing. The harness re-runs the mutant against everyone still addressable — so the rest of
the room is measured normally and only the handful whose identity moved comes back unmeasured. Blocking the module instead cost
715 of 718 proofs on the first real run, for six mutants.
"""

SCREEN_ATTEMPTS = 2
"""How many times the room is screened.

One pass names the tests that fail under shadowing and the second confirms that dropping them leaves the room green. A room still
red after that is a red suite, which is the harness's existing refusal rather than something to work around.
"""


@dataclasses.dataclass(frozen=True)
class Footprint:
    """What one test executes, and what it executes alone."""

    files: frozenset[str]
    unique: tuple[tuple[str, int], ...]


def footprints(contexts: subset.Contexts) -> dict[str, Footprint]:
    """Test to what it executes, inverted from the line-to-tests map.

    A line whose context tuple is empty ran at import and belongs to no test, so it contributes to nobody's footprint and can make
    nobody necessary — which is the honest reading of "pytest imported this during collection".
    """
    files: dict[int, set[str]] = collections.defaultdict(set)
    alone: dict[int, list[tuple[str, int]]] = collections.defaultdict(list)
    for relative, rows in contexts.lines.items():
        for lineno, found in rows.items():
            for index in found:
                files[index].add(relative)
            if len(found) == 1:
                alone[found[0]].append((relative, lineno))
    return {
        name: Footprint(files=frozenset(files.get(index, ())), unique=tuple(sorted(alone.get(index, ()))))
        for index, name in enumerate(contexts.tests)
    }


@dataclasses.dataclass(frozen=True)
class Survey:
    """The cheap condition, answered for the whole suite before anything is planted."""

    necessary: dict[str, tuple[str, int]]
    candidates: tuple[str, ...]

    @property
    def measured(self) -> int:
        return len(self.necessary) + len(self.candidates)


def survey(contexts: subset.Contexts) -> Survey:
    """Every test split into proven-necessary and still-a-candidate, with the line that proves each necessity."""
    found = footprints(contexts)
    necessary = {name: print_ for name, print_ in ((name, item.unique[0]) for name, item in found.items() if item.unique)}
    return Survey(necessary=necessary, candidates=tuple(sorted(name for name in found if name not in necessary)))


def selected(names: Iterable[str], prefixes: Sequence[str]) -> tuple[str, ...]:
    """The tests a caller named, by node id or by the file they live in."""
    return tuple(sorted(name for name in names if any(name == prefix or name.startswith(prefix) for prefix in prefixes)))


def scope_of(found: dict[str, Footprint], tests: Iterable[str]) -> tuple[str, ...]:
    """Every module the given tests execute — what has to be mutated for their proof to be complete."""
    modules: set[str] = set()
    for name in tests:
        modules |= found[name].files
    return tuple(sorted(modules))


def within(found: dict[str, Footprint], candidates: Iterable[str], modules: Iterable[str]) -> tuple[str, ...]:
    """Candidates whose whole footprint the scope covers, which is who the run can conclude about."""
    scope = frozenset(modules)
    return tuple(sorted(name for name in candidates if found[name].files and found[name].files <= scope))


def forced_contexts(modules: Sequence[str], tests: Sequence[str], repo: Path) -> subset.Contexts:
    """A context map that puts the whole run set in the room for every line of every module in scope.

    Not the measured subset, deliberately. A mutation to a module constant changes behaviour for a test that never executes a line
    of that module — coverage files import-time lines under no test at all — so selecting by the measured map would leave a real
    kill unobserved and a test looking emptier than it is. Running everybody against everything costs one subset run per mutant and
    removes the whole class.
    """
    indexes = tuple(range(len(tests)))
    lines = {module: dict.fromkeys(range(1, len((repo / module).read_text().splitlines()) + 2), indexes) for module in modules}
    return subset.Contexts(tests=tuple(tests), lines=lines)


def screen(plan: harness.Plan, room: Sequence[str], scratch: Path, scope: Sequence[str] = ()) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The room as it actually behaves against an unmutated copy, and whoever had to be dropped to get there.

    Run before anything is planted, for the same reason the harness runs a control: a failure that is already there is a failure
    every mutant inherits, and one test failing everywhere is one test subsuming everybody.
    """
    workers = harness.Workers(dataclasses.replace(plan, jobs=1), scratch)
    shadow, basetemp = workers.take()
    # The same text every mutant runs against. `ast.unparse` drops comments and
    # requotes every string, so a test sensitive to either passed the screen and
    # then aborted the whole run at the control — arriving as a harness error
    # with no test named, which is exactly what the screen exists to prevent.
    for relative in scope:
        source = (plan.repo / relative).read_text()
        harness.write_into(shadow, plan.source_root, relative, planter.round_trip(source))
    kept: list[str] = list(room)
    dropped: list[str] = []
    for _ in range(SCREEN_ATTEMPTS):
        # An empty list is not an empty run: pytest given no arguments falls back to `testpaths` and screens the whole suite.
        if not kept:
            raise RuntimeError(f'screening dropped all {len(dropped)} tests in the room, so there is nothing left to prove with')
        code, _, output = harness.run_pytest(
            plan, shadow, kept, stop_early=False, timeout=harness.CONTROL_TIMEOUT, basetemp=basetemp, summary=True
        )
        if code == 0:
            return tuple(kept), tuple(dropped)
        failing = harness.killers_in(output, kept)
        if code != 1 or not failing:
            raise RuntimeError(f'screening the room exited {code} and named {len(failing)} tests\n{output[-2000:]}')
        dropped.extend(failing)
        kept = [name for name in kept if name not in set(failing)]
    raise RuntimeError(f'the room is still red after dropping {len(dropped)} tests, so the suite is red rather than the harness')


@dataclasses.dataclass(frozen=True)
class Mutant:
    """One planted bug and who noticed it."""

    address: str
    description: str
    killers: frozenset[str]


def mutants(run: score.Run) -> tuple[tuple[Mutant, ...], tuple[str, ...]]:
    """The attributable kills, and the reasons the rest cannot be used.

    A timed-out mutant and a harness error are both kills nobody can be attributed, and treating either as killed-by-nobody or as
    killed-by-everybody makes a test look more redundant than it is. They come back as blockers instead.
    """
    found: list[Mutant] = []
    blocked: set[str] = set()
    seen: dict[tuple[str, int, int, str], int] = {}
    for result in run.results:
        if result.status in (score.TIMED_OUT, score.HARNESS_ERROR):
            blocked.add(result.file)
            continue
        if result.status != score.KILLED:
            continue
        key = (result.file, result.line, result.col, result.description)
        if key in seen:
            # Two mutants sharing an address would merge into one killer set, which unions their killers and weakens every proof
            # that rests on either. Refuse the file rather than quietly averaging them.
            blocked.add(result.file)
            continue
        seen[key] = len(found)
        found.append(Mutant(address=result.address, description=result.description, killers=frozenset(result.killers)))
    return tuple(found), tuple(sorted(blocked))


def unmeasured_by(run: score.Run) -> frozenset[str]:
    """Tests some mutant left unaddressable, gathered across every result rather than only the kills.

    A survivor carries them too, and it is the survivor that would go unnoticed: a mutant nothing killed blocks nobody, so a test
    whose node id it renamed would be judged on a measurement that never included it.
    """
    return frozenset(name for result in run.results for name in result.unmeasured)


@dataclasses.dataclass(frozen=True)
class Proof:
    """One candidate, everything it killed, and what covers it."""

    test: str
    killed: int
    subsumed_by: tuple[str, ...]
    sole_owner: tuple[str, str] | None = None
    together: bool = False
    """Whether this one survives being deleted alongside every other test marked the same way.

    Condition (b) is stated against the suite as it stands, so a pair that duplicates each other proves *both* redundant and
    neither is once the other has gone. Read on its own that is a report which cannot be acted on: deleting the whole list would
    take the last killer of a mutant with it. This flag is the answer to the question actually being asked — one representative of
    each such cluster is held back, and everything left is deletable in one go.
    """


@dataclasses.dataclass(frozen=True)
class Verification:
    """The proof carried out rather than computed: the same scope, planted again, with the deletions actually taken out.

    Bookkeeping over killer sets is only as good as the killer sets. This replays the whole scope against a room that no longer
    holds the tests being deleted and asks whether any mutant lost its last killer, which is the claim itself and not a proxy for
    it. `lost` empty is the verdict; anything in it falsifies the proof for that mutant.
    """

    deleted: int
    killed_before: int
    killed_after: int
    lost: tuple[tuple[str, str], ...]

    @property
    def holds(self) -> bool:
        return not self.lost


@dataclasses.dataclass(frozen=True)
class Verdicts:
    """What a run concluded, split by what it is entitled to say."""

    scope: tuple[str, ...]
    run_set: tuple[str, ...]
    planted: int
    attributable: int
    redundant: tuple[Proof, ...]
    load_bearing: tuple[Proof, ...]
    unprovable: tuple[tuple[str, str], ...]
    dropped: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    verified: Verification | None = None

    @property
    def deletable(self) -> tuple[str, ...]:
        return tuple(proof.test for proof in self.redundant if proof.together)


def together(planted: Sequence[Mutant], pool: Iterable[str], room: Iterable[str]) -> frozenset[str]:
    """The largest part of the redundant pool that can be deleted in one act rather than one at a time.

    Everything outside the pool stays, so it covers whatever it covers for free. What is left is the mutants only the pool
    catches, and one member of the pool is held back for each until they are covered — greedily, largest first, which is the
    standard cover and is near-optimal rather than optimal. Held back means kept, so the answer errs toward keeping a test.
    """
    pool = set(pool)
    keepers = set(room) - pool
    uncovered = [mutant for mutant in planted if mutant.killers and not mutant.killers & keepers]
    while uncovered:
        counted = collections.Counter(name for mutant in uncovered for name in mutant.killers & pool)
        if not counted:
            break
        best = min(counted.items(), key=lambda item: (-item[1], item[0]))[0]
        keepers.add(best)
        uncovered = [mutant for mutant in uncovered if best not in mutant.killers]
    return frozenset(pool - keepers)


def _cover(killed: Sequence[Mutant], test: str) -> tuple[str, ...]:
    """The other tests that between them catch everything this one catches.

    The intersection first, because a test in it subsumes this one on its own and that is the strongest thing the data supports.
    Where no single test covers the whole kill set, a greedy cover names the smallest group that does — still a proof, just a
    joint one.
    """
    others = [set(mutant.killers) - {test} for mutant in killed]
    always = set.intersection(*others) if others else set()
    if always:
        return tuple(sorted(always))
    remaining = list(others)
    chosen: list[str] = []
    while remaining:
        counted = collections.Counter(name for group in remaining for name in group)
        best = min(counted.items(), key=lambda item: (-item[1], item[0]))[0]
        chosen.append(best)
        remaining = [group for group in remaining if best not in group]
    return tuple(chosen)


def prove(
    run: score.Run,
    proving: Sequence[str],
    footprint: dict[str, Footprint],
    scope: Sequence[str],
    run_set: Sequence[str] = (),
    dropped: Sequence[str] = (),
) -> Verdicts:
    """Condition (b), for every candidate the run is entitled to conclude about."""
    planted, blocked = mutants(run)
    covered = frozenset(scope)
    unshadowable = frozenset(dropped)
    unaddressable = unmeasured_by(run)
    by_test: dict[str, list[Mutant]] = collections.defaultdict(list)
    for mutant in planted:
        for name in mutant.killers:
            by_test[name].append(mutant)

    redundant: list[Proof] = []
    load_bearing: list[Proof] = []
    unprovable: list[tuple[str, str]] = []
    for test in sorted(proving):
        files = footprint[test].files
        if test in unshadowable:
            unprovable.append((test, UNSHADOWABLE))
            continue
        if test in unaddressable:
            unprovable.append((test, UNADDRESSABLE))
            continue
        if not files <= covered:
            unprovable.append((test, f'{OUTSIDE_SCOPE}: {", ".join(sorted(files - covered))}'))
            continue
        if files & frozenset(blocked):
            unprovable.append((test, f'{BLOCKED}: {", ".join(sorted(files & frozenset(blocked)))}'))
            continue
        killed = by_test.get(test, [])
        if not killed:
            unprovable.append((test, NO_KILLS))
            continue
        alone = next((mutant for mutant in killed if mutant.killers == {test}), None)
        if alone is not None:
            load_bearing.append(Proof(test=test, killed=len(killed), subsumed_by=(), sole_owner=(alone.address, alone.description)))
            continue
        redundant.append(Proof(test=test, killed=len(killed), subsumed_by=_cover(killed, test)))

    # Every test the run saw kill something is in the room whether or not the caller listed it, and leaving one out would hold a
    # pool member back to cover a mutant something else already covers.
    room = set(run_set) | set(proving) | {name for mutant in planted for name in mutant.killers}
    joint = together(planted, [proof.test for proof in redundant], room)
    redundant = [dataclasses.replace(proof, together=proof.test in joint) for proof in redundant]

    return Verdicts(
        scope=tuple(scope),
        run_set=tuple(sorted(set(run_set) | set(proving))),
        planted=len(run.results),
        attributable=len(planted),
        redundant=tuple(redundant),
        load_bearing=tuple(load_bearing),
        unprovable=tuple(unprovable),
        dropped=tuple(sorted(unshadowable)),
        blocked=tuple(blocked),
    )


def killed_keys(run: score.Run) -> set[tuple[str, str]]:
    return {(result.address, result.description) for result in run.results if result.status == score.KILLED}


def verify(
    plan: harness.Plan, scope: Sequence[str], run_set: Sequence[str], deleting: Sequence[str], before: score.Run, announce: Callable
) -> Verification:
    """Plant the scope a second time with the deletions taken out of the room, and name any mutant that lost its last killer."""
    kept = [name for name in run_set if name not in set(deleting)]
    announce(f'verifying: replanting {len(scope)} modules with {len(deleting)} tests deleted, {len(kept)} left in the room')
    after = harness.measure(plan, list(scope), forced_contexts(scope, kept, plan.repo), announce=announce)
    was, now = killed_keys(before), killed_keys(after)
    return Verification(deleted=len(deleting), killed_before=len(was), killed_after=len(now), lost=tuple(sorted(was - now)))


def render(found: Survey, verdicts: Verdicts) -> list[str]:
    """The report as lines, so a test asserts on the numbers and only a person reads the layout."""
    lines = [
        f'suite            : {found.measured} tests measured',
        f'NECESSARY        : {len(found.necessary)}   uniquely execute a line, so nothing can prove them redundant',
        f'candidates       : {len(found.candidates)}',
        f'scope            : {", ".join(verdicts.scope)}',
        f'mutants planted  : {verdicts.planted}   {verdicts.attributable} killed and attributable',
        f'blocked modules  : {len(verdicts.blocked)}   {", ".join(verdicts.blocked) or "none"}',
        f'run set          : {len(verdicts.run_set)} tests in the room for every mutant, {len(verdicts.dropped)} dropped as unshadowable',
        f'REDUNDANT        : {len(verdicts.redundant)}   every bug they catch, something else catches',
        f"  deletable together: {sum(1 for proof in verdicts.redundant if proof.together)}   the rest are each other's only cover",
        f'load-bearing     : {len(verdicts.load_bearing)}   hold a kill alone',
        f'unprovable       : {len(verdicts.unprovable)}',
    ]
    for proof in verdicts.redundant:
        mark = 'REDUNDANT' if proof.together else 'holds-back'
        lines.append(f'  {mark} {proof.test}  kills {proof.killed}, all of them also killed by {", ".join(proof.subsumed_by[:4])}')
    for proof in verdicts.load_bearing:
        owner = proof.sole_owner[0] if proof.sole_owner else ''
        detail = proof.sole_owner[1] if proof.sole_owner else ''
        lines.append(f'  keeps     {proof.test}  alone kills {owner}  {detail}')
    for test, reason in verdicts.unprovable:
        lines.append(f'  unprovable {test}  {reason}')
    if verdicts.verified is not None:
        checked = verdicts.verified
        verdict = 'HOLDS' if checked.holds else 'FALSIFIED'
        lines.append(f'verification     : {verdict}  {checked.killed_before} kills before, {checked.killed_after} after')
        lines.append(f'                   {checked.deleted} tests deleted, {len(checked.lost)} kills lost')
        for address, description in checked.lost:
            lines.append(f'  LOST      {address}  {description}')
    return lines


def as_payload(found: Survey, verdicts: Verdicts) -> dict:
    return {
        'measured': found.measured,
        'necessary': {name: [where[0], where[1]] for name, where in found.necessary.items()},
        'candidates': list(found.candidates),
        'scope': list(verdicts.scope),
        'run_set': list(verdicts.run_set),
        'planted': verdicts.planted,
        'attributable': verdicts.attributable,
        'redundant': [dataclasses.asdict(proof) for proof in verdicts.redundant],
        'load_bearing': [dataclasses.asdict(proof) for proof in verdicts.load_bearing],
        'unprovable': [list(row) for row in verdicts.unprovable],
        'dropped': list(verdicts.dropped),
        'blocked': list(verdicts.blocked),
        'deletable': list(verdicts.deletable),
        'verified': dataclasses.asdict(verdicts.verified) if verdicts.verified is not None else None,
    }


def measure(
    plan: harness.Plan,
    contexts: subset.Contexts,
    prefixes: Sequence[str],
    *,
    exclude: Sequence[str] = (),
    verified: bool = False,
    announce: Callable[[str], None] = harness.say,
) -> tuple[Survey, Verdicts]:
    """The whole thing: survey, scope, plant every site in scope with everybody watching, and prove."""
    found = survey(contexts)
    footprint = footprints(contexts)
    proving = selected(found.candidates, prefixes)
    if not proving:
        raise RuntimeError(f'nothing selected by {", ".join(prefixes)} is a candidate; every match uniquely executes a line')

    scope = scope_of(footprint, proving)
    room = [name for name in within(footprint, found.candidates, scope) if not any(name.startswith(drop) for drop in exclude)]
    announce(f'proving {len(proving)} candidates over {len(scope)} modules, with {len(set(room) | set(proving))} tests in the room')

    with tempfile.TemporaryDirectory(prefix='dotfiles-redundancy-') as scratch:
        run_set, dropped = screen(plan, sorted(set(room) | set(proving)), Path(scratch), scope)
    if dropped:
        announce(f'{len(dropped)} tests dropped: they fail against an unmutated copy of the tree')

    run = harness.measure(plan, list(scope), forced_contexts(scope, run_set, plan.repo), announce=announce)
    verdicts = prove(run, proving, footprint, scope, run_set, dropped)
    if verified and verdicts.deletable:
        verdicts = dataclasses.replace(verdicts, verified=verify(plan, scope, run_set, verdicts.deletable, run, announce))
    return found, verdicts


def main(argv: Sequence[str] | None = None) -> int:
    repo = harness.repo_root()
    parser = argparse.ArgumentParser(description='Prove which tests catch nothing another test does not also catch')
    parser.add_argument('prove', nargs='+', help='Test node ids, or the files they live in, to attempt to prove')
    parser.add_argument('--exclude', action='append', default=[], help='Keep these out of the room: fewer proofs, never a false one')
    parser.add_argument('--jobs', type=int, default=max(2, (os.cpu_count() or 4) - 1))
    parser.add_argument(
        '--verify', action='store_true', help='Plant the scope again with the deletions taken out, and name any kill that was lost'
    )
    parser.add_argument('--json', type=Path, default=None, help='Write the verdicts here as well as printing them')
    parser.add_argument('--refresh-contexts', action='store_true', help='Re-measure which tests execute which line')
    parsed = parser.parse_args(argv)

    plan = harness.Plan(
        repo=repo,
        source_root=repo / 'src',
        cache_dir=subset.cache_for(paths.cache_home() / 'mutation', repo),
        jobs=parsed.jobs,
        context_args=('-n', str(max(2, (os.cpu_count() or 4) - 1))),
        record_killers=True,
    )
    contexts, cached, measured = subset.load(
        repo,
        plan.source_root,
        plan.cache_dir,
        pytest_prefix=plan.pytest_prefix,
        pytest_args=plan.context_args,
        trees=plan.trees,
        refresh=parsed.refresh_contexts,
    )
    harness.say(f'contexts {"measured" if measured else "cached"}: {cached}')

    found, verdicts = measure(plan, contexts, parsed.prove, exclude=parsed.exclude, verified=parsed.verify)
    for line in render(found, verdicts):
        harness.say(line)
    if parsed.json is not None:
        parsed.json.write_text(json.dumps(as_payload(found, verdicts), indent=2) + '\n')
        harness.say(f'wrote {parsed.json}')
    return 1 if verdicts.verified is not None and not verdicts.verified.holds else 0


if __name__ == '__main__':
    raise SystemExit(main())
