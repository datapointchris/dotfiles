# Testing

The dotfiles repository has three layers of testing:

1. **BATS unit + integration tests** — shell library and installer coverage
2. **pytest** — the Python side: the packages CLI, the manifest parser, the offline bundler
3. **Installation e2e tests** — Docker-based platform walkthroughs of `install.sh`

Fast tests run on every commit via pre-commit hooks: pytest, and BATS **unit** tests (gated to install-layer changes). The slower Docker-backed layers — BATS **integration** and the installation e2e tests — are run on demand (`task test:integration`, `task test`) rather than on every commit, to keep commits fast. See `.pre-commit-config.yaml` for the full wiring.

## BATS (Bash Tests)

Shell library and installer tests using [BATS (Bash Automated Testing System)](https://github.com/bats-core/bats-core).

### Running Tests

```sh
# All BATS tests (unit + integration)
task test

# Unit tests only — libraries + installer functions, no Docker, no network
task test:unit

# Integration tests — Docker-backed, will auto-build the base image on first run
task test:integration

# Watch mode (requires entr)
task test:watch
```

### Test Location

Tests are organized under `tests/`:

- `tests/libraries/` — Tests for shared shell libraries
- `tests/install/unit/` — Unit tests for installer functions (no Docker, no network). Run with `task test:unit`.
- `tests/install/integration/` — Integration tests. Requires Docker + the prebuilt base image `dotfiles-test-base:ubuntu-24.04`. If the image is missing, `tests/install/docker/build-base.sh` is invoked automatically before tests run — if the build itself fails, the test run fails loudly rather than silently skipping.

### Counting files in an assertion

Never compare a count from `fd` against a count from anything else. `fd`
respects `.gitignore` and `tar` does not, so a backup test asserting the archive
held as many files as the source directory compared 409 against 2929 and read as
a broken backup. Pass `--no-ignore --hidden` when the count has to mean "every
file on disk".

## pytest (Python Tests)

Python-side coverage for `install/parse_packages.py`, `apps/common/packages`
(including `packages verify`), and `install/offline/create_bundle.py`:

```sh
uv run pytest tests/
```

**Logic belongs here rather than in BATS, and moving it is the cheaper fix.**
The offline bundler was shell until the cost showed: verifying a checksum parser
written in awk meant a fixture tree and a subprocess per case, while the same
parser as a function is called directly with a string and returns a value. The
conversion traded seventeen BATS tests needing a shell for thirty-one pytest
ones needing nothing, and they finish in under a second. When a shell script
grows a parser, a cache, or a return value, that is the signal — see
[app installation patterns](../learnings/app-installation-patterns.md) for
where each language belongs.

**Every test builds its own synthetic tree and never reads the real repo.** A
`packages verify` test writes a `packages.yml` and manifest set into `tmp_path`,
runs `packages verify --root <tmp_path>` as a subprocess, and asserts on
stdout/stderr and exit code — one test per check. Reading the actual repo would
make each test a description of today's package list, failing on the next
unrelated addition and passing for reasons that have nothing to do with the
check.

`packages missing` needs the same isolation for *installed-ness*, which is
ambient. Those tests run with `PATH` pointed at a temp directory holding only
`uv` — needed for the script's own shebang — plus whatever binaries that
specific test decides exist.

## packages verify

`apps/common/packages verify` enforces drift-freeness across packages.yml, the machine manifests, and the installer script directories. See [Package Management — Drift Detection](../architecture/package-management.md#drift-detection) for the check catalog. Runs on every commit; also runnable manually:

```sh
apps/common/packages verify
```

### Writing Tests

Tests use BATS with assertion helpers, loaded through `tests/helpers/bats-libs`:

```bash
#!/usr/bin/env bats

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

@test "installer checks for dependencies" {
  run bash "$INSTALLER_SCRIPT"
  assert_output --partial "Checking dependencies"
}
```

Load the helper, never bats-support and bats-assert directly. Their own loaders
resolve each of their fifteen source paths with a `$(dirname)` subprocess, and
bats runs every `@test` in a fresh process, so that cost is paid per test — it
was more than half the suite's wall time. The helper sources the same files
using parameter expansion, and exports `DOTFILES_DIR` from the same expansion.

The expansion is depth-independent, so the line is identical in every test file
regardless of where it sits under `tests/`.

Each test being its own process also means the suite scales across cores:
`install/ops/test.sh` passes `--jobs` when GNU parallel is available, which is
what `dotfiles test` and `task test:*` both run.

See [Bash Testing Frameworks](https://docs.ichrisbirch.com/terminal/bash-testing-frameworks/) for detailed BATS usage.

## Installation Testing

Docker for Linux, a fresh user account for macOS. Both give a clean environment
that can be destroyed and rebuilt, which is the only way to know an install
works from nothing rather than from a machine that already had half of it.

macOS gets a user account rather than a VM because macOS VMs are slow and
awkward enough that they stop being used, and a fresh account reproduces
everything the install touches outside `/usr/local`.

The scripts are `eza -1 tests/install/e2e/`, one per environment, each pointed
at the matching machine manifest. Docker Desktop is the only prerequisite:

```sh
brew install --cask docker
```

## Verification

```sh
bash tests/install/verification/verify-installed-packages.sh
bash tests/install/verification/detect-installed-duplicates.sh
```

The first checks that everything the manifest declared is present *and in the
expected prefix*; the second catches the same tool installed twice by different
methods, which is the failure that PATH order hides — a stale copy in
`/usr/bin` shadowed by a current one in `~/.local/bin` works fine until the
order changes.

The e2e scripts run both automatically. Document platform quirks found this way
in [Platform Differences](../reference/platforms/differences.md).
