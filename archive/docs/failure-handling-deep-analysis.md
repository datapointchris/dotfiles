# Deep Analysis: Failure Handling Issues

## Critical Issues Discovered

### Issue 1: run_installer Captures ALL Output (CRITICAL)

**Location**: `install.sh:114`

```bash
output=$(bash "$script" 2>&1)
```

**Problem**:

- Captures BOTH stdout and stderr
- Users see ZERO output from installers
- Can't debug what's happening
- Phase 4 (Go) shows nothing
- Phase 5 (GitHub releases) shows nothing
- Makes debugging impossible

**Why This Happened**:

- Designed to parse structured failure data from output
- But capturing everything hides all log messages
- User can't see installation progress

**Solution**:

- Only capture stderr (where structured failure data lives)
- Let stdout flow through to terminal (where log messages go)
- Users see real-time installation progress
- We still parse failure data from stderr

**Fixed Code**:

```bash
run_installer() {
  local script="$1"
  local tool_name="$2"

  # Capture stderr only for parsing, let stdout flow through
  local stderr_file
  stderr_file=$(mktemp)

  bash "$script" 2>"$stderr_file"
  exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    rm -f "$stderr_file"
    return 0
  else
    # Parse structured failure data from stderr
    local output
    output=$(cat "$stderr_file")
    rm -f "$stderr_file"

    # ... rest of parsing logic ...
  fi
}
```

---

### Issue 2: platform-detection.sh Has set -euo pipefail

**Location**: `management/lib/platform-detection.sh:9`

**Problem**:

- This is a LIBRARY that gets sourced by many scripts
- Has `set -euo pipefail`
- Adds `-e` flag to any script that sources it
- Causes scripts to exit on first error before run_installer can capture failures

**Scripts that source it**:

- install.sh (CRITICAL!)
- update.sh
- management/common/update.sh
- management/common/install/fonts/fonts.sh

**Solution**:

- Remove `set -euo pipefail` from platform-detection.sh
- Libraries should NOT set shell options
- Let each script manage its own error handling

---

### Issue 3: Should Libraries Set ANY Flags?

**Current state**:

- `logging.sh` has `set -uo pipefail`
- `install-helpers.sh` has `set -uo pipefail`
- `github-release-installer.sh` has NO flags (correct!)

**Analysis**:
When a script sources a library, any `set` flags in the library affect the script:

```bash
# Library has: set -uo pipefail
# Script sources library
source library.sh  # Now script has -uo pipefail set!
```

**Question**: Should libraries set flags at all?

**Recommendation**: NO

- Libraries should not modify the behavior of scripts that source them
- Scripts should manage their own error handling and pipefail settings
- Libraries should be "pure" - only provide functions

**Exception**: If a library's functions specifically require certain flags, document it clearly

---

## Library Audit Results

### Libraries WITH flags (problematic)

1. `management/lib/platform-detection.sh` - `set -euo pipefail` ❌ CRITICAL
2. `platforms/common/.local/shell/logging.sh` - `set -uo pipefail` ⚠️
3. `management/common/lib/install-helpers.sh` - `set -uo pipefail` ⚠️
4. `management/macos/lib/brew-audit.sh` - `set -euo pipefail` ❌
5. `management/wsl/lib/docker-images.sh` - `set -euo pipefail` ❌

### Libraries WITHOUT flags (correct)

1. `management/common/lib/github-release-installer.sh` - None ✓

---

## Testing Strategy

### Test 1: Verify Output Visibility

Create mock installer that outputs log messages, verify they appear in terminal

### Test 2: Verify Failure Data Capture

Create mock installer that outputs structured failure data to stderr, verify run_installer parses it

### Test 3: Verify Libraries Don't Add Flags

Create test script that sources libraries, check if flags are added

### Test 4: Integration Test

Create comprehensive mock installation with success/failure scenarios

---

## Fix Order

1. Fix platform-detection.sh (remove set -e) - HIGHEST PRIORITY
2. Fix run_installer output capture - HIGHEST PRIORITY
3. Consider removing flags from other libraries
4. Create robust mock tests
5. Validate with minimal real installer test

---

## Files to Check/Modify

- `/Users/chris/dotfiles/install.sh` - run_installer function (line 106-155)
- `/Users/chris/dotfiles/management/lib/platform-detection.sh` - remove set flags (line 9)
- `/Users/chris/dotfiles/platforms/common/.local/shell/logging.sh` - consider removing flags
- `/Users/chris/dotfiles/management/common/lib/install-helpers.sh` - consider removing flags
- `/Users/chris/dotfiles/management/macos/lib/brew-audit.sh` - remove if sourced
- `/Users/chris/dotfiles/management/wsl/lib/docker-images.sh` - remove if sourced
