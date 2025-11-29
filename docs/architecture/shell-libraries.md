# Shell Libraries Architecture

The dotfiles repository provides three system-wide shell libraries for consistent, production-grade script development. Each library serves a distinct purpose and can be used independently or combined as needed.

## Library Overview

### logging.sh - Status Messages with Log Prefixes

**Location**: `~/.local/shell/logging.sh`
**Purpose**: Core logging for scripts that output status messages and may be logged/monitored
**Size**: ~116 lines

**When to use**:

- Scripts run unattended or in CI/CD
- Installation/update scripts that need logging
- Any script whose output might be piped to log files
- Scripts that need parseable output for tools like logsift

**Functions**:

- `log_info(message)` - [INFO] + cyan + ● icon
- `log_success(message)` - [INFO] + green + ✓ icon
- `log_warning(message)` - [WARNING] + yellow + ▲ icon → stderr
- `log_error(message, [file], [line])` - [ERROR] + red + ✗ icon → stderr
- `log_debug(message)` - [DEBUG] → stderr (only if DEBUG=true)
- `log_fatal(message, [file], [line])` - [FATAL] + red + ✗ icon → stderr, **exits 1**
- `die(message)` - Calls log_error then exit 1

**Output format**: Always includes [LEVEL] prefix for log parsers while remaining visually beautiful with colors and unicode icons.

**Example**:

```bash
#!/usr/bin/env bash
source "$HOME/.local/shell/logging.sh"

log_info "Starting backup process..."
log_success "Backed up 156 files"
log_warning "Skipped 3 files (permissions denied)"
log_error "Failed to backup config.yml" "$BASH_SOURCE" "$LINENO"
```

### formatting.sh - Visual Structure for Interactive Output

**Location**: `~/.local/shell/formatting.sh`
**Purpose**: Visual formatting for interactive scripts with headers, sections, banners
**Size**: ~730 lines

**When to use**:

- Interactive scripts run by humans at terminal
- Scripts with visual sections/phases
- Menu systems and interactive tools
- Scripts that prioritize visual appeal over parseability

**Structural Functions**:

- `print_header(text, [color])` - Thick borders, left-aligned
- `print_section(text, [color])` - Thin underline
- `print_banner(text, [color])` - Double bars (═)
- `print_title(text, [color])` - Centered, full-width
- Variants: `_success`, `_error`, `_warning`, `_info` with emojis

**Status Functions** (for visual-only scripts):

- `print_success(message)` - Green + ✓ icon (no [LEVEL] prefix)
- `print_error(message)` - Red + ✗ icon (no [LEVEL] prefix)
- `print_warning(message)` - Yellow + ▲ icon (no [LEVEL] prefix)
- `print_info(message)` - Cyan + ● icon (no [LEVEL] prefix)

**Utility**:

- `has_command(cmd)` - Check if single command exists (returns 0/1)

**Example**:

```bash
#!/usr/bin/env bash
source "$HOME/.local/shell/formatting.sh"

print_header "Backup Tool" "blue"
print_section "Phase 1: Scanning"

# Visual-only script - no logging needed
for file in *.txt; do
  print_success "Scanned: $file"
done

print_header_success "Backup Complete"
```

### error-handling.sh - Robust Error Management

**Location**: `~/.local/shell/error-handling.sh`
**Purpose**: Error trapping, cleanup handlers, and verification utilities
**Size**: ~319 lines
**Dependencies**: Sources logging.sh

**When to use**:

- Scripts that create temporary files/directories
- Download/installation scripts needing retry logic
- Scripts requiring cleanup on exit (success or failure)
- Complex scripts needing stack traces for debugging
- Any script where errors must be trapped and logged

**Core Functions**:

*Cleanup & Traps*:

- `enable_error_traps()` - Set up ERR and EXIT signal handlers
- `register_cleanup(cmd)` - Register cleanup commands for exit
- `run_cleanup()` - Execute all registered cleanups

*Verification Helpers*:

- `require_commands(cmd1 cmd2...)` - Verify commands exist, fatal if missing
- `verify_file(path, desc)` - Check file exists and not empty
- `verify_directory(path, desc)` - Check directory exists
- `create_directory(path, desc)` - Create dir with error handling

*Advanced Helpers*:

- `run_with_context(desc, cmd...)` - Run command with logged description
- `download_file_with_retry(url, output, desc, [retries])` - Download with retry
- `safe_move(src, dest, desc)` - Move file with verification

*Exit & Debug*:

- `exit_success()` - Clean exit after running cleanup
- `exit_error(message)` - Error exit with cleanup
- `enable_debug()` / `disable_debug()` - Toggle debug mode

**Example**:

```bash
#!/usr/bin/env bash
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/error-handling.sh"
enable_error_traps

# Register cleanup
TMP_DIR=$(mktemp -d)
register_cleanup "rm -rf $TMP_DIR"

# Verify prerequisites
require_commands curl tar jq

# Download with retry
download_file_with_retry \
  "https://example.com/package.tar.gz" \
  "$TMP_DIR/package.tar.gz" \
  "Package archive" \
  3

# Verify and install
verify_file "$TMP_DIR/package.tar.gz" "Downloaded package"
safe_move "$TMP_DIR/binary" "$HOME/.local/bin/binary" "Binary"

# Cleanup runs automatically on exit
exit_success
```

## Decision Guide: log_*vs print_*

### Use log_* functions when

✅ Script output will be logged to files
✅ Script runs unattended (cron, CI/CD, automated)
✅ Output needs to be parseable by log aggregators
✅ Script is part of installation/update process
✅ You need [LEVEL] prefixes for filtering/monitoring

**Examples**: install.sh, update.sh, package installers, CI scripts

### Use print_* status functions when

✅ Script is purely interactive (run by human at terminal)
✅ Visual appeal is priority over parseability
✅ Output will NEVER be piped to log files
✅ Script is a menu system or interactive tool
✅ Logging overhead not needed

**Examples**: backup-dirs, interactive menus, demo scripts, dev tools

### Use both when

✅ Script has both logged sections (log_*) and visual structure (print_header/section)
✅ Most management scripts fall into this category

**Example**:

```bash
source "$HOME/.local/shell/logging.sh"
source "$HOME/.local/shell/formatting.sh"

print_header "System Update" "blue"

print_section "Phase 1: Package Updates"
log_info "Updating apt packages..."
sudo apt update && sudo apt upgrade -y
log_success "Packages updated"

print_section "Phase 2: Cleanup"
log_info "Removing old kernels..."
sudo apt autoremove -y
log_success "Cleanup complete"

print_header_success "Update Complete"
```

## Common Patterns

### Simple Status Script (logging only)

```bash
#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.local/shell/logging.sh"

log_info "Processing files..."
# do work
log_success "Processed 42 files"
```

### Visual Interactive Script (formatting only)

```bash
#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.local/shell/formatting.sh"

print_header "File Manager" "cyan"
print_info "Loading files..."
# show menu
print_success "File selected"
```

### Installation Script (logging + formatting)

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_header "Install Package" "blue"

print_section "Phase 1: Download"
log_info "Downloading package..."
# download
log_success "Package downloaded"

print_header_success "Installation Complete"
```

### Complex Script with Error Handling

```bash
#!/usr/bin/env bash
set -euo pipefail

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/error-handling.sh"
source "$SHELL_DIR/formatting.sh"
enable_error_traps

# Setup cleanup
TMP_DIR=$(mktemp -d)
register_cleanup "rm -rf $TMP_DIR"

print_header "Build Project" "blue"

# Verify prerequisites
require_commands node npm git

print_section "Phase 1: Dependencies"
run_with_context "Installing dependencies" npm install

print_section "Phase 2: Build"
run_with_context "Building project" npm run build

print_header_success "Build Complete"
exit_success
```

## Function Reference Quick Lookup

### Logging (with [LEVEL] prefixes)

| Function | Purpose | Output | Exit Code |
|----------|---------|--------|-----------|
| `log_info` | Informational message | [INFO] ● cyan | - |
| `log_success` | Success message | [INFO] ✓ green | - |
| `log_warning` | Warning message | [WARNING] ▲ yellow | - |
| `log_error` | Error message | [ERROR] ✗ red | - |
| `log_debug` | Debug message (DEBUG=true) | [DEBUG] gray | - |
| `log_fatal` | Fatal error | [FATAL] ✗ red | **1** |
| `die` | Simple fatal error | [ERROR] ✗ red | **1** |

### Formatting - Status (no [LEVEL] prefixes)

| Function | Purpose | Output | Exit Code |
|----------|---------|--------|-----------|
| `print_success` | Visual success | ✓ green | - |
| `print_error` | Visual error | ✗ red | - |
| `print_warning` | Visual warning | ▲ yellow | - |
| `print_info` | Visual info | ● cyan | - |

### Formatting - Structure

| Function | Purpose | Visual Style |
|----------|---------|--------------|
| `print_header` | Main header | Thick borders (━) |
| `print_section` | Section header | Thin underline (─) |
| `print_banner` | Tool banner | Double bars (═) |
| `print_title` | Page title | Centered, full-width |

Each has color variants and `_success/_error/_warning/_info` variants with emojis.

### Error Handling

| Function | Purpose |
|----------|---------|
| `enable_error_traps` | Set up ERR/EXIT handlers |
| `register_cleanup` | Add cleanup command |
| `require_commands` | Verify multiple commands |
| `verify_file` | Check file exists/not empty |
| `verify_directory` | Check directory exists |
| `create_directory` | Create dir with error handling |
| `download_file_with_retry` | Download with retry logic |
| `safe_move` | Move file with verification |
| `run_with_context` | Run command with logging |
| `exit_success` | Clean exit with cleanup |
| `exit_error` | Error exit with cleanup |

## Sourcing Patterns

### From Scripts in Repo (use DOTFILES_DIR)

```bash
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
```

### From Scripts After Installation (use SHELL_DIR or HOME)

```bash
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/logging.sh"
source "$SHELL_DIR/formatting.sh"
source "$SHELL_DIR/error-handling.sh"
```

### From Interactive Shell (already sourced in .zshrc)

Functions are available directly in interactive shells - no need to source.

## Best Practices

1. **Always use log_* for installation/update scripts** - They need parseability
2. **Always use print_* for purely visual tools** - No logging overhead
3. **Source error-handling.sh for complex scripts** - Automatic cleanup is valuable
4. **Use file:line in log_error/log_fatal** - Makes debugging easier
5. **Register cleanup early** - Before creating temp files
6. **Prefer log_fatal over die** when you have file:line info
7. **Use print_header/section for visual structure** - Even in logged scripts
8. **Don't mix print_success with log_info** - Pick one style per script

## See Also

- `docs/architecture/structured-logging.md` - Details on log parsing
- `platforms/common/.local/shell/colors.sh` - Color definitions
- `.claude/skills/symlinks-developer` - Symlinks manager documentation
