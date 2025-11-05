# Taskfile System Modular Refactor

**Date:** 2025-11-04
**Type:** Major Refactor
**Scope:** Task automation system, package management

---

## Summary

Completely refactored the Taskfile system to be truly modular with platform-specific `update-all` commands that update every package manager and tool on that platform. Removed ambiguous generic tasks in favor of clear, platform-specific orchestration.

## Problem Statement

The previous Taskfile system had several significant issues:

1. **Ambiguous generic tasks**: `task update` was unclear - it only updated brew, npm, and uv, but users wouldn't know that without reading the code
2. **Incomplete coverage**: Missing updates for mas (Mac App Store), cargo (Rust), shell plugins, tmux plugins, and system package managers
3. **Scattered configuration**: Package lists were hardcoded across multiple taskfiles instead of centralized
4. **Not modular**: Adding new components required editing multiple files with duplicated logic
5. **Update/upgrade separation**: Some systems had separate update and upgrade tasks that should have been combined

## Solution Overview

Implemented a comprehensive modular task system with the following architecture:

1. **Centralized package configuration** in `config/packages.yml`
2. **Internal task modules** in `taskfiles/internal/` for each component type
3. **Platform-specific `update-all` commands** that orchestrate all updates for that platform
4. **Removed generic cross-platform tasks** that were ambiguous

## Implementation Details

### Phase 1: Expand Package Configuration

**File Modified:** `config/packages.yml`

Added new sections to centralize all package definitions:

- `cargo_packages` - Rust tools installed via cargo
- `tmux_plugins` - TPM managed plugins with repo URLs
- `mas_apps` - Mac App Store apps (informational)

All package managers now have their package lists in a single, easily editable location.

### Phase 2: Create Internal Task Modules

**Files Created:**
- `taskfiles/internal/cargo.yml`
- `taskfiles/internal/mas.yml`
- `taskfiles/internal/tmux-plugins.yml`
- `taskfiles/internal/apt.yml`
- `taskfiles/internal/pacman.yml`
- `taskfiles/internal/yay.yml`

Each internal taskfile has a single `update` task marked as `internal: true` that:
- Checks if the tool is available
- Gracefully skips if not installed
- Provides informative output about what's being updated
- Handles both optimal (cargo-update) and fallback (manual loop) approaches

Example from `cargo.yml`:
- Checks for `cargo-install-update` tool
- Falls back to manual reinstallation loop if not available
- Provides helpful tip about installing cargo-update

### Phase 3: Update Existing Component Taskfiles

**Files Modified:**
- `taskfiles/brew.yml`
- `taskfiles/npm.yml`
- `taskfiles/uv.yml`
- `taskfiles/shell.yml`

Changes made to each:

1. **brew.yml:**
   - Combined `update` and `upgrade` into single `update` task
   - Marked task as `internal: true`
   - Simplified to run `brew update && brew upgrade`

2. **npm.yml:**
   - Added `update` task (was missing)
   - Marked as `internal: true`
   - Loads nvm and runs `npm update -g`

3. **uv.yml:**
   - Added `update` task (was missing)
   - Marked as `internal: true`
   - Runs `uv tool upgrade --all`

4. **shell.yml:**
   - Marked existing `update` task as `internal: true`
   - Cleaned up output formatting
   - Suppressed verbose git output

### Phase 4: Platform-Specific Update-All Commands

**Files Modified:**
- `taskfiles/macos.yml`
- `taskfiles/wsl.yml`
- `taskfiles/arch.yml`

Each platform taskfile now:

1. **Includes internal taskfiles** with `internal: true` flag:
   ```yaml
   includes:
     brew:
       taskfile: ./brew.yml
       internal: true
     cargo:
       taskfile: ./internal/cargo.yml
       internal: true
     # ... etc
   ```

2. **Defines comprehensive `update-all` task:**

   **macOS (7 update steps):**
   1. Homebrew (formulas + casks)
   2. Mac App Store (mas)
   3. npm global packages
   4. Python tools (uv)
   5. Rust packages (cargo)
   6. Shell plugins
   7. Tmux plugins

   **WSL Ubuntu (6 update steps):**
   1. System packages (apt)
   2. npm global packages
   3. Python tools (uv)
   4. Rust packages (cargo)
   5. Shell plugins
   6. Tmux plugins

   **Arch Linux (7 update steps):**
   1. System packages (pacman)
   2. AUR packages (yay)
   3. npm global packages
   4. Python tools (uv)
   5. Rust packages (cargo)
   6. Shell plugins
   7. Tmux plugins

Each update-all task provides clear visual separation with informative headers and step indicators.

### Phase 5: Remove Generic Cross-Platform Tasks

**File Modified:** `Taskfile.yml`

Removed tasks:
- `update` - Ambiguous generic task
- `clean` - Users should run native commands directly

Kept tasks:
- `install` - Platform auto-detection and installation
- `install-macos`, `install-wsl`, `install-arch` - Platform-specific installations
- `default` - Show available tasks

### Phase 6: Documentation Update

**File Modified:** `docs/reference/tasks.md`

Major documentation rewrite including:

1. **New philosophy section** explaining platform-specific approach
2. **Package Management section** with clear examples of each platform's `update-all` command
3. **Detailed breakdown** of what gets updated on each platform
4. **Direct command reference** for selective updates
5. **Design Principles** explaining modular internal tasks
6. **Single Source of Truth** documentation for package lists

Documentation now clearly explains:
- Why generic tasks were removed
- How to update everything on your platform (one command)
- How to selectively update specific components (native commands)
- The modular internal task architecture

## Testing Methodology

### Syntax Validation

```bash
task --list
# Result: ✅ All taskfiles parse correctly
# Result: ✅ Only platform-specific update-all tasks visible
```

### Internal Task Verification

```bash
task --list-all | grep update
# Result: ✅ Internal update tasks not shown in regular list
# Result: ✅ Platform update-all tasks are public
```

### Task Summary Inspection

```bash
task macos:update-all --summary
# Result: ✅ Shows all 7 update steps
# Result: ✅ Correct namespace references (macos:brew:update, etc.)
```

## Files Modified

### Created
- `taskfiles/internal/cargo.yml` - Rust package updates
- `taskfiles/internal/mas.yml` - Mac App Store updates
- `taskfiles/internal/tmux-plugins.yml` - Tmux plugin updates
- `taskfiles/internal/apt.yml` - APT package updates
- `taskfiles/internal/pacman.yml` - Pacman package updates
- `taskfiles/internal/yay.yml` - AUR package updates
- `.planning/taskfile-refactor-plan.md` - Comprehensive refactor plan

### Modified
- `config/packages.yml` - Added cargo_packages, tmux_plugins, mas_apps sections
- `taskfiles/brew.yml` - Consolidated update+upgrade, marked internal
- `taskfiles/npm.yml` - Added update task, marked internal
- `taskfiles/uv.yml` - Added update task, marked internal
- `taskfiles/shell.yml` - Marked update task internal
- `taskfiles/macos.yml` - Added includes and update-all task
- `taskfiles/wsl.yml` - Added includes and update-all task
- `taskfiles/arch.yml` - Added includes and update-all task
- `Taskfile.yml` - Removed generic update and clean tasks
- `docs/reference/tasks.md` - Complete rewrite of package management section

## Design Decisions

### Why Internal Tasks?

Internal tasks provide modular, reusable update logic without polluting the user-facing task list. Users don't need to know about individual component updates - they just run `task <platform>:update-all`.

Benefits:
- Clean task namespace (only platform tasks visible)
- Reusable logic across platforms
- Easy to add new components (create internal task, include in platform)
- Separation of concerns (implementation vs interface)

### Why Platform-Specific Instead of Generic?

Each platform has different package managers and tools:
- macOS: brew, mas (unique to macOS)
- WSL: apt (unique to Debian/Ubuntu)
- Arch: pacman, yay (unique to Arch)

A generic `task update` would either:
1. Not work on all platforms (mas doesn't exist on Linux)
2. Have complex conditional logic in one file
3. Be ambiguous about what it updates

Platform-specific tasks are:
- Clear: Users know exactly what gets updated
- Maintainable: Each platform's logic is isolated
- Flexible: Easy to add platform-specific tools
- Comprehensive: Can update ALL package managers on that platform

### Why Centralized Package Configuration?

Before: Package lists were hardcoded in taskfiles:
- npm packages: hardcoded in `taskfiles/npm.yml`
- uv tools: hardcoded in `taskfiles/uv.yml`
- Shell plugins: in `config/packages.yml`
- No cargo, tmux, or mas tracking

After: All in `config/packages.yml`:
- Single file to edit when adding/removing packages
- Clear documentation of what's installed
- Easy to review what tools you have
- Consistent structure across package types

### Why Combine Update + Upgrade?

Systems like brew have separate `update` (fetch package lists) and `upgrade` (install new versions). But users almost always want both operations together.

Before:
- `task brew:update` - Just fetches package lists
- `task brew:upgrade` - Just installs updates
- Users had to remember to run both

After:
- `task macos:update-all` - Does both automatically
- For selective updates, use `brew update && brew upgrade` directly
- No wrapper tasks for simple operations

## Migration Guide

### Before This Refactor

```bash
# Update packages (only updated brew, npm, uv)
task update

# Clean caches
task clean
```

### After This Refactor

```bash
# Update ALL packages on macOS
task macos:update-all

# Update ALL packages on WSL
task wsl:update-all

# Update ALL packages on Arch
task arch:update-all

# For selective updates, use native commands:
brew update && brew upgrade
mas upgrade
sudo apt update && sudo apt upgrade -y
npm update -g
uv tool upgrade --all
cargo install-update -a
```

## Key Learnings

### 1. Taskfile Internal Tasks Are Powerful

The `internal: true` flag creates function-like tasks that can be composed into public orchestration tasks. This is perfect for modular design.

Pattern:
```yaml
# In internal taskfile
tasks:
  update:
    internal: true
    cmds:
      - # update logic

# In platform taskfile
includes:
  component:
    taskfile: ./internal/component.yml
    internal: true  # Hide ALL tasks from this include

tasks:
  update-all:
    cmds:
      - task: component:update
```

### 2. Include with Internal Flag Prevents Namespace Pollution

Without `internal: true` on includes, all tasks from included files appear in the parent namespace. With it, they're hidden but still callable.

This creates a clean public API (only platform tasks) while maintaining modular implementation.

### 3. Platform-Specific Beats Generic

Trying to make tasks work across all platforms leads to:
- Complex conditional logic
- Ambiguous task names
- Incomplete functionality
- Harder maintenance

Platform-specific tasks are:
- Simpler to implement
- Clearer to users
- Easier to maintain
- More comprehensive

### 4. Centralized Config Reduces Duplication

Having package lists in one file means:
- Single source of truth
- Easy to add/remove packages
- Clear documentation of installed tools
- Consistent structure

The `config/packages.yml` approach works well and should be extended to more components.

### 5. Graceful Degradation in Update Tasks

Update tasks should check if tools are installed and skip gracefully if not:

```yaml
cmds:
  - |
    if ! command -v tool >/dev/null 2>&1; then
      echo "  tool not installed - skipping"
      exit 0
    fi
    # update logic
```

This allows update-all to work even if some components aren't installed.

## Future Enhancements

Potential improvements for future work:

1. **cargo-update installation** - Add cargo install cargo-update to platform setup tasks
2. **TPM auto-installation** - Detect if TPM is missing and offer to install
3. **Update logging** - Log update history to track when packages were last updated
4. **Parallel updates** - Investigate running independent updates in parallel for speed
5. **Update summary** - Show summary at end: "Updated 15 packages, skipped 3 not installed"

## Conclusion

This refactor transforms the Taskfile system from an ambiguous collection of wrapper tasks into a clear, modular, platform-specific automation system. Users can now update everything on their platform with one command, and adding new components is straightforward.

The modular internal task architecture sets a pattern for future task organization and makes the system much more maintainable.

**Key Outcomes:**
- ✅ Clear platform-specific update commands
- ✅ Comprehensive updates (all package managers + tools)
- ✅ Modular, maintainable architecture
- ✅ Single source of truth for package configuration
- ✅ Graceful degradation when tools aren't installed
- ✅ Excellent documentation

**User Impact:**
- Before: `task update` (ambiguous, incomplete)
- After: `task macos:update-all` (clear, comprehensive)
