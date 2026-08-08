# Dotfiles Testing

Organized test structure covering apps, libraries, and installation system.

## Structure

```text
tests/
├── apps/
│   └── all-apps.sh                      # Quick test of all user-facing apps
├── libraries/
│   ├── logging.sh                       # Test logging.sh library
│   ├── formatting.sh                    # Test formatting.sh library
│   └── error-handling.sh                # Test error-handling.sh library
└── install/
    ├── unit/                            # Unit tests for installer functions
    ├── integration/                     # Integration tests for components
    ├── e2e/                             # End-to-end installation tests
    ├── docker/                          # Docker-based tests
    ├── utils/                           # Validation and utility scripts
    └── helpers.sh                       # Shared test utilities
```

**Logic:**

- `tests/apps/` = Tests for user-facing applications
- `tests/libraries/` = Tests for shared shell libraries
- `tests/install/` = Tests for installation system (unit → integration → e2e → utils)

## Running Tests

### Quick App Test (Run Before Commit)

```bash
bash tests/apps/all-apps.sh
```

Tests all user-facing tools can be invoked:

- apps: notes, toolbox, theme-sync, menu
- shell libraries: logging.sh, formatting.sh, error-handling.sh
- platform-specific: ghostty-theme, _aws-profiles

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

Create or update tests in `tests/libraries/`:

```bash
#!/usr/bin/env bash
set -euo pipefail

source "$DOTFILES_DIR/configs/common/.local/shell/my-library.sh"
# Add tests...
```

### Installation Tests

- **Unit tests** (`tests/install/unit/`): Test individual functions
- **Integration tests** (`tests/install/integration/`): Test wrapper behavior
- **E2E tests** (`tests/e2e/`): Full installation in a container, per environment
- **Host E2E** (`tests/install/e2e/`): the cases a container cannot be

### Best Practices

- Keep app tests fast (< 10 seconds total)
- Only test non-interactive commands
- Test workflows, not implementation details
- Focus on what matters, not what changes
- Run `refcheck` before expensive e2e tests
