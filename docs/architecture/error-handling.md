# Error Handling Library

## Overview

The Error Handling library provides robust error handling for management scripts with automatic cleanup, line number tracking, and consistent error reporting. It's built on top of the Structured Logging library to provide a complete production-grade foundation.

## Philosophy

Error handling in this repository follows the "fail fast and loud" principle:

- **Exit immediately on errors** - No silent failures or defensive programming
- **Clear, actionable messages** - Include file:line references for debugging
- **Automatic cleanup** - No orphaned processes, temp files, or partial state
- **Trap-based handling** - ERR and EXIT traps ensure consistent behavior
- **Simple patterns** - Reusable library with straightforward usage

## Architecture

### Library Chain

```text
script.sh
  └─> error-handling.sh
       ├─> set -euo pipefail (error safety)
       ├─> Trap handlers (ERR, EXIT)
       ├─> Cleanup registration
       └─> logging.sh
            └─> colors.sh
```

Sourcing `error-handling.sh` and calling `enable_error_traps` provides:

- Error safety (`set -euo pipefail`)
- Automatic cleanup on exit (success or failure)
- Structured logging (dual-mode: visual/structured)
- File:line references in error messages
- Stack traces in debug mode

## Core Functions

### Enable Error Handling

```bash
source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps
```

**What it does:**

- Sets `set -euo pipefail` (exit on error, undefined variables, pipe failures)
- Enables `set -o errtrace` (trap inheritance in functions/subshells)
- Registers ERR trap for error handling
- Registers EXIT trap for cleanup
- Sets PS4 for enhanced error output with line numbers

### Cleanup Registration

```bash
# Register cleanup function to run on exit
TMP_DIR=$(mktemp -d)
register_cleanup "rm -rf $TMP_DIR"

# Multiple cleanups can be registered
register_cleanup "pkill -f my-process || true"
register_cleanup "rm -f /tmp/lockfile"
```

**Cleanup runs:**

- On successful exit
- On error exit
- On script interruption (Ctrl-C)
- Even if script fails partway through

**Example:**

```bash
#!/usr/bin/env bash
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps

# Setup temp directory
TMP_DIR=$(mktemp -d)
register_cleanup "rm -rf $TMP_DIR"

# Do work (temp dir automatically cleaned up on exit)
curl -fsSL "$URL" -o "$TMP_DIR/file.tar.gz"
tar -xzf "$TMP_DIR/file.tar.gz" -C "$TMP_DIR"
mv "$TMP_DIR/binary" ~/.local/bin/

# No manual cleanup needed - registered cleanup runs automatically
```

### Error Logging

```bash
# Fatal error (logs and exits)
log_fatal "Failed to download file" "${BASH_SOURCE[0]}" "$LINENO"

# Error (logs to stderr, doesn't exit)
log_error "Retry failed" "${BASH_SOURCE[0]}" "$LINENO"

# Warning
log_warning "Using fallback method"

# Info
log_info "Downloading package..."

# Success
log_success "Installation complete"
```

**Output modes:**

**Terminal (visual):**

```yaml
✗ Failed to download file
  at install-tool.sh:42
```

**Pipe/log (structured):**

```bash
[FATAL] Failed to download file in install-tool.sh:42
```

### Stack Traces

Enable debug mode for stack traces:

```bash
DOTFILES_DEBUG=true bash management/common/install/github-releases/tool.sh
```

**Output:**

```bash
[ERROR] Command failed with exit code 1 in install-tool.sh:42
[ERROR] Failed command: curl -fsSL https://example.com/file.tar.gz
[INFO] Stack trace:
42 install-tool.sh main
17 install-tool.sh source
```

## Helper Functions

### Command Verification

```bash
# Require commands to be available
require_commands curl tar unzip

# Exits with clear error if missing:
# [FATAL] Missing required commands: tar unzip
```

### File Verification

```bash
# Verify file exists and is not empty
verify_file "$TMP_DIR/download.tar.gz" "Downloaded archive"

# Exits if:
# - File doesn't exist: [FATAL] Downloaded archive not found: /tmp/xyz/download.tar.gz
# - File is empty: [FATAL] Downloaded archive is empty: /tmp/xyz/download.tar.gz
```

### Safe Exit Functions

```bash
# Success exit (runs cleanup, exits 0)
exit_success

# Fatal exit (logs error, runs cleanup, exits 1)
exit_with_error "Installation failed"
```

## Integration with GitHub Release Installer

The GitHub Release Installer library assumes `error-handling.sh` has been sourced:

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

# Now all functions have:
# - Automatic cleanup via register_cleanup()
# - Structured logging via log_*()
# - Error traps for fail-fast behavior
```

**Example from `install_from_tarball()`:**

```bash
install_from_tarball() {
  local binary_name="$1"
  local download_url="$2"

  local temp_tarball="/tmp/${binary_name}.tar.gz"

  # Download with automatic cleanup on failure
  log_info "Downloading $binary_name..."
  if ! curl -fsSL "$download_url" -o "$temp_tarball"; then
    log_fatal "Failed to download from $download_url" "${BASH_SOURCE[0]}" "$LINENO"
  fi
  register_cleanup "rm -f '$temp_tarball' 2>/dev/null || true"

  # Extract (error handling automatic via set -e)
  log_info "Extracting..."
  tar -xzf "$temp_tarball" -C /tmp

  # Install
  mv "/tmp/$binary_name" "$HOME/.local/bin/"

  # Cleanup runs automatically via trap
}
```

## Usage Patterns

### Basic Script Template

```bash
#!/usr/bin/env bash

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps

print_banner "Installing Tool"

# Setup
TMP_DIR=$(mktemp -d)
register_cleanup "rm -rf $TMP_DIR"

# Do work
require_commands curl tar
log_info "Downloading..."
curl -fsSL "$URL" -o "$TMP_DIR/file.tar.gz"
verify_file "$TMP_DIR/file.tar.gz" "Downloaded file"

log_info "Extracting..."
tar -xzf "$TMP_DIR/file.tar.gz" -C "$TMP_DIR"

log_info "Installing..."
mv "$TMP_DIR/tool" ~/.local/bin/

log_success "Installation complete"
exit_success
```

### Error Scenarios

**Network failure:**

```bash
curl -fsSL "$URL" -o "$TMP_DIR/file.tar.gz"
# Fails with:
# [ERROR] Command failed with exit code 6 in install-tool.sh:23
# [ERROR] Failed command: curl -fsSL https://example.com/file.tar.gz
# [INFO] Running cleanup...
```

**Missing dependency:**

```bash
require_commands curl tar jq
# Fails with:
# [FATAL] Missing required commands: jq
```

**Empty download:**

```bash
verify_file "$TMP_DIR/file.tar.gz" "Downloaded file"
# Fails with:
# [FATAL] Downloaded file is empty: /tmp/xyz/file.tar.gz
```

## Design Decisions

### Why Traps Instead of Try/Catch?

**Bash doesn't have try/catch** - traps are the idiomatic way to handle errors and cleanup.

**Benefits:**

- Automatic cleanup even on unexpected failures
- Works with `set -e` (fail fast)
- Handles interruptions (Ctrl-C)
- Simpler than manual error checking everywhere

### Why Not Retry Logic?

**Rejected:** Automatic retry with exponential backoff

**Chosen:** Fail fast, user retries if needed

**Rationale:**

- Aligns with "fail fast and loud" philosophy
- Network failures are usually persistent (need fix, not retry)
- Retry logic adds complexity for rare benefit
- User can re-run script (idempotent design)

### Why File:Line References?

**Debugging speed:** Knowing exact failure location is critical.

**Before (no context):**

```yaml
Error: Failed to download file
```

**After (with context):**

```bash
[ERROR] Failed to download file in install-tool.sh:42
```

Jump directly to line 42, fix the issue. **10x faster debugging**.

## Error Safety Audit

All management scripts should use error-handling.sh:

```bash
# Check scripts using error handling
grep -l "source.*error-handling.sh" management/**/*.sh | wc -l

# Check scripts using old formatting.sh  
grep -l "source.*formatting.sh" management/**/*.sh | wc -l
```

**Current status:**

- ✅ All 16 GitHub release installers use error-handling.sh
- ✅ All converted scripts have automatic cleanup
- ✅ All errors include file:line references

## Testing Error Handling

### Test Cleanup

```bash
# Add debug output
register_cleanup "echo 'Cleanup running'; rm -rf /tmp/test"

# Run script, verify cleanup happens:
# - On success (exit 0)
# - On error (exit 1)
# - On interruption (Ctrl-C)
```

### Test Error Reporting

```bash
# Trigger error, verify output includes:
# - Error message
# - File name
# - Line number
# - Structured format (if piped)
```

### Test Stack Traces

```bash
DOTFILES_DEBUG=true bash script.sh

# Verify stack trace shows:
# - Function call chain
# - Line numbers
# - File names
```

## Related Documentation

- [Shell Libraries](shell-libraries.md)
- [GitHub Release Installer](github-release-installer.md)
- Production-Grade Management Enhancements (planning doc)

## Files

**Library:**

- `platforms/common/.local/shell/error-handling.sh` (319 lines)
- `platforms/common/.local/shell/logging.sh` (116 lines)

**All scripts using error-handling:**

- All 16 GitHub release installers
- All converted management scripts
