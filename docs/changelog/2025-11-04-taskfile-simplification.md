# Taskfile System Simplification

## Problem Statement

The Taskfile system had grown bloated with 86+ wrapper tasks that added no value beyond simple command execution. Many tasks were just wrappers around single commands (`task brew:clean` = `brew cleanup`), making the system harder to navigate and maintain. Additionally, there were verification tasks with hardcoded package lists that would become outdated as packages were added or removed.

The system violated the Taskfile best practices of using tasks for orchestration rather than simple command wrappers.

## Solution Overview

Radically simplified the Taskfile system by removing all wrapper tasks and focusing on orchestration. Adopted a "tasks for orchestration, not wrappers" philosophy following official [Taskfile best practices](https://taskfile.dev/docs/guide).

**Key Changes:**
- Removed all verify/check tasks (18 tasks)
- Removed wrapper tasks for info/update/cleanup/doctor/notes (30+ tasks)
- Simplified task names (`install-all` → `install`)
- Made all install tasks idempotent
- Centralized shell plugins to read from `config/packages.yml`
- Added `silent: true` to all tasks for clean output
- Completely rewrote documentation to reflect simpler approach

## Tasks Removed

### Verification Tasks (18 removed)
- `brew:verify` - Checked if Brewfile packages installed
- `npm:verify` - Checked hardcoded list of npm packages
- `uv:verify` - Checked hardcoded list of uv tools
- `nvm:verify` - Checked if nvm/node installed
- `shell:verify` - Checked hardcoded list of shell plugins
- `macos:verify` - Checked if Homebrew/Xcode installed
- `wsl:verify` - Checked hardcoded list of tools
- `arch:verify` - Checked hardcoded list of tools
- Main `check` and `verify` tasks

### Wrapper Tasks (30+ removed)

**Homebrew:**
- `brew:clean` → Use `brew cleanup` directly
- `brew:doctor` → Use `brew doctor` directly
- `brew:info` → Use `brew --version` directly
- `brew:list` → Use `brew list` directly
- `brew:check-python-deps` → Use `brew uses --installed python@X` directly

**npm:**
- `npm:update` → Use `npm update -g` directly

**uv:**
- `uv:update` → Use `uv tool upgrade --all` directly

**nvm:**
- `nvm:update-nvm` → Use git commands directly

**Shell:**
- `shell:list` → Use `ls -1 ~/.config/zsh/plugins` directly
- `shell:info` → Use git commands directly
- `shell:clean` → Use `rm -rf` directly
- `shell:reinstall` → Removed

**macOS:**
- `macos:verify` → Removed
- `macos:info` → Use `sw_vers` directly
- `macos:update` → Use `softwareupdate` directly
- `macos:cleanup` → Use `brew cleanup` directly
- `macos:doctor` → Use `brew doctor` directly
- `macos:install-prerequisites` → Consolidated
- `macos:install-essential-tools` → Consolidated

**WSL:**
- `wsl:verify` → Removed
- `wsl:info` → Use `uname -r` directly
- `wsl:update` → Use `apt` directly
- `wsl:cleanup` → Use `apt` directly
- `wsl:update-system` → Consolidated into install-packages

**Arch:**
- `arch:verify` → Removed
- `arch:info` → Use `uname -r` directly
- `arch:update` → Use `pacman` directly
- `arch:cleanup` → Use `pacman` directly
- `arch:notes` → Removed
- `arch:update-system` → Consolidated into install-packages

## Tasks Simplified

**Renamed for Consistency:**
- `brew:install-all` → `brew:install`
- `npm:install-all` → `npm:install`
- `uv:install-all` → `uv:install`

**Removed Separate Install Tasks:**
- `brew:install-formulas` - Not needed, just use `brew:install`
- `brew:install-casks` - Not needed, just use `brew:install`
- `npm:install-language-servers` - Consolidated into `npm:install`
- `npm:install-linters-formatters` - Consolidated into `npm:install`
- `uv:install-linters-formatters` - Consolidated into `uv:install`
- `uv:install-code-quality` - Consolidated into `uv:install`
- `uv:install-sql` - Consolidated into `uv:install`
- `uv:install-markdown` - Consolidated into `uv:install`
- `uv:install-template` - Consolidated into `uv:install`
- `uv:install-utilities` - Consolidated into `uv:install`

## Tasks Added/Modified

**Shell Plugin Centralization:**
Modified `shell:install`, `shell:update`, and removed `shell:verify` to read plugins dynamically from `config/packages.yml` using `yq` instead of having hardcoded plugin names in multiple places.

**Silent Flag:**
Added `silent: true` to all tasks to prevent command echo noise and show only actual output.

**Internal Flag:**
Added `internal: true` to helper tasks (configure-finder, configure-dock, etc.) so they don't clutter `task --list` output.

## Files Modified

**Taskfiles:**
- `Taskfile.yml` - Removed check/verify, updated install orchestration
- `taskfiles/brew.yml` - Removed verify, clean, doctor, info, list, check-python-deps
- `taskfiles/npm.yml` - Removed verify, update; simplified install
- `taskfiles/uv.yml` - Removed verify, update; simplified install
- `taskfiles/nvm.yml` - Removed verify, update-nvm
- `taskfiles/shell.yml` - Removed verify, list, info, clean, reinstall; centralized to read from config
- `taskfiles/macos.yml` - Removed verify, info, update, cleanup, doctor; consolidated install tasks
- `taskfiles/wsl.yml` - Removed verify, info, update, cleanup, update-system
- `taskfiles/arch.yml` - Removed verify, info, update, cleanup, notes, update-system

**Documentation:**
- `docs/reference/tasks.md` - Complete rewrite emphasizing orchestration philosophy
- `CLAUDE.md` - Removed theme task references (from previous cleanup)
- `macos/.local/bin/theme-sync` - Updated help text

**Config:**
- `config/packages.yml` - Already had shell plugins defined; now used as single source of truth

## Testing Methodology

**Task Count Verification:**
```sh
# Before
task --list | wc -l
# Output: 86 tasks

# After
task --list | wc -l
# Output: 40 tasks
# 53% reduction
```

**Task List Output:**
```sh
task --list
# Verified clean output with only meaningful orchestration tasks
```

**Install Dry Run:**
```sh
task install --dry
# Verified orchestration flow works correctly
```

**Shell Plugin Verification:**
```sh
yq eval '.shell_plugins[] | .name + "|" + .repo' config/packages.yml
# Verified yq parsing works correctly

task shell:install --dry
# Verified dynamic plugin reading works
```

## Final Resolution

The Taskfile system is now:
- **53% smaller** (40 tasks vs 86 tasks)
- **More maintainable** - No hardcoded lists to keep updated
- **Clearer purpose** - Only orchestration tasks remain
- **Better documented** - Philosophy and direct commands clearly explained
- **Idempotent** - All install tasks can be run multiple times safely
- **Cleaner output** - Silent flag removes command echo noise

**Core Tasks Remaining:**
- `install`, `install-macos`, `install-wsl`, `install-arch` - Platform orchestration
- `update`, `clean` - Multi-component orchestration
- `brew:install`, `npm:install`, `uv:install`, `nvm:install`, `shell:install` - Component installation
- `macos:configure`, `wsl:configure-wsl`, `arch:configure` - Platform configuration
- `docs:serve`, `docs:build`, `docs:deploy` - Documentation management

## Key Learnings

### Orchestration vs Wrappers

Tasks should coordinate multiple operations, not wrap single commands. If a task just runs one command, users should run that command directly. This makes the system more transparent and reduces maintenance burden.

**Bad (wrapper):**
```yaml
update:
  desc: Update packages
  cmds:
    - sudo apt update && sudo apt upgrade -y
```

**Good (orchestration):**
```yaml
update:
  desc: Update all packages
  cmds:
    - task: brew:update
    - npm update -g
    - uv tool upgrade --all
    - task: shell:update
```

### Single Source of Truth

Hardcoding lists (like package names) in multiple tasks creates maintenance problems. Use configuration files and read them dynamically.

**Before:** Plugin names hardcoded in `install-git-open`, `install-zsh-vi-mode`, `update-git-open`, `update-zsh-vi-mode`, and `verify` tasks.

**After:** All tasks read from `config/packages.yml` using `yq`.

### Idempotent Installs > Verification

Instead of separate verification tasks, make install tasks idempotent. Let `npm install -g` and `uv tool install` handle checking if packages are already installed.

**Before:** Separate `verify` tasks that check and report missing packages.

**After:** Just run `task install` again - it will skip what's installed and add what's missing.

### Documentation is Critical

When simplifying a system, update documentation immediately. Users need to know:
- Why the change was made (philosophy)
- What commands to use directly
- What tasks remain and why

### Silent Output

Task execution with `silent: false` (default) shows both the command AND its output, which is noisy and hard to read. Adding `silent: true` shows only actual output.

## Related

- [Taskfile Best Practices](https://taskfile.dev/docs/guide)
