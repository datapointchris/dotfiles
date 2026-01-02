# Production-Grade Management Enhancements

**Status**: ✅ Complete
**Created**: 2025-11-28
**Completed**: 2025-11-28
**Owner**: Chris
**Goal**: Elevate management/ scripts from personal dotfiles to production-quality with industry-standard logging, error handling, and robustness

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Design Philosophy Alignment](#design-philosophy-alignment)
4. [Enhancement Priorities](#enhancement-priorities)
5. [Detailed Design: Structured Logging](#detailed-design-structured-logging)
6. [Detailed Design: Error Handling](#detailed-design-error-handling)
7. [Detailed Design: GitHub Release Abstraction](#detailed-design-github-release-abstraction)
8. [Tradeoff Analysis: Checksums](#tradeoff-analysis-checksums)
9. [Tradeoff Analysis: Installation Registry](#tradeoff-analysis-installation-registry)
10. [Tradeoff Analysis: Rollback Capability](#tradeoff-analysis-rollback-capability)
11. [Implementation Phases](#implementation-phases)
12. [Success Metrics](#success-metrics)
13. [Research Sources](#research-sources)

---

## Executive Summary

### The Opportunity

Transform management/ scripts from personal dotfiles into production-quality installation infrastructure that could be deployed across a corporate environment with:

- **Structured logging** compatible with log aggregation tools (logsift)
- **Robust error handling** that fails fast with clear, actionable messages
- **Reduced duplication** through smart abstraction of GitHub release patterns
- **Verification confidence** through improved testing and validation

### Key Constraints

Must preserve dotfiles philosophy:

- ✅ **Fail fast and loud** - no silent errors or defensive programming that masks issues
- ✅ **Explicit over hidden** - platform logic stays at top level, visible
- ✅ **Straightforward over complex** - prefer some duplication to abstraction mazes
- ✅ **Idempotent by design** - scripts can be run repeatedly until success

### Recommended Approach

**Phase 1 (High Impact, Low Risk):**

1. Implement dual-mode logging (visual terminal + structured logsift)
2. Standardize error handling with traps and cleanup
3. Create generic GitHub release installer

**Phase 2 (Medium Impact, Evaluate):**
4. Enhanced verification with optional checksums
5. Keep current packages.yml registry (no complex state tracking)
6. Skip rollback capability (idempotency + verification is sufficient)

**Rationale**: Focus on logging and error handling provides 80% of production-readiness benefit while maintaining simplicity. Advanced features like rollback add complexity that contradicts the "fail fast and fix it" philosophy.

---

## Current State Analysis

### What Works Well ✅

**Excellent structure** (post-reorganization):

```
management/
├── lib/                     # Shared utilities
├── test-install-*.sh        # Flat, discoverable test scripts
├── common/
│   ├── install/
│   │   ├── github-releases/ # 16 similar scripts
│   │   ├── language-managers/
│   │   ├── language-tools/
│   │   └── plugins/
│   ├── lib/
│   └── update.sh
└── {platform}/
    ├── install/
    ├── lib/
    └── update.sh
```

**Strong foundation**:

- Platform abstraction is clean and extensible
- Testing infrastructure is production-quality (Docker isolation, temp users)
- Documentation is comprehensive
- packages.yml provides single source of truth
- Idempotent design allows safe re-execution

### What Needs Improvement ⚠️

**1. Logging Output** (CRITICAL)

Current formatting.sh output:

```bash
print_success " Yazi already installed"  # Visual, emoji-heavy
print_error " Download failed"           # Colors but no structure
```

Issues:

- Not parseable by log aggregation tools
- No [ERROR], [WARNING], [INFO] prefixes
- No file:line references for debugging
- Stderr vs stdout usage is inconsistent
- Beautiful for terminals, useless for automation

**2. Error Handling** (HIGH PRIORITY)

Current state:

- 51/60 scripts (85%) use `set -euo pipefail` ✅
- 9 scripts missing error safety ❌
- No trap handlers for cleanup ❌
- Limited error context (no line numbers, stack traces) ❌
- Inconsistent error message formats ❌

**3. Code Duplication** (MEDIUM PRIORITY)

GitHub releases: 16 scripts, 1,517 total lines, 85% similarity

- Same platform detection in every script
- Same version checking logic
- Same download/extract/verify pattern
- Same manual install instructions

**4. Verification** (LOW PRIORITY)

Current approach:

- File existence checks: `if [[ -f ~/.local/bin/tool ]]; then`
- Version checks: Parse `tool --version` output
- verify-installed-packages.sh runs comprehensive checks
- detect-installed-duplicates.sh finds alternate installations

Missing:

- No checksum verification (corruption/tampering)
- No installation manifest (what was installed when)
- No validation of binary integrity after install

---

## Design Philosophy Alignment

### Core Principle: Fail Fast and Loud

**From README.md**: "Scripts don't hide errors or work around problems silently. If something's wrong, you'll know immediately with a clear error message. No defensive programming that masks the real issue."

**Implications for design**:

- ✅ Use structured logging with clear [ERROR] prefixes
- ✅ Exit immediately on errors (preserve `set -e`)
- ✅ Provide actionable error messages
- ❌ Don't add complex retry logic
- ❌ Don't implement automatic fallbacks that hide problems
- ❌ Don't build elaborate error recovery

### Core Principle: Straightforward and Simple

**From README.md**: "Prefer some duplication over complex abstractions. Three similar install scripts (one per platform) are clearer than one script with conditional maze."

**Implications for design**:

- ✅ Abstract GitHub release pattern (85% duplication is too much)
- ✅ Keep platform update scripts separate (they're clear)
- ❌ Don't create complex state machines
- ❌ Don't add dependency resolution
- ❌ Don't implement package graph management

### Core Principle: Visual Formatting for Humans

**From README.md**: "Default Assumption: Output is for human consumption, not log aggregation systems. Readability trumps machine parsability."

**NEW CONTEXT**: Now we also care about log parsing (logsift)

**Resolution**: **Dual-mode logging**

- Terminal mode: Colors, emojis, beautiful formatting
- Log mode: Structured [LEVEL] prefixes, file:line refs
- Auto-detect: If stdout is a TTY → visual, else → structured
- Manual override: DOTFILES_LOG_MODE=structured or DOTFILES_LOG_MODE=visual

This preserves the human-first philosophy while enabling automation.

### Core Principle: Idempotent by Design

**Current approach**: Scripts can be run repeatedly, check for existing installations, skip if present

**Implications**:

- ✅ This is BETTER than rollback for most scenarios
- ✅ Failed install? Fix the issue, run again
- ✅ Partial install? Run again, it continues from where it left off
- ⚠️ Registry/rollback adds complexity for minimal benefit in idempotent world

---

## Enhancement Priorities

### P0: Structured Logging (CRITICAL)

**Impact**: High - Enables automation, debugging, log analysis
**Effort**: Medium (2-4 hours)
**Risk**: Low - Additive, doesn't change existing behavior
**Complexity**: Low - Simple wrapper functions

**Why P0**:

- Required for production deployments with log aggregation
- Enables logsift analysis for debugging
- Minimal complexity, high value
- Aligns with industry standards

### P0: Error Handling Standardization (CRITICAL)

**Impact**: High - Prevents silent failures, improves debuggability
**Effort**: Medium (3-5 hours)
**Risk**: Low - Hardens existing scripts
**Complexity**: Low - trap handlers, error logging

**Why P0**:

- 9 scripts missing `set -euo pipefail` is a production risk
- No cleanup on failure can leave system in bad state
- Line numbers + context make debugging 10x faster
- Industry best practice (78% of automation incidents preventable with proper error handling)

### P1: GitHub Release Abstraction (HIGH PRIORITY)

**Impact**: High - Eliminates 1,200 lines, makes adding tools trivial
**Effort**: Medium (4-6 hours initial, 8-12 hours migration)
**Risk**: Medium - Need to test all 16 tools
**Complexity**: Medium - Need flexible configuration

**Why P1**:

- 85% code duplication is maintenance nightmare
- Adding new tool currently requires 80-120 lines of boilerplate
- After abstraction: new tool is ~15 lines + config
- Aligns with "straightforward" principle (reduces cognitive load overall)

### P2: Enhanced Verification (OPTIONAL)

**Impact**: Medium - Catches corruption, improves confidence
**Effort**: Medium (4-6 hours)
**Risk**: Low - Additive feature
**Complexity**: Medium - Checksum verification, manifest tracking

**Why P2**:

- Nice to have, not essential for idempotent system
- Checksums protect against corruption/tampering
- Manifest useful for auditing
- BUT: Adds complexity, may not be worth it (see tradeoff analysis)

### P3: Rollback Capability (NOT RECOMMENDED)

**Impact**: Low - Idempotency solves most rollback use cases
**Effort**: High (8-16 hours)
**Risk**: High - Complex state management
**Complexity**: High - Version tracking, backup/restore

**Why NOT recommended**:

- Contradicts "fail fast and fix it" philosophy
- Idempotency already provides safety (just run again)
- Adds significant complexity for rare edge cases
- Most failures are environmental, not package-specific
- Corporate users would have proper backup/restore systems

---

## Detailed Design: Structured Logging

### Goals

1. **Dual-mode output**: Beautiful in terminal, parseable in logs
2. **Industry-standard formats**: Compatible with logsift and other tools
3. **Backward compatible**: Existing scripts don't break
4. **Zero config**: Works out of the box, auto-detects mode

### Design: Dual-Mode Logging Library

**File**: `management/common/lib/structured-logging.sh`

```bash
#!/usr/bin/env bash
# ================================================================
# Structured Logging Library
# ================================================================
# Provides industry-standard logging with dual-mode output:
#   - Terminal mode: Colors, emojis, visual formatting
#   - Log mode: Structured [LEVEL] prefixes for parsing
#
# Auto-detects mode based on TTY or DOTFILES_LOG_MODE env var
# ================================================================

# Detect output mode
if [[ -n "${DOTFILES_LOG_MODE:-}" ]]; then
  LOG_MODE="$DOTFILES_LOG_MODE"
elif [[ -t 1 ]]; then
  LOG_MODE="visual"    # stdout is a terminal
else
  LOG_MODE="structured" # stdout is redirected (pipe, file, log aggregator)
fi

# Source visual formatting if in visual mode
if [[ "$LOG_MODE" == "visual" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  DOTFILES_DIR="${DOTFILES_DIR:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
  source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
fi

# ================================================================
# Logging Functions
# ================================================================

log_info() {
  local message="$1"
  if [[ "$LOG_MODE" == "visual" ]]; then
    print_info "$message"
  else
    echo "[INFO] $message"
  fi
}

log_success() {
  local message="$1"
  if [[ "$LOG_MODE" == "visual" ]]; then
    print_success "$message"
  else
    echo "[INFO] ✓ $message"
  fi
}

log_warning() {
  local message="$1"
  if [[ "$LOG_MODE" == "visual" ]]; then
    print_warning "$message"
  else
    echo "[WARNING] $message" >&2
  fi
}

log_error() {
  local message="$1"
  local file="${2:-}"
  local line="${3:-}"

  if [[ "$LOG_MODE" == "visual" ]]; then
    print_error "$message"
    if [[ -n "$file" && -n "$line" ]]; then
      echo "  at $file:$line" >&2
    fi
  else
    # Structured format for log parsing
    if [[ -n "$file" && -n "$line" ]]; then
      echo "[ERROR] $message in $file:$line" >&2
    else
      echo "[ERROR] $message" >&2
    fi
  fi
}

log_fatal() {
  local message="$1"
  local file="${2:-}"
  local line="${3:-}"

  if [[ "$LOG_MODE" == "visual" ]]; then
    print_header_error "Fatal Error"
    echo "$message" >&2
    if [[ -n "$file" && -n "$line" ]]; then
      echo "  at $file:$line" >&2
    fi
  else
    echo "[FATAL] $message in ${file:-unknown}:${line:-?}" >&2
  fi
  exit 1
}

log_section() {
  local message="$1"
  local color="${2:-cyan}"

  if [[ "$LOG_MODE" == "visual" ]]; then
    print_section "$message" "$color"
  else
    echo ""
    echo "[SECTION] $message"
    echo "─────────────────────────────────────"
  fi
}

log_header() {
  local message="$1"
  local color="${2:-blue}"

  if [[ "$LOG_MODE" == "visual" ]]; then
    print_header "$message" "$color"
  else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "[HEADER] $message"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
  fi
}

# ================================================================
# Backward Compatibility Aliases
# ================================================================
# Allow existing scripts to continue using print_* functions
# They automatically work in dual-mode

if [[ "$LOG_MODE" != "visual" ]]; then
  # In structured mode, redirect print_* to log_* equivalents
  print_info() { log_info "$@"; }
  print_success() { log_success "$@"; }
  print_warning() { log_warning "$@"; }
  print_error() { log_error "$@"; }
  print_section() { log_section "$@"; }
  print_header() { log_header "$@"; }
  print_banner() { log_header "$@"; }

  # Die and fatal already exist, make them compatible
  die() { log_fatal "$@"; }
fi
```

### Migration Strategy

**Phase 1: Add structured logging library**

- Create `management/common/lib/structured-logging.sh`
- Test dual-mode output (TTY vs pipe)
- Verify logsift can parse structured output

**Phase 2: Update high-traffic scripts**

- install.sh, update.sh
- Platform-specific install scripts
- All test scripts

**Phase 3: Update remaining scripts**

- GitHub release scripts
- Helper scripts
- Plugin installers

**Phase 4: Documentation**

- Add to docs/architecture/
- Update CLAUDE.md with logging guidelines
- Add to learnings/ if any gotchas discovered

### Testing Structured Logging

```bash
# Visual mode (TTY)
./install.sh

# Structured mode (redirected)
./install.sh 2>&1 | tee install.log

# Force structured mode
DOTFILES_LOG_MODE=structured ./install.sh

# Test with logsift
./install.sh 2>&1 | logsift monitor
logsift analyze install.log
```

### Example Output Comparison

**Visual mode** (current):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Phase 3 - GitHub Release Tools
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ● Fetching latest version...
  ✓ Download complete
  ✗ Extraction failed
```

**Structured mode** (new):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HEADER] Phase 3 - GitHub Release Tools
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[INFO] Fetching latest version...
[INFO] ✓ Download complete
[ERROR] Extraction failed in install-yazi.sh:84
```

### Logsift Compatibility

The structured format will be parseable by logsift:

- `[ERROR]` prefix → Detected as error
- `file:line` pattern → Extracted for code fixes
- Stderr → Errors highlighted in red
- Context lines → Preserved for debugging

---

## Detailed Design: Error Handling

### Goals

1. **100% scripts with error safety**: All 60 scripts use `set -euo pipefail`
2. **Cleanup on failure**: No orphaned processes, temp files, or partial state
3. **Actionable error messages**: Line numbers, context, next steps
4. **Consistent patterns**: Reusable error handling library

### Design: Error Handling Library

**File**: `management/common/lib/error-handling.sh`

```bash
#!/usr/bin/env bash
# ================================================================
# Error Handling Library
# ================================================================
# Provides robust error handling with:
#   - Automatic cleanup on exit
#   - Line number tracking
#   - Stack traces for debugging
#   - Consistent error reporting
# ================================================================

# Source structured logging
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/structured-logging.sh"

# ================================================================
# Error Handling State
# ================================================================

# Track cleanup functions to run on exit
declare -a CLEANUP_FUNCTIONS=()

# Track script name for error messages
SCRIPT_NAME="$(basename "${BASH_SOURCE[1]}" 2>/dev/null || echo "unknown")"

# ================================================================
# Cleanup Registration
# ================================================================

# Register a cleanup function to run on exit
# Usage: register_cleanup "rm -rf /tmp/my-temp-dir"
register_cleanup() {
  CLEANUP_FUNCTIONS+=("$1")
}

# Run all registered cleanup functions
run_cleanup() {
  if [[ ${#CLEANUP_FUNCTIONS[@]} -gt 0 ]]; then
    log_info "Running cleanup..."
    for cleanup_cmd in "${CLEANUP_FUNCTIONS[@]}"; do
      eval "$cleanup_cmd" 2>/dev/null || true
    done
  fi
}

# ================================================================
# Error Traps
# ================================================================

# Trap handler for errors (ERR signal)
error_trap_handler() {
  local exit_code=$?
  local line_number=${1:-$LINENO}
  local bash_lineno=${BASH_LINENO[0]:-$line_number}

  # Don't report errors from cleanup
  if [[ "$BASH_COMMAND" == *"run_cleanup"* ]]; then
    return
  fi

  log_error "Command failed with exit code $exit_code" "$SCRIPT_NAME" "$bash_lineno"
  log_error "Failed command: $BASH_COMMAND"

  # Show stack trace in debug mode
  if [[ "${DOTFILES_DEBUG:-false}" == "true" ]]; then
    log_info "Stack trace:"
    local frame=0
    while caller $frame >&2; do
      ((frame++))
    done
  fi
}

# Trap handler for exit (normal or error)
exit_trap_handler() {
  local exit_code=$?
  run_cleanup

  if [[ $exit_code -ne 0 ]]; then
    log_error "Script exited with code $exit_code"
  fi
}

# Enable error trapping
enable_error_traps() {
  # Exit on error, undefined variables, pipe failures
  set -euo pipefail

  # Enable error trap inheritance in functions/subshells
  set -o errtrace

  # Set up trap handlers
  trap 'error_trap_handler $LINENO' ERR
  trap exit_trap_handler EXIT

  # Enhance error output with line numbers
  export PS4='+(${BASH_SOURCE}:${LINENO}): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'
}

# ================================================================
# Helper Functions
# ================================================================

# Run command with error context
# Usage: run_with_context "Installing package" apt-get install package
run_with_context() {
  local description="$1"
  shift

  log_info "$description..."

  if "$@"; then
    log_success "$description completed"
    return 0
  else
    local exit_code=$?
    log_error "$description failed with exit code $exit_code"
    return $exit_code
  fi
}

# Check for required commands
# Usage: require_commands git curl jq
require_commands() {
  local missing=()

  for cmd in "$@"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      missing+=("$cmd")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    log_fatal "Missing required commands: ${missing[*]}"
  fi
}

# Verify file exists and is not empty
# Usage: verify_file "/path/to/file" "Downloaded tarball"
verify_file() {
  local file="$1"
  local description="${2:-File}"

  if [[ ! -f "$file" ]]; then
    log_fatal "$description not found: $file"
  fi

  if [[ ! -s "$file" ]]; then
    log_fatal "$description is empty: $file"
  fi
}

# ================================================================
# Usage Example (at top of scripts)
# ================================================================
# source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
# enable_error_traps
#
# # Register cleanup for temp files
# TMP_DIR=$(mktemp -d)
# register_cleanup "rm -rf $TMP_DIR"
#
# # Use helper functions
# require_commands curl tar
# run_with_context "Downloading package" curl -L "$URL" -o /tmp/package.tar.gz
# verify_file /tmp/package.tar.gz "Downloaded package"
```

### Migration Plan

**Phase 1: Add error handling library** (1 hour)

- Create `management/common/lib/error-handling.sh`
- Test trap handlers, cleanup functions
- Document usage patterns

**Phase 2: Fix missing `set -euo pipefail`** (30 minutes)

- Audit all 60 scripts
- Add to 9 scripts missing it
- Add pre-commit hook to enforce

**Phase 3: Add traps to high-risk scripts** (2-3 hours)

- Scripts that create temp files/directories
- Scripts that download large files
- Scripts that modify system state
- Platform install scripts

**Phase 4: Migrate remaining scripts** (2-3 hours)

- GitHub release installers
- Plugin installers
- Helper scripts

### Example Before/After

**Before** (no error handling):

```bash
#!/usr/bin/env bash
set -euo pipefail

source "$HOME/dotfiles/platforms/common/.local/shell/formatting.sh"

curl -L "$URL" -o /tmp/yazi.zip
cd /tmp
unzip yazi.zip
mv yazi ~/.local/bin/
rm yazi.zip
```

**After** (with error handling):

```bash
#!/usr/bin/env bash

# Source error handling (includes structured logging)
source "$HOME/dotfiles/management/common/lib/error-handling.sh"
enable_error_traps

# Setup
TMP_DIR=$(mktemp -d)
register_cleanup "rm -rf $TMP_DIR"

# Install
require_commands curl unzip
run_with_context "Downloading Yazi" \
  curl -L "$URL" -o "$TMP_DIR/yazi.zip"
verify_file "$TMP_DIR/yazi.zip" "Yazi archive"

cd "$TMP_DIR"
run_with_context "Extracting Yazi" unzip -q yazi.zip
run_with_context "Installing Yazi" mv yazi ~/.local/bin/

log_success "Yazi installed successfully"
```

**Benefits**:

- Temp dir automatically cleaned up on exit (success or failure)
- Clear error messages with line numbers
- Command verification before execution
- Consistent logging format
- File existence/size validation

---

## Detailed Design: GitHub Release Abstraction

### Goals

1. **Eliminate 1,200 lines of duplication** across 16 similar scripts
2. **Make adding new tools trivial** (~15 lines of config)
3. **Maintain clarity** - abstraction should reduce complexity, not add it
4. **Preserve flexibility** - support different archive formats, binary patterns

### Design: Generic Installer + Configuration

**File 1**: `management/common/lib/github-release-installer.sh`

```bash
#!/usr/bin/env bash
# ================================================================
# Generic GitHub Release Installer
# ================================================================
# Installs binary tools from GitHub releases with:
#   - Platform/architecture detection
#   - Version checking (skip if already installed)
#   - Download with retry
#   - Archive extraction (tar.gz, zip, binary)
#   - Binary installation to ~/.local/bin
#   - Post-install hooks
#
# Configuration read from packages.yml via parse-packages.py
# ================================================================

source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps

# ================================================================
# Platform Detection
# ================================================================

detect_platform_arch() {
  local platform=$(uname -s)
  local arch=$(uname -m)

  # Normalize platform
  case "$platform" in
    Darwin) PLATFORM_OS="darwin" ;;
    Linux)  PLATFORM_OS="linux" ;;
    *)      log_fatal "Unsupported platform: $platform" ;;
  esac

  # Normalize architecture
  case "$arch" in
    x86_64)         PLATFORM_ARCH="amd64" ;;
    aarch64|arm64)  PLATFORM_ARCH="arm64" ;;
    *)              log_fatal "Unsupported architecture: $arch" ;;
  esac

  export PLATFORM_OS PLATFORM_ARCH
}

# ================================================================
# Configuration Loading
# ================================================================

load_tool_config() {
  local tool_name="$1"

  # Read from packages.yml via parse-packages.py
  TOOL_REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" \
    --github-binary="$tool_name" --field=repo)

  TOOL_VERSION=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" \
    --github-binary="$tool_name" --field=version 2>/dev/null || echo "latest")

  ARCHIVE_FORMAT=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" \
    --github-binary="$tool_name" --field=archive_format 2>/dev/null || echo "tar.gz")

  BINARY_PATTERN=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" \
    --github-binary="$tool_name" --field=binary_pattern 2>/dev/null || echo "{name}-{os}-{arch}")

  INSTALL_FILES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" \
    --github-binary="$tool_name" --field=install_files 2>/dev/null || echo "$tool_name")
}

# ================================================================
# Version Checking
# ================================================================

check_existing_version() {
  local tool_name="$1"
  local desired_version="$2"
  local bin_path="$HOME/.local/bin/$tool_name"

  # Skip if FORCE_INSTALL
  if [[ "${FORCE_INSTALL:-false}" == "true" ]]; then
    return 1  # Not installed (force reinstall)
  fi

  # Check if binary exists
  if [[ ! -f "$bin_path" ]]; then
    return 1  # Not installed
  fi

  # Check if in PATH
  if ! command -v "$tool_name" >/dev/null 2>&1; then
    log_warning "$tool_name found at $bin_path but not in PATH"
    return 1  # Not accessible
  fi

  # If version is "latest", accept any existing version
  if [[ "$desired_version" == "latest" ]]; then
    return 0  # Already installed
  fi

  # Check version (tool-specific, can be overridden)
  local current_version
  current_version=$("$tool_name" --version 2>&1 | head -n1 || echo "unknown")

  if echo "$current_version" | grep -q "$desired_version"; then
    return 0  # Already installed
  fi

  return 1  # Version mismatch
}

# ================================================================
# Download and Installation
# ================================================================

install_github_binary() {
  local tool_name="$1"

  log_header "Installing $tool_name" "cyan"

  # Detect platform
  detect_platform_arch

  # Load configuration
  load_tool_config "$tool_name"

  # Check existing installation
  if check_existing_version "$tool_name" "$TOOL_VERSION"; then
    log_success "$tool_name already installed, skipping"
    return 0
  fi

  # Setup temp directory
  local tmp_dir
  tmp_dir=$(mktemp -d)
  register_cleanup "rm -rf $tmp_dir"

  # Get version (fetch latest if needed)
  if [[ "$TOOL_VERSION" == "latest" ]]; then
    TOOL_VERSION=$(fetch_latest_release "$TOOL_REPO")
  fi

  log_info "Target: $TOOL_VERSION ($PLATFORM_OS/$PLATFORM_ARCH)"

  # Build download URL
  local binary_name
  binary_name=$(echo "$BINARY_PATTERN" | \
    sed "s/{name}/$tool_name/g" | \
    sed "s/{os}/$PLATFORM_OS/g" | \
    sed "s/{arch}/$PLATFORM_ARCH/g")

  local download_url="https://github.com/${TOOL_REPO}/releases/download/${TOOL_VERSION}/${binary_name}.${ARCHIVE_FORMAT}"

  # Download
  local archive_path="$tmp_dir/archive.${ARCHIVE_FORMAT}"
  run_with_context "Downloading $tool_name" \
    curl -fsSL "$download_url" -o "$archive_path"
  verify_file "$archive_path" "Downloaded archive"

  # Extract
  cd "$tmp_dir"
  case "$ARCHIVE_FORMAT" in
    tar.gz)
      run_with_context "Extracting archive" tar -xzf "$archive_path"
      ;;
    zip)
      run_with_context "Extracting archive" unzip -q "$archive_path"
      ;;
    binary)
      # No extraction needed, rename archive to binary
      mv "$archive_path" "$tool_name"
      chmod +x "$tool_name"
      ;;
  esac

  # Install binaries
  mkdir -p "$HOME/.local/bin"
  for binary in $INSTALL_FILES; do
    # Find binary in extracted directory (may be nested)
    local binary_path
    binary_path=$(find "$tmp_dir" -type f -name "$binary" | head -n1)

    if [[ -z "$binary_path" ]]; then
      log_fatal "Binary not found in archive: $binary"
    fi

    run_with_context "Installing $binary" \
      mv "$binary_path" "$HOME/.local/bin/"
    chmod +x "$HOME/.local/bin/$binary"
  done

  # Verify installation
  if command -v "$tool_name" >/dev/null 2>&1; then
    local installed_version
    installed_version=$("$tool_name" --version 2>&1 | head -n1 || echo "installed")
    log_success "$tool_name: $installed_version"
  else
    log_fatal "$tool_name installation verification failed (check PATH)"
  fi

  log_success "$tool_name installation complete"
}

# ================================================================
# Helper Functions
# ================================================================

fetch_latest_release() {
  local repo="$1"
  local version

  if ! version=$(curl -fsSL "https://api.github.com/repos/${repo}/releases/latest" | jq -r .tag_name); then
    log_fatal "Failed to fetch latest release for $repo (check network/API rate limit)"
  fi

  echo "$version"
}
```

**File 2**: Updated `packages.yml` with GitHub binary config

```yaml
github_binaries:
  # Simple case: standard pattern
  - name: lazygit
    repo: jesseduffield/lazygit
    version: v0.40.2
    archive_format: tar.gz
    binary_pattern: "{name}_{version}_{os}_{arch}"
    install_files: lazygit

  # Complex case: multiple binaries
  - name: yazi
    repo: sxyazi/yazi
    version: latest
    archive_format: zip
    binary_pattern: "{name}-{os}-{arch}"
    install_files: "yazi ya"
    post_install: |
      ya pkg add BennyOe/tokyo-night
      ya pkg add dangooddd/kanagawa

  # Build from source case
  - name: fzf
    repo: junegunn/fzf
    build_from_source: true
    min_version: "0.50.0"
```

**File 3**: Individual tool script (now ~15 lines)

```bash
#!/usr/bin/env bash
# ================================================================
# Install Yazi from GitHub Releases
# ================================================================
# Downloads and installs latest Yazi with flavors/plugins
# Configuration: management/packages.yml
# ================================================================

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

# Install via generic installer
install_github_binary "yazi"

# Tool-specific post-install (if needed)
if [[ -f "$HOME/.local/bin/ya" ]]; then
  log_info "Installing Yazi flavors..."
  export GIT_TERMINAL_PROMPT=0
  ya pkg add BennyOe/tokyo-night || true
  ya pkg add dangooddd/kanagawa || true
fi
```

### Migration Strategy

**Phase 1: Build and test generic installer** (4-6 hours)

- Create `github-release-installer.sh`
- Update `packages.yml` with github_binaries config
- Test with 2-3 simple tools (lazygit, duf, glow)

**Phase 2: Migrate remaining tools** (4-6 hours)

- Migrate all 16 GitHub release tools
- Handle edge cases (build from source, multiple binaries, post-install)
- Test on all platforms (macOS, WSL, Arch)

**Phase 3: Update install.sh** (1 hour)

- Update to use new structure
- Remove old individual script calls
- Test full installation

**Phase 4: Cleanup and documentation** (1 hour)

- Archive old scripts
- Update docs
- Add to learnings/ if patterns discovered

### Benefits

**Before**: 16 scripts × 95 lines average = 1,520 lines
**After**: 1 library (200 lines) + 16 configs (15 lines each) = 440 lines
**Reduction**: 1,080 lines (71% reduction)

**Adding new tool**:

- Before: 80-120 lines of boilerplate
- After: 5-10 lines in packages.yml, maybe 15-line script if post-install needed

---

## Tradeoff Analysis: Checksums

### What Are Checksums?

Cryptographic hashes (SHA256, SHA512) used to verify file integrity:

- Detect corruption during download
- Detect tampering by malicious actors
- Ensure binary matches what was published

### Industry Practice

**Package managers use checksums extensively**:

- npm: SHA1 and SHA512
- rpm/yum: `rpm -K` verifies checksums + GPG signatures
- apt/dpkg: `debsums` verifies package checksums
- Homebrew: SHA256 verification for all downloads

**GitHub releases**: Many projects publish SHA256SUMS file alongside releases

### Implementation Approach

```bash
# In github-release-installer.sh
verify_checksum() {
  local file="$1"
  local expected_checksum="${2:-}"

  if [[ -z "$expected_checksum" ]]; then
    log_warning "No checksum provided, skipping verification"
    return 0
  fi

  local actual_checksum
  actual_checksum=$(sha256sum "$file" | awk '{print $1}')

  if [[ "$actual_checksum" != "$expected_checksum" ]]; then
    log_fatal "Checksum mismatch for $file\n  Expected: $expected_checksum\n  Actual:   $actual_checksum"
  fi

  log_success "Checksum verified"
}

# In packages.yml
github_binaries:
  - name: lazygit
    repo: jesseduffield/lazygit
    version: v0.40.2
    checksum: "sha256:abc123..."  # Optional
```

### Benefits

✅ **Security**: Detect tampering, man-in-the-middle attacks
✅ **Reliability**: Detect corrupted downloads
✅ **Compliance**: Some corporate environments require it
✅ **Peace of mind**: Know you got what you expected

### Costs

❌ **Maintenance burden**: Must update checksum for every version bump
❌ **Manual work**: Fetching checksums for 16+ tools across 3 platforms
❌ **Fragility**: Wrong checksum = installation fails (happens often)
❌ **False security**: Only protects against corruption/tampering, not malicious source
❌ **Limited value**: GitHub already uses HTTPS, corruption is rare

### Recommendation: **Optional Checksums**

**Approach**: Support checksums but don't require them

```yaml
github_binaries:
  - name: lazygit
    repo: jesseduffield/lazygit
    version: v0.40.2
    checksum: "sha256:abc123..."  # OPTIONAL - verify if present

  - name: yazi
    repo: sxyazi/yazi
    version: latest
    # No checksum - installation proceeds without verification
```

**Rationale**:

1. **Fail fast philosophy**: If checksum is wrong, fail immediately
2. **Optional for most tools**: Only add for high-security tools (awscli, terraform)
3. **Gradual adoption**: Can add checksums over time as versions are updated
4. **Not a blocker**: Don't let missing checksums prevent installation

**When to use checksums**:

- ✅ Security-critical tools (awscli, terraform, kubectl)
- ✅ Corporate deployment requirements
- ✅ Tools with known supply chain risks
- ❌ Low-risk CLI tools (lazygit, yazi, glow)
- ❌ Frequently updated tools (maintenance burden)

---

## Tradeoff Analysis: Installation Registry

### What Is an Installation Registry?

A manifest file tracking what was installed, when, and what version:

```json
{
  "installations": [
    {
      "tool": "lazygit",
      "version": "v0.40.2",
      "installed_at": "2025-11-28T10:30:00Z",
      "installed_by": "chris",
      "checksum": "sha256:abc123...",
      "files": [
        "/Users/chris/.local/bin/lazygit"
      ]
    }
  ]
}
```

### Industry Practice

**Package managers maintain state**:

- apt: `/var/lib/dpkg/status`
- rpm: `/var/lib/rpm` database
- Homebrew: `/usr/local/Cellar/` directory structure
- npm: `package-lock.json`, `node_modules/`

**Benefits in those systems**:

- Dependency resolution (install A requires B)
- Upgrade path (know what's installed to upgrade)
- Uninstall (remove all files from package)
- Audit trail (compliance, security scanning)

### Proposed Implementation

**File**: `~/.dotfiles-registry.json`

```json
{
  "schema_version": "1.0",
  "platform": "macos",
  "last_updated": "2025-11-28T10:30:00Z",
  "installations": [
    {
      "tool": "lazygit",
      "source": "github_release",
      "repo": "jesseduffield/lazygit",
      "version": "v0.40.2",
      "installed_at": "2025-11-28T10:30:00Z",
      "checksum": "sha256:abc123...",
      "files": [
        "/Users/chris/.local/bin/lazygit"
      ]
    }
  ]
}
```

**Functions**:

```bash
# management/common/lib/registry.sh

register_installation() {
  local tool="$1"
  local version="$2"
  local files=("${@:3}")

  # Add to ~/.dotfiles-registry.json
}

verify_registry() {
  # Check all files in registry still exist
  # Verify checksums if available
}

list_installations() {
  # Show what's installed
}
```

### Benefits

✅ **Audit trail**: Know what was installed when
✅ **Verification**: `task verify-all` checks all installations
✅ **Debugging**: See installation history
✅ **Compliance**: Meet corporate audit requirements
✅ **Uninstall**: Know what files to remove

### Costs

❌ **Complexity**: JSON parsing/writing in bash (or need Python)
❌ **Maintenance**: Registry can get out of sync with reality
❌ **Duplication**: packages.yml already defines what should be installed
❌ **Scope creep**: Leads to dependency management, version constraints
❌ **Philosophy conflict**: "Registry is reality" vs "Just check if it works"

### Current Approach (No Registry)

**packages.yml = Source of Truth**:

- Lists what SHOULD be installed
- Scripts are idempotent (check if exists, skip if present)
- verify-installed-packages.sh checks if tools work

**Verification approach**:

```bash
# Check if tool is installed and working
if command -v lazygit >/dev/null 2>&1; then
  echo "✓ lazygit installed"
  lazygit --version
else
  echo "✗ lazygit not found"
fi
```

**Benefits of current approach**:

- ✅ Simple: If it works, it's installed
- ✅ Reality-based: Checks actual system state
- ✅ No state management: Can't get out of sync
- ✅ No parsing: Direct shell commands

### Recommendation: **Keep Current Approach, Add Lightweight Tracking**

**Option 1: No Registry** (Recommended)

Rationale:

- packages.yml already defines what should be installed
- verify-installed-packages.sh already checks what is installed
- Idempotency means state doesn't matter (just run again)
- No complex state to maintain

**Option 2: Lightweight Tracking** (If audit trail needed)

Simple append-only log, not a registry:

**File**: `~/.dotfiles-install.log`

```
2025-11-28T10:30:00Z INSTALL lazygit v0.40.2 github_release
2025-11-28T10:31:00Z INSTALL yazi latest github_release
2025-11-28T10:32:00Z VERIFY lazygit v0.40.2 success
```

**Benefits**:

- ✅ Simple append-only (no JSON parsing)
- ✅ Audit trail for compliance
- ✅ Debugging aid
- ✅ No state management (never read, only append)
- ✅ Can be ignored (optional)

**Implementation**:

```bash
# In github-release-installer.sh
log_installation() {
  local tool="$1"
  local version="$2"
  echo "$(date -Iseconds) INSTALL $tool $version github_release" >> ~/.dotfiles-install.log
}
```

---

## Tradeoff Analysis: Rollback Capability

### What Is Rollback?

Ability to undo an installation and restore previous state:

- Downgrade to previous version
- Restore old binary if new one fails
- Undo system changes

### Industry Practice

**Package managers support rollback**:

- apt: `apt install package=old-version`
- Homebrew: `brew switch package version`
- npm: `npm install package@old-version`
- NixOS: Entire system rollback (atomic deployments)

**Corporate systems**:

- Blue/green deployments
- Canary releases with automated rollback
- Snapshot-based systems (VM snapshots, ZFS)

### Proposed Implementation

**Approach 1: Backup Previous Binary**

```bash
# In github-release-installer.sh
backup_previous_version() {
  local tool="$1"
  local bin_path="$HOME/.local/bin/$tool"
  local backup_dir="$HOME/.dotfiles-backups"

  if [[ -f "$bin_path" ]]; then
    local current_version
    current_version=$("$bin_path" --version | head -n1)

    mkdir -p "$backup_dir/$tool"
    cp "$bin_path" "$backup_dir/$tool/${current_version}"

    log_info "Backed up $tool $current_version"
  fi
}

rollback_installation() {
  local tool="$1"
  local backup_dir="$HOME/.dotfiles-backups/$tool"

  # Find most recent backup
  local latest_backup
  latest_backup=$(ls -t "$backup_dir" | head -n1)

  if [[ -z "$latest_backup" ]]; then
    log_fatal "No backup found for $tool"
  fi

  cp "$backup_dir/$latest_backup" "$HOME/.local/bin/$tool"
  log_success "Rolled back $tool to $latest_backup"
}
```

**Approach 2: Version Manager**

```bash
# Keep multiple versions, symlink to current
~/.local/opt/
  lazygit/
    v0.40.2/bin/lazygit
    v0.41.0/bin/lazygit
~/.local/bin/lazygit -> ~/.local/opt/lazygit/v0.41.0/bin/lazygit

# Switch versions
switch_version() {
  local tool="$1"
  local version="$2"
  ln -sf "$HOME/.local/opt/$tool/$version/bin/$tool" "$HOME/.local/bin/$tool"
}
```

### Benefits

✅ **Safety**: Undo bad upgrades
✅ **Confidence**: Know you can go back
✅ **Testing**: Try new version, rollback if issues
✅ **Corporate**: Required for production systems

### Costs

❌ **Complexity**: Version tracking, symlink management
❌ **Disk space**: Keep multiple versions around
❌ **Maintenance**: Garbage collect old versions
❌ **Edge cases**: What if config format changed?
❌ **Philosophy conflict**: "Fail fast and fix" vs "Have safety net"

### Why Current Approach (Idempotency) Is Better

**Scenario: Failed upgrade**

**With rollback**:

1. Upgrade lazygit v0.40.2 → v0.41.0
2. New version has bug
3. Rollback to v0.40.2
4. Wait for v0.41.1 fix
5. Upgrade again

**With idempotency (current)**:

1. Attempt upgrade to v0.41.0
2. Notice bug
3. Edit packages.yml to pin v0.40.2
4. Run install.sh again (idempotent, downgrades)
5. Wait for v0.41.1 fix
6. Edit packages.yml to v0.41.1
7. Run install.sh again

**Benefits of idempotent approach**:

- ✅ No state management needed
- ✅ Explicit version control in packages.yml
- ✅ Can "rollback" by changing config and re-running
- ✅ Works for partial failures (just run again)
- ✅ Simpler mental model

### Real-World Scenarios

**Scenario 1: Upgrade breaks something**

- Rollback approach: `task rollback lazygit`
- Idempotent approach: Edit packages.yml, run install.sh
- Winner: Tie (both work, rollback slightly faster)

**Scenario 2: Network failure during download**

- Rollback approach: Need to cleanup partial state, complicated
- Idempotent approach: Just run again, temp cleanup happens automatically
- Winner: Idempotent (simpler)

**Scenario 3: Want to test new version**

- Rollback approach: Upgrade, test, rollback if needed
- Idempotent approach: Change version in packages.yml, run install.sh, change back if needed
- Winner: Tie (both work)

**Scenario 4: Configuration format changed**

- Rollback approach: Binary rolls back but config is incompatible, manual fix needed
- Idempotent approach: Binary re-installs but config is incompatible, manual fix needed
- Winner: Tie (both have the problem)

### Recommendation: **Skip Rollback, Rely on Idempotency**

**Rationale**:

1. **Philosophy alignment**: "Fail fast and fix" means if something breaks, you WANT to fix it, not hide behind rollback
2. **Idempotency sufficient**: Can achieve same outcome by changing packages.yml version and re-running
3. **Complexity cost**: Rollback adds significant complexity for rare benefit
4. **Corporate context**: Corporate users have backup/restore at infrastructure level (VM snapshots, etc.)
5. **Real failures**: Most failures are environmental (network, permissions) not version-specific

**Alternative: Document Rollback Procedure**

Instead of building rollback into scripts, document manual rollback:

```markdown
# docs/reference/troubleshooting.md

## Rolling Back a Tool Version

If an upgrade causes issues, rollback by reinstalling the old version:

1. Edit packages.yml to specify the old version:
   ```yaml
   - name: lazygit
     version: v0.40.2  # Change from v0.41.0
   ```

2. Force reinstall:

   ```bash
   FORCE_INSTALL=true ./install.sh
   ```

3. Verify:

   ```bash
   lazygit --version
   ```

For critical tools, consider pinning versions instead of using "latest".

```

---

## Implementation Phases

### Phase 1: Structured Logging (Week 1)

**Effort**: 2-4 hours
**Risk**: Low
**Dependencies**: None

**Tasks**:
1. Create `management/common/lib/structured-logging.sh`
2. Add TTY detection for dual-mode output
3. Test with logsift to verify parsing
4. Update 3-5 high-traffic scripts (install.sh, update.sh, test scripts)
5. Document in docs/architecture/

**Success criteria**:
- [ ] Logsift can parse structured output
- [ ] Terminal output still looks beautiful
- [ ] Auto-detection works (TTY vs pipe)
- [ ] Manual override works (DOTFILES_LOG_MODE)

### Phase 2: Error Handling (Week 1)

**Effort**: 3-5 hours
**Risk**: Low
**Dependencies**: Structured logging

**Tasks**:
1. Create `management/common/lib/error-handling.sh`
2. Add trap handlers for cleanup
3. Audit all 60 scripts, add `set -euo pipefail` to 9 missing
4. Add pre-commit hook to enforce error safety
5. Update high-risk scripts with cleanup traps

**Success criteria**:
- [ ] All 60 scripts have `set -euo pipefail`
- [ ] Pre-commit hook prevents new scripts without it
- [ ] Trap handlers clean up temp files on failure
- [ ] Error messages include line numbers

### Phase 3: GitHub Release Abstraction (Week 2-3)

**Effort**: 6-12 hours
**Risk**: Medium
**Dependencies**: Error handling

**Tasks**:
1. Create `management/common/lib/github-release-installer.sh`
2. Update `packages.yml` with github_binaries configuration
3. Migrate 2-3 simple tools (lazygit, duf, glow)
4. Test on all platforms (macOS, WSL, Arch)
5. Migrate remaining 13 tools
6. Update install.sh to use new structure
7. Archive old scripts
8. Document patterns in docs/architecture/

**Success criteria**:
- [ ] All 16 tools install successfully
- [ ] New tool can be added with ~15 lines of config
- [ ] Edge cases handled (build from source, post-install)
- [ ] Code reduction: 1,080 lines eliminated

### Phase 4: Enhanced Verification (Optional - Week 4)

**Effort**: 4-6 hours
**Risk**: Low
**Dependencies**: GitHub release abstraction

**Tasks**:
1. Add optional checksum support to github-release-installer.sh
2. Add checksums for security-critical tools (awscli, terraform)
3. Add lightweight installation log (~/.dotfiles-install.log)
4. Document checksum usage in CLAUDE.md

**Success criteria**:
- [ ] Checksums verified when present
- [ ] Installation proceeds without checksums
- [ ] Install log tracks all installations
- [ ] Documentation covers when to use checksums

### Phase 5: Documentation & Rollout (Week 4)

**Effort**: 2-3 hours
**Risk**: None
**Dependencies**: All previous phases

**Tasks**:
1. Update docs/architecture/ with new patterns
2. Add to docs/learnings/ if patterns discovered
3. Update CLAUDE.md with logging/error handling guidelines
4. Create announcement/changelog
5. Test full installation on clean system

**Success criteria**:
- [ ] All documentation updated
- [ ] Clean installation succeeds on all platforms
- [ ] CLAUDE.md reflects new patterns
- [ ] Learnings captured for future reference

---

## Success Metrics

### Quantitative Metrics

**Code reduction**:
- Before: 1,517 lines in GitHub release scripts
- After: ~440 lines (library + configs)
- **Reduction: 1,080 lines (71%)**

**Error safety**:
- Before: 51/60 scripts with error handling (85%)
- After: 60/60 scripts with error handling (100%)
- **Improvement: +9 scripts hardened**

**Time to add new tool**:
- Before: 80-120 lines of boilerplate, 30-60 minutes
- After: 15 lines of config, 5-10 minutes
- **Improvement: 6x faster**

### Qualitative Metrics

**Production readiness**:
- ✅ Structured logging enables log aggregation
- ✅ Error handling prevents silent failures
- ✅ Trap handlers ensure cleanup
- ✅ Reduced duplication improves maintainability

**Debugging efficiency**:
- ✅ Line numbers in error messages
- ✅ File:line format for quick navigation
- ✅ Consistent error message format
- ✅ Stack traces in debug mode

**Corporate deployment viability**:
- ✅ Log aggregation compatible
- ✅ Audit trail available (optional install log)
- ✅ Optional checksums for security
- ✅ Comprehensive testing infrastructure

---

## Research Sources

### Bash Error Handling Best Practices

- [Error handling in Bash - Stack Overflow](https://stackoverflow.com/questions/64786/error-handling-in-bash)
- [Bulletproof Bash Scripts: Mastering Error Handling](https://karandeepsingh.ca/posts/bash-error-handling-bulletproof-scripts/)
- [Error Handling in Bash: 5 Essential Methods](https://jsdev.space/error-handling-bash/)
- [Robust error handling in Bash](https://dev.to/banks/stop-ignoring-errors-in-bash-3co5)
- [Red Hat: Error handling in Bash scripts](https://www.redhat.com/sysadmin/error-handling-bash-scripting)
- [Learn Bash error handling by example](https://www.redhat.com/en/blog/bash-error-handling)

**Key insights**: 78% of production incidents from automation could be prevented with proper error handling. Use `set -euo pipefail`, trap handlers, and explicit error checking.

### Package Verification and Checksums

- [Ensuring Integrity: How to Verify Package Checksums in Linux](https://en.ittrip.xyz/linux/linux-checksum-verify)
- [Verify Installer Package Checksum - Informatica](https://docs.informatica.com/data-integration/powercenter/10-5-3/upgrading-from-version-10-4-0-and-later--10-5-3-/informatica-client-upgrade/verify-installer-package-checksum.html)
- [Checksum.sh - Verify install scripts](https://news.ycombinator.com/item?id=33375554)
- [RPM Package Verification](https://serverfault.com/questions/457368/verification-of-downloaded-package-with-rpm)

**Key insights**: Checksums protect against corruption and tampering. Common in package managers (npm SHA512, rpm GPG+checksum, apt checksums). Best for security-critical tools.

---

## Open Questions for User

### 1. Structured Logging Format Preference

**Option A**: Logsift format (simple prefix)
```

[INFO] Starting installation
[ERROR] Download failed in install-yazi.sh:84

```

**Option B**: JSON Lines format (more structured)
```json
{"level":"INFO","message":"Starting installation","timestamp":"2025-11-28T10:30:00Z"}
{"level":"ERROR","message":"Download failed","file":"install-yazi.sh","line":84}
```

**Recommendation**: Option A (simple prefix) - easier to read, logsift can parse both

### 2. Installation Log Location

**Option A**: `~/.dotfiles-install.log` (user home)
**Option B**: `management/.install.log` (in repo, gitignored)
**Option C**: No log, rely on verify-installed-packages.sh

**Recommendation**: Option C (no log) unless audit requirement exists

### 3. Checksum Requirement Level

**Option A**: Required for all tools (strict)
**Option B**: Optional, verify if present (recommended)
**Option C**: No checksums (current)

**Recommendation**: Option B (optional) - add for security-critical tools over time

### 4. Terminal Detection Override

Should we support:

- `DOTFILES_LOG_MODE=visual` - Force visual even in pipes
- `DOTFILES_LOG_MODE=structured` - Force structured even in terminal
- `DOTFILES_LOG_MODE=auto` - Auto-detect (default)

**Recommendation**: Support all three, default to auto

---

## Conclusion

This plan elevates management/ from personal dotfiles to production-quality infrastructure while preserving the core philosophy of fail fast, explicit, and straightforward design.

**Key decisions**:

1. ✅ **Structured logging**: Dual-mode (visual + parseable) - IMPLEMENT
2. ✅ **Error handling**: Traps, cleanup, line numbers - IMPLEMENT
3. ✅ **GitHub abstraction**: Generic installer - IMPLEMENT
4. ⚠️ **Checksums**: Optional, for security-critical tools - OPTIONAL
5. ❌ **Installation registry**: Keep packages.yml, skip complex state - SKIP
6. ❌ **Rollback capability**: Idempotency sufficient - SKIP

**Total estimated effort**: 15-25 hours over 2-4 weeks

**Expected outcome**: Production-ready installation scripts that maintain simplicity while gaining reliability, debuggability, and automation compatibility.

Ready to proceed with Phase 1 (Structured Logging)?
