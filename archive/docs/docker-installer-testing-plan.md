# Docker-Based Installer Testing Plan

## Prerequisites - Completed Logging Consistency Work ✅

**Background**: Before starting Docker-based testing, a comprehensive logging consistency project was completed (December 10, 2025). This work established:

1. **Standard Logging Pattern**: All installers log their own success/skip messages with installation paths
2. **Removed Double Messages**: Eliminated generic success logs from `run_installer` wrapper
3. **Test Philosophy**: Tests validate behavior (does it work?) not implementation (exact log text)
4. **All Tests Passing**: 138/138 tests pass (17 network-dependent tests appropriately skipped)

**Why This Matters for Docker Testing**:

- Installers now follow consistent patterns, making validation predictable
- Tests focus on behavior, so Docker tests can validate real installations
- Network-dependent tests are currently skipped - Docker testing will enable them
- Clean foundation: no pending logging work to conflict with Docker implementation

**Files Modified in Logging Work**: 48 files total

- 3 core infrastructure files (run-installer, github-release-installer, install.sh)
- 45 installer scripts (fonts, GitHub releases, custom, Go, Rust, themes, plugins)
- 7 test files with ~100 assertion updates

**Key Learnings Applied**:

- Never commit with failing tests
- Never change production code to satisfy fragile tests
- Remove fragile tests that check implementation details
- Skip network tests temporarily (Docker will solve this)

**Reference**: See `docs/archive/logging-consistency-fixes.md` for complete details of the completed work.

---

## Problem Statement

Current integration tests skip all network-dependent installer tests, which means we're not testing the core functionality: downloading and installing from the internet. For installers, network interaction IS the main function we need to test.

**Current State:**

- 17/138 tests skipped due to network dependencies
- Tests use complete mocks that will drift out of sync
- No validation that installers actually work with real GitHub API, real downloads, real installations

**Desired State:**

- Test real installers in isolated Docker environments
- Real network calls, real downloads, real output validation
- Reusable base images to avoid rebuilding environment every time
- Fast iteration cycle for test development

## Research Findings

### Docker Multi-Stage Builds (2025 Best Practices)

- **Named stages**: Use `FROM base AS stage-name` for reusability
- **Target specific stages**: `docker build --target=test-base` to stop at intermediate stage
- **Layer caching**: Order layers from least-to-most frequently changed
- **BuildKit**: Efficiently skips unused stages, builds stages concurrently

Sources:

- [Multi-stage | Docker Docs](https://docs.docker.com/build/building/multi-stage/)
- [Docker Multi Stage Builds Works: Best Practices](https://cyberpanel.net/blog/docker-multi-stage-builds)
- [Advanced Dockerfiles: Faster Builds - Docker Blog](https://www.docker.com/blog/advanced-dockerfiles-faster-builds-and-smaller-images-using-buildkit-and-multistage-builds/)

### Docker Layer Caching for CI/CD

- **Pre-build base images**: Separate pipeline builds image with dependencies, reuse across tests
- **Registry caching**: Push intermediate layers to registry for reuse
- **Inline cache**: `--build-arg BUILDKIT_INLINE_CACHE=1` for multi-stage builds
- **Order matters**: Stack layers from least to most frequently mutated

Sources:

- [Docker Layer Caching: Speed Up CI/CD Builds](https://www.bunnyshell.com/blog/docker-layer-caching-speed-up-cicd-builds/)
- [CircleCI Docker Layer Caching Best Practices](https://circleci.com/blog/config-best-practices-docker-layer-caching/)
- [GitLab Docker Layer Caching Docs](https://docs.gitlab.com/ci/docker/docker_layer_caching/)

### pytest-docker Integration Testing

- **Fixtures for lifecycle**: Manage container creation, startup, shutdown
- **wait_until_responsive()**: Poll services until ready
- **Automatic cleanup**: Guaranteed clean environment each run
- **Network isolation**: Tests can make real network calls in isolated environment

Sources:

- [pytest-docker GitHub](https://github.com/avast/pytest-docker)
- [Using pytest with Docker for isolated testing](https://woteq.com/how-to-use-pytest-with-docker-for-isolated-testing-environments/)
- [Building Resilient API Test Automation](https://manishsaini74.medium.com/building-resilient-api-test-automation-pytest-docker-integration-guide-9710359b6d9b)

## Existing Infrastructure

We already have sophisticated Docker-based e2e tests in `tests/install/e2e/`:

**Key Files:**

- `wsl-docker.sh`: Full WSL environment testing (8 steps, ~400 lines)
- `arch-docker.sh`: Arch Linux environment testing
- `management/wsl/lib/docker-images.sh`: Docker image management utilities

**Patterns We Can Reuse:**

1. **Base image caching**: Downloads Ubuntu WSL rootfs once, caches in `.wsl-rootfs-cache/`
2. **Image tagging**: `wsl-ubuntu:24.04`, `archlinux:latest`
3. **Container reuse**: `--reuse` flag to continue from previous run
4. **Keep for debugging**: `--keep` flag to inspect failures
5. **Mount pattern**: Read-only mount of dotfiles, copy to writable location
6. **Non-root testing**: Creates test user, runs as non-root for realism
7. **Helper functions**: `tests/install/helpers.sh` with timing, logging, cleanup

## Proposed Architecture

### Three-Tier Docker Image Strategy

```text
┌─────────────────────────────────────────────────────────┐
│  Tier 1: Base OS Image (Official)                      │
│  - ubuntu:24.04, archlinux:latest                      │
│  - Pulled from Docker Hub                              │
│  - Rarely changes                                       │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Tier 2: System Packages Base (Our Build)              │
│  - Built from Tier 1                                    │
│  - System packages installed (apt/pacman)               │
│  - Test user created, sudo configured                   │
│  - Tag: dotfiles-test-base:ubuntu-24.04                │
│  - Rebuild: Weekly or when system packages change       │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Tier 3: Test Containers (Ephemeral)                   │
│  - Started from Tier 2 image                           │
│  - Dotfiles copied, installer group run                 │
│  - Destroyed after test completes                       │
│  - Fresh start each test run                            │
└─────────────────────────────────────────────────────────┘
```

### Dockerfile Multi-Stage Approach

```dockerfile
# Stage 1: Base OS with user setup
FROM ubuntu:24.04 AS base
RUN useradd -m -G sudo -s /bin/bash testuser && \
    echo "testuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
ENV HOME=/home/testuser
USER testuser
WORKDIR /home/testuser

# Stage 2: System packages (the reusable base)
FROM base AS system-packages
USER root
COPY management/wsl/install/system-packages.sh /tmp/
RUN bash /tmp/system-packages.sh
USER testuser

# Stage 3: Test runner (can target different installer groups)
FROM system-packages AS test-runner
COPY --chown=testuser:testuser . /home/testuser/dotfiles/
WORKDIR /home/testuser/dotfiles
```

**Build commands:**

```bash
# Build and tag the reusable base (Tier 2)
docker build --target=system-packages -t dotfiles-test-base:ubuntu-24.04 .

# Run tests using the base image
docker run --rm dotfiles-test-base:ubuntu-24.04 \
  bash -c "cd ~/dotfiles && bash management/common/install/github-releases/lazygit.sh"
```

## Implementation Plan

### Phase 1: Foundation (Prove the Concept)

**Goal**: Set up reusable base image and test ONE installer group to validate approach

**Steps:**

1. Create `tests/install/docker/Dockerfile` with multi-stage build
   - Stage 1: base (OS + user setup)
   - Stage 2: system-packages (our reusable base)
   - Stage 3: test-runner (for running installer tests)

2. Create `tests/install/docker/build-base.sh`
   - Builds system-packages stage
   - Tags as `dotfiles-test-base:ubuntu-24.04`
   - Caches image locally
   - Reports build time and image size

3. Create `tests/install/docker/run-installer-test.sh`
   - Starts container from base image
   - Copies current dotfiles into container
   - Runs specified installer script
   - Captures output for validation
   - Cleans up container
   - Example: `./run-installer-test.sh github-releases/lazygit.sh`

4. Test with **system packages** (bulletproof, as user noted)
   - Run: `./run-installer-test.sh wsl/install/system-packages.sh`
   - Validate: Check exit code, check installed packages exist
   - Timing: Measure total time (should be fast with base image)

5. Prove base image reuse
   - Run same test twice
   - First run: May take time to download packages
   - Second run: Should be much faster (base image cached)

**Success Criteria:**

- Base image builds successfully and is reusable
- Can run system package installer and validate installation
- Second test run is significantly faster than first
- Tests make real network calls, real installations
- Output is captured and can be validated

**Estimated Time**: 4-6 hours of focused work

### Phase 2: Expand to GitHub Release Installers

**Goal**: Test real GitHub API calls and downloads in isolated environment

**Steps:**

1. Update `run-installer-test.sh` to support validation scripts
   - Pass installer script path
   - Pass expected binary name for validation
   - Example: `./run-installer-test.sh github-releases/lazygit.sh lazygit`

2. Create validation helper
   - Check binary exists in `~/.local/bin/`
   - Check binary is executable
   - Check binary runs (`--version` flag)
   - Capture version output

3. Test all 12 GitHub release installers
   - lazygit, fzf, neovim, yazi, glow, duf, tflint, terraformer, terrascan, trivy, zk, tenv
   - Each test: Real GitHub API call, real download, real extraction
   - Validation: Binary exists, runs, returns version

4. Handle test isolation
   - Each test starts from clean base image
   - No state pollution between tests
   - Can run in parallel if needed

**Success Criteria:**

- All 12 GitHub release installers work in Docker
- Tests validate real installations, not mocks
- GitHub API rate limiting handled gracefully
- Clear pass/fail output for each test

**Estimated Time**: 6-8 hours

### Phase 3: Integrate with Bats Test Suite

**Goal**: Convert skipped integration tests to use Docker backend

**Steps:**

1. Create `tests/install/integration/docker-helpers.sh`
   - Functions to start/stop test containers
   - Functions to run installers in containers
   - Functions to validate installations

2. Update existing bats tests
   - Replace `skip "Requires network"` with Docker-based test
   - Use fixtures to manage container lifecycle
   - Validate real output instead of mocking

3. Example transformation:

   ```bash
   # BEFORE (skipped):
   @test "lazygit: accepts --update flag" {
     skip "Requires network access to GitHub API"
     run bash "$DOTFILES_DIR/.../lazygit.sh" --update
     assert_success
   }

   # AFTER (real Docker test):
   @test "lazygit: accepts --update flag" {
     container_id=$(start_test_container)

     run docker_exec "$container_id" \
       "bash ~/dotfiles/management/common/install/github-releases/lazygit.sh --update"

     assert_success
     assert_output --regexp "Latest version: v[0-9]+"

     cleanup_test_container "$container_id"
   }
   ```

4. Run full test suite
   - All 138 tests should run (no skips)
   - Tests make real network calls in isolated Docker
   - Pass/fail based on real behavior

**Success Criteria:**

- 0 skipped tests (down from 17)
- All tests validate real installer behavior
- Tests are repeatable and isolated
- CI can run full suite

**Estimated Time**: 8-10 hours

### Phase 4: CI/CD Integration & Optimization

**Goal**: Fast, reliable CI testing with pre-built base images

**Steps:**

1. Set up GitHub Actions caching
   - Cache Docker layers
   - Cache base images
   - Use `mode=max` for inline cache

2. Create `build-base-images` workflow
   - Runs weekly or on system-packages changes
   - Builds and pushes base images to registry
   - Tags: `latest`, `ubuntu-24.04-YYYY-MM-DD`

3. Update test workflow
   - Pull pre-built base image
   - Run installer tests in parallel
   - Collect and report results

4. Add performance monitoring
   - Track test duration per installer
   - Alert on slowdowns or failures
   - Compare against baseline

**Success Criteria:**

- CI test run completes in <10 minutes
- Base image rebuild is automated
- Test failures are clear and actionable
- No flaky tests due to network issues

**Estimated Time**: 6-8 hours

## Directory Structure

```bash
tests/install/docker/
├── Dockerfile                    # Multi-stage build definition
├── build-base.sh                 # Build reusable base image
├── run-installer-test.sh         # Run single installer test
├── validate-installation.sh      # Validation helpers
└── README.md                     # Docker testing documentation

tests/install/integration/
├── docker-helpers.sh             # Bats fixtures for Docker
└── *.bats                        # Updated to use Docker backend
```

## Key Design Decisions

### Why Multi-Stage Dockerfile?

**Pros:**

- Explicit dependency layers
- Can target specific stages with `--target`
- BuildKit optimizes build order
- Single source of truth for environment

**Cons:**

- Requires Dockerfile maintenance
- Build step before testing

**Decision**: Use multi-stage for reusable base, but allow ad-hoc containers for development

### Why Not Full Mock Approach?

**Pros of Mocking:**

- Fast, no network needed
- Predictable output

**Cons of Mocking:**

- Mocks drift out of sync with reality
- Don't test actual download/installation logic
- Don't catch GitHub API changes
- Don't test error handling with real failures

**Decision**: Test real installers with real network in isolated Docker

### Why Not TestContainers Library?

**Pros of TestContainers:**

- High-level API for container management
- Language-specific (Python, Go)
- Automatic cleanup

**Cons:**

- Extra dependency
- Learning curve
- We already have working Docker patterns

**Decision**: Use existing bash-based Docker patterns from e2e tests, proven and simple

### Why Separate Base Image Build?

**Pros:**

- Massive time savings (system packages install once)
- Tests start from known-good state
- Can version/tag base images
- Easier debugging (inspect base image separately)

**Cons:**

- Adds complexity
- Need to rebuild when system packages change
- Storage overhead (extra image)

**Decision**: Speed benefit is worth it, especially for frequent test runs

## Risks and Mitigations

### Risk 1: GitHub API Rate Limiting

**Impact**: Tests fail intermittently when rate limited

**Mitigation:**

- Use GitHub token for authenticated API calls (5000 req/hr instead of 60)
- Cache successful responses for repeated tests
- Implement exponential backoff and retry logic
- Run tests in isolated batches if needed

### Risk 2: Docker Storage Bloat

**Impact**: Local disk fills with images/containers

**Mitigation:**

- Automatic cleanup in test scripts
- Weekly pruning job: `docker system prune -f`
- Monitor disk usage, alert when high
- Document cleanup commands for developers

### Risk 3: Network-Dependent Tests Still Flaky

**Impact**: Real network calls introduce variability

**Mitigation:**

- Retry failed tests once before marking as failure
- Separate "network health" from "installer broken"
- CI runs in consistent network environment
- Log network errors separately from code errors

### Risk 4: Base Image Drift

**Impact**: Base image becomes stale, doesn't match production

**Mitigation:**

- Automated weekly rebuild
- Version tagging with date stamps
- Tests compare base image date vs current date
- Alert if base image >7 days old

### Risk 5: Test Time Increases

**Impact**: Full installer tests take too long

**Mitigation:**

- Parallel test execution (Docker makes this easy)
- Pre-built base image (biggest time saver)
- Only run subset of tests on PR, full suite on merge
- Cache downloads where possible

## Success Metrics

**Phase 1 Success:**

- [ ] Base image builds in <5 minutes
- [ ] Base image reused successfully (no rebuild)
- [ ] System package installer test passes
- [ ] Second test run <30 seconds (base cached)

**Phase 2 Success:**

- [ ] All 12 GitHub release installers tested
- [ ] Real downloads, real installations validated
- [ ] Tests pass 100% on clean run
- [ ] Clear error messages on failures

**Phase 3 Success:**

- [ ] 0 skipped tests (down from 17)
- [ ] Full test suite <10 minutes
- [ ] No false positives or negatives
- [ ] Easy to debug failures

**Phase 4 Success:**

- [ ] CI runs full test suite on every PR
- [ ] Base image auto-rebuild weekly
- [ ] Test duration tracked over time
- [ ] Zero manual intervention needed

## Next Steps

1. **Review this plan** - Gather feedback, refine approach
2. **Create Phase 1 branch** - `feature/docker-installer-testing`
3. **Implement Phase 1** - Build base image, test system packages
4. **Validate approach** - Ensure speed/isolation benefits are real
5. **Only then proceed** - Move to Phase 2 after Phase 1 is rock solid

## References

- Existing e2e tests: `tests/install/e2e/wsl-docker.sh`, `tests/install/e2e/arch-docker.sh`
- Docker helpers: `management/wsl/lib/docker-images.sh`
- Test helpers: `tests/install/helpers.sh`
- Current integration tests: `tests/install/integration/*.bats`
