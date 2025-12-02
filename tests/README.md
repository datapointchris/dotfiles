# Dotfiles Testing

Simple test organization - tests live near what they test.

## Structure

```text
tests/
└── test-all-apps.sh           # Quick test of all user-facing apps

management/tests/
├── test-install-wsl-docker.sh           # E2E: WSL installation
├── test-install-arch-docker.sh          # E2E: Arch installation
├── test-install-macos-temp-user.sh      # E2E: macOS installation
├── test-install-current-user-current-platform.sh
├── verify-installed-packages.sh         # Validation
├── detect-installed-duplicates.sh       # Validation
└── helpers.sh                           # Shared utilities
```

**Logic:**

- `tests/` = Tests for user-facing apps (notes, sess, toolbox, etc.)
- `management/tests/` = Tests for installation/deployment infrastructure

## Running Tests

### Quick App Test (Run Before Commit)

```bash
bash tests/test-all-apps.sh
```

Tests all user-facing tools can be invoked:

- apps: notes, sess, toolbox, theme-sync, menu
- shell libraries: logging.sh, formatting.sh, error-handling.sh
- platform-specific: ghostty-theme, aws-profiles

**Speed:** Fast (~5 seconds)

### Management Tests

#### Validate Installation

```bash
bash management/tests/verify-installed-packages.sh
bash management/tests/detect-installed-duplicates.sh
```

#### Full E2E Installation Test

```bash
bash management/tests/test-install-wsl-docker.sh
bash management/tests/test-install-arch-docker.sh
```

**Speed:** Slow (5-15 minutes, requires Docker)

## Adding Tests

### App Tests

Add to `tests/test-all-apps.sh`:

```bash
test_cmd "my-app help" "my-app --help"
```

### Workflow Tests

Create `tests/my-workflow_test.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Testing my workflow..."
# Test how multiple tools work together
```

### Best Practices

- Keep app tests fast (< 10 seconds total)
- Only test non-interactive commands
- Test workflows, not implementation details
- Focus on what matters, not what changes
- Don't add tests to apps still evolving
