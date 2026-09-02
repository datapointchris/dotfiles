# Testing

Everything is pytest. There is one runner, and the tiers are defined by **what a
test may touch** rather than by how long it takes:

- **pure and host-tool** — runs on every commit. Reads `tmp_path`, runs real
  binaries, reaches no network.
- **`e2e`** — reaches the real network or the real `HOME`. Deselected unless
  `--e2e`.
- **`docker`** — installs a whole machine in a container. Deselected unless
  `--docker`.
- **`replants`** — the mutation harness's own tests that drive a real pytest
  against a real toy package. Deselected unless `--replants`.

`task --list-all` names the entry points. `tests/conftest.py` declares the three
opt-in tiers, and carries why the deselection lives there rather than in
`addopts`.

**Three axes place a test, and none of them competes with the others.** A tier
says what a test is *allowed* to touch, and is a marker. A level says how much
machine has to *exist* before it can run, and is read off the fixture the test
asks for. A door says which surface the test comes in by.

The container tier therefore divides into levels — an empty container, one
section over a base, a machine already installed, a machine installed now.
`--level` reaches one without paying for the rest, and `tests/e2e/levels.py`
holds what each costs and what it can answer.

The door is the membership rule for `tests/matrix/`. That package builds one
synthetic machine out of files and drives the real CLI against it in process,
with nothing in `src/dotfiles/` stubbed. The rule, and the four things that send
a test to `tests/resources/` instead, are the module docstring in
`tests/matrix/__init__.py`. `tests/matrix/harness.py` carries why the two
import-time seams need rebinding rather than an environment variable.

## Tests are flat functions, grouped by a section comment

The great majority of test files already are, so this is the house style rather
than a new rule — `rg -c '^class Test' tests/` counts the exceptions against
`fd -e py 'test_' tests/`. A file groups with a `# ────` band carrying the
section's prose, and `-k` selects on the name, which is why every test name here
is a declarative sentence rather than a noun.

**A guarantee shared by a whole group is an autouse fixture, not a class-level
marker.** That is the one thing a class carried that a section comment cannot,
and `tests/install/test_bundle_build.py` is the worked case: six classes each
carrying `@pytest.mark.usefixtures('declaration')` became one autouse fixture
saying the same thing once.

## Coverage says a line ran; the mutation harness says whether anything asserted on it

`dotfiles report upload` shipped selecting run records by the wrong identifier
while the suite held 3468 tests at 87.77% line coverage. `report._send` had zero
executed statements and a file named for the verb held four tests, every one of
them exercising a pure leaf helper. Coverage cannot report that, because a
module counts covered the moment it is imported.

`tests/mutation/` answers the question coverage cannot. It plants one bug at a
time, runs only the tests that execute that line, and counts the bugs nobody
noticed. A line no test executes comes back UNREACHED without a pytest being
spawned at all, which is what would have answered the defect above in seconds.

```sh
task test:mutation                       # the modules targets.py names
task test:mutation:diff                  # only the lines this branch changed
task test:redundancy -- <test file>      # prove a test catches nothing another does
```

`tests/mutation/README.md` is the reference — the four buckets, what makes a
number believable, and how a deletion is proved rather than argued. It is not in
this nav because it sits beside the code it describes and is read there.

**It is wired into nothing.** Neither pre-commit nor CI runs it, because a slow
integration hook does not belong in pre-commit — a full
run is tens of minutes. `task test:mutation:diff` over one branch's changed lines
is the shape that could be, and `targets.THRESHOLD` is the floor waiting for
something to enforce it.

## Drive real shells from pytest, not from a second framework

`tests/shell/` drives real `bash`, real `zsh` and a real `tmux` from pytest. bats
is the rejected runner — a second test framework, with its own custom installer
and its own assertion library, to run assertions pytest expresses directly. It
stays declared in `install/packages.yml` because other shell repos in the
portfolio use it, and both the generated pre-commit hook and the generated CI
step are guarded to pass a repo holding no `.bats` file.

Three properties are the reasons to keep this shape:

**stdout and stderr stay apart.** bats merges them into one `$output`, so an
assertion passes whichever stream the code chose. That is how logging.sh's stderr
routing regressed unnoticed. Porting the update suite found the same class of
thing immediately — the dry-run announcement is on stderr and the resolved item
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

**Tables are tables.** bats spawns a process per `@test`, which pushes a file
toward one `@test` holding fifteen assertions — so a failure names the group
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

Assert on the finding, never on the sentence describing it. The wording is free
to change and the finding is not, so an assertion over printed output through a
subprocess breaks on a reworded message.

The package resource needs the same isolation for *installed-ness*, which is
ambient rather than on disk. `tests/resources/test_packages.py` injects it
through the knobs the code already honours — `PATH` and `UV_TOOL_DIR` — with
`/usr/bin:/bin` kept behind the fake bin dir so the fixture's own helpers still
resolve.

**Nothing in `src/dotfiles/` is monkeypatched.** The injection points are real
environment knobs. Exactly two bug classes survive that boundary — a real tool
differing from its stub, and the bootstrap — and those are what the container
tier is for.

## Never compare an `fd` count against a count from anything else

Never compare a count from `fd` against a count from anything else. `fd` respects
`.gitignore` and `tar` does not, so a backup test asserting the archive held as
many files as the source directory compared 409 against 2929 and read as a broken
backup. Pass `--no-ignore --hidden` when the count has to mean "every file on
disk".

## An install is only proven from nothing

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

## What the container rig must not do

**The probes are derived from the plan and only the blocklist is declared.** The
offline and restricted environments resolve `wsl-work-workstation` through
`network.derive`, so a tool added to that manifest is rehearsed without anyone
regenerating a fixture. `BLOCKED_HOSTS` in `tests/e2e/harness.py` names what the
rehearsed firewall takes down, which is why `github.com` stays *reachable*:
blackholing it takes every clone-based installer with it, and the three asset CDNs
are how a refused release download is expressed as a host rule instead. Probes
replay the derived request, user agent included — a synthesized one reported
crates.io blocked on what was really a 403.

No measurement of a real network is committed here, and
`tests/install/test_network.py` fails if one appears. A recorded verdict is one
machine's answer on one day; the declaration is what every machine resolves.

**The container is authenticated from the host's `gh`.** Sixty anonymous API calls
an hour are shared with the host's public IP and one full install spends most of
them, so an unauthenticated second run inside the hour is indistinguishable from a
broken installer. The token is passed by name so it stays out of an argument list,
`pytest_report_header` prints whether the run got a credential, and a check at the
cheapest tier asserts the *container's* own rate limit is 5000 rather than 60 —
the header reads the host and proves only that a credential was found.

**The base image lives in docker's store; the ledger lives in the cache dir.** The
image is the artifact, and `docker save`/`load` of 14 GB duplicates storage docker
already manages. What docker cannot say is which plan produced a tag, so
`$XDG_CACHE_HOME/dotfiles/e2e-bases.json` says it: tagged by a digest of the
*resolved plan* at or below the stage plus the source image id, so a comment edit
does not rebuild and a dropped package does. Rebuilt after two weeks regardless,
because the digest cannot see which versions the distro shipped.

**The harness never reads the product's environment.** It mounted
`paths.REPO_ROOT`, which honours `$DOTFILES_DIR`, so every run launched from a
worktree installed `main`'s code while reporting on the branch. Anchor on marker
files, not on the product's own configuration and not on `parents[n]`.

**Production code never asks whether it is under test.** A resource probes the
real precondition rather than reading `DOTFILES_DOCKER_TEST`, which is a harness
telling production code it is being tested. `bootstrap.SYSTEM_BUS` and
`evidence.AMD_KFD` carry the reasoning at the constants themselves, including
what was tried instead.

## Verification asks the machine, never the product's own evidence

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
[Tool Availability](../reference/platforms/tools.md).
