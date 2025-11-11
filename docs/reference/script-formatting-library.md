# Shell Formatting Library Reference

Portable shell script formatting and color utilities for consistent, readable script output.

## Location

**Two files for clean separation:**

- `platforms/common/shell/colors.sh` - Color definitions and color functions
- `platforms/common/shell/formatting.sh` - Formatting functions (sources colors.sh)

**Sourced system-wide**: `formatting.sh` is automatically loaded in your shell session via `.zshrc`, making all functions available in your terminal and any scripts.

## Usage

### In Interactive Shell

All functions are already available in your shell:

```bash
# Just use them directly
print_success "Command completed successfully"
print_error "Something went wrong"
```

### In Scripts (Within Dotfiles)

Already available via $PATH, but can source explicitly:

```bash
#!/usr/bin/env bash
source "$HOME/shell/formatting.sh"

print_header "My Script"
print_section "Phase 1: Setup"
print_success "Setup complete"
```

### Copy to Other Projects

The libraries are self-contained and portable. Copy both files to your project:

```bash
cp platforms/common/shell/colors.sh ~/my-project/lib/
cp platforms/common/shell/formatting.sh ~/my-project/lib/
```

Then source formatting.sh in your scripts (it will source colors.sh):

```bash
source "$(dirname "$0")/lib/formatting.sh"
```

Or if you only need colors:

```bash
source "$(dirname "$0")/lib/colors.sh"
```

## Quick Reference

### Titles (Centered)

```bash
print_title "My Application"                  # Blue, full terminal width, 5-space padding
print_title_success "Setup Complete"          # Green with ✅, full width, 5-space padding
```

Titles automatically use the full terminal width (via `tput cols`) with 5 spaces of padding on each side for visual breathing room.

### Headers (Left-aligned)

```bash
print_header "Installation Starting"          # Blue thick borders
print_header_success "Installation Complete"  # Green with ✅
print_header_error "Installation Failed"      # Red with ❌
print_section "Phase 1: Packages"             # Cyan, no borders
```

### Status Messages

```bash
print_success "Package installed"             # Green with ✓
print_error "Installation failed"             # Red with ✗
print_warning "This might take a while"       # Yellow with ⚠️
print_info "Downloading packages..."          # Cyan with ℹ️
```

### Colors

```bash
print_red "Error text"
print_green "Success text"
print_yellow "Warning text"
print_blue "Info text"
print_cyan "Highlight text"

# Or use color variables directly
echo -e "${COLOR_GREEN}Success!${COLOR_RESET}"
```

### Utilities

```bash
die "Fatal error occurred"                    # Print error and exit
fatal "Cannot continue"                       # Print error header and exit
require_command "git" || die "git required"   # Check if command exists
```

### Additional Utilities

```bash
center_text "Some Text"                       # Center text in terminal
section_separator                             # Underlined full-width separator
terminal_width_separator "="                  # Full-width character separator
```

### Demo/Testing

```bash
test_formatting                               # Show all formatting options
```

## Color Variables

### Basic Colors

- `COLOR_BLACK`, `COLOR_RED`, `COLOR_GREEN`, `COLOR_YELLOW`
- `COLOR_BLUE`, `COLOR_MAGENTA`, `COLOR_CYAN`, `COLOR_WHITE`

### Bright Colors

- `COLOR_BRIGHT_BLACK`, `COLOR_BRIGHT_RED`, `COLOR_BRIGHT_GREEN`
- `COLOR_BRIGHT_YELLOW`, `COLOR_BRIGHT_BLUE`, `COLOR_BRIGHT_MAGENTA`
- `COLOR_BRIGHT_CYAN`, `COLOR_BRIGHT_WHITE`

### Aliases

Shorter aliases for convenience:

- `NC`, `RED`, `GREEN`, `YELLOW`, `BLUE`, `CYAN`

### Reset

- `COLOR_RESET` - Reset to default colors

## Unicode Characters

### Status Indicators

- `UNICODE_CHECK` (✓)
- `UNICODE_CROSS` (✗)
- `UNICODE_WARNING` (⚠️)
- `UNICODE_INFO` (ℹ️)
- `UNICODE_CHECKBOX_CHECKED` (✅)
- `UNICODE_CHECKBOX_UNCHECKED` (❌)

### Formatting

- `BOX_THICK` (━)
- `BOX_THIN` (─)

## Examples

### Basic Script

```bash
#!/usr/bin/env bash
source "$(dirname "$0")/lib/script-formatting.sh"

set -euo pipefail

print_header "Package Installer"

print_section "Phase 1: Checking Dependencies"
if require_command "git"; then
  print_success "git found"
else
  print_error "git not found"
  die "Please install git first"
fi

print_section "Phase 2: Installing Packages"
print_info "Downloading package list..."
print_info "Installing packages..."
print_success "All packages installed"

print_header_success "Installation Complete"
```

### Multi-Phase Installation

```bash
print_header "System Setup"

print_section "[1/3] System Packages"
print_info "Updating package lists..."
print_success "Packages updated"

print_section "[2/3] Development Tools"
print_info "Installing Node.js..."
print_success "Node.js installed"

print_section "[3/3] Configuration"
print_info "Creating config files..."
print_success "Configuration complete"

print_header_success "Setup Complete"
echo ""
print_cyan "Next steps:"
echo "  - Restart your terminal"
echo "  - Run 'npm install'"
```

### With Error Handling

```bash
print_header "Deployment Script"

print_section "Validating Environment"
if ! require_command "docker"; then
  print_header_error "Deployment Failed"
  print_error "Docker is required but not installed"
  echo ""
  print_cyan "Install Docker:"
  echo "  - macOS: brew install docker"
  echo "  - Linux: apt install docker.io"
  exit 1
fi

print_success "Environment validated"
print_header_success "Deployment Complete"
```

## Philosophy

The library follows the visual formatting philosophy:

- **Color-coded hierarchy**: Blue for main sections, Cyan for subsections, Green/Red for status
- **Sparing emoji use**: `✓`/`✗` for items, `✅`/`❌` for final status
- **Spacing**: Extra blank lines around major sections for breathing room
- **Consistency**: Same patterns across all scripts

## Portability

- Uses ANSI escape codes (no `tput` dependency)
- Pure bash, no external dependencies
- Works on macOS, Linux, WSL
- Can be copied to any bash project

## When to Use Conservative Formatting

If your script's output will be ingested by log aggregation systems (Splunk, ELK, etc.), consider using plain text instead:

```bash
# Instead of:
print_success "Done"

# Use:
echo "Done"
```

Or set a variable to toggle formatting:

```bash
PLAIN_OUTPUT="${PLAIN_OUTPUT:-false}"

if [[ "$PLAIN_OUTPUT" == "true" ]]; then
  echo "Success"
else
  print_success "Success"
fi
```

## See Also

- [Dotfiles Philosophy](../../README.md#dotfiles-philosophy)
- [Visual Formatting and Emoji](../../README.md#visual-formatting-and-emoji)
- [~/CLAUDE.md](../../CLAUDE.md) - Global formatting guidelines
