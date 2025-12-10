# Docker-Based Installer Testing

Test installers in isolated Docker containers with real network calls and real installations.

## Architecture

Three-tier Docker image strategy:

1. **Tier 1**: Base OS (ubuntu:24.04)
2. **Tier 2**: Reusable base with system packages pre-installed (`dotfiles-test-base:ubuntu-24.04`)
3. **Tier 3**: Ephemeral test containers that use the base image

## Files

- `Dockerfile` - Multi-stage build (base → system-packages → test-runner)
- `build-base.sh` - Build the reusable base image with system packages
- `run-installer-test.sh` - Run an installer test in a fresh container
- `validate-installation.sh` - Validate that installed binaries exist and run correctly
- `test-all-github-releases.sh` - Batch test runner for all 12 GitHub release installers

## Usage

### Build Base Image (First Time or After System Package Changes)

```bash
cd tests/install/docker
./build-base.sh
```

Build time: ~4 minutes (one-time)
Image size: 3.24GB

### Run Installer Tests

```bash
# Test a GitHub release installer
./run-installer-test.sh management/common/install/github-releases/lazygit.sh

# Test system packages (should skip - already installed in base)
./run-installer-test.sh management/wsl/install/system-packages.sh

# Keep container for debugging
./run-installer-test.sh management/common/install/github-releases/lazygit.sh --keep
```

Test time: ~12-15 seconds per installer (base image reused)

## Phase 1 Results ✅

**Goal**: Prove the Docker-based testing concept with reusable base images

**Achievements**:

- ✅ Base image builds successfully in 4m 6s
- ✅ Base image is 3.24GB with all system packages pre-installed
- ✅ Tests make real network calls to GitHub API
- ✅ Real downloads, real extractions, real installations
- ✅ Base image reuse confirmed - tests run in 12-15 seconds
- ✅ No rebuilding between tests - massive time savings

**Example Test Output**:

```bash
$ time ./run-installer-test.sh management/common/install/github-releases/glow.sh
[INFO] ● Latest version: v1.5.1
[INFO] ● Download URL: https://github.com/...
[INFO] ● Downloading glow...
[INFO] ● Extracting...
[INFO] ● Installing to ~/.local/bin...
[INFO] ● Duration: 12s
```

**What We Tested**:

- GitHub release installers (lazygit, glow, duf) - real API calls, downloads, installations
- System packages installer - validates idempotency (skips when already installed)

**Known Limitations** (Phase 1):

- PATH verification may fail (installers work, but ~/.local/bin not in container PATH)
- No validation helpers yet (just exit code checks)
- Manual test execution (no Bats integration yet)

## Phase 2 Results ✅

**Goal**: Test all 12 GitHub release installers with real network calls and validation

**Achievements**:

- ✅ All 12 GitHub release installers tested: duf, fzf, glow, lazygit, neovim, tenv, terraformer, terrascan, tflint, trivy, yazi, zk
- ✅ 100% pass rate (12/12) in 197.7 seconds (3m 17s)
- ✅ Validation system checks binary exists, is executable, runs with version output
- ✅ PATH environment properly configured for unmodified installers
- ✅ Real bugs found and fixed in production code (terraformer: undefined variable, missing mkdir)
- ✅ Test environment adapts to code, not vice versa

**Files Added**:

- `validate-installation.sh` (84 lines) - Binary validation helper
- `test-all-github-releases.sh` (128 lines) - Batch test runner
- Updates to `Dockerfile` (added `file` and `unzip` packages, created `~/.local/bin`)

**Batch Test Usage**:

```bash
cd tests/install/docker
./test-all-github-releases.sh

# Keep containers on failure for debugging
./test-all-github-releases.sh --keep-on-failure
```

## Phase 3 Results ✅

**Goal**: Integrate Docker backend with Bats test suite to eliminate skipped network tests

**Achievements**:

- ✅ 22 network-dependent tests converted from skipped to Docker-based execution
- ✅ Network-related skips reduced from 22 to 0
- ✅ All converted tests pass with real GitHub API calls in isolated containers
- ✅ Tests validate real installer behavior, not mocks

**Files Modified**:

- `tests/install/integration/docker-helpers.sh` (89 lines, new) - Container lifecycle management for Bats
- `tests/install/integration/github-releases-update.bats` (11 tests converted)
- `tests/install/integration/custom-installers-update.bats` (6 tests converted)
- `tests/install/integration/version-helpers.bats` (4 tests converted)
- `tests/install/integration/language-managers-update.bats` (1 test converted)

**Test Results**:

- github-releases-update.bats: 13/13 passing ✅
- custom-installers-update.bats: 12/12 passing ✅
- version-helpers.bats: 30/30 passing ✅
- Total: 55/55 tests passing, 0 network-related skips

**Usage**:

Tests automatically use Docker when base image is available. Build base image once:

```bash
cd tests/install/docker && ./build-base.sh
```

Then run Bats tests normally:

```bash
bats tests/install/integration/github-releases-update.bats
bats tests/install/integration/*.bats
```

## Project Status

**Complete**: Phases 1-3 finished and committed

This Docker testing infrastructure is fully functional for local development. It provides isolated testing with real network calls, real installations, and proper validation - all without requiring CI/CD integration.

## Troubleshooting

### Base Image Not Found

```bash
./build-base.sh
```

### Permission Errors

The script automatically fixes ownership after copying files. If you see permission errors, check that the `chown` step completed successfully.

### Container Debugging

```bash
# Keep container after test
./run-installer-test.sh <installer> --keep

# Connect to container
docker exec -it <container-name> /bin/bash

# Clean up
docker rm -f <container-name>
```

### Force Rebuild Base Image

```bash
./build-base.sh --no-cache
```
