# Error Handling Library Organization Plan

## Current State Analysis

### Three Shell Libraries

**1. logging.sh** (116 lines) - `platforms/common/.local/shell/logging.sh`

- **Purpose**: Core logging with [LEVEL] prefixes + unicode icons
- **Functions**:
  - `log_info()` - [INFO] + cyan + ● icon
  - `log_success()` - [INFO] + green + ✓ icon
  - `log_warning()` - [WARNING] + yellow + ▲ icon → stderr
  - `log_error(msg, file, line)` - [ERROR] + red + ✗ icon → stderr, file:line support
  - `log_debug()` - [DEBUG] → stderr (only if DEBUG=true)
  - `log_fatal(msg, file, line)` - [FATAL] + red + ✗ icon → stderr, file:line, **exits 1**
  - `die(msg)` - Calls log_error then exit 1

**2. formatting.sh** (762 lines) - `platforms/common/.local/shell/formatting.sh`

- **Purpose**: Visual formatting for headers, sections, banners
- **Structural Functions**:
  - `print_header/section/banner/title()` with color variants
  - `print_header_success/error/warning/info()` with emojis
  - All the visual "print_*" hierarchy
- **Legacy Status Functions** (should be removed?):
  - `print_success/error/warning/info()` - Old style with unicode icons (redundant with log_*)
- **Utility Functions**:
  - `die(msg)` - Calls print_error then exit 1 **[DUPLICATE]**
  - `fatal(msg)` - Prints error header and exits **[OVERLAP with log_fatal]**
  - `require_command(cmd)` - Checks single command **[SIMILAR to error-handling's require_commands]**

**3. error-handling.sh** (319 lines) - `management/common/lib/error-handling.sh`

- **Purpose**: Robust error handling with traps, cleanup, and verification helpers
- **Dependencies**: Sources logging.sh
- **Cleanup & Traps**:
  - `register_cleanup(cmd)` - Register cleanup functions for exit
  - `run_cleanup()` - Execute all registered cleanups
  - `enable_error_traps()` - Set up ERR and EXIT signal handlers
  - `error_trap_handler()` - ERR trap with stack traces
  - `exit_trap_handler()` - EXIT trap that runs cleanup
- **Helper Functions**:
  - `run_with_context(desc, cmd...)` - Run command with logged description
  - `require_commands(cmd1 cmd2...)` - Verify multiple commands exist, uses log_fatal
  - `verify_file(path, desc)` - Check file exists and not empty, uses log_fatal
  - `verify_directory(path, desc)` - Check directory exists, uses log_fatal
  - `create_directory(path, desc)` - Create dir with error handling, uses log_fatal
  - `download_file_with_retry(url, output, desc, retries)` - Download with retry, uses log_fatal
  - `safe_move(src, dest, desc)` - Move file with verification, uses log_fatal
- **Exit Helpers**:
  - `exit_success()` - Clean exit after running cleanup
  - `exit_error(msg)` - Error exit with cleanup, uses log_error
- **Debug Helpers**:
  - `enable_debug()` - Enable DOTFILES_DEBUG and set -x
  - `disable_debug()` - Disable debug mode

## Issues Identified

### 1. Duplicate/Conflicting Functions

| Function | logging.sh | formatting.sh | error-handling.sh | Issue |
|----------|-----------|---------------|-------------------|-------|
| `die()` | ✓ (log_error + exit) | ✓ (print_error + exit) | - | **DUPLICATE** - Same behavior, different implementation |
| `fatal()` | - | ✓ (print_header_error + exit) | - | **OVERLAP** - Similar to log_fatal but more visual |
| `log_fatal()` | ✓ (exits) | - | - | Core function, good |
| `require_command(s)` | - | ✓ (singular) | ✓ (plural) | **SIMILAR** - Naming confusion |

### 2. Location Issues

- **error-handling.sh** is in `management/common/lib/` but should be system-wide
- Only used by a few management scripts currently
- Should be available to ALL scripts like logging.sh and formatting.sh

### 3. Legacy Functions in formatting.sh

The old status functions in formatting.sh are now redundant:

- `print_success()` - Use `log_success()` instead
- `print_error()` - Use `log_error()` instead
- `print_warning()` - Use `log_warning()` instead
- `print_info()` - Use `log_info()` instead

BUT: These are still in formatting.sh and may be used by scripts we just updated!

## Proposed Solution

### Option A: Three-Library Architecture (Recommended)

Keep three distinct libraries with clear separation of concerns:

**1. logging.sh** - Core Logging

- Keep: log_info, log_success, log_warning, log_error, log_debug, log_fatal
- Keep: die() (canonical implementation)
- Location: `platforms/common/.local/shell/logging.sh` ✓ (already there)

**2. formatting.sh** - Visual Structure

- Keep: All print_header/section/banner/title functions and variants
- **Remove**: print_success/error/warning/info (redundant with log_*)
- **Remove**: die() (use logging.sh version)
- **Remove**: fatal() (redundant with log_fatal)
- **Keep**: require_command() but consider renaming to avoid confusion
- Location: `platforms/common/.local/shell/formatting.sh` ✓ (already there)

**3. error-handling.sh** - Error Traps & Utilities

- Keep: All cleanup, trap, helper, exit, and debug functions
- Dependencies: Sources logging.sh (already does)
- Location: **MOVE TO** `platforms/common/.local/shell/error-handling.sh` (promote to SHELL_DIR)

### Option B: Two-Library Architecture (Simpler)

Merge error-handling into logging, keep formatting separate:

**1. logging.sh** - Logging + Error Handling

- All log_* functions
- All error-handling functions (traps, cleanup, helpers)
- die() canonical implementation
- Would be ~435 lines (116 + 319)

**2. formatting.sh** - Visual Structure Only

- All print_* structural functions
- Remove status functions and utilities

### Option C: Mega-Library (Not Recommended)

Merge everything into one universal library - would be ~1200 lines, too monolithic.

## Recommended Approach: Option A

### Step 1: Promote error-handling.sh to SHELL_DIR

```bash
mv management/common/lib/error-handling.sh platforms/common/.local/shell/error-handling.sh
```

Update its header to indicate it's system-wide:

```bash
# Source error handling (system-wide library)
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/logging.sh"
```

### Step 2: Clean Up formatting.sh

Remove redundant functions:

- Remove `print_success()` (line 445-448)
- Remove `print_error()` (line 450-453)
- Remove `print_warning()` (line 456-459)
- Remove `print_info()` (line 462-465)
- Remove `die()` (line 473-476)
- Remove `fatal()` (line 479-485)
- Remove `require_command()` (line 488-493) OR rename to `has_command()` for clarity

This removes ~45 lines, reducing formatting.sh to ~717 lines focused purely on visual structure.

### Step 3: Update All Scripts

Scripts that currently use formatting.sh's die/fatal/print_info need updates:

- Replace `die` calls with `log_fatal` or import logging.sh
- Replace `print_info` with `log_info`
- Replace `print_success` with `log_success`
- Replace `print_warning` with `log_warning`
- Replace `print_error` with `log_error`

Actually... wait. We JUST did this conversion! So formatting.sh's old status functions are already obsolete.

### Step 4: Document the Three-Library System

Create clear documentation on when to use each:

**logging.sh** - Always source for any script that outputs status

- Use log_* for all status messages
- Use die() for simple fatal errors
- Use log_fatal() for fatal errors with file:line tracking

**formatting.sh** - Source for scripts with visual output (headers, sections)

- Use print_header/section/banner/title for structure
- Never use for status messages (that's logging.sh's job)

**error-handling.sh** - Source for complex scripts that need:

- Cleanup on exit (temp files, background processes)
- Error trapping with stack traces
- File/directory verification helpers
- Download/move operations with retry logic
- Debug mode support

## Migration Impact

### Scripts Currently Using error-handling.sh

Only 2 scripts source it currently:

1. `management/macos/setup/preferences.sh` - Uses enable_error_traps
2. Others may use indirectly through other libs

### Scripts That Might Benefit

Scripts that create temp files, download files, or need cleanup:

- All GitHub release installers (create temp dirs)
- Font download/install scripts
- Language manager installers
- Test scripts

## Questions to Answer

1. **Should we remove formatting.sh's legacy status functions now?**
   - Yes - we just converted all scripts to use log_*
   - Need to verify no scripts still use print_info/success/warning/error

2. **Should we keep die() in logging.sh or move to error-handling.sh?**
   - Keep in logging.sh - it's simple and commonly used
   - error-handling.sh provides exit_error() for more complex cases

3. **Should error-handling.sh be automatically sourced?**
   - No - only source when needed (traps, cleanup, helpers)
   - logging.sh and formatting.sh are more universal

4. **Should we create a "core.sh" that sources all three?**
   - No - explicit sourcing is better for clarity
   - Scripts should only load what they need

## Testing Plan

1. Move error-handling.sh to SHELL_DIR
2. Update error-handling.sh source path
3. Remove legacy functions from formatting.sh
4. Grep for any usage of removed functions
5. Update any remaining usage
6. Test a sample of scripts:
   - Simple script (logging only)
   - Visual script (logging + formatting)
   - Complex script (all three libraries)
7. Document in architecture docs

## Files to Update

After decision:

1. `platforms/common/.local/shell/error-handling.sh` (move + update paths)
2. `platforms/common/.local/shell/formatting.sh` (remove legacy functions)
3. Any scripts using removed functions
4. Documentation in `docs/architecture/`
5. Update CLAUDE.md instructions
