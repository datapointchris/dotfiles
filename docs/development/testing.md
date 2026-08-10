# Testing

Everything is pytest. There is one runner, and the tiers are defined by **what a
test may touch** rather than by how long it takes:

- **pure and host-tool** — runs on every commit. Reads `tmp_path`, runs real
  binaries, reaches no network.
- **`e2e`** — reaches the real network or the real `HOME`. Deselected unless
  `--e2e`.
- **`docker`** — installs a whole machine in a container. Deselected unless
  `--docker`.

`task --list-all` names the entry points; `tests/conftest.py` is where the two
opt-in tiers are declared, and `.pre-commit-config.yaml` is the full hook wiring.

**Levels are a second axis, and not a competing one.** A tier says what a test is
*allowed* to touch and is a marker; a level says how much machine has to *exist*
before it can run, and is read off the fixture the test asks for. So the whole
container tier divides into levels — an empty container, one section over a base,
a machine already installed, a machine installed now — and `--level` is how to
reach one without also paying for the rest. `tests/e2e/levels.py` holds what each
costs and what it can answer.

The deselection lives in `tests/conftest.py` rather than as `-m 'not e2e'` in
`addopts`, because forge owns `addopts` — a deselection written there is erased
by the next `sync-pyproject` run.

## The shell is still the subject

`tests/shell/` drives real `bash`, real `zsh` and a real `tmux` from pytest. The
runner changed; the thing under test did not. bats was that runner until the
Python conversion, and it was a second test framework — installed from its own
custom installer, with its own assertion library, its own CI job and its own
`task` verbs — to run assertions pytest can express directly.

Three things got better in the move, and they are the reasons to keep the shape:

**stdout and stderr stay apart.** bats merged them into one `$output`, so an
assertion passed whichever stream the code chose. That is how logging.sh's stderr
routing regressed unnoticed, and porting the update suite immediately found the
same class of thing — the dry-run announcement is on stderr and the resolved item
list is on stdout, which no bats assertion could have distinguished.

**A skipped interpreter is a case, not a silence.** zsh is a parameter, so a
machine without it reports the skip per test instead of quietly covering half of
one. That is the right answer on a workstation and the wrong one on a runner,
where a missing interpreter would leave the tier reporting green having run a
third of itself — so `--require-interpreters` inverts it into a refusal to start,
and CI passes the flag. The set it enforces is read back off the collected tests,
so a test that starts driving a third interpreter is covered without the workflow
changing. `tests/shell/test_interpreter_gate.py` asserts both readings by running
pytest against a PATH with the interpreters taken off it.

**Tables are tables.** bats spawns a process per `@test`, which pushed every file
toward one `@test` holding fifteen assertions — so a failure named the group
rather than the property. Parametrized cases cost nothing and name themselves.

`tests/shell/shells.py` is the whole harness: it runs a snippet in a fresh shell
with one library sourced and hands back stdout, stderr and the exit code, kept
apart. Fresh every time, because these libraries resolve things at *source* time
— the colour gate most obviously — so a reused interpreter would answer with
whatever the first test decided.

## Logic belongs in Python, and moving it is the cheaper fix

The offline bundler was shell until the cost showed: verifying a checksum parser
written in awk meant a fixture tree and a subprocess per case, while the same
parser as a function is called directly with a string and returns a value. That
conversion traded seventeen shell tests needing a subprocess for thirty-one
Python ones needing nothing.

When a shell script grows a parser, a cache, or a return value, that is the
signal — see
[app installation patterns](../learnings/app-installation-patterns.md) for where
each language belongs. What stays shell is what is genuinely shell: an installer
that drives a package manager, a library sourced into an interactive shell.

## Every test builds its own tree

A declaration-validation test writes a `packages.yml` and manifest set into
`tmp_path`, calls `validate.declaration(root)` and asserts on the findings it
returns — one test per check. Reading the actual repo would make each test a
description of today's package list: failing on the next unrelated addition, and
passing for reasons that have nothing to do with the check.

They asserted on fragments of printed output through a subprocess until the
findings became values. Assert on the finding, never on the sentence describing
it: the wording is free to change and the finding is not.

The package resource needs the same isolation for *installed-ness*, which is
ambient rather than on disk. `tests/resources/test_packages.py` injects it
through the knobs the code already honours — `PATH` and `UV_TOOL_DIR` — with
`/usr/bin:/bin` kept behind the fake bin dir so the fixture's own helpers still
resolve.

**Nothing in `src/dotfiles/` is monkeypatched.** The injection points are real
knobs: `HOME`, `PATH`, `XDG_STATE_HOME`, `UV_TOOL_DIR`. Exactly two bug classes
survive that boundary — a real tool differing from its stub, and the bootstrap —
and those are what the container tier is for.

## Counting files in an assertion

Never compare a count from `fd` against a count from anything else. `fd` respects
`.gitignore` and `tar` does not, so a backup test asserting the archive held as
many files as the source directory compared 409 against 2929 and read as a broken
backup. Pass `--no-ignore --hidden` when the count has to mean "every file on
disk".

## Installation testing

Docker for Linux, a fresh user account for macOS. Both give a clean environment
that can be destroyed and rebuilt, which is the only way to know an install works
from nothing rather than from a machine that already had half of it.

macOS gets a user account rather than a VM because macOS VMs are slow and awkward
enough that they stop being used, and a fresh account reproduces everything the
install touches outside `/usr/local`.

The container environments are one pytest rig with the environments as
parameters: `tests/e2e/harness.py` holds the definitions, each pointed at the
matching machine manifest. `eza -1 tests/install/e2e/` is what a container cannot
be — a real macOS account, or the current machine.

## Verification

On a real machine, ask the machine:

```sh
dotfiles plan     # what apply would still change
dotfiles check    # what is wrong, which a machine merely behind is not
```

A tool with a second copy nothing declares is one of `check`'s findings. That is
the failure PATH order hides — a stale copy in `/usr/bin` shadowed by a current
one in `~/.local/bin` works fine until the order changes — and it lives there
rather than in a test because it is a question about a machine somebody is using.

A copy is only a finding when nothing explains it. Two explanations are read off
the declaration: the location the item's own evidence names, and a copy the OS
package manager attributes to a package this manifest declares. The second is not
a nicety — fnm owns `node` and `npm` while pacman's `nodejs` ships `/usr/bin/node`
underneath it, which is the bootstrap the declaration asks for, and reporting that
pair was two of the nine findings the shell script produced on a healthy machine.

**In the e2e tier, verification is deliberately a second opinion.**
`tests/e2e/test_verification.py` asks the container in shell and never runs
`dotfiles check`: a verification reading the product's own evidence agrees with
the installer exactly when they are wrong together. It takes the *expectations*
from `resolve.resolve`, so a tool added or removed changes what is verified with
no list to update, and every declared item is its own test node — a missing tool
is a named red line rather than a return code with a transcript attached.

**A refusal is not a missing tool.** Each node reads this machine's own pinned run
record and skips anything that run reached and deliberately wrote nothing for — an
offline install has no go.dev to fetch a toolchain from, because its bundle stages
the Go and Rust *tools* prebuilt instead, so it converges with four items refused.
Counting those as failures described seven broken tools on a machine built exactly
as intended, and a verdict nobody believes is one nobody reads. Every way of
failing to read that record leaves the set empty and requires everything, because
a record it cannot read has to make the check stricter.

Document platform quirks found this way in
[Platform Differences](../reference/platforms/differences.md).
