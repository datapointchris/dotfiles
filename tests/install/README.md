# Installation Tests

Tests for dotfiles installation and deployment infrastructure.

## Directory Structure

```text
tests/install/
├── e2e/           End-to-end tests (full install.sh runs)
├── integration/   Integration tests (multi-component)
└── unit/          Unit tests (isolated functions)
```

## E2E Tests

Full installation tests in clean Docker environments.

- `wsl-docker.sh` - WSL installation in Docker
- `wsl-network-restricted.sh` - WSL installation with network restrictions
- `offline-docker.sh` - Offline installation from cached bundles
- `arch-docker.sh` - Arch Linux installation in Docker

**Usage:**

```bash
bash tests/install/e2e/wsl-docker.sh
bash tests/install/e2e/wsl-network-restricted.sh --keep  # Keep container for debugging
```

## Integration Tests

Test specific installation phases or components together. All use BATS framework.

- `github-releases-pattern.bats` - GitHub release installer pattern validation
- `github-releases-docker.bats` - GitHub releases in Docker
- `github-releases-update.bats` - GitHub release update mechanism
- `installation-orchestration.bats` - Full installation orchestration
- `language-managers-pattern.bats` - Language manager installer patterns
- `language-managers-update.bats` - Language manager updates
- `custom-installers-update.bats` - Custom installer updates
- `bats-installer.bats` - BATS installer itself
- `version-helpers.bats` - Version comparison helpers

## Unit Tests

Test isolated installer functions and components using BATS.

- `library-flag-pollution.bats` - Verify libraries don't set shell options
- `dotfiles-dir.bats` - DOTFILES_DIR resolution

## Running Tests

```bash
# Unit tests (fast, isolated)
bats tests/install/unit/

# Integration tests
bats tests/install/integration/

# E2E tests (slow, requires Docker)
bash tests/install/e2e/wsl-docker.sh
```
