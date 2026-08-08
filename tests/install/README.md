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

The container installs are `tests/e2e/`, driven by pytest — one rig, with the
environments as parameters. `uv run pytest tests/e2e --docker` runs them all,
`-k <name>` picks one, `--keep` leaves the containers up and `--reuse` keeps a
kept container's OS state while still refreshing the repo inside it.

What remains here in `e2e/` are the ones that cannot be a container: a real macOS
user account, the current machine, and the firewalled WSL case.

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
uv run pytest tests/e2e --docker
```
