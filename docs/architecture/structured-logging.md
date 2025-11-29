# Structured Logging

How the dotfiles management scripts use dual-mode logging for both human readability and log parsing.

## Overview

The management/ scripts use a dual-mode logging system that automatically adapts output based on context:

- **Terminal mode**: Beautiful colors, emojis, visual formatting (default when outputting to terminal)
- **Structured mode**: Clean `[LEVEL]` prefixes with file:line references (automatic when piped or redirected)

This enables both excellent human readability during interactive use and reliable log parsing for debugging and automation.

## Why Dual-Mode?

The dotfiles philosophy prioritizes human-readable output (colors, emojis, visual hierarchy), but production-grade systems need structured logs for parsing and analysis.

Instead of choosing one over the other, the structured logging library provides both:

```bash
# Interactive terminal use - Visual mode
./install.sh
  ✓ Homebrew already installed
  ● Installing system packages...

# Piped to log file - Structured mode
./install.sh 2>&1 | tee install.log
[INFO] ✓ Homebrew already installed
[INFO] Installing system packages...
```

## Usage

Source the structured logging library instead of formatting.sh:

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/structured-logging.sh"

# Use logging functions
log_info "Starting installation"
log_success "Package installed"
log_warning "Configuration not found"
log_error "Download failed" "${BASH_SOURCE[0]}" "$LINENO"
```

## Available Functions

### Basic Logging

```bash
log_info "message"       # Info message with ● or [INFO]
log_success "message"    # Success message with ✓ or [INFO] ✓
log_warning "message"    # Warning message with ▲ or [WARNING]
log_error "message" ["file"] ["line"]  # Error with optional context
log_fatal "message" ["file"] ["line"]  # Fatal error + exit 1
```

### Structural Elements

```bash
log_section "Section Name" ["color"]  # Section header with underline
log_header "Header Text" ["color"]    # Header with thick borders
log_banner "Banner Text" ["color"]    # Banner with double bars
log_title "Title Text" ["color"]      # Centered title (full-width)
```

### Success/Error Variants

```bash
log_header_success "message"  # Success header with green borders
log_header_error "message"    # Error header with red borders
log_title_success "message"   # Success title (centered)
log_banner_success "message"  # Success banner
```

### Backward Compatibility

All `print_*` functions from formatting.sh still work:

```bash
print_info "message"     # Works in both modes
print_success "message"  # Works in both modes
print_error "message"    # Works in both modes
```

## Output Modes

### Auto-Detection

The library automatically detects the appropriate mode:

```bash
# Terminal (TTY) - Uses visual mode
./install.sh

# Pipe - Uses structured mode
./install.sh | cat
./install.sh 2>&1 | tee install.log

# Redirect - Uses structured mode
./install.sh > install.log 2>&1
```

### Manual Override

Force a specific mode with environment variable:

```bash
# Force visual mode (even when piped)
DOTFILES_LOG_MODE=visual ./install.sh | cat

# Force structured mode (even in terminal)
DOTFILES_LOG_MODE=structured ./install.sh
```

### Check Current Mode

```bash
current_mode=$(get_log_mode)
echo "Running in $current_mode mode"
```

## Output Examples

### Visual Mode (Terminal)

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Phase 3 - GitHub Release Tools
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Installing LazyGit
═══════════════════════════════════════════

  ● Fetching latest version...
  ● Target: v0.40.2 (Darwin/arm64 → Darwin_arm64)
  ● Downloading...
  ✓ Download complete
  ● Extracting...
  ● Installing to ~/.local/bin...
  ✓ lazygit installed

═══════════════════════════════════════════
✅ LazyGit installation complete
═══════════════════════════════════════════
```

### Structured Mode (Piped/Logged)

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HEADER] Phase 3 - GitHub Release Tools
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Installing LazyGit
═══════════════════════════════════════════

[INFO] Fetching latest version...
[INFO] Target: v0.40.2 (Darwin/arm64 → Darwin_arm64)
[INFO] Downloading...
[INFO] ✓ Download complete
[INFO] Extracting...
[INFO] Installing to ~/.local/bin...
[INFO] ✓ lazygit installed

═══════════════════════════════════════════
✅ LazyGit installation complete
═══════════════════════════════════════════
```

## Error Message Format

Errors include file:line references for quick debugging:

### Visual Mode

```text
  ✗ Download failed
  at install-lazygit.sh:76
```

### Structured Mode

```text
[ERROR] Download failed in install-lazygit.sh:76
```

This format is parseable by logsift and other log analysis tools for automated error detection and code navigation.

## Integration with Logsift

The structured format is designed for logsift compatibility:

```bash
# Monitor installation in real-time
./install.sh 2>&1 | logsift monitor

# Analyze log file after installation
./install.sh 2>&1 | tee install.log
logsift analyze install.log

# Extract errors with context
logsift analyze install.log --errors-only
```

Logsift can:

- Detect `[ERROR]` and `[WARNING]` prefixes
- Extract file:line references for code navigation
- Highlight errors in red, warnings in yellow
- Provide context lines around errors

## Migration Guide

### From formatting.sh to structured-logging.sh

Update the source statement:

```bash
# Before
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# After
source "$DOTFILES_DIR/management/common/lib/structured-logging.sh"
```

All `print_*` functions continue to work unchanged. No other changes required.

### Adding Error Context

Enhanced error reporting with file:line information:

```bash
# Before
log_error "Download failed"

# After (recommended)
log_error "Download failed" "${BASH_SOURCE[0]}" "$LINENO"
```

The file:line parameters are optional but highly recommended for debugging.

## Implementation Details

### Mode Detection

```bash
detect_log_mode() {
  # Manual override takes precedence
  if [[ -n "${DOTFILES_LOG_MODE:-}" ]]; then
    echo "$DOTFILES_LOG_MODE"
    return
  fi

  # Auto-detect: stdout to terminal = visual, else structured
  if [[ -t 1 ]]; then
    echo "visual"
  else
    echo "structured"
  fi
}
```

### Visual Mode

In visual mode, the library:

1. Sources `platforms/common/.local/shell/formatting.sh`
2. Uses all existing formatting functions (colors, emojis, borders)
3. Provides backward compatibility with `print_*` functions

### Structured Mode

In structured mode, the library:

1. Provides simple implementations of all logging functions
2. Uses `[LEVEL]` prefixes for parseable output
3. Sends errors to stderr (`>&2`)
4. Includes file:line references where provided

## Best Practices

### Always Provide Error Context

```bash
# Good
log_error "Download failed" "${BASH_SOURCE[0]}" "$LINENO"

# Acceptable
log_error "Download failed"
```

### Use Appropriate Log Levels

```bash
log_info "Starting download..."        # Normal progress
log_success "Download complete"         # Positive outcome
log_warning "Using fallback mirror"     # Non-critical issue
log_error "Download failed"             # Recoverable error
log_fatal "Network unreachable"         # Unrecoverable error (exits)
```

### Structure Your Output

Use structural functions to organize output:

```bash
log_header "Phase 1 - System Setup" "blue"
log_section "Installing Dependencies" "cyan"
log_info "Installing package..."
log_success "Package installed"
```

### Preserve Stderr for Errors

Always send errors to stderr:

```bash
# The library handles this automatically
log_error "message"    # Goes to stderr
log_warning "message"  # Goes to stderr
log_info "message"     # Goes to stdout
```

## Testing

Test both modes work correctly:

```bash
# Test visual mode
DOTFILES_LOG_MODE=visual ./your-script.sh

# Test structured mode
DOTFILES_LOG_MODE=structured ./your-script.sh

# Test auto-detection
./your-script.sh              # Visual (in terminal)
./your-script.sh | cat        # Structured (piped)
```

Verify logsift can parse output:

```bash
./your-script.sh 2>&1 | tee test.log
logsift analyze test.log
```

## See Also

- [Error Handling](error-handling.md) - Error handling patterns and trap usage
- [Design Principles](design-principles.md) - Philosophy behind visual formatting
- [Logsift Guide](../claude-code/log-monitoring-research.md) - Log monitoring with logsift
