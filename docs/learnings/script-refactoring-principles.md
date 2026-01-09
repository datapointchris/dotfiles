# Script Refactoring Principles

**Context**: Refactoring update.sh from 6 fragmented files (326 lines) to single consolidated script (156 lines).
**Commits**: c7205d5, 862b9ea
**Date**: December 2025

## The Problem Pattern

Scripts often accumulate complexity over time through well-intentioned but misguided additions:

- Comments explaining structure (instead of using visual indicators)
- Abstraction layers "for reusability" (that get called once)
- Defensive checks "just in case" (that make assumptions about the environment)
- Fragmentation "for organization" (that creates indirection)

This refactor demonstrates how to recognize and reverse these patterns.

## Core Principles

### 1. Visual Indicators Over Comments

**Bad Pattern**:

```bash
# Update Homebrew packages
brew update
brew upgrade

# Update Mac App Store
mas upgrade
```

**Good Pattern**:

```bash
print_header "Updating System Packages"

log_info "Updating Homebrew packages..."
brew update && brew upgrade

log_info "Updating Mac App Store apps..."
mas upgrade
```

**Why**: Comments are passive and easily outdated. Visual indicators (headers, logs) actively communicate structure during execution, are always in sync with code, and provide user feedback.

**When building new scripts**: If you're writing a comment to explain what a section does, use a print/log function instead.

### 2. Inline Over Unnecessary Abstraction

**Bad Pattern** (6 files):

```bash
# update.sh
bash "$DOTFILES_DIR/management/macos/update.sh"
bash "$DOTFILES_DIR/management/common/update.sh"

# management/macos/update.sh
update_homebrew() { brew update; brew upgrade; }
update_mas() { mas upgrade; }
update_homebrew
update_mas
```

**Good Pattern** (1 file):

```bash
main() {
  case "$platform" in
    macos)
      log_info "Updating Homebrew packages..."
      brew update && brew upgrade

      log_info "Updating Mac App Store apps..."
      mas upgrade
      ;;
  esac
}
```

**Why**: Each layer of abstraction (separate file, wrapper function) adds cognitive overhead without adding value. The actual work is simple - just run the commands.

**Decision Tree**:

- Single command or simple sequence → inline it
- Complex logic (loops, conditionals, parsing) → extract to function
- Called once → inline it
- Called multiple times → consider function (but still might inline for clarity)

**When building new scripts**: Start inline. Only extract to function when you have a concrete reason (complexity, reuse, testing).

### 3. Trust Your Environment

**Bad Pattern**:

```bash
update_uv_tools() {
  command -v uv >/dev/null 2>&1 || return 0
  source "$HOME/.local/bin/env" 2>/dev/null || true
  uv tool upgrade --all
}
```

**Good Pattern**:

```bash
update_common_tools() {
  log_info "Updating Python tools via $(print_green "uv tool upgrade --all")"
  if uv tool upgrade --all; then
    log_success "Python tools updated"
  else
    log_warning "Python tools update failed"
  fi
}
```

**Why**:

- If `uv` isn't in PATH during updates, something is already broken - let it fail loudly
- Silent failures hide problems
- Defensive checks add noise and suggest unreliable environment
- Update scripts assume a working system (unlike install scripts)

**When building new scripts**:

- Install scripts: Check and handle missing tools
- Update scripts: Assume tools exist, fail clearly if not
- Internal scripts: Trust the environment completely

### 4. Proper Encapsulation with main()

**Bad Pattern**:

```bash
#!/usr/bin/env bash
PLATFORM=$(detect_platform)

# Global level code
brew update
mas upgrade
npm update -g
```

**Good Pattern**:

```bash
#!/usr/bin/env bash

update_common_tools() {
  # Helper functions
}

main() {
  local platform
  platform=$(detect_platform)

  case "$platform" in
    macos)
      # Platform-specific logic
      ;;
  esac
}

main
```

**Why**:

- Everything in functions = testable, readable, organized
- Local variables in main = no global state pollution
- Clear entry point = obvious execution flow
- Follows install.sh pattern = consistency

**When building new scripts**: Start with main() from the beginning. Put setup and helpers above, orchestration in main().

### 5. Consistent Heading Hierarchy

**Bad Pattern** (inconsistent levels):

```bash
print_header "Dotfiles Update"
print_section "Platform Updates"
log_info "Updating brew..."
# Later...
print_banner_success "Updates complete"  # Different from print_header!
```

**Good Pattern** (consistent hierarchy):

```bash
print_title "System Update - $platform"        # h1 - main title
  print_header "Updating System Packages"     # h2 - major section
    print_section "Updating Homebrew..."       # h3 - subsection
      log_info/success/warning/error           # body text
print_title_success "Updates complete (23s)"   # h1 - matching end
```

**Why**: Like markdown heading levels (h1 > h2 > h3), visual hierarchy should be consistent and meaningful. Users mentally parse the structure.

**When building new scripts**: Choose your heading functions deliberately:

- `print_title` - once at start, once at end (with `_success`)
- `print_header` - major sections (2-5 per script)
- `print_section` - subsections within headers
- `log_*` - individual operations

### 6. Explicit Commands with Color

**Bad Pattern**:

```bash
log_info "Updating npm global packages..."
npm update -g
```

**Good Pattern**:

```bash
print_section "Updating npm global packages via $(print_green "npm update -g")"
if npm update -g 2>&1 | grep -v "npm warn"; then
  log_success "npm global packages updated (warnings suppressed)"
```

**Why**:

- Shows user exactly what command is running
- Green color distinguishes command from surrounding text
- Helps debugging (can copy-paste the exact command)
- Documents the script's behavior in its output

**When building new scripts**: Always show the actual command being executed, especially for:

- Package managers (brew, apt, npm, cargo)
- Version control operations
- Network operations
- Any command that might fail

### 7. Consolidation Over Fragmentation

**Bad Pattern**:

```text
update.sh                      # Wrapper
├─ management/macos/update.sh  # 40 lines
├─ management/wsl/update.sh    # 23 lines
├─ management/arch/update.sh   # 33 lines
└─ management/common/update.sh # 159 lines
```

**Good Pattern**:

```text
update.sh                      # 156 lines total
├─ update_shell_plugins()      # Complex logic
├─ update_common_tools()       # Simple wrappers
└─ main()                      # Platform switch + orchestration
```

**Why**:

- Single source of truth - all logic in one place
- Easy to see full behavior at once
- No jumping between files
- Reduced boilerplate (one setup instead of six)

**Decision criteria for when to split**:

- File > 500 lines → consider splitting by major functionality
- Truly independent concerns → separate files
- Shared across multiple scripts → extract to library
- Otherwise → keep consolidated

**When building new scripts**: Start with single file. Only split when you have concrete evidence it's too large or truly independent.

### 8. Simplify Dependencies

**Bad Pattern**:

```bash
update_npm_globals() {
  export NVM_DIR="$HOME/.local/share/nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
  bash "$DOTFILES_DIR/management/common/install/language-tools/npm-install-globals.sh"
}
```

**Good Pattern**:

```bash
update_common_tools() {
  print_section "Updating npm global packages via $(print_green "npm update -g")"
  if npm update -g 2>&1 | grep -v "npm warn"; then
    log_success "npm global packages updated (warnings suppressed)"
  fi
}
```

**Why**:

- Install scripts handle setup (source nvm, install packages from packages.yml)
- Update scripts assume working environment (npm in PATH, packages installed)
- Mixing install and update logic is confusing
- Each script has a clear, focused purpose

**When building new scripts**: Understand the script's lifecycle position:

- Bootstrap scripts: Handle everything from scratch
- Install scripts: Set up environment, install tools
- Update scripts: Assume environment works, just update
- Runtime scripts: Pure execution, no setup

## Anti-Patterns to Avoid

### Defensive Overengineering

**Symptom**: `command -v tool || return 0` for every tool in an update script

**Why it's bad**: Silently skipping updates hides problems. If `cargo` isn't in PATH, the user should know.

**Fix**: Remove checks. Let failures fail loudly with clear error messages.

### Abstraction for Single Use

**Symptom**: Function with 3 lines called once

```bash
update_homebrew() {
  brew update || return 1
  brew upgrade || return 1
}
# Called exactly once
```

**Why it's bad**: No reuse, adds indirection, makes code harder to follow

**Fix**: Inline it where it's used

### Comments Instead of Code Structure

**Symptom**:

```bash
# ================================================================
# Update Homebrew packages
# ================================================================
brew update
brew upgrade
```

**Why it's bad**: Comments are passive, easily outdated, not visible to users

**Fix**: Use visual indicators that execute:

```bash
print_header "Updating System Packages"
log_info "Updating Homebrew packages..."
```

### Fragmentation for "Organization"

**Symptom**: 6 files totaling 300 lines with 200 lines of boilerplate

**Why it's bad**:

- Each file needs setup boilerplate (source libraries, set variables)
- Navigation overhead (jumping between files)
- Harder to see complete behavior
- More places for bugs to hide

**Fix**: Consolidate into sections within single file

## Refactoring Checklist

When refactoring an existing script:

- [ ] **Remove defensive checks** - Assume environment is set up (for update/runtime scripts)
- [ ] **Replace comments with visual indicators** - Use print/log functions
- [ ] **Inline single-use functions** - Remove unnecessary abstraction
- [ ] **Consolidate fragmented files** - Single source of truth
- [ ] **Add main() function** - Proper encapsulation
- [ ] **Use consistent heading hierarchy** - title > header > section > logs
- [ ] **Show commands in output** - Use $(print_green "command") pattern
- [ ] **Remove sourcing** - Trust PATH (for update/runtime scripts)
- [ ] **Use if-then-else over one-liners** - Readability over cleverness
- [ ] **Check for dead code** - Incomplete refactors leave fragments

## Building New Scripts Correctly

Start with this template to avoid needing refactoring:

```bash
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DOTFILES_DIR
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Only extract complex logic to helper functions
helper_function_if_truly_needed() {
  # Complex logic (loops, parsing, conditionals)
}

main() {
  local platform start_time end_time total_duration
  platform=$(detect_platform)
  start_time=$(date +%s)

  print_title "Script Purpose - $platform"

  # Inline simple operations directly in main
  print_header "Major Section"

  print_section "Doing something via $(print_green "actual-command")"
  if actual-command; then
    log_success "something completed"
  else
    log_warning "something failed"
  fi

  end_time=$(date +%s)
  total_duration=$((end_time - start_time))

  print_title_success "Complete (${total_duration}s)"
}

main
```

**Key decisions**:

- main() from the start (not added later)
- Visual indicators, not comments
- Inline by default, extract only when complex
- Consistent heading hierarchy
- Show commands in output
- Trust environment (or fail clearly)

## Metrics of Good Refactoring

**Quantitative**:

- Line count reduction (but not at expense of clarity)
- File count reduction
- Function count reduction
- Reduced nesting depth

**Qualitative**:

- Can understand flow without jumping files
- Visual output matches code structure
- Failures are loud and clear
- Easy to modify without touching multiple files
- No "what does this do?" moments

## Learning from Incomplete Refactors

**What happened**: Earlier failure registry refactor converted most files to new pattern but missed cleaning up old error-handling imports and dead code checks.

**Lesson**: Comprehensive refactoring requires:

1. Searching for ALL instances (don't trust memory)
2. Checking both active code and imports/setup
3. Running checks (grep for old patterns)
4. Testing the actual behavior
5. Reviewing the diff to catch missed cleanup

**Prevention**: When refactoring, grep for patterns:

```bash
# Find old pattern usage
grep -r "old_function" .
grep -r "old_variable" .
grep -r "old_import" .
```

## Conclusion

Great scripts are:

- **Visual**: Structure shown through execution, not comments
- **Simple**: Inline by default, abstract only when needed
- **Trustful**: Fail loudly when environment is wrong
- **Consolidated**: Single source of truth
- **Explicit**: Show what you're doing
- **Hierarchical**: Consistent heading levels
- **Maintainable**: Easy to modify, understand, and debug

When building new scripts, start with these principles. When refactoring old scripts, move toward them systematically.

The best refactoring makes code so clear that the next person (often future you) says "obviously it should be this way" and forgets it was ever different.
