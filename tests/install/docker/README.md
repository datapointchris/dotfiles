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

## Next Steps

**Phase 2**: Expand to all 12 GitHub release installers with proper validation
**Phase 3**: Integrate with Bats test suite
**Phase 4**: CI/CD integration with pre-built base images

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
