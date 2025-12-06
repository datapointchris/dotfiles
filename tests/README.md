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

- apps: notes, sess, toolbox, theme-sync, menu
- shell libraries: logging.sh, formatting.sh, error-handling.sh
- platform-specific: ghostty-theme, aws-profiles

**Speed:** Fast (~5 seconds)

### Installation Tests

#### Validate File References

```bash
bash tests/install/utils/verify-file-references.sh
```

Checks for broken file references before running expensive tests.

#### Validate Installation

```bash
bash tests/install/utils/verify-installed-packages.sh
bash tests/install/utils/detect-installed-duplicates.sh
```

#### Full E2E Installation Test

```bash
bash tests/install/e2e/wsl-docker.sh
bash tests/install/e2e/arch-docker.sh
bash tests/install/e2e/macos-temp-user.sh
bash tests/install/e2e/current-user.sh
```

**Speed:** Slow (5-15 minutes, requires Docker)

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

source "$DOTFILES_DIR/platforms/common/.local/shell/my-library.sh"
# Add tests...
```

### Installation Tests

- **Unit tests** (`tests/install/unit/`): Test individual functions
- **Integration tests** (`tests/install/integration/`): Test wrapper behavior
- **E2E tests** (`tests/install/e2e/`): Full installation in clean environment

### Best Practices

- Keep app tests fast (< 10 seconds total)
- Only test non-interactive commands
- Test workflows, not implementation details
- Focus on what matters, not what changes
- Run `verify-file-references.sh` before expensive e2e tests
