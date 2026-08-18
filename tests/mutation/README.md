# Mutation testing

Coverage says a line ran. This says whether anything asserted on what it did.

The harness plants one bug at a time — a flipped comparison, an incremented
integer, a string with a marker appended — runs only the tests that execute that
line, and counts the bugs nobody noticed. A survivor is a line the suite executes
and no test constrains.

It exists because `dotfiles report upload` shipped broken while the suite held
3468 tests at 87.77% coverage. `report._send` had zero executed statements and a
file named for the verb held four tests, all of them exercising one
pure leaf helper. Coverage cannot see that, and a mutation run would have
answered it in seconds without planting anything: with no test executing a line
of that function, every site in it comes back UNREACHED.

## Running it

```sh
task test:mutation                      # the modules targets.py names
task test:mutation -- src/dotfiles/x.py # one module
task test:mutation:diff                 # only the lines this branch changed
task test:mutation:report               # the newest run against the one before
uv run python tests/mutation/run.py --explain src/dotfiles/commands/report.py
```

The first run of a session measures which tests execute which line, which is one
whole-suite pass under coverage. Every run after it reads that from the cache
until the source or test trees change.

## What the four buckets mean

**UNREACHED is the headline and it is free.** A line whose coverage-context set
is empty has no test that executes it, so nothing can kill a mutation there. It
is reported without spawning a single pytest, and it is strictly worse than a
survivor: a survivor at least has a test in the room.

**SURVIVED** is a line the tests execute and nothing asserts on. That is the gap
worth writing a test for, and `score.py` names each one by file and line.

**Rendering mutants are planted and then excluded from the score.** A string is
rendering when only a person reads it and logic when a machine does, and
`classify.py` decides that by AST position rather than by content — what call it
is an argument to, what keyword it is bound to, whether it is a docstring, which
module it is in. `run.py --explain <file>` prints every site with its bucket and
the rule that assigned it, so the classifier is audited rather than trusted.

**PROSE-PINNED is the fourth bucket and it is reported as loudly as the score.**
A rendering mutant that *died* means a test asserted on a sentence, which
`docs/development/testing.md` forbids — "assert on the finding, never on the
sentence describing it". Without this counter the score could be raised by
writing exactly the assertions the standard bans.

It is compared against the previous run rather than capped at a number. An
absolute ceiling would be a committed score under another name: set to whatever
the suite happens to do today and edited upward the first time it fails. The
direction cannot be gamed, so the run fails on a rendering mutant that dies where
one did not die before.

The counter earns its place immediately. On the first `report.py` run it named
four dict keys inside `table.add_row(*(str(row[key]) for key in (...)))` — a
machine contract the render-call rule had swallowed, found because a rendering
mutant is not supposed to die. `classify._children` now takes what a
comprehension *reads* as logic wherever it sits.

## What makes a number believable

**The working tree is never mutated.** `configs/`, `shell/` and `apps/` are
symlinked live into `$HOME` here and the CLI is installed editable against
`src/`, so a mutation written in place is a mutated `dotfiles` deployed on the
machine — and an interrupted run never puts it back. Each worker gets its own
copy of `src/` in a temporary directory and shadows the checkout with
`PYTHONPATH=<copy>/src`, which precedes the editable install's `.pth` entry on
`sys.path`. The checkout is only ever read.

**A control run happens before anything is planted.** The chosen subset runs
against an unmutated round trip of the target through `ast.unparse`, and it has
to pass. Without it a bad pytest flag makes every mutant look killed: the first
prototype passed `--timeout`, which is not installed here, so pytest exited 4 on
every mutant and reported a perfect score that was pure artifact.

**A crash is not a kill.** Exit 1 means tests failed and is the only exit code
that kills. 2, 3, 4 and 5 are interrupted, internal error, usage error and
nothing collected — harness faults, reported separately and never scored.

**The shadowed source never has bytecode.** A `.pyc` is revalidated against the
source's size and its mtime *in whole seconds*, and mutants land on the same
path in rapid succession — so two of equal length inside one second are
indistinguishable to that check and the second imports the first one's
bytecode. Both directions were measured on the toy in `test_redundancy.py`:
`LIMIT = 3` -> `4` is the same length as the original and survived without ever
being compiled, and `'under'` -> `'under-mutant'` is the same length as the
`'over'` mutant that ran before it in the same worker, so it was reported killed
by a test that never reaches the branch it changed. `PYTHONDONTWRITEBYTECODE`
alone is half a fix, because an existing `.pyc` is still read, so the worker's
copy also declines to bring `__pycache__` with it. Measured at no cost: only the
copied `src/` recompiles and the checkout's `tests/` cache is untouched.

Three smaller things follow from the same instinct. A mutant that produces no
result inside three times the measured control duration is reported as a timeout
rather than as a survivor, because a flipped loop condition hangs rather than
passing. A site the harness declines to plant is still counted and given a
reason, so nothing leaves the denominator silently. And every survivor gets a
second run without `-x`, which confirms it against the whole subset instead of
against whichever test happened to be first.

## Test selection is derived, never declared

The suite runs once with `--cov-context=test`, and `coverage.CoverageData` then
says which tests executed which line. Only a test that executes the mutated line
can kill the mutant, so that context set is the exact subset. A hand-written
module-to-tests map would be a second keying of the same fact and would rot from
the first renamed test onward.

The map is cached under `$XDG_CACHE_HOME/dotfiles/mutation/`, keyed on a digest
of the source and test trees, and regenerated rather than repaired — a stale
context map is indistinguishable from a correct one until it produces a wrong
kill.

A line that only runs at import time carries no test name, because pytest imports
during collection. Those get the union of every test that executes any line of
the file, which over-reports survivors rather than inventing kills.

## What is recorded, and what is committed

Each invocation writes a run to
`$XDG_STATE_HOME/dotfiles/mutation-runs/<timestamp>-<machine-id>.json`. The
machine suffix is there for the reason `paths.machine_id` gives: state is a
Syncthing folder, and four boxes writing `<timestamp>.json` would overwrite one
another.

`targets.py` commits a **threshold** and never a score. A committed baseline is
edited to match whatever the suite currently does, so it drifts upward on a good
day and downward on a bad one and never fails. Where the score has *gone* is
`score.compare`'s question, answered against the previous recorded run and
naming each survivor that was not there before.

## Proving a test redundant

The score answers whether the suite catches a bug. `redundancy.py` answers the
opposite question — whether anything would stop being caught if a given test
were deleted — and it answers it with a measurement rather than a judgement.

```sh
task test:redundancy -- tests/resolver/test_versions.py
task test:redundancy -- tests/install/test_release_assets.py --exclude tests/shell
uv run python tests/mutation/redundancy.py <test file> --json /tmp/verdicts.json
```

Two conditions decide it, and the second is the proof.

**A test that uniquely executes a line cannot be redundant.** Inverting the
context map gives, for every line, the tests that ran it; a test holding one
alone is proven necessary for the cost of reading a JSON file. It is a
necessary condition and never a sufficient one, because executing a line is not
constraining it — which is why the harness above exists at all.

**Everything else has to have every one of its kills shared.** Each mutant is
planted with the whole candidate set in the room and `-rfE` names the tests that
failed, so a mutant carries its killer set. A candidate whose every kill is also
somebody else's is subsumed, and the tests that subsume it are named. One
holding a single kill alone is load-bearing, and the mutant proving it is
printed.

**A test that kills nothing is unprovable, not deletable.** The operators are
comparison swaps, boolean swaps, dropped negations and one-step tweaks to ints,
floats, bools and strings. An exception *type*, the order of two effects, a
subprocess argv, a resource being released, a timing bound and a file that must
*not* be written are all outside that set. Silence from the prover is silence,
and those come back in their own bucket with the reason attached.

### What a naive version would get wrong

**The scope is the union of the candidates' own footprints, and a test reaching
outside it is unprovable.** A mutant nobody planted is a bug nobody looked for.
This is what keeps a run honest and what makes it small enough to finish.

**Every site in scope is planted, not only the ones coverage attributes.**
`planter` addresses a site by the line of its node and coverage records the line
a statement starts on, so a constant on the third line of a call is executed and
unattributed. Selecting by the measured map would leave those unplanted.

**A mutant that breaks import is attributed rather than discarded.** Changing
`'darwin'` in `coordinates.py` makes the catalog refuse every manifest, so a
test module importing it cannot be collected and the node ids named on the
command line stop resolving — pytest exits 4, which the scoring run reads as a
harness fault. That reading blocked 715 of 718 proofs on the first real run.
A killer-recording run passes `--continue-on-collection-errors`, reads the file
named in the summary, and attributes the kill to the tests the subset holds
there. The original guard survives intact because attribution is what decides
it: a genuine usage error prints no summary, so there are no killers and the
result stays a harness fault.

**A mutant that renames a parametrised case blocks only the tests it renamed.**
`'apt'` -> `'apt-mutant'` in `coordinates.py` turns
`test_every_package_manager_names_an_installer_family[apt]` into a node id
nothing answers to, and pytest exits 4 having run none of the subset. Reading
that as a blocked module cost 715 of 718 proofs for six mutants. The harness
names the ids that vanished, re-runs the mutant against everyone still
addressable, and records the rest as unmeasured — so those tests come back
unprovable and nobody else is affected.

**The room is screened against an unmutated copy first.** A test anchored on
something beside the package — `pyproject.toml`, the checkout's layout — does
not find it on the shadowed `PYTHONPATH`, so it fails against every mutant and
against none, which would make it everybody's subsumer. Screening drops it and
names it. `tests/test_dependencies.py` is the real case.

**The per-test list is not a list of deletions.** Condition (b) is stated
against the suite as it stands, so two tests that duplicate each other are
*both* redundant and neither is once the other has gone. The report marks the
subset that survives being deleted in one act, holding one representative of
each such cluster back. `test_redundancy.py` measures both readings against the
toy: dropping the joint set leaves the kill count unchanged and dropping every
redundant test does not.

Omitting a test with `--exclude` costs proofs and cannot manufacture one — a
test absent from the room can only fail to be somebody's subsumer. That is what
makes it safe to keep the slow tiers out of a run.

## Adding to it

**A rendering position is a row in `POSITIONS`** in
`test_mutation_harness.py`, and a rule constant in `classify.py`. The default
direction is deliberate: everything unmatched is LOGIC, because a logic string
wrongly marked rendering vanishes from the score with nothing to notice it, while
a rendering string wrongly marked logic surfaces as a survivor a person corrects.

**A mutation operator is a branch in `planter._mutation` and a row in
`OPERATORS`.** Anything the harness will not plant is still enumerated, counted
and given a reason — the first prototype dropped strings of forty characters or
more without saying so, which silently excluded every long logic string.
