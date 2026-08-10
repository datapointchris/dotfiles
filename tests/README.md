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
bash tests/install/verification/verify-installed-packages.sh
bash tests/install/verification/detect-installed-duplicates.sh
```

#### Container installs

`tests/e2e/` is one rig with the environments as parameters, and it comes in four
tiers. **Reach for the cheapest one that can answer the question** — a full
install takes half an hour and answers nothing about the harness, or about an
assertion, that a cheaper tier cannot answer in seconds.

```bash
uv run pytest tests/e2e/test_harness.py             # 0.1s, no Docker
uv run pytest tests/e2e/test_container.py --docker  # ~25s per environment
uv run pytest tests/e2e --docker --installed        # seconds: assert, do not install
uv run pytest tests/e2e --docker                    # the full installs
```

`test_harness.py` is everything decidable without starting anything: the network
derivation, the environment definitions, the exec script. `test_container.py`
starts a container and copies the repo but installs nothing — the tier where the
rig's own failures live, and where a wrong PATH or a firewall that does not match
the measurement shows up. `test_machine.py` needs an installed machine.

`--installed` reads the exit status and log the last install left in the
container instead of producing them again, so changing an assertion costs seconds
rather than a second half hour. It re-copies the repo first, so the verification
scripts and the editable CLI are current; what is stale is exactly the install
log and its status. Install for real when `install.sh`, a phase script or a
package list changes — use `--installed` for everything else.

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
quietly selects all four. The environments are independent containers, so four
shells running one `--environment` each finish in the time of the slowest rather
than the sum. `--keep` leaves containers up; `--reuse` and `--installed` imply it.

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
