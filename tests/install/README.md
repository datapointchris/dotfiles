# Installation Tests

Tests for dotfiles installation and deployment infrastructure.

## Directory Structure

```text
tests/install/
├── e2e/           End-to-end tests (full install.sh runs)
├── integration/   Integration tests (multi-component)
├── unit/          Unit tests (isolated functions)
├── docker/        Docker-based tests
├── utils/         Validation and utility scripts
└── helpers.sh     Shared test utilities
```

## E2E Tests

Full installation tests in clean environments.

- `test-install-wsl-network-restricted.sh` - WSL installation with network restrictions

**Usage:**

```bash
bash tests/install/e2e/test-install-wsl-network-restricted.sh
bash tests/install/e2e/test-install-wsl-network-restricted.sh --keep  # Keep container for debugging
```

## Integration Tests

Test specific installation phases or components together.

- `test-cargo-phase-blocking.sh` - Cargo phase with network restrictions
- `test-cargo-binstall-blocking.sh` - Cargo binstall blocking
- `test-nvm-failure-handling.sh` - NVM failure handling

## Unit Tests

Test isolated installer functions and components.

See `unit/` directory for individual test files testing `run_installer`, failure capture, stderr handling, etc.

## Validation Utilities

Post-install verification scripts.

- `utils/verify-installed-packages.sh` - Check all expected packages installed
- `utils/detect-installed-duplicates.sh` - Find duplicate tool installations
- `utils/verify-docker-container-network-restrictions.sh` - Verify network restrictions in Docker

**Usage:**

```bash
bash tests/install/utils/verify-installed-packages.sh
bash tests/install/utils/detect-installed-duplicates.sh
bash tests/install/utils/verify-docker-container-network-restrictions.sh <container-name>
```

## Running Tests

```bash
# Unit tests (fast, isolated)
bash tests/install/unit/test-run-installer-output-visibility.sh

# Integration tests
bash tests/install/integration/test-cargo-phase-blocking.sh

# E2E tests (slow, requires Docker)
bash tests/install/e2e/test-install-wsl-network-restricted.sh

# Post-install validation
bash tests/install/utils/verify-installed-packages.sh
```
