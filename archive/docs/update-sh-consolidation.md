# Update.sh Consolidation Plan

## Problem Statement

Current update system is fragmented across 6 files with unnecessary complexity:

- Top-level update.sh just calls other scripts (boilerplate layer)
- Each platform script (macos/wsl/arch) has logging boilerplate
- common/update.sh has useless platform detection for step counting
- Dead code: 4 blocks checking DOTFILES_FAILURE_REGISTRY
- Broken references: init_failure_registry, display_failure_summary
- Excessive logging throughout

## Design Goals

Follow successful patterns from font installers:

1. **Functions do pure work** - no logging/printing inside functions
2. **Visual indicators at call site** - top-level has print/log functions
3. **Continue-on-error semantics** - no `set -e`, use `set -uo pipefail`
4. **Simple error handling** - functions return 0/1, print_warning on failure
5. **No abstraction overhead** - single file, clear sections, minimal complexity
6. **Consistent step presentation** - no platform-specific step counting

## Current File Structure

```text
update.sh                      # Top-level wrapper (calls other scripts)
├─ management/macos/update.sh  # Homebrew + Mac App Store (2 steps)
├─ management/wsl/update.sh    # apt packages (1 step)
├─ management/arch/update.sh   # pacman + AUR (2 steps)
└─ management/common/update.sh # Languages + plugins (5 steps)
```

**Total**: 6 files, ~230 lines (including boilerplate)

## Issues with Current Implementation

### 1. Broken References (update.sh)

```bash
Line 24: init_failure_registry        # Function doesn't exist
Line 66: display_failure_summary      # Function doesn't exist
```

### 2. Dead Code (management/common/update.sh)

```bash
Lines 64-71:   # Check DOTFILES_FAILURE_REGISTRY - never set
Lines 83-90:   # Check DOTFILES_FAILURE_REGISTRY - never set
Lines 114-119: # Check DOTFILES_FAILURE_REGISTRY - never set
Lines 147-154: # Check DOTFILES_FAILURE_REGISTRY - never set
```

### 3. Useless Complexity (management/common/update.sh)

```bash
Lines 25-43: Platform detection just to set START_STEP
  macos: START_STEP=3  # After Homebrew + Mac App Store
  wsl:   START_STEP=2  # After System Packages
  arch:  START_STEP=3  # After System Packages + AUR

# Used to calculate step numbers in print_banner calls
# Adds calculation overhead for purely visual numbering
```

### 4. Error Handling Mismatch

- Uses `set -euo pipefail` (auto-exit on error)
- Then wraps with `|| log_warning` (expects to continue)
- Contradiction: `-e` exits, `||` expects to catch failures

### 5. Excessive Boilerplate

Each script sources same libraries, sets DOTFILES_DIR, exports TERM, etc.

## Proposed Structure

**Single file**: `update.sh` (~150-180 lines, 25-35% reduction)

```sql
#!/usr/bin/env bash
set -uo pipefail  # Explicit error handling (no auto-exit)

# Setup
DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source libraries...
detect platform...

# ================================================================
# Platform Update Functions (pure work, no logging)
# ================================================================

upgrade_homebrew() { ... }
upgrade_mas() { ... }
upgrade_apt() { ... }
upgrade_pacman() { ... }
upgrade_yay() { ... }

# ================================================================
# Language & Tool Update Functions (pure work, no logging)
# ================================================================

update_npm_globals() { ... }
update_uv_tools() { ... }
update_cargo_packages() { ... }
update_shell_plugins() { ... }
update_tmux_plugins() { ... }

# ================================================================
# Main Update Orchestration (visual indicators here)
# ================================================================

print_header "Dotfiles Update" "brightcyan"

# Platform updates
print_section "Platform Updates" "brightmagenta"
case "$PLATFORM" in
  macos)
    log_info "Updating Homebrew packages..."
    upgrade_homebrew || print_warning "Homebrew update failed"

    log_info "Updating Mac App Store apps..."
    upgrade_mas || print_warning "mas update failed (try: mas signin)"
    ;;
  wsl)
    log_info "Updating system packages..."
    upgrade_apt || print_warning "apt update failed"
    ;;
  arch)
    log_info "Updating system packages..."
    upgrade_pacman || print_warning "pacman update failed"

    log_info "Updating AUR packages..."
    upgrade_yay || print_warning "yay update failed"
    ;;
esac

# Language & tool updates
print_section "Language & Tools" "brightmagenta"

log_info "Updating npm global packages..."
update_npm_globals || print_warning "npm update failed"

log_info "Updating Python tools (uv)..."
update_uv_tools || print_warning "uv update failed"

log_info "Updating Rust packages (cargo)..."
update_cargo_packages || print_warning "cargo update failed"

log_info "Updating shell plugins..."
update_shell_plugins || print_warning "shell plugin updates failed"

log_info "Updating tmux plugins..."
update_tmux_plugins || print_warning "tmux plugin update failed"

print_banner_success "Updates complete"
```

## Benefits of Consolidation

1. **Single source of truth** - all update logic in one file
2. **Clear structure** - functions section + orchestration section
3. **No step counting** - remove useless platform detection for numbering
4. **Consistent error handling** - `set -uo pipefail` + `|| print_warning`
5. **Easier to maintain** - see all updates at once, no jumping between files
6. **Less boilerplate** - one setup block instead of 6
7. **Better readability** - log messages at call site show intent

## Function Patterns

### Platform Updates

```bash
upgrade_homebrew() {
  brew update || return 1
  brew upgrade || return 1
  brew upgrade --cask --greedy || return 1
  return 0
}

upgrade_mas() {
  # Skip if not installed
  command -v mas >/dev/null 2>&1 || return 0

  # Run update, return exit code
  mas upgrade
}

upgrade_apt() {
  sudo apt update || return 1
  sudo apt upgrade -y || return 1
  return 0
}

upgrade_pacman() {
  sudo pacman -Syu --noconfirm
}

upgrade_yay() {
  # Skip if not installed
  command -v yay >/dev/null 2>&1 || return 0

  yay -Syu --noconfirm
}
```

### Language & Tool Updates

```bash
update_npm_globals() {
  # Skip if nvm not available
  [[ ! -d "$HOME/.config/nvm" ]] && return 0

  # Source nvm and run npm-install-globals.sh
  export NVM_DIR="$HOME/.config/nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

  bash "$DOTFILES_DIR/management/common/install/language-tools/npm-install-globals.sh"
}

update_uv_tools() {
  command -v uv >/dev/null 2>&1 || return 0

  source "$HOME/.local/bin/env" 2>/dev/null || true
  uv tool upgrade --all
}

update_cargo_packages() {
  command -v cargo >/dev/null 2>&1 || return 0

  source "$HOME/.cargo/env" 2>/dev/null || true
  cargo install-update -a
}

update_shell_plugins() {
  local plugins_dir="$HOME/.config/shell/plugins"
  [[ ! -d "$plugins_dir" ]] && return 0

  local plugins
  plugins=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" \
    --type=shell-plugins --format=names)

  local failed=0
  for name in $plugins; do
    local plugin_dir="$plugins_dir/$name"
    [[ ! -d "$plugin_dir" ]] && continue

    cd "$plugin_dir" || continue

    # Get default branch
    local branch
    branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
    [[ -z "$branch" ]] && branch=$(git remote show origin | grep 'HEAD branch' | cut -d' ' -f5)

    # Update plugin
    git pull origin "$branch" --quiet || ((failed++))
  done

  return $failed
}

update_tmux_plugins() {
  local tpm_dir="$HOME/.config/tmux/plugins/tpm"
  local update_script="$tpm_dir/bin/update_plugins"

  [[ ! -f "$update_script" ]] && return 0

  "$update_script" all
}
```

### Error Handling Pattern

```bash
# At call site - logging and error handling
log_info "Updating Homebrew packages..."
if ! upgrade_homebrew; then
  print_warning "Homebrew update failed"
  print_info "Manual steps:"
  print_info "  brew update"
  print_info "  brew upgrade"
  print_info "  brew upgrade --cask --greedy"
fi

# Or shorter form
log_info "Updating Homebrew packages..."
upgrade_homebrew || print_warning "Homebrew update failed (run manually: brew update && brew upgrade)"
```

## Implementation Phases

### Phase 1: Create Consolidated Script

- Create new update.sh with all functions
- Use `set -uo pipefail` (explicit error handling)
- Move platform-specific updates to functions
- Move common updates to functions
- Add orchestration section with visual indicators

### Phase 2: Remove Old Files

- Delete management/macos/update.sh
- Delete management/wsl/update.sh
- Delete management/arch/update.sh
- Delete management/common/update.sh

### Phase 3: Testing

- Test on macOS: `./update.sh`
- Verify all updates run
- Verify continue-on-error behavior
- Verify warnings display correctly

### Phase 4: Documentation

- Update docs/reference/tasks.md if update tasks mentioned
- Update CHANGELOG.md

## Comparison: Before vs After

### Before (6 files, ~230 lines total)

```bash
update.sh (71 lines)
├─ Calls init_failure_registry (BROKEN)
├─ Detects platform
├─ Calls management/{platform}/update.sh
├─ Calls management/common/update.sh
└─ Calls display_failure_summary (BROKEN)

management/macos/update.sh (40 lines)
├─ Source libraries (boilerplate)
├─ Step 1: Homebrew
└─ Step 2: Mac App Store

management/wsl/update.sh (23 lines)
├─ Source libraries (boilerplate)
└─ Step 1: System packages

management/arch/update.sh (33 lines)
├─ Source libraries (boilerplate)
├─ Step 1: System packages
└─ Step 2: AUR packages

management/common/update.sh (159 lines)
├─ Source libraries (boilerplate)
├─ Platform detection for START_STEP (USELESS)
├─ Step START_STEP: npm globals
├─ Step START_STEP+1: Python/uv (+ dead code)
├─ Step START_STEP+2: Rust/cargo (+ dead code)
├─ Step START_STEP+3: Shell plugins (+ dead code)
└─ Step START_STEP+4: Tmux plugins (+ dead code)
```

### After (1 file, ~150-180 lines)

```bash
update.sh (~150-180 lines)
├─ Setup (source libraries, detect platform)
├─ Platform update functions (30-40 lines)
│  ├─ upgrade_homebrew()
│  ├─ upgrade_mas()
│  ├─ upgrade_apt()
│  ├─ upgrade_pacman()
│  └─ upgrade_yay()
├─ Language/tool update functions (60-80 lines)
│  ├─ update_npm_globals()
│  ├─ update_uv_tools()
│  ├─ update_cargo_packages()
│  ├─ update_shell_plugins()
│  └─ update_tmux_plugins()
└─ Orchestration (40-50 lines)
   ├─ Platform updates (case statement)
   └─ Language/tool updates (sequential)
```

## What to Keep from Current Implementation

### Keep These Patterns

1. **Manual step suggestions** - when failures occur, show recovery steps
2. **Command checks** - `command -v tool >/dev/null` before running
3. **Shell plugin update logic** - git pull with default branch detection
4. **npm-install-globals.sh reuse** - don't inline, call existing script
5. **Source cargo/nvm env** - ensure tools are in PATH

### Keep These Commands

```bash
# Homebrew
brew update
brew upgrade
brew upgrade --cask --greedy  # Also update auto-updating casks

# Mac App Store
mas upgrade

# apt (WSL)
sudo apt update && sudo apt upgrade -y

# pacman (Arch)
sudo pacman -Syu --noconfirm

# yay (Arch AUR)
yay -Syu --noconfirm

# npm globals
bash "$lang_tools/npm-install-globals.sh"

# Python/uv
uv tool upgrade --all

# Rust/cargo
cargo install-update -a

# Shell plugins
git pull origin "$default_branch" --quiet

# Tmux plugins
$TPM_DIR/bin/update_plugins all
```

## What NOT to Copy from install.sh

Based on user feedback about install.sh issues:

1. **NO failure registry** - updates don't need structured failure tracking
2. **NO run_installer wrapper** - updates are simpler, don't need wrapper abstraction
3. **NO step counting complexity** - remove platform-specific START_STEP calculation
4. **NO excessive abstraction** - keep it straightforward
5. **NO output_failure_data** - use simple print_warning with manual steps

## Edge Cases & Error Scenarios

### mas not logged in

```bash
log_info "Updating Mac App Store apps..."
if ! upgrade_mas; then
  print_warning "mas update failed"
  print_info "If not signed in, run: mas signin"
fi
```

### cargo-update not installed

```bash
update_cargo_packages() {
  command -v cargo >/dev/null 2>&1 || return 0

  # Check if cargo-update is installed
  if ! cargo install-update --help >/dev/null 2>&1; then
    echo "cargo-update not installed, run: cargo install cargo-update" >&2
    return 1
  fi

  source "$HOME/.cargo/env" 2>/dev/null || true
  cargo install-update -a
}
```

### Shell plugin git pull failure

```bash
update_shell_plugins() {
  # ... setup ...

  local failed=0
  for name in $plugins; do
    # ... validation ...

    if ! git pull origin "$branch" --quiet; then
      echo "Failed to update $name" >&2
      ((failed++))
    fi
  done

  # Return failure count as exit code (0 = success, >0 = some failed)
  return $failed
}
```

### nvm not sourced

```bash
update_npm_globals() {
  export NVM_DIR="$HOME/.config/nvm"

  # Check if nvm.sh exists
  [[ ! -s "$NVM_DIR/nvm.sh" ]] && return 0

  # Source nvm
  source "$NVM_DIR/nvm.sh"

  # Run npm globals installer
  bash "$DOTFILES_DIR/management/common/install/language-tools/npm-install-globals.sh"
}
```

## Testing Checklist

- [ ] Script runs without errors on macOS
- [ ] Script runs without errors on WSL
- [ ] Script runs without errors on Arch
- [ ] All platform updates execute
- [ ] All language/tool updates execute
- [ ] Failures show warnings (not exit)
- [ ] Script continues after failures
- [ ] Manual step suggestions appear on failures
- [ ] No references to DOTFILES_FAILURE_REGISTRY
- [ ] No calls to init_failure_registry or display_failure_summary
- [ ] Timing information displayed at end
- [ ] Exit code is 0 even if some updates fail

## Success Criteria

1. ✅ Single update.sh file consolidates all update logic
2. ✅ Functions do pure work, no logging inside
3. ✅ Top-level orchestration has visual indicators
4. ✅ Uses `set -uo pipefail` (explicit error handling)
5. ✅ Continues on errors, shows warnings
6. ✅ No step counting complexity
7. ✅ No dead code (DOTFILES_FAILURE_REGISTRY)
8. ✅ No broken references (init_failure_registry, display_failure_summary)
9. ✅ 25-35% line reduction (230 → 150-180 lines)
10. ✅ Clear, maintainable, follows font installer pattern

## Notes from User Feedback

> "For each platform update script, they now each have the boilerplate of sourcing and then doing a bunch of logging, looking at macos/update.sh the actual commands are brew update, brew upgrade, (not sure what is brew upgrade --cask --greedy, i have never used that myself), mas upgrade, and that is it."

- Reduce boilerplate by consolidating
- Actual work is minimal (2-3 commands per platform)

> "In general this could be an upgrade_macos() function in the main update.sh file, then it would follow the pattern that is nice which we found with the font installers where the log and print functions are in the top level used as visual indicators to avoid needing comments, and then the functions purely do the work."

- Functions do work only
- Logging at call site for visual indicators

> "the platform detection just to decide which step to display is incredibly useless and adds complexity and calculation to code, that should be absolutely removed, force macos to be the same, don't count brew and mas as separate, but just platform updates as one thing."

- Remove START_STEP calculation
- Simplify to single "Platform Updates" section

> "Along with doing the cleanup of old functions and registries we don't need, but keep the manual steps and they can just be print_warning probably if failure (not expected)"

- Remove DOTFILES_FAILURE_REGISTRY dead code
- Keep manual step suggestions
- Use print_warning for failures

> "Let's take some hints from install.sh, but not try to make it exact, as I see quite a few issues with install.sh itself that I don't want to copy"

- Don't copy failure registry pattern
- Don't copy excessive abstraction
- Focus on simplicity

## brew upgrade --cask --greedy Explanation

From Homebrew docs:

- `--cask`: Upgrade cask installations (GUI apps)
- `--greedy`: Also upgrade casks with `auto_updates true` or `version :latest`

Without `--greedy`, Homebrew skips casks that:

- Auto-update themselves (e.g., browsers, Slack, Discord)
- Are marked as always latest

With `--greedy`, Homebrew updates these too, ensuring:

- You get the latest version even if the app auto-updates
- Homebrew tracking stays accurate
- No version drift between Homebrew and actual app

Example apps that need `--greedy`:

- Google Chrome (auto-updates)
- Firefox (auto-updates)
- Slack (auto-updates)
- Visual Studio Code (auto-updates)

**Verdict**: Keep `--greedy` to ensure all casks are up-to-date.
