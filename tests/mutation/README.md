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
task test:mutation -- --explain src/dotfiles/commands/report.py
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
module it is in. `--explain <file>` prints every site with its bucket and
the rule that assigned it, so the classifier is audited rather than trusted.

**PROSE-PINNED is the fourth bucket and it is reported as loudly as the score.**
A rendering mutant that *died* means a test asserted on a sentence, which
`docs/development/testing.md` forbids. Without this counter the score could be
raised by writing exactly the assertions the standard bans, so it is compared
against the previous run rather than capped at a number.

It earned its place on the first run, by naming four dict keys the render-call
rule had swallowed inside a `table.add_row` comprehension — a machine contract,
found because a rendering mutant is not supposed to die.

## What makes a number believable

Five guards, each with its reasoning in the constant or function that enforces
it. This is the list; the arguments are one `rg` away and are not repeated here.

- **The working tree is never mutated** — a worker's copy, shadowed on
  `PYTHONPATH`. `subset.pythonpath`.
- **A control run passes before anything is planted**, or no kill is attributed.
  `run.control`.
- **A crash is not a kill.** Exit 1 alone kills. `run.outcome_for`.
- **The shadowed source never has bytecode**, because a `.pyc` is revalidated on
  whole-second mtimes. `run.NO_BYTECODE`.
- **Attribution comes from pytest, not from its output.** `mutation/failures.py`.

A mutant that outruns three times the control is a timeout rather than a
survivor, a site the harness declines to plant stays in the denominator with a
reason, and every survivor is confirmed a second time without `-x`.

## Test selection is derived, never declared

The suite runs once with `--cov-context=test`, and only a test that executes the
mutated line can kill the mutant — so that context set is the exact subset. The
alternative is a hand-written module-to-tests map, which rots from the first
renamed test onward.

`subset.py` holds the rest: how the map is cached and why it is regenerated
rather than repaired, and what happens to a line that only runs at import time.

## What is recorded, and what is committed

Each invocation writes a run to
`$XDG_STATE_HOME/dotfiles/mutation-runs/`, under a name carrying the machine —
that directory is a Syncthing folder, and `score.recorded` reads only this box's
own history back.

`targets.py` commits a **threshold** and never a score, and `targets.THRESHOLD`
says why a committed baseline always drifts instead of failing. Where the score
has *gone* is `score.compare`'s question.

## Proving a test redundant

The score answers whether the suite catches a bug. `redundancy.py` answers the
opposite question — whether anything would stop being caught if a given test
were deleted — and it answers it with a measurement rather than a judgment.

```sh
task test:redundancy -- tests/resolver/test_versions.py
task test:redundancy -- tests/install/test_release_assets.py --exclude tests/shell
task test:redundancy -- <test file> --json /tmp/verdicts.json
```

Two conditions decide it, and the second is the proof.

**A test that uniquely executes a line cannot be redundant.** Inverting the
context map gives, for every line, the tests that ran it; a test holding one
alone is proven necessary for the cost of reading a JSON file. It is a
necessary condition and never a sufficient one, because executing a line is not
constraining it — which is why the harness above exists at all.

**Everything else has to have every one of its kills shared.** A mutant carries
the tests that killed it, so a candidate whose every kill is also somebody
else's is subsumed and the tests subsuming it are named. One holding a kill
alone is load-bearing, and the mutant proving it is printed.

**A test that kills nothing is unprovable, not deletable.** The operators are
comparison swaps, boolean swaps, dropped negations and one-step tweaks to ints,
floats, bools and strings. An exception *type*, the order of two effects, a
subprocess argv, a resource being released, a timing bound and a file that must
*not* be written are all outside that set. Silence from the prover is silence,
and those come back in their own bucket with the reason attached.

### What a naive version would get wrong

Four, each argued where it is enforced.

- **A test reaching outside the scope is unprovable**, because a mutant nobody
  planted is a bug nobody looked for. `redundancy.within`.
- **Every site in scope is planted**, not only the ones coverage attributes to a
  test. `redundancy.footprints`.
- **A mutant that breaks import is attributed rather than discarded.** Reading it
  as a harness fault blocked 715 of 718 proofs on the first real run.
  `run.UNCOLLECTABLE`.
- **A mutant that renames a parametrised case blocks only the tests it renamed**,
  not the module. `run.vanished_in`.

**The room is screened against an unmutated copy first**, which drops a test that
fails whatever is planted and would otherwise subsume everybody.
`redundancy.screen`; `tests/test_dependencies.py` is the real case.

**The per-test list is not a list of deletions.** Two tests duplicating each
other are *both* redundant, and neither is once the other has gone, so the
report separately marks the subset that survives being deleted in one act.
`redundancy.prove`.

Omitting a test with `--exclude` costs proofs and cannot manufacture one, which
is what makes it safe to keep the slow tiers out of a run.

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
