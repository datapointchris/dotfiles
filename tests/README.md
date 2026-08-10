# Dotfiles Testing

One runner. `eza -1 tests/` lists the directories; each is named for what it
covers, and the two that are not obvious:

- `tests/shell/` — the shell code, driven from pytest through a real `bash`,
  `zsh` or `tmux`. The runner is Python; the subject is not.
- `tests/e2e/` — one rig that installs whole machines in containers, with the
  environments as parameters.

`docs/development/testing.md` is why it is arranged this way.

## Running Tests

### Quick App Test (Run Before Commit)

```bash
bash tests/apps/all-apps.sh
```

Asserts every user-facing tool can be invoked on *this* machine, against the
deployed tree rather than the repo — `rg test_cmd tests/apps/all-apps.sh` is the
list. That is what makes it different from everything else here: it is the only
check that reads what `dotfiles apply` actually put on disk.

**Speed:** Fast (~5 seconds)

### Installation Tests

#### Validate File References

```bash
refcheck
```

Resolves every `source` and `bash` target in the repo, including the ones behind
`$DOTFILES_DIR`, and checks them against disk. Seconds, and worth running before
anything expensive.

#### Validate Installation

```bash
dotfiles plan     # what apply would still change on this machine
dotfiles check    # what is wrong, including a tool with a copy nothing declares
```

#### Container installs

`tests/e2e/` is one rig with the environments as parameters, arranged as a ladder
of levels. **Reach for the cheapest rung that can answer the question** — a full
install takes half an hour and answers nothing about the harness, or about an
assertion, that a cheaper rung cannot answer in seconds.

A level is named for how much machine has to exist, so picking one needs no
lookup. `tests/e2e/levels.py` is what each costs and what it can answer, and
`task --list-all | rg test:` is the roster — neither is restated here, because a
copy of either is the thing that goes stale.

```bash
task test:matrix              # every level over every environment, and it costs an hour
task test:matrix:quick        # the same without the rung measured in hours
task test:<level>             # one rung, all environments
task test:level -- --level <level> --environment wsl   # one cell
```

`--level` also works on `pytest` directly, and carries the modes it implies:
`--docker`, and `--installed` for the rung that asserts against an install rather
than performing one. Those two rungs run the same tests, and that flag is the
whole difference between twenty seconds and twenty-four minutes.

**The matrix runs one pytest process per cell**, each to its own log under
`$XDG_STATE_HOME/dotfiles/test-runs/` beside a record of what every cell cost. It
stops at the first level that fails, because the rung above costs more to say the
same thing, and it builds any missing image once before fanning out — two
environments share one image, and the fixture that builds a missing image itself
raced two `docker build` processes into a single tag the first time this fanned
out. `task test:report` reads those records; `--stats` is the one worth having,
because a cell that is usually thirty seconds and took nine minutes is the
interesting kind of green. The history is Syncthing-shared, so each record names
its machine and checkout and `--stats --machine <name>` narrows it.

`task test:logs -- <cell>` follows a cell that is running now, and
`task test:containers` says what exists and what each container is for: a name
carries its purpose (`machine`, `empty`, `section`, `base-build`) and, in a
worktree, that worktree — so two checkouts cannot claim one container.

The section-over-base level is the rung between "nothing installed" and "everything installed",
and it exists because there was no way to ask about *one installer* without
building a whole machine. It starts a throwaway container from a **base image** —
the environment installed `--through system_upgrade`, so packages and app stores
and nothing above them — and runs `dotfiles packages apply --source <section>`
over it.

A set never declares its prerequisites. `registry.ToolchainProvider.needed_by`
already says the Rust toolchain is wanted when `cargo_packages` resolve, so
`--source cargo_packages` on a bare base brings rustup with it. The base supplies
only the part no section declares: an OS with a package manager, curl, git and
unzip.

The base is tagged `dotfiles-e2e-base:<digest>`, where the digest covers the
resolved plan at or below that stage plus the source image's id — so a comment
edit in `packages.yml` does not rebuild multiple GB and a manifest that drops a
package does. The digest is the whole tag, so two environments differing only in
how the install is *run* against the base share one image: `offline` and
`restricted` declare the same manifest over the same source image, and naming
each in its own tag built and stored that base twice. It is rebuilt anyway after
two weeks, because the digest cannot see which versions the distro shipped.
`$XDG_CACHE_HOME/dotfiles/e2e-bases.json` records what each tag holds — the
source image and manifest that made it, never which environment asked first —
and docker's store is the storage.

`test_harness.py` is everything decidable without starting anything: the network
derivation, the environment definitions, the exec script. `test_container.py`
starts a container and copies the repo but installs nothing — the rung where the
rig's own failures live, and where a wrong PATH or a firewall that does not match
the measurement shows up. `test_machine.py` needs an installed machine.

Which rung a test sits at is read off the fixture it asks for — `over_base`,
`machine`, `container` — never a list of module names, so a test moved between
files lands where its fixtures put it and a new file needs nothing declared.

`--installed` reads the exit status, log and run record the last install pinned in
the container instead of producing them again, so changing an assertion costs
seconds rather than a second half hour. It re-copies the repo first, so the
verification scripts and the editable CLI are current; what is stale is exactly
those three artifacts. Install for real when `install.sh`, a provider or a package
list changes — use `--installed` for everything else.

The record is pinned rather than read from `dotfiles/latest` because *something
always applies afterwards* — the next test in the file is the second-apply
idempotence check — so `latest` describes that run while the status beside it still
describes the install, and comparing the two was comparing two different runs.

**A container install borrows the host's `gh` credential.** GitHub allows 60
anonymous API calls an hour *per public IP*, the container shares the host's, and
one full install spends most of them — so an unauthenticated second run inside
the hour answers "did not answer with a release" for every release tool, which
reads exactly like a broken installer. The harness passes `GITHUB_TOKEN` through
when `gh auth token` answers, and the pytest header says which run you got:

```text
github: authenticated
github: ANONYMOUS — 60 API calls/hour, release failures are suspect (gh auth login)
```

Add `--environment <name>` for one — never `-k`, which matches test names too and
quietly selects all four. `--keep` leaves containers up; `--reuse` and
`--installed` imply it.

**Two full installs at a time is free on this box; four is not.** Measured
2026-08-10 on the Arch workstation: archlinux and wsl installed concurrently in
962s wall clock against 1604s serial — exactly the slower of the pair, so no
contention penalty, and no movement on disk. Each level declares its own width in
`levels.py` and `--concurrency` overrides it. The reason the width is a property
of the rung rather than of the box is that four containers merely existing is
free and four installing a machine each is not.

`eza -1 tests/install/e2e/` is what is left: the cases that cannot be a container
at all, needing a real macOS account, the current machine, or a real firewall.

## Adding Tests

### App Tests

Add to `tests/apps/all-apps.sh`:

```bash
test_cmd "my-app help" "my-app --help"
```

### Library Tests

Create or update tests in `tests/shell/`. `shells.py` runs a snippet in a fresh
shell with one library sourced and hands back stdout, stderr and the exit code
kept apart:

```python
from shells import source


def test_a_library_does_the_thing() -> None:
    assert source('my-library.sh', 'my_function arg').stdout == 'expected\n'
```

### Installation Tests

- **Python** (`tests/install/`): the resolver, the bundler, the run records
- **Shell** (`tests/shell/`): the install scripts that are still shell
- **E2E** (`tests/e2e/`): a full installation in a container, per environment
- **Host E2E** (`tests/install/e2e/`): the cases a container cannot be

### Best Practices

- Keep app tests fast (< 10 seconds total)
- Only test non-interactive commands
- Test workflows, not implementation details
- Focus on what matters, not what changes
- Run `refcheck` before expensive e2e tests
