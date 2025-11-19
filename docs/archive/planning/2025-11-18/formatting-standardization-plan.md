# Formatting Standardization Plan

## Executive Summary

Standardize all script formatting across the dotfiles repository to use the comprehensive shell formatting library (`platforms/common/shell/formatting.sh` and `colors.sh`). This will create visual consistency, reduce code duplication, and improve maintainability.

## Current State Analysis

### Shell Scripts Inventory (23 files)

**Setup Scripts (3):**
- `management/wsl-setup.sh` - WSL Ubuntu bootstrap
- `management/macos-setup.sh` - macOS bootstrap
- `management/arch-setup.sh` - Arch Linux bootstrap

**Verification and Testing Scripts (2):**
- `management/verify-installation.sh` - Installation verification
- `management/test-wsl-setup.sh` - WSL setup testing in Multipass VM

**Install Scripts (7):**
- `management/taskfiles/scripts/install-fzf.sh`
- `management/taskfiles/scripts/install-neovim.sh`
- `management/taskfiles/scripts/install-lazygit.sh`
- `management/taskfiles/scripts/install-yazi.sh`
- `management/taskfiles/scripts/install-go.sh`
- `management/taskfiles/scripts/nvm-install-node.sh`
- `management/taskfiles/scripts/nvm-install-lts.sh`
- `management/taskfiles/scripts/npm-install-globals.sh`

**App Scripts (3):**
- `apps/common/theme-sync` - Base16 theme manager
- `apps/common/menu` - Workflow tools launcher
- `apps/common/notes` - Note-taking CLI with zk

**Shell Function Libraries (6):**
- `platforms/common/shell/colors.sh` - ✓ Already standardized
- `platforms/common/shell/formatting.sh` - ✓ Already standardized
- `platforms/common/shell/aliases.sh` - No formatting changes needed
- `platforms/common/shell/functions.sh` - Examine for formatting
- `platforms/common/shell/fzf-functions.sh` - Examine for formatting
- `platforms/macos/shell/macos-aliases.sh` - No formatting changes needed
- `platforms/macos/shell/macos-functions.sh` - Examine for formatting
- `platforms/wsl/shell/wsl-aliases.sh` - No formatting changes needed
- `platforms/wsl/shell/wsl-functions.sh` - Examine for formatting

**Test Scripts (1):**
- `TESTING.sh` - Temporary testing script

### Go Applications (2)

**toolbox:**
- `apps/common/toolbox/display.go` - ANSI color codes, manual formatting
- Other Go files in toolbox/ - Minimal formatting

**sess:**
- `apps/common/sess/cmd/session/main.go` - Minimal output formatting
- Other Go files in sess/ - Minimal formatting

### Python Applications (1)

**symlinks:**
- `management/symlinks/symlinks/cli.py` - Uses Rich library for formatting
- No changes needed (Rich is appropriate for Python CLI)

## Current Formatting Patterns

### Pattern 1: Manual Color Definitions (Most Common)
```bash
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE} Title Text${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
```

**Found in:** wsl-setup.sh, macos-setup.sh, arch-setup.sh, verify-installation.sh, test-wsl-setup.sh

### Pattern 2: Color Helper Functions
```bash
color_green() { echo -e "\033[32m$1\033[0m"; }
color_blue() { echo -e "\033[34m$1\033[0m"; }
color_yellow() { echo -e "\033[33m$1\033[0m"; }

echo "$(color_blue "Title Text")"
```

**Found in:** theme-sync, menu, notes

### Pattern 3: Plain Text Borders
```bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Building fzf from Source"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
```

**Found in:** install-fzf.sh, install-neovim.sh

### Pattern 4: Go ANSI Color Codes
```go
const (
    ansiReset  = "\033[0m"
    ansiBlue   = "\033[34m"
    ansiGreen  = "\033[32m"
)

func colorBlue(text string) string {
    return ansiBlue + text + ansiReset
}
```

**Found in:** apps/common/toolbox/display.go

## Target State

### Standardized Formatting Functions Usage

All shell scripts will use the standardized formatting library with these functions:

**Structural Types:**
- `print_title "Text" ["color"]` - Centered, full-width titles
- `print_header "Text" ["color"]` - Left-aligned headers with thick borders
- `print_banner "Text" ["color"]` - Double-bar banners
- `print_section "Text" ["color"]` - Simple sections with thin underline

**Semantic Variants:**
- `print_title_success/info/warning/error "Text"` - Colored with emoji
- `print_header_success/info/warning/error "Text"` - Colored with emoji
- `print_banner_success/info/warning/error "Text"` - Colored with emoji
- `print_section_success/info/warning/error "Text"` - Colored with emoji

**Status Messages:**
- `print_success "Message"` - Green with ✓
- `print_error "Message"` - Red with ✗
- `print_warning "Message"` - Yellow with ▲
- `print_info "Message"` - Cyan with ●

**Utilities:**
- `die "Error message"` - Print error and exit
- `fatal "Error message"` - Print error header and exit

### Sourcing Strategy

**Before Installation (Setup Scripts):**
```bash
#!/usr/bin/env bash
set -euo pipefail

# Source formatting library from dotfiles repo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"
```

**After Installation (App Scripts):**
```bash
#!/usr/bin/env bash
set -euo pipefail

# Formatting library is available in shell path
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"
```

**NO Guard Clauses** - Per project philosophy, scripts should not check if formatting is available

### Go Applications Strategy

Go apps cannot source bash scripts, so they will:

1. **Maintain their own ANSI codes** - Keep constants in each app
2. **Standardize visual style** - Match shell formatting library appearance
3. **Consistent patterns** - Use same thick borders (━), colors, emoji

## Implementation Plan

### Phase 1: Setup Scripts (Highest Priority)

These are the entry points for fresh installations and must work before symlinks are established.

**Files:**
1. `management/wsl-setup.sh`
2. `management/macos-setup.sh`
3. `management/arch-setup.sh`

**Changes:**
- Add relative sourcing of formatting.sh
- Replace manual color definitions
- Convert all headers to `print_header_*` variants
- Convert all status messages to `print_success/error/info`
- Convert final summary to `print_header_success`

**Testing:**
- Test in VM/fresh environment before symlinking
- Verify sourcing works correctly

### Phase 2: Verification and Testing Scripts

**Files:**
1. `management/verify-installation.sh`
2. `management/test-wsl-setup.sh`

**Changes:**
- Source formatting.sh (can use $HOME/dotfiles since runs after setup)
- Replace manual color definitions
- Convert print_section helper to use `print_section`
- Convert headers to `print_header`
- Keep custom timing/logging helpers

### Phase 3: Install Scripts

**Files (8 scripts):**
1. `management/taskfiles/scripts/install-fzf.sh`
2. `management/taskfiles/scripts/install-neovim.sh`
3. `management/taskfiles/scripts/install-lazygit.sh`
4. `management/taskfiles/scripts/install-yazi.sh`
5. `management/taskfiles/scripts/install-go.sh`
6. `management/taskfiles/scripts/nvm-install-node.sh`
7. `management/taskfiles/scripts/nvm-install-lts.sh`
8. `management/taskfiles/scripts/npm-install-globals.sh`

**Changes:**
- Source formatting.sh
- Convert plain borders to `print_header` or `print_banner`
- Add color to titles
- Convert checkmarks to `print_success/error`

### Phase 4: App Scripts

**Files:**
1. `apps/common/theme-sync`
2. `apps/common/menu`
3. `apps/common/notes`

**Changes:**
- Source formatting.sh
- Remove local color helper functions
- Convert to standardized functions
- Maintain current functionality

### Phase 5: Shell Function Libraries

**Files to Examine:**
1. `platforms/common/shell/functions.sh`
2. `platforms/common/shell/fzf-functions.sh`
3. `platforms/macos/shell/macos-functions.sh`
4. `platforms/wsl/shell/wsl-functions.sh`

**Changes (if any formatting found):**
- Minimal - these are libraries loaded into shell
- Only if they output formatted text
- Already have access to formatting.sh functions

### Phase 6: Go Applications

**Files:**
1. `apps/common/toolbox/display.go`
2. `apps/common/sess/cmd/session/main.go`

**Changes:**
- Standardize ANSI color codes to match shell colors
- Update border characters to use ═ and ━ consistently
- Match emoji usage (✓ for success, ✗ for error)
- Keep helper functions (Go can't source bash)

## Detailed Migration Examples

### Example 1: Setup Script Header

**Before:**
```bash
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE} WSL Ubuntu Dotfiles Bootstrap${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
```

**After:**
```bash
print_header "WSL Ubuntu Dotfiles Bootstrap" "blue"
```

### Example 2: Status Messages

**Before:**
```bash
echo -e "  ${GREEN}✓${NC} Taskfile installed to ~/.local/bin"
```

**After:**
```bash
print_success "Taskfile installed to ~/.local/bin"
```

### Example 3: Section Headers

**Before:**
```bash
echo ""
echo -e "${CYAN}[1/2] Checking Taskfile${NC}"
echo ""
```

**After:**
```bash
print_section "[1/2] Checking Taskfile" "cyan"
```

### Example 4: Final Success Message

**Before:**
```bash
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN} ✅ WSL Ubuntu Bootstrap Complete${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
```

**After:**
```bash
print_header_success "WSL Ubuntu Bootstrap Complete"
```

### Example 5: App Script Helper Functions

**Before:**
```bash
color_green() { echo -e "\033[32m$1\033[0m"; }
color_blue() { echo -e "\033[34m$1\033[0m"; }

echo "$(color_blue "Applying theme:") $theme"
```

**After:**
```bash
# Remove helper functions, just use:
print_info "Applying theme: $theme"
# Or for inline coloring:
echo "$(print_cyan "Applying theme:") $theme"
```

### Example 6: Go Application Formatting

**Before:**
```go
fmt.Println(colorBlue("═══════════════════════════════════════════"))
fmt.Println(colorBold(name))
fmt.Println(colorBlue("═══════════════════════════════════════════"))
```

**After:**
```go
// Keep the same pattern, but ensure consistency
// Use ━ (thick) for major headers, ═ (double) for banners
fmt.Println(colorBlue("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
fmt.Println(colorBold(name))
fmt.Println(colorBlue("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
```

## Testing Strategy

### Unit Testing (Per File)

After converting each file:
1. **Syntax check:** `bash -n <file>`
2. **Shellcheck:** If applicable
3. **Manual execution:** Run the script and verify output

### Integration Testing

**Setup Scripts:**
1. Test in fresh VM (Multipass for WSL/Arch)
2. Test on clean macOS install if available
3. Verify all formatting displays correctly

**Install Scripts:**
1. Run via Task commands
2. Verify output formatting
3. Check that installations still work

**App Scripts:**
1. Test each command/subcommand
2. Verify interactive prompts still work
3. Check error handling

### Smoke Testing

Final smoke test of entire dotfiles installation:
1. Fresh VM setup
2. Run full installation
3. Verify all formatting is consistent
4. Check no regressions in functionality

## Rollback Plan

If issues are discovered:

1. **Per-file rollback:** Git allows reverting individual files
2. **Phase rollback:** Can revert an entire phase of changes
3. **Full rollback:** Can revert the entire formatting branch

Recommendation: Implement in phases with commits per phase for granular rollback.

## Success Criteria

- [ ] All shell scripts source formatting.sh (no duplicated color definitions)
- [ ] Consistent visual appearance across all scripts
- [ ] No functionality regressions
- [ ] All tests pass
- [ ] Documentation updated (if needed)
- [ ] Go applications use consistent visual style
- [ ] Zero guard clauses added (per project philosophy)

## Timeline Estimate

- **Phase 1:** 2-3 hours (Setup scripts - highest priority, most critical)
- **Phase 2:** 1 hour (Verification scripts)
- **Phase 3:** 2-3 hours (Install scripts - 8 files)
- **Phase 4:** 1-2 hours (App scripts)
- **Phase 5:** 1 hour (Function libraries - examination + changes if needed)
- **Phase 6:** 1-2 hours (Go applications)
- **Testing:** 2-3 hours (Throughout, plus final smoke test)

**Total:** 10-15 hours

## Notes and Considerations

### Sourcing Approach

The user specified to use `$HOME/dotfiles/platforms/common/shell/formatting.sh` for sourcing. This works because:
- Setup scripts run from `dotfiles/management/` directory
- User clones/has dotfiles in `$HOME/dotfiles`
- Symlinks manager will later symlink these to proper locations

Relative sourcing alternative for setup scripts:
```bash
source "$(dirname "${BASH_SOURCE[0]}")/../platforms/common/shell/formatting.sh"
```

Both approaches work, user prefers `$HOME/dotfiles/` approach for clarity.

### No Guard Clauses

Per project philosophy:
- NO `if [ -f formatting.sh ]` checks
- Scripts should fail if formatting library missing
- This enforces correct setup and catches issues early

### Python Symlinks Manager

The Python symlinks manager uses Rich library for formatting. This is appropriate and should NOT be changed:
- Rich is the Python equivalent of our shell formatting library
- Already provides excellent formatting
- Would be inappropriate to shell out to bash for formatting

### Function Libraries

Shell function libraries (`functions.sh`, `fzf-functions.sh`, etc.) are sourced into the user's shell environment. They likely don't output formatted text themselves, but if they do, they already have access to formatting.sh functions since both are loaded into the shell.

## Risk Assessment

**Low Risk:**
- App scripts (theme-sync, menu, notes) - Non-critical, easy to test
- Install scripts - Run via Task, can test individually
- Function libraries - Minimal changes expected

**Medium Risk:**
- Verification script - Important for testing, but not critical path
- Test script - Used for testing, not production

**High Risk:**
- Setup scripts - Critical entry points, must work in fresh environments
- These run BEFORE symlinks are established
- Must test thoroughly in VMs

**Mitigation:**
- Start with low-risk files to establish pattern
- Use fresh VMs for testing setup scripts
- Commit after each phase for easy rollback
- Keep commits small and focused

## Post-Implementation

### Documentation Updates

Files to potentially update:
- `docs/reference/script-formatting-library.md` - Add examples from real scripts
- `CLAUDE.md` - Note that all scripts use standardized formatting
- `README.md` - Mention consistent formatting if relevant

### Maintenance

Going forward:
- New scripts must use formatting library
- Pre-commit hook could check for hardcoded ANSI codes (future enhancement)
- Claude Code should suggest formatting functions when writing new scripts
