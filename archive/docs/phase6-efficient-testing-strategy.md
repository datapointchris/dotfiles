# Phase 6.3 - Efficient Testing Strategy

## The Problem

Running full install.sh (10+ minutes) just to verify a simple shell variable is madness. We need:

1. **Minimal focused tests** - Test ONE thing at a time
2. **Mock/stub components** - Don't download real tools for testing
3. **Fast feedback loops** - Seconds, not minutes
4. **Isolated testing** - Each component independently

## Current Inefficiency

```bash
# BAD: Testing DOTFILES_DIR by running entire install
docker exec container bash /root/dotfiles/install.sh
# Wait 10 minutes...
# Check if variable was set
# Repeat
```

## Efficient Testing Approaches

### 1. Minimal DOTFILES_DIR Test (30 seconds)

Create a tiny test script that ONLY tests the variable initialization:

```bash
# test-dotfiles-dir.sh
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
echo "SCRIPT_DIR=$SCRIPT_DIR"
echo "BASH_SOURCE[0]=${BASH_SOURCE[0]}"
echo "$0=$0"
```

Run in Docker:

```bash
docker run --rm -v "$PWD:/root/dotfiles" ubuntu:22.04 bash /root/dotfiles/test-dotfiles-dir.sh
# Result in 5 seconds
```

### 2. Mock Install Script (1 minute)

Create `test-install-mock.sh` with dummy phases:

```bash
#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$SCRIPT_DIR"
export DOTFILES_DIR

# Source real logging
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

# Initialize failures log
FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"
export FAILURES_LOG

# Real run_installer function
run_installer() { ... }

# Create mock installers directory
mkdir -p /tmp/mock-installers

# Mock success installer
cat > /tmp/mock-installers/success.sh << 'EOF'
#!/usr/bin/env bash
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
log_info "Mock success tool installing..."
exit 0
EOF

# Mock failure installer
cat > /tmp/mock-installers/fail.sh << 'EOF'
#!/usr/bin/env bash
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

log_error "Mock failure"
output_failure_data "mock-tool" "https://example.com/mock.tar.gz" "v1.0" "Manual steps here" "Download failed"
exit 1
EOF

chmod +x /tmp/mock-installers/*.sh

# Run mock installation
log_info "Running mock installation..."
run_installer /tmp/mock-installers/success.sh "mock-success"
run_installer /tmp/mock-installers/fail.sh "mock-fail"
run_installer /tmp/mock-installers/success.sh "mock-success-2"

# Show summary
show_failures_summary
```

Test in Docker:

```bash
docker run --rm -v "$PWD:/root/dotfiles" ubuntu:22.04 bash /root/dotfiles/test-install-mock.sh
# Result in 10 seconds
# Validates: DOTFILES_DIR, run_installer, failures log, summary
```

### 3. Pre-built Docker Image (5 minutes first time, 10 seconds after)

Create Dockerfile with common dependencies cached:

```dockerfile
# .docker/test-base.Dockerfile
FROM ubuntu:22.04

# Cache apt update (this is slow)
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Create test user
RUN useradd -m -s /bin/bash testuser
USER testuser
WORKDIR /home/testuser
```

Build once:

```bash
docker build -t dotfiles-test-base -f .docker/test-base.Dockerfile .
```

Use for all tests:

```bash
docker run --rm -v "$PWD:/home/testuser/dotfiles" dotfiles-test-base bash /home/testuser/dotfiles/test-install-mock.sh
```

### 4. Unit Test Individual Functions

Test `run_installer` in isolation:

```bash
# test-run-installer.sh
#!/usr/bin/env bash
set -euo pipefail

source platforms/common/.local/shell/logging.sh
source management/common/lib/install-helpers.sh

FAILURES_LOG="/tmp/test-run-installer.log"
export FAILURES_LOG
rm -f "$FAILURES_LOG"

# Copy run_installer from install.sh
run_installer() { ... }

# Create inline test script
TEST_FAIL=$(cat << 'EOF'
#!/usr/bin/env bash
echo "FAILURE_TOOL='test-tool'"
echo "FAILURE_URL='https://example.com'"
echo "FAILURE_VERSION='v1.0'"
echo "FAILURE_REASON='Test failure'"
echo "FAILURE_MANUAL<<'END_MANUAL'"
echo "Manual steps"
echo "END_MANUAL"
exit 1
EOF
)

# Write to temp file
echo "$TEST_FAIL" > /tmp/test-installer.sh
chmod +x /tmp/test-installer.sh

# Test it
if run_installer /tmp/test-installer.sh "test-tool"; then
  echo "ERROR: Should have failed"
  exit 1
fi

# Verify log
if [[ ! -f "$FAILURES_LOG" ]]; then
  echo "ERROR: No log created"
  exit 1
fi

if ! grep -q "test-tool - Installation Failed" "$FAILURES_LOG"; then
  echo "ERROR: Wrong format"
  cat "$FAILURES_LOG"
  exit 1
fi

echo "✓ run_installer working correctly"
```

Run locally (no Docker):

```bash
bash test-run-installer.sh
# Result in 1 second
```

## Testing Strategy for Phase 6.3

1. **Step 1: Verify DOTFILES_DIR fix** (30 seconds)
   - Create minimal test script
   - Run in Docker
   - Confirm variable is set correctly

2. **Step 2: Test run_installer in isolation** (1 second)
   - Unit test locally
   - No Docker needed
   - Validates core logic

3. **Step 3: Test with mock install script** (10 seconds)
   - Mock installers that succeed/fail quickly
   - Run in Docker
   - Validates full integration

4. **Step 4: Final real test** (5 minutes, only if mocks pass)
   - Run actual network-restricted test
   - Only after confirming all components work

## Implementation Plan

1. Create `tests/install/unit/test-dotfiles-dir.sh` - minimal DOTFILES_DIR test
2. Create `tests/install/unit/test-run-installer.sh` - isolated function test
3. Create `tests/install/integration/test-install-mock.sh` - mock integration test
4. Create `.docker/test-base.Dockerfile` - cached base image
5. Update `management/tests/test-install-wsl-network-restricted.sh` to use base image
6. Run tests in order: unit → mock → real

## Time Savings

- Old approach: 10+ minutes per iteration
- New approach:
  - Unit tests: 1-5 seconds each
  - Mock integration: 10 seconds
  - Real test: 5 minutes (only once at end)

Total time for debugging: ~2 minutes instead of 30+ minutes
