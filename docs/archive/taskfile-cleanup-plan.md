# Taskfile Cleanup & Simplification Plan

**Status**: Ready for Implementation
**Created**: 2025-11-28
**Problem**: Taskfiles are misused as bash wrappers, creating unnecessary abstraction

---

## The Core Problem

**Task is being used for the wrong purpose**. Task was designed for:
- ✅ Build automation (like Make)
- ✅ Incremental compilation
- ✅ Complex dependency graphs

**Not for**:
- ❌ Wrapping package manager commands
- ❌ Calling bash scripts that have all the logic
- ❌ Being a glorified alias system

---

## Current State

**18 taskfiles, 1,330 lines of YAML**

**Category Breakdown**:
- **Pure Wrappers** (7 files, 39%): Zero value, just call 1-2 commands
- **Unnecessary Abstraction** (7 files, 39%): Could be simple bash scripts
- **Legitimate Use** (4 files, 22%): Actually use Task features properly

**Anti-Pattern Discovered**: Circular dependencies
```
update-macos.sh → task brew:update → brew update
                → task npm:update → npm-install-globals.sh
                → task cargo:update → cargo install-update
```

Why have Task in the middle? The bash script could just call the commands directly.

---

## Files Analysis

### ELIMINATE (7 files - Pure Wrappers)

No value, just indirection:

1. **apt.yml** (26 lines) - Wraps `sudo apt update && sudo apt upgrade -y`
2. **pacman.yml** (22 lines) - Wraps `sudo pacman -Syu --noconfirm`
3. **yay.yml** (22 lines) - Wraps `yay -Syu --noconfirm`
4. **brew.yml** (26 lines) - Wraps 3 brew commands
5. **cargo-update.yml** (26 lines) - Wraps `cargo install-update -a`
6. **tmux-plugins.yml** (36 lines) - Wraps a single script call
7. **npm-global.yml** (26 lines) - Wraps npm-install-globals.sh

**Total to delete**: ~190 lines of YAML that do nothing

### CONVERT TO BASH (7 files - Unnecessary Abstraction)

These have inline bash that should be scripts:

8. **go-tools.yml** (73 lines) → `scripts/install-go-tools.sh`
9. **uv-tools.yml** (75 lines) → `scripts/install-uv-tools.sh`
10. **nvm.yml** (74 lines) → `scripts/install-nvm.sh`
11. **tenv.yml** (78 lines) → `scripts/install-tenv.sh`
12. **shell-plugins.yml** (83 lines) → `scripts/install-shell-plugins.sh`
13. **macos.yml** (227 lines) → Extract inline bash to scripts, keep minimal orchestration
14. **wsl.yml** (82 lines) → Extract inline bash to scripts
15. **arch.yml** (201 lines) → Extract inline bash to scripts

### KEEP (4 files - Legitimate Task Use)

These actually use Task features properly:

16. **symlinks.yml** (128 lines) ✅ - Uses `env:`, `vars:`, semantic interface
17. **sess/Taskfile.yml** (86 lines) ✅ - Build automation, incremental builds
18. **toolbox/Taskfile.yml** (80 lines) ✅ - Build automation, incremental builds
19. **docs.yml** (26 lines) ✅ - Documentation shortcuts (acceptable)

---

## Implementation Plan

### Phase 1: Remove Duplication (ALREADY DONE ✅)

From the font refactor work, we already removed:
- Taskfile install tasks (duplicated install.sh)

**Result**: install.sh is the single entry point

### Phase 2: Eliminate Pure Wrappers (Quick Win - 1 hour)

**Goal**: Remove 7 useless taskfiles

**Steps**:

1. **Update `update-macos.sh`** to call commands directly:
   ```bash
   # Before: task brew:update
   # After:
   brew update && brew upgrade && brew upgrade --cask --greedy

   # Before: task cargo-update:update
   # After:
   source "$HOME/.cargo/env" && cargo install-update -a
   ```

2. **Update `update-wsl.sh`**:
   ```bash
   # Before: task apt:update
   # After:
   sudo apt update && sudo apt upgrade -y
   ```

3. **Update `update-arch.sh`**:
   ```bash
   # Before: task pacman:update
   # After:
   sudo pacman -Syu --noconfirm
   ```

4. **Delete taskfiles**:
   ```bash
   rm management/taskfiles/apt.yml
   rm management/taskfiles/pacman.yml
   rm management/taskfiles/yay.yml
   rm management/taskfiles/brew.yml
   rm management/taskfiles/cargo-update.yml
   rm management/taskfiles/tmux-plugins.yml
   rm management/taskfiles/npm-global.yml
   ```

5. **Update `Taskfile.yml`** - Remove includes:
   ```yaml
   # DELETE these lines:
   brew:
     taskfile: ./management/taskfiles/brew.yml
   apt:
     taskfile: ./management/taskfiles/apt.yml
   pacman:
     taskfile: ./management/taskfiles/pacman.yml
   yay:
     taskfile: ./management/taskfiles/yay.yml
   cargo-update:
     taskfile: ./management/taskfiles/cargo-update.yml
   npm-global:
     taskfile: ./management/taskfiles/npm-global.yml
   tmux-plugins:
     taskfile: ./management/taskfiles/tmux-plugins.yml
   ```

**Impact**:
- Remove ~190 lines of useless YAML
- Remove circular dependencies
- Simpler update scripts

**Risk**: Low - these are just pass-throughs

---

### Phase 3: Convert Abstraction to Scripts (Medium Effort - 3-4 hours)

**Goal**: Replace 5 abstraction taskfiles with proper bash scripts

#### 3a. Create `scripts/install-go-tools.sh`

**Replace**: `go-tools.yml`

**Script content**:
```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source formatting
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Check Go is installed
if ! command -v go &>/dev/null; then
    print_error "Go is not installed"
    exit 1
fi

# Get Go tools from packages.yml
GO_TOOLS=$(python3 "$DOTFILES_DIR/management/parse-packages.py" --type=go-tools)

print_section "Installing Go Tools" "cyan"

for tool in $GO_TOOLS; do
    echo "  Installing $tool..."
    if go install "$tool@latest"; then
        print_success "$tool installed"
    else
        print_warning "Failed to install $tool"
    fi
done
```

#### 3b. Create `scripts/install-uv-tools.sh`

**Replace**: `uv-tools.yml`

Similar pattern to go-tools.sh

#### 3c. Create `scripts/install-shell-plugins.sh`

**Replace**: `shell-plugins.yml`

Move the 30+ lines of inline bash from the taskfile to a proper script.

#### 3d. Simplify `nvm.yml` and `tenv.yml`

**Option A**: Convert to bash scripts (preferred)
**Option B**: Keep minimal taskfiles if they're used by install.sh

Since install.sh calls `task nvm:install` and `task tenv:install`, we have two options:

1. **Remove taskfiles, update install.sh** to call scripts directly
2. **Keep minimal taskfiles** as thin wrappers

**Recommendation**: Option 1 - update install.sh to call scripts directly

**Delete taskfiles**:
```bash
rm management/taskfiles/go-tools.yml
rm management/taskfiles/uv-tools.yml
rm management/taskfiles/shell-plugins.yml
rm management/taskfiles/nvm.yml
rm management/taskfiles/tenv.yml
```

**Update `Taskfile.yml`** - Remove includes

**Update `install.sh`** - Replace task calls:
```bash
# Before: cd "$DOTFILES_DIR" && task go-tools:install
# After:
bash "$DOTFILES_DIR/management/scripts/install-go-tools.sh"

# Before: cd "$DOTFILES_DIR" && task uv-tools:install
# After:
bash "$DOTFILES_DIR/management/scripts/install-uv-tools.sh"
```

**Impact**:
- Remove ~400 lines of YAML
- Add ~200 lines of focused bash scripts
- No more inline bash in YAML
- Clearer logic flow

**Risk**: Medium - need to test all platforms

---

### Phase 4: Simplify Platform Files (Higher Effort - 4-5 hours)

**Goal**: Extract inline bash from platform taskfiles to dedicated scripts

#### Current State:

**macos.yml** (227 lines):
- `install-packages` - 50+ lines of inline bash
- `configure-finder` - 20 lines of inline bash
- `configure-dock` - 15 lines of inline bash
- `configure-safari` - 10 lines of inline bash

#### Proposed Changes:

**Extract to scripts**:
```
management/scripts/macos/
├── install-packages.sh          # Replaces inline bash in macos:install-packages
├── configure-finder.sh          # Replaces macos:configure-finder
├── configure-dock.sh            # Replaces macos:configure-dock
└── configure-safari.sh          # Replaces macos:configure-safari
```

**Keep in macos.yml**:
```yaml
tasks:
  install-packages:
    desc: Install macOS system packages
    cmds:
      - bash {{.ROOT_DIR}}/management/scripts/macos/install-packages.sh

  configure-finder:
    desc: Configure Finder preferences
    cmds:
      - bash {{.ROOT_DIR}}/management/scripts/macos/configure-finder.sh
```

**Or eliminate entirely** and call scripts directly from install.sh?

**Recommendation**: Eliminate the taskfile, call scripts directly from install.sh

Same approach for **wsl.yml** and **arch.yml**.

**Impact**:
- Remove ~300 lines of inline bash from YAML
- Add focused, testable scripts
- Easier to understand and modify

**Risk**: Medium-High - these are critical installation components

---

## Final Architecture

### What Stays in Taskfile.yml (Root)

**Minimal orchestration only**:

```yaml
version: '3'

includes:
  symlinks:
    taskfile: ./management/taskfiles/symlinks.yml
  docs:
    taskfile: ./management/taskfiles/docs.yml

tasks:
  default:
    desc: Show available tasks
    cmds:
      - task --list

  # Optional: convenience wrapper
  install:
    desc: Install dotfiles (delegates to install.sh)
    cmds:
      - bash install.sh {{.CLI_ARGS}}

  # Font installation (standalone tasks)
  fonts:download:
    desc: Download coding fonts from GitHub releases
    cmds:
      - bash management/scripts/fonts/download.sh {{.CLI_ARGS}}

  fonts:install:
    desc: Install downloaded fonts to system font directory
    cmds:
      - bash management/scripts/fonts/install.sh {{.CLI_ARGS}}
```

**That's it**. Everything else is bash scripts or app-specific taskfiles.

### What Stays in management/taskfiles/

```
management/taskfiles/
├── symlinks.yml          # KEEP - Proper Task use
└── docs.yml              # KEEP - Documentation shortcuts
```

**2 files instead of 18** (89% reduction)

### What Moves to scripts/

```
management/scripts/
├── fonts/
│   ├── download.sh
│   └── install.sh
├── install-go.sh
├── install-go-tools.sh          # NEW
├── install-fzf.sh
├── install-neovim.sh
├── install-lazygit.sh
├── install-yazi.sh
├── install-rust.sh
├── install-cargo-binstall.sh
├── install-cargo-tools.sh
├── install-nvm.sh               # Enhanced from nvm.yml
├── install-tenv.sh              # Enhanced from tenv.yml
├── install-uv.sh
├── install-uv-tools.sh          # NEW
├── install-shell-plugins.sh     # NEW
├── install-tpm.sh
├── install-tmux-plugins.sh
├── install-nvim-plugins.sh
├── macos/
│   ├── install-packages.sh      # NEW (from macos.yml)
│   ├── configure-finder.sh      # NEW (from macos.yml)
│   ├── configure-dock.sh        # NEW (from macos.yml)
│   └── configure-safari.sh      # NEW (from macos.yml)
├── wsl/
│   └── install-packages.sh      # NEW (from wsl.yml)
├── arch/
│   └── install-packages.sh      # NEW (from arch.yml)
├── update-macos.sh              # Simplified (no task calls)
├── update-wsl.sh                # Simplified (no task calls)
└── update-arch.sh               # Simplified (no task calls)
```

### App Taskfiles (Build Automation)

```
apps/common/sess/Taskfile.yml       # KEEP - Build automation
apps/common/toolbox/Taskfile.yml    # KEEP - Build automation
```

---

## Benefits of This Approach

1. **Clarity**: Bash scripts are easier to read than YAML with inline bash
2. **Testability**: Each script has a single, clear purpose
3. **No Circular Dependencies**: install.sh → scripts → commands (linear)
4. **Less Abstraction**: Fewer layers between intent and execution
5. **Better Error Messages**: Bash gives better stack traces than Task
6. **Easier Debugging**: No context switching between YAML and bash
7. **Smaller Surface Area**: 2 taskfiles instead of 18
8. **Task Used Properly**: Only for build automation and documentation

---

## Metrics

### Before Cleanup:
- **18 taskfiles** (~1,330 lines)
- **Circular dependencies**: Bash → Task → Bash → Task
- **Inline bash**: ~300 lines scattered in YAML
- **Pure wrappers**: 7 files doing nothing

### After Cleanup:
- **2 taskfiles** (~150 lines) - 89% reduction
- **Linear flow**: install.sh → scripts → commands
- **No inline bash**: All logic in dedicated scripts
- **+8 new scripts**: Each with clear, single purpose

### Code Impact:
- **Delete**: ~1,180 lines of YAML
- **Add**: ~400 lines of bash scripts
- **Net reduction**: ~780 lines
- **Complexity reduction**: Massive

---

## Implementation Order

**Recommended sequence**:

1. ✅ **Phase 1**: Remove install task duplication (DONE)
2. **Phase 2**: Eliminate pure wrapper taskfiles (1 hour, low risk)
3. **Phase 3**: Convert abstraction to scripts (3-4 hours, medium risk)
4. **Phase 4**: Simplify platform files (4-5 hours, higher risk)

**Total time**: ~10 hours of work
**Total impact**: Remove 89% of taskfiles, eliminate all circular dependencies

---

## Testing Strategy

After each phase:

1. **Test on macOS**: `./install.sh` (dry run first with added echo statements)
2. **Test updates**: `bash management/scripts/update-macos.sh`
3. **Verify tools installed**: Check `~/go/bin/`, `~/.cargo/bin/`, etc.
4. **Test symlinks**: `task symlinks:check`
5. **Test docs**: `task docs:serve`

---

## Migration Notes

**For users**:
- `./install.sh` remains the entry point (no change)
- Most task commands will be removed
- Only keep: `task symlinks:*`, `task docs:*`, `task fonts:*`

**Documentation to update**:
- Remove references to platform taskfiles
- Update README to show simplified Task usage
- Add note about Task being for build automation only

---

## Conclusion

The current taskfile structure is **over-engineered**. Task is a build automation tool, not a package manager wrapper.

**The fix**: Keep Task for what it's good at (building Go apps, running docs, managing symlinks). Use bash scripts for everything else.

This results in:
- **Clearer architecture** - Fewer abstractions
- **Easier maintenance** - Less code to maintain
- **Better debugging** - Simpler error traces
- **Proper tool usage** - Task for builds, bash for orchestration

**Next step**: Decide which phases to implement.
