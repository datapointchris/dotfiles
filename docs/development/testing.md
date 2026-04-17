# Testing

The dotfiles repository has three layers of testing:

1. **BATS unit + integration tests** — shell library and installer coverage
2. **pytest** — Python code (packages CLI, `packages verify`, `parse_packages.py`)
3. **Installation e2e tests** — Docker-based platform walkthroughs of `install.sh`

All three run on every commit via pre-commit hooks. See `.pre-commit-config.yaml` for the full wiring.

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

## pytest (Python Tests)

Python-side coverage for `install/parse_packages.py` and `apps/common/packages` (including `packages verify`):

```sh
uv run pytest tests/
```

Test files:

- `tests/install/test_parse_packages.py` — packages.yml parser (filtered-by-manifest behavior, section field extraction).
- `tests/install/test_parse_packages_simple.py` — core parse-helper sanity.
- `tests/apps/test_packages_verify.py` — `packages verify` drift detection. Every test builds a synthetic `install/packages.yml` + manifest tree in `tmp_path`, invokes `packages verify --root <tmp_path>` via subprocess, and asserts on stdout/stderr + exit code. One test per check. The real repo is never read.

## packages verify

`apps/common/packages verify` enforces drift-freeness across packages.yml, the machine manifests, and the installer script directories. See [Package Management — Drift Detection](../architecture/package-management.md#drift-detection) for the check catalog. Runs on every commit; also runnable manually:

```sh
apps/common/packages verify
```

### Writing Tests

Tests use BATS with assertion helpers:

```bash
#!/usr/bin/env bats

# Load helpers
load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

@test "installer checks for dependencies" {
  run bash "$INSTALLER_SCRIPT"
  assert_output --partial "Checking dependencies"
}
```

See [bash-testing-frameworks-guide.md](../learnings/bash-testing-frameworks-guide.md) for detailed BATS usage.

## Installation Testing

Testing dotfiles installation across platforms using containers and virtual machines.

## Why Test in Isolated Environments

- Clean environment every time
- Rapid iteration: destroy, fix, test again
- Test all platforms without multiple machines
- Catch installation issues early
- Match production environment exactly

## Testing Strategy

| Platform | Method | Tool | Accuracy | Machine Manifest |
|----------|--------|------|----------|-----------------|
| Ubuntu (WSL) | Docker | Official WSL rootfs | 100% exact match | `wsl-work-workstation` |
| Arch Linux | Docker | Official Arch base image | 100% exact match | `archlinux-personal-workstation` |
| Ubuntu (Server) | Docker | Official Ubuntu image | 100% exact match | `ubuntu-lxc-server` |
| macOS | Fresh user account | Local testing | Full | `macos-personal-workstation` |

## Prerequisites

```sh
# Docker Desktop (required)
brew install --cask docker
```

## Testing with Docker (Recommended)

### Platform-Specific Test Scripts

Located in `tests/install/e2e/`:

- `wsl-docker.sh` - WSL Ubuntu testing with Docker
- `archlinux-docker.sh` - Arch Linux testing with Docker
- `offline-docker.sh` - Offline installation testing with Docker
- `wsl-network-restricted.sh` - Network-restricted WSL testing
- `macos-temp-user.sh` - macOS testing with fresh user account
- `current-user.sh` - Test on current user (any platform)

All test scripts pass `--machine <manifest>` to `install.sh` and forward the host's GitHub token for authenticated API calls inside containers. The token is resolved from `gh auth token` on the host at test setup time, since `gh` is not available inside the test containers.

### Why Docker for Testing

Docker provides **100% exact match** to real environments:

**WSL Ubuntu**:

- 563 pre-installed packages (same as WSL Ubuntu 24.04)
- Official Microsoft/Canonical WSL distribution
- Fast container startup (~seconds vs minutes for VMs)

**Arch Linux**:

- Official Arch Linux base image
- Latest rolling release packages
- Realistic Arch environment
- Automatic library linking fixes (pcre2 for git)
- Binary naming differences (7z vs 7zz) handled automatically

**Advantages**:

- Lightweight resource usage
- Fast iteration (destroy, fix, test again)
- No guessing about environment differences
- Automated cleanup (or keep with `-k` flag)

### Test Phases

Docker test scripts run comprehensive phases:

1. **Prepare Docker Image** - Pull/update official platform image
2. **Start Container** - Launch container with dotfiles mounted and GitHub token
3. **Prepare Environment** - Create test user, install bootstrap packages (python3, python-yaml), copy dotfiles
4. **Run Installation** - Execute `install.sh --machine <manifest>`
5. **Verify Installation** - Run `verify-installation.sh` checks
6. **Detect Alternates** - Run `detect-alternate-installations.sh`
7. **Test Updates** - Run platform-specific `update-all` task

### Features

- Real-time output with logging (`test-{platform}-docker.log`)
- Timing for each step (MM:SS format)
- Colored output with section headers
- Automatic cleanup (or keep with `-k` flag)
- Comprehensive verification and duplicate detection

### Test Logs

Each test run creates a detailed log file:

- WSL: `test-wsl-docker.log`
- Arch Linux: `test-archlinux-docker.log`
- macOS: `test-macos.log`

Logs include all installation output, timing information, and test results.

## Alternative Testing

Docker is the recommended approach. For environments without Docker, VMs or cloud instances can be used but require more setup time and resources.

## macOS Testing

**Use separate user account**:

1. Create new standard user in System Preferences
2. Log in as that user
3. Install and test dotfiles
4. Delete user when done

macOS VMs are too complex and resource-intensive. Fresh user accounts provide clean testing environment.

## Verification

The test scripts automatically run comprehensive verification using `install/verify-installation.sh`. This checks:

- Core build tools (git, curl, wget, make)
- Task runner installation
- Shell and terminal tools (zsh, tmux, bat, fd, fzf, ripgrep, zoxide, eza)
- Development tools (neovim, lazygit, yazi, glow, duf)
- Version managers (nvm, uv, cargo-binstall)
- Language servers and Go tools
- Platform-specific tools

The verification script validates that tools are installed in the expected locations (e.g., `~/.local/bin/`, `~/.cargo/bin/`) and reports any duplicate installations.

### Manual Verification

If testing manually without the automated scripts:

```sh
# Run comprehensive verification
cd ~/dotfiles
bash tests/install/verification/verify-installed-packages.sh

# Check for duplicate installations
bash tests/install/verification/detect-installed-duplicates.sh
```

## Iteration Workflow

1. **Test** in clean VM
2. **Capture errors** (screenshot, save output)
3. **Fix** bootstrap/taskfile scripts
4. **Destroy** VM
5. **Repeat** until flawless

Document quirks discovered in [Platform Differences](../reference/platforms/differences.md).
