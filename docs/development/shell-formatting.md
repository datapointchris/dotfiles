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

### Titles (Centered, Full-Width)

```bash
print_title "My Application"                  # Plain (no color)
print_title "My Application" "blue"           # Blue title
print_title "My Application" "orange"         # Orange title
print_title_success "Setup Complete"          # Green with ✅
print_title_info "Information"                # Cyan with ℹ️
print_title_warning "Caution"                 # Yellow with ⚠️
print_title_error "Failed"                    # Red with ❌
```

Titles automatically use the full terminal width (via `tput cols`) with 5 spaces of padding on each side for visual breathing room.

### Headers (Left-Aligned, Thick Borders)

```bash
print_header "Installation"                   # Plain (no color)
print_header "Installation" "blue"            # Blue thick borders
print_header_success "Installation Complete"  # Green with ✅
print_header_info "Information"               # Cyan with ℹ️
print_header_warning "Caution"                # Yellow with ⚠️
print_header_error "Installation Failed"      # Red with ❌
```

### Banners (Double Bars)

```bash
print_banner "ripgrep"                        # Plain (no color)
print_banner "ripgrep" "orange"               # Orange double bars
print_banner_success "Success"                # Green with ✅
print_banner_info "Information"               # Cyan with ℹ️
print_banner_warning "Caution"                # Yellow with ⚠️
print_banner_error "Error"                    # Red with ❌
```

### Sections (Thin Underline)

```bash
print_section "Phase 1: Packages"             # Plain (no color)
print_section "Phase 1: Packages" "cyan"      # Cyan underline
print_section_success "Success"               # Green with ✅
print_section_info "Information"              # Cyan with ℹ️
print_section_warning "Caution"               # Yellow with ⚠️
print_section_error "Error"                   # Red with ❌
```

### Status Messages (Unicode Icons)

```bash
print_success "Package installed"             # Green with ✓
print_error "Installation failed"             # Red with ✗
print_warning "This might take a while"       # Yellow with ▲
print_info "Downloading packages..."          # Cyan with ●
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
formatting_demo                               # Show usage menu
formatting_demo all                           # Show all formatting examples
formatting_demo titles                        # Show only title variants and colors
formatting_demo headers                       # Show only header variants and colors
formatting_demo banners                       # Show only banner variants and colors
formatting_demo sections                      # Show only section variants and colors
formatting_demo status                        # Show only status message functions
formatting_demo colors                        # Show only color functions
formatting_demo utilities                     # Show only utility functions
```

The demo shows all 17 available colors plus all 4 semantic variants for each structural type.

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

### Status Indicators (Unicode - for status messages)

- `UNICODE_CHECK` (✓) - Success
- `UNICODE_CROSS` (✗) - Error
- `UNICODE_WARNING` (▲) - Warning
- `UNICODE_INFO` (●) - Info

### Structural Variant Icons (Emoji - for headers/titles)

- `EMOJI_SUCCESS` (✅) - Success
- `EMOJI_ERROR` (❌) - Error
- `EMOJI_WARNING` (⚠️) - Warning
- `EMOJI_INFO` (ℹ️) - Info

### Box Drawing Characters

- `BOX_THICK` (━) - Thick borders for titles and headers
- `BOX_THIN` (─) - Thin underlines for sections
- `BOX_DOUBLE` (═) - Double bars for banners

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

The formatting library is designed around human-readable script output with clear visual hierarchy and semantic meaning.

### Structural Types

Four main structural types for organizing output:

1. **Titles** - Centered, full terminal width with thick borders (━), for main script headers
2. **Headers** - Left-aligned with thick borders (━), for major sections
3. **Banners** - Double-bar borders (═), for distinctive tool or feature sections
4. **Sections** - Simple text with thin underline (─), for subsections

Each structural type accepts an **optional color parameter** for customization, with no default color (must be explicitly specified).

### Color System

**17 available colors** via simple name mapping:

**Standard colors (8):**

- `red`, `green`, `yellow`, `blue`, `cyan`, `magenta` (or `purple`), `black`, `white`

**Bright colors (8):**

- `brightred`, `brightgreen`, `brightyellow`, `brightblue`, `brightcyan`, `brightmagenta` (or `brightpurple`), `brightblack` (or `gray`/`grey`), `brightwhite`

**Extended colors (1):**

- `orange` (256-color palette)

**Design rationale:** Simple lowercase names without underscores (`brightred` not `bright_red`) for ease of use. Intuitive aliases (`gray` for `brightblack`, `purple` for `magenta`).

### Semantic Variants

Each structural type has four semantic variants that automatically apply appropriate colors and emoji icons:

- **Success** - Green with ✅ emoji (operations completed successfully)
- **Info** - Cyan with ℹ️ emoji (informational messages)
- **Warning** - Yellow with ⚠️ emoji (cautions and important notes)
- **Error** - Red with ❌ emoji (failures and critical issues)

Examples: `print_title_success`, `print_header_error`, `print_banner_warning`, `print_section_info`

### Icon Philosophy

**Two-tier icon system** based on context:

**Emoji icons (structural variants):** High visual weight for headers and titles

- ✅ Success, ℹ️ Info, ⚠️ Warning, ❌ Error
- Used in: `print_title_error`, `print_header_success`, etc.

**Unicode icons (status messages):** Subtle, list-friendly for inline messages

- ✓ Success, ● Info, ▲ Warning, ✗ Error
- Used in: `print_success`, `print_info`, `print_warning`, `print_error`

**Rationale:** Emoji for major headings draws attention, unicode for list items avoids visual clutter.

### Visual Hierarchy

- **Spacing**: Extra blank lines around structural elements for breathing room
- **Borders**: Thick (━) for major divisions, thin (─) for subsections, double (═) for special emphasis
- **Alignment**: Titles centered, everything else left-aligned
- **Consistency**: Same patterns across all dotfiles scripts

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

- [Development Standards](go-apps/go-development.md) - Related development standards for Go apps
- [Testing Guide](testing.md) - Testing shell scripts in VMs
