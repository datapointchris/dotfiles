# Option B Refactoring Guide

## Systematic Installation System Simplification

**Goal**: Replace complex trap-based failure registry with simple single-file structured logging.

**Principles**:

- Clear, explicit code flow (no magic)
- Test after each change
- Commit after each working task
- Integration tests per installer TYPE, not per script
- Balance testing value vs maintenance burden

---

## Overview: What Changes

### Before (Current)

```bash
install.sh (set -euo pipefail)
  ├─ init_failure_registry() → creates /tmp/dotfiles-failures-$$
  ├─ run_phase_installer() → checks if failure reported to registry
  ├─ Scripts call report_failure() → writes to registry/timestamp-tool.txt
  ├─ Scripts use enable_error_traps() → EXIT/ERR traps
  └─ display_failure_summary() → reads registry files, creates permanent log
```

### After (Option B)

```bash
install.sh (set +e, explicit error handling)
  ├─ FAILURES_LOG=/tmp/dotfiles-install-failures-TIMESTAMP.txt
  ├─ run_installer() → captures output, checks exit code, appends to log
  ├─ Scripts output structured data to stderr (optional)
  ├─ Scripts use set -euo pipefail (no traps)
  └─ show_failures_summary() → reads and formats log file
```

---

## Phase 0: Restructure Tests

**Goal**: Clean up test organization before refactoring begins

### Task 0.1: Remove ShellSpec

ShellSpec adds complexity and is barely used (1 spec file vs 15+ bash tests).

**Actions**:

```bash
# Remove ShellSpec files
rm tests/unit/failure_registry_spec.sh
rm tests/.shellspec
rm .shellspec

# Keep the bash test
# tests/unit/test_failure_registry.sh (will be moved in next task)
```

**Remove from packages** (if present):

- Check `management/common/install/custom-installers/shellspec.sh`
- Remove if it exists

**Commit**: `test: remove shellspec framework (unused)`

---

### Task 0.2: Restructure tests/ directory

**New structure**:

```bash
tests/
├── apps/
│   └── all-apps.sh                      # Existing: tests/test-all-apps.sh
├── libraries/
│   ├── logging.sh                       # New: test platforms/common/.local/shell/logging.sh
│   ├── formatting.sh                    # New: test platforms/common/.local/shell/formatting.sh
│   └── error-handling.sh                # New: test platforms/common/.local/shell/error-handling.sh
└── install/
    ├── unit/
    │   └── install-helpers.sh           # Existing: tests/unit/test_failure_registry.sh
    ├── integration/
    │   └── install-wrapper.sh           # Existing: tests/integration/test_install_wrapper.sh
    └── e2e/
        ├── wsl-docker.sh                # Existing: management/tests/test-install-wsl-docker.sh
        ├── arch-docker.sh               # Existing: management/tests/test-install-arch-docker.sh
        ├── macos-temp-user.sh           # Existing: management/tests/test-install-macos-temp-user.sh
        └── current-user.sh              # Existing: management/tests/test-install-current-user-current-platform.sh
```

**Actions**:

```bash
# Create new structure
mkdir -p tests/{apps,libraries,install/{unit,integration,e2e}}

# Move existing tests
mv tests/test-all-apps.sh tests/apps/all-apps.sh
mv tests/unit/test_failure_registry.sh tests/install/unit/install-helpers.sh
mv tests/integration/test_install_wrapper.sh tests/install/integration/install-wrapper.sh
mv management/tests/test-install-wsl-docker.sh tests/install/e2e/wsl-docker.sh
mv management/tests/test-install-arch-docker.sh tests/install/e2e/arch-docker.sh
mv management/tests/test-install-macos-temp-user.sh tests/install/e2e/macos-temp-user.sh
mv management/tests/test-install-current-user-current-platform.sh tests/install/e2e/current-user.sh

# Move helpers
mv management/tests/helpers.sh tests/helpers.sh

# Keep in management/tests/:
# - verify-installed-packages.sh
# - detect-installed-duplicates.sh
# - test-dns-blocking.sh
# - test-cargo-*.sh (component tests)

# Clean up empty directories
rmdir tests/unit tests/integration 2>/dev/null || true
```

**Update tests/README.md** to reflect new structure

**Test**: Run moved tests to verify they still work

```bash
bash tests/apps/all-apps.sh
bash tests/install/unit/install-helpers.sh
bash tests/install/integration/install-wrapper.sh
```

**Commit**: `test: restructure tests into logical hierarchy`

---

### Task 0.3: Rename install-helpers.sh to install-helpers.sh

**Why**: "program-helpers" is too generic - this library provides helpers for installation scripts

**Actions**:

```bash
# Rename the file
git mv management/common/lib/install-helpers.sh management/common/lib/install-helpers.sh

# Update all references (find them first)
grep -r "install-helpers.sh" --include="*.sh" .
```

**Files to update** (likely):

- All scripts in `management/common/install/`
- `install.sh`
- Test files

**Update each file**:

```bash
# Change:
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

# To:
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"
```

**Update header comment** in the renamed file:

```bash
# OLD:
# Shared Helper Functions for GitHub Binary Installation

# NEW:
# Installation Helper Functions
# Provides shared utilities for installation scripts:
# - Package configuration parsing
# - Download handling with retry
# - GitHub release version fetching
# - Failure registry for resilient installations
```

**Test**: Run existing tests to verify rename works

```bash
bash tests/install/unit/install-helpers.sh
bash tests/install/integration/install-wrapper.sh
```

**Commit**: `refactor(install): rename install-helpers.sh to install-helpers.sh`

---

## Phase 1: Core Library Updates

**Goal**: Create new failure handling, remove trap setup, test in isolation

### Task 1.1: Create new failure output helper

**File**: `management/common/lib/install-helpers.sh`

**Add new function** (keep old functions for now):

```bash
# Output structured failure data for wrapper to capture
# Usage: output_failure_data <tool_name> <download_url> <version> <manual_steps> <reason>
output_failure_data() {
  local tool_name="$1"
  local download_url="$2"
  local version="${3:-unknown}"
  local manual_steps="$4"
  local reason="${5:-Installation failed}"

  # Output to stderr in parseable format
  cat >&2 << EOF
FAILURE_TOOL='$tool_name'
FAILURE_URL='$download_url'
FAILURE_VERSION='$version'
FAILURE_REASON='$reason'
FAILURE_MANUAL<<'END_MANUAL'
$manual_steps
END_MANUAL
EOF
}
```

**Test**: Add to `tests/unit/failure_registry_spec.sh`

```bash
Describe 'output_failure_data()'
  BeforeEach source_program_helpers

  It 'outputs structured format to stderr'
    When call output_failure_data "test-tool" "https://example.com/tool.tar.gz" "v1.0" "Manual steps here" "Download failed"
    The status should be success
    The stderr should include "FAILURE_TOOL='test-tool'"
    The stderr should include "FAILURE_URL='https://example.com/tool.tar.gz'"
    The stderr should include "FAILURE_VERSION='v1.0'"
    The stderr should include "FAILURE_REASON='Download failed'"
    The stderr should include "FAILURE_MANUAL"
  End

  It 'handles multiline manual steps'
    manual="Line 1
Line 2
Line 3"
    When call output_failure_data "test" "http://url" "v1" "$manual" "reason"
    The stderr should include "Line 1"
    The stderr should include "Line 2"
    The stderr should include "Line 3"
  End
End
```

**Run test**:

```bash
shellspec tests/unit/failure_registry_spec.sh
```

**Commit**: `refactor(install): add structured failure output helper`

---

### Task 1.2: Remove trap setup from error-handling.sh

**File**: `platforms/common/.local/shell/error-handling.sh`

**Remove**:

- `enable_error_traps()` function
- `exit_trap_handler()` function
- `error_trap_handler()` function

**Keep**:

- `register_cleanup()` - still useful
- `run_cleanup()` - still useful
- `require_commands()` - still useful
- `retry()` - still useful

**Test**: Verify remaining functions still work (optional - these are rarely used)

```bash
# Could add to tests/unit/error_handling_spec.sh if needed
# Not critical for refactor - these functions are stable
```

**Run test**:

```bash
shellspec tests/unit/
```

**Commit**: `refactor(install): remove trap setup from error-handling.sh`

---

## Phase 2: Update install.sh Core

**Goal**: Replace wrapper and failure handling in main install script

### Task 2.1: Create new run_installer wrapper

**File**: `install.sh`

**Add after sourcing libraries** (keep old run_phase_installer for now):

```bash
# New simplified installer wrapper
# Captures output, checks exit code, logs failures
# Usage: run_installer <script_path> <tool_name>
run_installer() {
  local script="$1"
  local tool_name="$2"

  # Capture both stdout and stderr
  local output
  local exit_code

  output=$(bash "$script" 2>&1)
  exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    log_success "$tool_name installed"
    return 0
  else
    log_warning "$tool_name installation failed (see $FAILURES_LOG)"

    # Parse structured failure data from output
    local failure_url failure_version failure_reason failure_manual
    failure_url=$(echo "$output" | grep "^FAILURE_URL=" | cut -d"'" -f2)
    failure_version=$(echo "$output" | grep "^FAILURE_VERSION=" | cut -d"'" -f2)
    failure_reason=$(echo "$output" | grep "^FAILURE_REASON=" | cut -d"'" -f2)

    # Extract multiline manual steps
    if echo "$output" | grep -q "^FAILURE_MANUAL<<"; then
      failure_manual=$(echo "$output" | sed -n '/^FAILURE_MANUAL<</,/^END_MANUAL/p' | sed '1d;$d')
    fi

    # Append to failures log
    cat >> "$FAILURES_LOG" << EOF
========================================
$tool_name - Installation Failed
========================================
Script: $script
Exit Code: $exit_code
Timestamp: $(date -Iseconds)
${failure_url:+Download URL: $failure_url}
${failure_version:+Version: $failure_version}
${failure_reason:+Reason: $failure_reason}

${failure_manual:+Manual Installation Steps:
$failure_manual
}
---

EOF
    return 1
  fi
}
```

**Test**: Create `management/tests/test-run-installer.sh` (simple bash script)

```bash
#!/usr/bin/env bash
# Test run_installer wrapper function

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Testing run_installer() wrapper"

# Source the function (will be in install.sh after Task 2.1)
export FAILURES_LOG="/tmp/test-failures-$$.log"
rm -f "$FAILURES_LOG"

# We'll add the function here temporarily for testing
# (Later it will be in install.sh)
run_installer() {
  # ... function implementation ...
}

# Test 1: Passing script
log_section "Test 1: Passing script"
cat > /tmp/test-pass.sh << 'EOF'
#!/bin/bash
exit 0
EOF
chmod +x /tmp/test-pass.sh

if run_installer /tmp/test-pass.sh "test-tool"; then
  log_success "Passing script handled correctly"
else
  log_error "Passing script should succeed"
  exit 1
fi

# Test 2: Failing script with structured output
log_section "Test 2: Failing script captures structured data"
# ... similar pattern ...

print_banner_success "All run_installer tests passed"
rm -f "$FAILURES_LOG" /tmp/test-*.sh
```

**Commit**: `refactor(install): add new run_installer wrapper with structured logging`

---

### Task 2.2: Update install.sh error handling mode

**File**: `install.sh`

**Change**:

```bash
# OLD (line 14):
set -euo pipefail

# NEW:
set -uo pipefail  # Keep undefined var check and pipefail, but NOT exit-on-error
# We handle errors explicitly with run_installer wrapper
```

**Add after sourcing libraries**:

```bash
# Initialize failures log
FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"
export FAILURES_LOG
```

**Remove**:

```bash
# Delete these lines (around line 136):
# Initialize failure registry for resilient installation
init_failure_registry
```

**Test**: Manual test that install.sh sources correctly

```bash
bash -c 'source install.sh && echo "Sourced successfully"'
```

**Commit**: `refactor(install): change to explicit error handling (set +e)`

---

### Task 2.3: Create new show_failures_summary function

**File**: `install.sh`

**Add** (replace old display_failure_summary later):

```bash
# Display failures summary from log file
# Simpler than old registry-based approach
show_failures_summary() {
  if [[ ! -f "$FAILURES_LOG" ]]; then
    return 0
  fi

  # Count failures (each has a separator line)
  local failure_count
  failure_count=$(grep -c "^---$" "$FAILURES_LOG" || echo 0)

  if [[ $failure_count -eq 0 ]]; then
    return 0
  fi

  # Display header
  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "Installation Summary"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
  log_warning "$failure_count installation(s) failed"
  log_info "This is common in restricted network environments"
  echo ""

  # Display the log file contents (already formatted)
  cat "$FAILURES_LOG"

  echo "════════════════════════════════════════════════════════════════"
  echo "Full report saved to: $FAILURES_LOG"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
}
```

**Test**: Simple validation (no need for dedicated test script - will test with real installer in Task 2.4)

**Commit**: `refactor(install): add simple show_failures_summary function`

---

### Task 2.4: Test new wrapper with one real installer

**Goal**: Verify new system works end-to-end before updating all installers

**Pick simplest installer**: `management/common/install/github-releases/duf.sh`

**Temporarily update duf.sh** to use new pattern:

- Remove `enable_error_traps()` call
- Replace `report_failure()` calls with `output_failure_data()`
- Keep everything else the same

**Test**:

```bash
# Create test script
cat > /tmp/test-single-installer.sh << 'EOF'
#!/bin/bash
set -uo pipefail

source platforms/common/.local/shell/logging.sh
source platforms/common/.local/shell/formatting.sh
source management/common/lib/install-helpers.sh

FAILURES_LOG="/tmp/test-install-$(date +%s).log"

# Source the run_installer function from install.sh
source <(grep -A 50 "^run_installer()" install.sh)

# Test with duf
run_installer management/common/install/github-releases/duf.sh "duf"

# Show summary
source <(grep -A 30 "^show_failures_summary()" install.sh)
show_failures_summary

echo "Test completed. Failures log: $FAILURES_LOG"
EOF

bash /tmp/test-single-installer.sh
```

**Expected**: Either installs successfully OR logs failure with structured data

**Commit**: `test(install): verify new wrapper with duf installer`

---

## Phase 3: Update Installer Scripts by Type

**Goal**: Migrate installers to new pattern, test each type

### Task 3.1: Create integration test for GitHub release installers

**File**: `management/tests/test-github-releases-pattern.sh`

**Test pattern** (tests the PATTERN, not every script - similar to existing test-nvm-failure-handling.sh):

```bash
#!/usr/bin/env bash
# Integration test for GitHub release installers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Testing GitHub Releases Pattern"

export FAILURES_LOG="/tmp/test-github-releases-$$.log"
rm -f "$FAILURES_LOG"

# Test: Script outputs structured failure data on error
log_section "Test: Structured failure output"
# Run a script that will fail (mock curl or use blocked network)
# Verify it outputs FAILURE_* fields

# Test: run_installer captures failure data
log_section "Test: Wrapper captures failure"
# Similar to test-nvm-failure-handling.sh pattern

print_banner_success "GitHub releases pattern test passed"
rm -f "$FAILURES_LOG"
```

**Commit**: `test(install): add GitHub releases integration test`

---

### Task 3.2: Update GitHub release installers (github-release-installer.sh library)

**File**: `management/common/lib/github-release-installer.sh`

**Strategy**: Update the library functions that GitHub release scripts use

**Update download_and_extract_tarball** and similar functions:

- Remove calls to old `report_failure()`
- Add calls to `output_failure_data()` on errors
- Return 1 instead of calling log_fatal (which exits)

**Example**:

```bash
# OLD:
if ! curl -fsSL "$download_url" -o "$temp_file"; then
  report_failure "$tool_name" "$download_url" "$version" "$manual_steps" "Download failed"
  log_fatal "Failed to download from $download_url"
fi

# NEW:
if ! curl -fsSL "$download_url" -o "$temp_file"; then
  output_failure_data "$tool_name" "$download_url" "$version" "$manual_steps" "Download failed"
  log_error "Failed to download from $download_url"
  return 1
fi
```

**Test**: Run integration test

```bash
shellspec tests/integration/github_releases_spec.sh
```

**Commit**: `refactor(install): update github-release-installer.sh to use structured output`

---

### Task 3.3: Update individual GitHub release scripts

**Files**: All scripts in `management/common/install/github-releases/`

**Changes per script**:

1. Remove: `enable_error_traps()` call
2. Remove: `source error-handling.sh` (unless using cleanup helpers)
3. Keep: `set -euo pipefail`
4. Update: Error paths to use `output_failure_data()` instead of `report_failure()`

**Do in batches of 3-4 scripts, test after each batch**:

**Batch 1**: duf.sh, glow.sh, fzf.sh
**Batch 2**: lazygit.sh, yazi.sh, neovim.sh
**Batch 3**: tflint.sh, terraformer.sh, terrascan.sh
**Batch 4**: trivy.sh, (any others)

**Test after each batch**:

```bash
shellspec tests/integration/github_releases_spec.sh
```

**Commit after each batch**: `refactor(install): update [batch] GitHub release installers`

---

### Task 3.4: Create integration test for language managers

**File**: `management/tests/test-language-managers-pattern.sh`

**Test** (similar to existing test-nvm-failure-handling.sh):

```bash
#!/usr/bin/env bash
# Integration test for language manager installers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Testing Language Managers Pattern"

export FAILURES_LOG="/tmp/test-langmgr-$$.log"
rm -f "$FAILURES_LOG"

# Test: Script outputs structured failure data
log_section "Test: Structured failure output"
# Similar pattern to test-nvm-failure-handling.sh

# Test: Wrapper captures and logs failure
log_section "Test: Wrapper integration"
# Run with run_installer, verify log created

print_banner_success "Language managers pattern test passed"
rm -f "$FAILURES_LOG"
```

**Commit**: `test(install): add language managers integration test`

---

### Task 3.5: Update language manager installers

**Files**: nvm.sh, uv.sh, rust.sh, go.sh, tenv.sh

**Already updated nvm.sh in previous work** - verify it matches new pattern

**Update each**:

1. Remove `enable_error_traps()` if present
2. Replace `report_failure()` with `output_failure_data()`
3. Change `exit 1` to `return 1`
4. Remove `|| true` from install.sh calls (not needed with set +e)

**Test after each**:

```bash
bash management/tests/test-language-managers-pattern.sh
```

**Commit after each**: `refactor(install): update [name] to structured failure output`

---

## Phase 4: Update install.sh Phase Calls

**Goal**: Replace all run_phase_installer calls with run_installer

### Task 4.1: Update Phase 5 (GitHub Releases)

**File**: `install.sh` around line 168-180

**Change**:

```bash
# OLD:
print_header "Phase 5 - GitHub Release Tools" "cyan"
run_phase_installer "$github_releases/fzf.sh" "fzf" || true
run_phase_installer "$github_releases/neovim.sh" "neovim" || true
...

# NEW:
print_header "Phase 5 - GitHub Release Tools" "cyan"
run_installer "$github_releases/fzf.sh" "fzf"
run_installer "$github_releases/neovim.sh" "neovim"
...
```

**Remove all `|| true`** - not needed with `set +e`

**Commit**: `refactor(install): update Phase 5 to use new run_installer`

---

### Task 4.2: Update Phase 7 (Language Managers)

**File**: `install.sh` around line 194-199

**Change**:

```bash
# OLD:
print_header "Phase 7 - Language Package Managers" "cyan"
bash "$lang_managers/nvm.sh" || true
bash "$lang_tools/npm-install-globals.sh" || true
...

# NEW:
print_header "Phase 7 - Language Package Managers" "cyan"
run_installer "$lang_managers/nvm.sh" "nvm"
run_installer "$lang_tools/npm-install-globals.sh" "npm-globals"
...
```

**Commit**: `refactor(install): update Phase 7 to use new run_installer`

---

### Task 4.3: Update remaining phases

**Files**: Install phases 6, 8, 9, 10, 11, 12

**Wrap any direct `bash` calls** with `run_installer` where appropriate

**Some phases** (like Phase 10 symlinks) might not need wrapper - use judgment

**Commit**: `refactor(install): update remaining phases to new pattern`

---

### Task 4.4: Replace display_failure_summary with show_failures_summary

**File**: `install.sh` around line 226

**Change**:

```bash
# OLD:
display_failure_summary

# NEW:
show_failures_summary
```

**Commit**: `refactor(install): use new show_failures_summary`

---

## Phase 5: Cleanup Dead Code

**Goal**: Remove old functions and code now unused

### Task 5.1: Remove old functions from install-helpers.sh

**File**: `management/common/lib/install-helpers.sh`

**Remove**:

- `init_failure_registry()`
- `report_failure()`
- `display_failure_summary()`

**Keep**:

- `output_failure_data()` (new function)
- `get_package_config()`
- `print_manual_install()` (still useful for standalone scripts)
- Download helpers

**Test**: Ensure install.sh still sources correctly

```bash
bash -c 'source install.sh && echo OK'
```

**Commit**: `refactor(install): remove old failure registry functions`

---

### Task 5.2: Remove old run_phase_installer wrapper

**File**: `install.sh`

**Delete** the old `run_phase_installer()` function (around line 99-124)

**Verify** no references remain:

```bash
grep -n "run_phase_installer" install.sh
# Should return nothing
```

**Commit**: `refactor(install): remove old run_phase_installer wrapper`

---

### Task 5.3: Archive old tests

**Goal**: Remove tests for old system

**Remove**:

- `management/tests/test-failure-registry-components.sh` (old registry test)
- Any other old failure registry tests

**Keep**:

- New shellspec tests created during refactor
- DNS blocking test (still useful)
- Cargo phase test (still useful)

**Commit**: `test(install): remove old failure registry tests`

---

## Phase 6: Final Integration Test

**Goal**: Verify entire system works end-to-end

### Task 6.1: Create comprehensive integration test

**File**: `management/tests/integration/full-install-test.sh`

**Test** (runs actual install phases with mocked failures):

```bash
#!/bin/bash
# Full installation integration test
# Tests install.sh with mixed successes and failures

set -uo pipefail

source platforms/common/.local/shell/logging.sh
source management/common/lib/install-helpers.sh
source install.sh

FAILURES_LOG="/tmp/full-install-test-$(date +%s).log"

log_info "Testing installation with simulated failures..."

# Test 1: Run a few real installers that should work
run_installer management/common/install/custom-installers/aws-cli.sh "aws-cli"

# Test 2: Simulate failure by mocking curl
curl() { return 7; }
export -f curl

run_installer management/common/install/github-releases/duf.sh "duf" || true

# Test 3: Show summary
show_failures_summary

# Verify
if [[ -f "$FAILURES_LOG" ]]; then
  if grep -q "duf - Installation Failed" "$FAILURES_LOG"; then
    log_success "Failure correctly logged"
  else
    log_error "Failure not logged correctly"
    exit 1
  fi
else
  log_error "Failures log not created"
  exit 1
fi

log_success "Integration test passed"
rm "$FAILURES_LOG"
```

**Run**:

```bash
bash management/tests/integration/full-install-test.sh
```

**Commit**: `test(install): add full installation integration test`

---

### Task 6.2: Update network-restricted test for new system

**File**: `management/tests/test-install-wsl-network-restricted.sh`

**Update validation** (around line 293-360):

- Change check from looking for `/tmp/dotfiles-failures-*/` to checking for `/tmp/dotfiles-install-failures-*.txt`
- Update test assertions for new log format

**Commit**: `test(install): update network-restricted test for new failure logging`

---

### Task 6.3: Final full Docker test

**ONLY RUN AFTER ALL PREVIOUS TASKS COMPLETE**

**Command**:

```bash
bash management/tests/test-install-wsl-network-restricted.sh --keep
```

**Expected**:

- Installation completes all phases
- Failures logged to single `/tmp/dotfiles-install-failures-*.txt` file
- Summary displayed at end
- Test assertions pass

**If failures occur**:

- Debug specific issue
- Fix and commit
- Re-run test

**Final Commit**: `refactor(install): complete Option B simplification`

---

## Summary Checklist

### Phase 0: Restructure Tests ✓

- [ ] Remove ShellSpec (rm failure_registry_spec.sh, .shellspec files)
- [ ] Restructure tests/ directory (apps/, libraries/, install/{unit,integration,e2e})
- [ ] Rename install-helpers.sh to install-helpers.sh
- [ ] Update all references to install-helpers.sh
- [ ] Verify moved tests still work

### Phase 1: Libraries ✓

- [ ] Add output_failure_data() to install-helpers.sh
- [ ] Test with bash tests/install/unit/install-helpers.sh
- [ ] Remove traps from error-handling.sh (optional)

### Phase 2: install.sh Core ✓

- [ ] Add run_installer() wrapper
- [ ] Change to set +e mode
- [ ] Add show_failures_summary()
- [ ] Test with single real installer (duf.sh)

### Phase 3: Installer Scripts ✓

- [ ] Create tests/install/integration/github-releases-pattern.sh
- [ ] Update github-release-installer.sh library
- [ ] Update GitHub release scripts (11 scripts, in batches)
- [ ] Create tests/install/integration/language-managers-pattern.sh
- [ ] Update language manager scripts (5 scripts)

### Phase 4: install.sh Phases ✓

- [ ] Update Phase 5 calls
- [ ] Update Phase 7 calls
- [ ] Update remaining phase calls
- [ ] Replace display_failure_summary call

### Phase 5: Cleanup ✓

- [ ] Remove old functions from install-helpers.sh
- [ ] Remove run_phase_installer()
- [ ] Archive old tests

### Phase 6: Final Testing ✓

- [ ] Create full integration test
- [ ] Update network-restricted test
- [ ] Run final Docker test

---

## Rollback Plan

If at any point the refactor causes issues:

1. **Revert last commit**: `git reset --hard HEAD~1`
2. **Identify issue**: Review test output
3. **Fix in isolation**: Create minimal reproduction
4. **Test fix**: Verify with relevant shellspec test
5. **Continue**: Proceed from where you left off

---

## Estimated Effort

- Phase 0: ~30 min (restructure tests, rename file, update references)
- Phase 1: ~20 min (add new function, update test)
- Phase 2: ~1 hour (new wrapper, update install.sh, test)
- Phase 3: ~2 hours (update 16+ scripts, test batches)
- Phase 4: ~30 min (update install.sh phase calls)
- Phase 5: ~15 min (cleanup)
- Phase 6: ~30 min (final testing)

**Total**: ~4-5 hours of systematic refactoring
