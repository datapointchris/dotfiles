# Management Tests

Tests for dotfiles installation and deployment infrastructure.

## Scripts

### E2E Installation Tests

Full installation tests in clean environments (Docker/VM).

- `test-install-wsl-docker.sh` - Ubuntu WSL installation test
- `test-install-arch-docker.sh` - Arch Linux installation test
- `test-install-macos-temp-user.sh` - macOS fresh user test
- `test-install-current-user-current-platform.sh` - Quick test on current system

**Usage:**

```bash
bash management/tests/test-install-wsl-docker.sh
bash management/tests/test-install-wsl-docker.sh --reuse  # Reuse container
bash management/tests/test-install-wsl-docker.sh --keep   # Keep for debugging
```

### Post-Install Validation

Verify installation completed successfully.

- `verify-installed-packages.sh` - Check all expected packages installed
- `detect-installed-duplicates.sh` - Find duplicate tool installations

**Usage:**

```bash
bash management/tests/verify-installed-packages.sh
bash management/tests/detect-installed-duplicates.sh
```

### Utilities

- `helpers.sh` - Shared test utilities

## Running Tests

```bash
# Quick validation of current system
bash management/tests/verify-installed-packages.sh

# Full E2E test (requires Docker)
bash management/tests/test-install-wsl-docker.sh

# Test current platform (no Docker required)
bash management/tests/test-install-current-user-current-platform.sh
```
