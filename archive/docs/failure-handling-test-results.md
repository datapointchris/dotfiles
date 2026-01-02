# Failure Handling - Test Results & Required Fixes

## Test Summary

All three unit tests completed successfully and identified the root causes.

### Test 1: Output Visibility ❌ FAIL (Bug Confirmed)

**File**: `tests/install/unit/test-run-installer-output-visibility.sh`

**Result**: FAILED - run_installer captures ALL output

**Evidence**:

- User only sees: `[INFO] ✓ mock-tool installed`
- User should see:
  - `[INFO] ● Starting installation...`
  - `[INFO] ● Downloading package...`
  - `[INFO] ● Extracting files...`
  - `[INFO] ✓ Installation complete!`

**Impact**: Users can't see what's happening during installation, making debugging impossible.

---

### Test 2: Failure Data Capture ✓ PASS (Fix Validated)

**File**: `tests/install/unit/test-run-installer-failure-capture.sh`

**Result**: PASSED - Fixed version works correctly

**Validation**:

1. ✓ User sees installer output (stdout flows through)
2. ✓ Failure log created with structured data
3. ✓ All fields captured: URL, version, reason, manual steps

**Fix Applied**: Changed from `output=$(bash "$script" 2>&1)` to stderr-only capture:

```bash
stderr_file=$(mktemp)
bash "$script" 2>"$stderr_file"
# ... parse stderr for failure data ...
```

---

### Test 3: Library Flag Pollution ❌ FAIL (3 Libraries)

**File**: `tests/install/unit/test-library-flag-pollution.sh`

**Libraries that ADD -e flag** (CRITICAL):

1. ❌ `management/lib/platform-detection.sh` - sourced by install.sh!
2. ❌ `management/macos/lib/brew-audit.sh` - sourced by audit scripts
3. ⚠️  `management/wsl/lib/docker-images.sh` - (test failed due to path issue)

**Libraries that PASS**:

1. ✓ `platforms/common/.local/shell/logging.sh` - No -e (already fixed)
2. ✓ `platforms/common/.local/shell/error-handling.sh` - No -e
3. ✓ `management/common/lib/install-helpers.sh` - No -e (already fixed)
4. ✓ `management/common/lib/github-release-installer.sh` - No flags at all

---

## Required Fixes

### Priority 1: CRITICAL (Blocks all failure handling)

#### 1. Fix run_installer output capture in install.sh

**File**: `/Users/chris/dotfiles/install.sh` (line 106-155)

**Current (line 114)**:

```bash
output=$(bash "$script" 2>&1)
```

**Fixed**:

```bash
# Capture stderr only for parsing, let stdout flow through
local stderr_file
stderr_file=$(mktemp)

bash "$script" 2>"$stderr_file"
exit_code=$?

if [[ $exit_code -eq 0 ]]; then
  rm -f "$stderr_file"
  log_success "$tool_name installed"
  return 0
else
  log_warning "$tool_name installation failed (see $FAILURES_LOG)"

  # Parse structured failure data from stderr
  local output
  output=$(cat "$stderr_file")
  rm -f "$stderr_file"

  # ... rest of parsing logic unchanged ...
fi
```

**Impact**: Users will see real-time installation progress.

---

#### 2. Fix platform-detection.sh library

**File**: `/Users/chris/dotfiles/management/lib/platform-detection.sh` (line 9)

**Current**:

```bash
set -euo pipefail
```

**Fixed**:

```bash
# Note: Libraries that are sourced should not use 'set -e' as it modifies
# the error handling behavior of scripts that source them.
set -uo pipefail
```

**Or better yet** (completely remove):

```bash
# Note: Libraries should not set shell options. Scripts that source
# this library should manage their own error handling.
```

**Impact**: Scripts that source this library will no longer have `-e` added unexpectedly.

---

### Priority 2: RECOMMENDED (Consistency)

#### 3. Fix brew-audit.sh library

**File**: `/Users/chris/dotfiles/management/macos/lib/brew-audit.sh` (line 4)

**Same fix as platform-detection.sh**

---

#### 4. Fix docker-images.sh library

**File**: `/Users/chris/dotfiles/management/wsl/lib/docker-images.sh` (line 8)

**Same fix as platform-detection.sh**

---

#### 5. Consider removing all flags from libraries

**Files**:

- `platforms/common/.local/shell/logging.sh` - Currently has `set -uo pipefail`
- `management/common/lib/install-helpers.sh` - Currently has `set -uo pipefail`

**Question**: Should libraries set ANY flags?

**Recommendation**: Remove all `set` statements from libraries. Let scripts manage their own error handling.

**Rationale**:

- Libraries should be "pure" - only provide functions
- Scripts should control their own execution environment
- Reduces unexpected behavior when sourcing libraries

---

## Testing Checklist

After applying fixes:

- [ ] Test 1: Run output visibility test - should PASS
- [ ] Test 2: Run failure capture test - should still PASS
- [ ] Test 3: Run library flag test - should PASS (0 failures)
- [ ] Run minimal installer test (e.g., just fzf.sh with network block)
- [ ] Verify output is visible
- [ ] Verify failure log is created
- [ ] Then (and only then) run full Docker test

---

## Files Created

All tests are permanent and reusable:

1. `/Users/chris/dotfiles/tests/install/unit/test-run-installer-output-visibility.sh`
2. `/Users/chris/dotfiles/tests/install/unit/test-run-installer-failure-capture.sh`
3. `/Users/chris/dotfiles/tests/install/unit/test-library-flag-pollution.sh`

These can be run anytime to validate the system works correctly.

---

## Next Steps

1. Apply Fix #1 (run_installer) to install.sh
2. Apply Fix #2 (platform-detection.sh)
3. Re-run all 3 unit tests to verify fixes
4. Create one more integration test with real installer (mock network failure)
5. Only after ALL unit tests pass → run Docker test
