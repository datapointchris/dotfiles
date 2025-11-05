# Taskfile System Refactor - Comprehensive Plan

**Date:** 2025-11-04
**Goal:** Make the Taskfile system truly modular with platform-specific update-all commands

---

## Research Findings

### Taskfile Best Practices

1. **Includes for Modularity**
   - Use `includes` to separate concerns into logical groups
   - Set `internal: true` on includes for utility tasks not meant to be called directly
   - Use `dir` attribute to set working directory for included tasks
   - Can pass `vars` to includes to parameterize behavior

2. **Internal Tasks**
   - Mark utility/helper tasks as `internal: true`
   - These become function-like reusable components
   - Don't appear in `task --list` but can be called by other tasks
   - Perfect for shared update logic

3. **Variable Architecture**
   - Variables in includes can be overridden by parent Taskfile
   - Use `{{.VAR | default "value"}}` for defaults in reusable tasks
   - Can read from external YAML files using `sh:` or tools like `yq`

4. **Monorepo Patterns**
   - Root Taskfile includes component Taskfiles
   - Each component manages its own concerns
   - Platform-specific logic isolated to platform Taskfiles
   - Internal includes prevent task namespace pollution

---

## Current Issues Analysis

1. **Generic Tasks Are Ambiguous**
   - `task update` - What does it update? Only brew, npm, uv
   - Missing: mas, cargo, shell plugins, tmux plugins, system packages
   - No platform-specific considerations

2. **Update and Upgrade Separated**
   - `brew:update` and `brew:upgrade` should be together
   - Same pattern should apply everywhere

3. **Component Lists Buried**
   - npm packages hardcoded in taskfiles/npm.yml
   - uv tools hardcoded in taskfiles/uv.yml
   - Shell plugins in config/packages.yml but not cargo, mas, etc.

4. **Missing Update Mechanisms**
   - No cargo update task
   - No mas (Mac App Store) update task
   - No tmux plugin update task (TPM handles this but not automated)
   - No system package manager updates (apt, pacman)

5. **Not Modular Enough**
   - Adding new components requires editing multiple files
   - No clear internal/public task separation
   - Duplication across platform files

---

## Design Decisions

### 1. Component Lists in config/packages.yml

Expand `config/packages.yml` to be the single source of truth for ALL updatable components:

```yaml
# config/packages.yml structure:
npm_globals:        # Already exists
uv_tools:           # Already exists
shell_plugins:      # Already exists
cargo_packages:     # NEW - rust tools installed via cargo install
mas_apps:           # NEW - Mac App Store apps (optional, usually in Brewfile)
tmux_plugins:       # NEW - TPM managed plugins
```

**Rationale:** Single file to edit when adding/removing components

### 2. Create Internal Update Task Modules

Create new internal taskfiles in `taskfiles/internal/`:

```text
taskfiles/
├── internal/
│   ├── cargo.yml           # cargo update logic
│   ├── mas.yml             # mas upgrade logic (macOS only)
│   ├── tmux-plugins.yml    # TPM update logic
│   ├── apt.yml             # apt update+upgrade (WSL/Ubuntu)
│   ├── pacman.yml          # pacman -Syu (Arch)
│   └── yay.yml             # yay -Syu (Arch AUR)
├── brew.yml                # Keep existing, mark update tasks internal
├── npm.yml                 # Keep existing, mark update tasks internal
├── uv.yml                  # Keep existing, mark update tasks internal
├── shell.yml               # Keep existing, mark update tasks internal
├── macos.yml               # Keep, add macos:update-all
├── wsl.yml                 # Keep, add wsl:update-all
└── arch.yml                # Keep, add arch:update-all
```

**Rationale:**

- Clear separation of internal implementation vs public commands
- Each component has its own update logic
- Platform files orchestrate platform-specific combinations

### 3. Platform-Specific update-all Commands

Create comprehensive update commands for each platform:

**macOS (`macos:update-all`):**

1. brew update && brew upgrade (formulas + casks)
2. mas upgrade (Mac App Store apps)
3. npm update -g (global packages via nvm)
4. uv tool upgrade --all (Python tools)
5. cargo install-update -a (Rust tools, if cargo-update installed)
6. Update zsh plugins (git pull in each)
7. Update tmux plugins (via TPM)

**WSL (`wsl:update-all`):**

1. sudo apt update && sudo apt upgrade -y
2. npm update -g
3. uv tool upgrade --all
4. cargo install-update -a (if available)
5. Update zsh plugins
6. Update tmux plugins

**Arch (`arch:update-all`):**

1. sudo pacman -Syu (system packages)
2. yay -Syu (AUR packages)
3. npm update -g
4. uv tool upgrade --all
5. cargo install-update -a (if available)
6. Update zsh plugins
7. Update tmux plugins

### 4. Remove Generic Cross-Platform Tasks

**Remove from main Taskfile.yml:**

- `update` - Too ambiguous, use platform-specific
- `clean` - Use native commands directly
- `upgrade` - Doesn't exist in main but remove if found

**Keep in main Taskfile.yml:**

- `install` - Auto-detect and install (orchestration task)
- `install-macos`, `install-wsl`, `install-arch` - Platform installations
- `default` - Show available tasks

### 5. Install cargo-update if Needed

Add `cargo-update` installation to platform setup:

- macOS: `cargo install cargo-update` after rust/cargo available
- WSL: Same
- Arch: Available via `pacman -S cargo-update` or AUR

**Fallback:** If cargo-update not available, use manual update loop:

```sh
for pkg in $(cargo install --list | grep -E '^[a-z]' | cut -d' ' -f1); do
  cargo install "$pkg"
done
```

---

## Implementation Plan

### Phase 1: Expand config/packages.yml

1. Add `cargo_packages` section with currently installed cargo tools
2. Add `tmux_plugins` section (optional, TPM handles this)
3. Add `mas_apps` section (optional, usually managed by Brewfile)

**Files to modify:**

- `config/packages.yml`

### Phase 2: Create Internal Task Modules

1. Create `taskfiles/internal/` directory
2. Create `taskfiles/internal/cargo.yml` with:
   - `update` task (internal)
   - Checks for cargo-update, uses it if available
   - Falls back to manual loop
3. Create `taskfiles/internal/mas.yml` with:
   - `update` task (internal)
   - Runs `mas upgrade` (macOS only)
4. Create `taskfiles/internal/tmux-plugins.yml` with:
   - `update` task (internal)
   - Runs `~/.tmux/plugins/tpm/bin/update_plugins all`
5. Create `taskfiles/internal/apt.yml` with:
   - `update` task (internal)
   - Runs `sudo apt update && sudo apt upgrade -y`
6. Create `taskfiles/internal/pacman.yml` with:
   - `update` task (internal)
   - Runs `sudo pacman -Syu`
7. Create `taskfiles/internal/yay.yml` with:
   - `update` task (internal)
   - Runs `yay -Syu`

**Files to create:**

- `taskfiles/internal/cargo.yml`
- `taskfiles/internal/mas.yml`
- `taskfiles/internal/tmux-plugins.yml`
- `taskfiles/internal/apt.yml`
- `taskfiles/internal/pacman.yml`
- `taskfiles/internal/yay.yml`

### Phase 3: Update Existing Taskfiles

1. **brew.yml:**
   - Mark `update` and `upgrade` tasks as `internal: true`
   - Combine into single `update` task that does update+upgrade

2. **npm.yml:**
   - Mark any update tasks as `internal: true`
   - Add `update` task if missing

3. **uv.yml:**
   - Mark any update tasks as `internal: true`
   - Add `update` task if missing

4. **shell.yml:**
   - Mark `update` task as `internal: true`

**Files to modify:**

- `taskfiles/brew.yml`
- `taskfiles/npm.yml`
- `taskfiles/uv.yml`
- `taskfiles/shell.yml`

### Phase 4: Update Platform Taskfiles

1. **macos.yml:**
   - Include internal taskfiles
   - Create `update-all` task that calls all update tasks in sequence
   - Add informative echo statements between each step

2. **wsl.yml:**
   - Include internal taskfiles
   - Create `update-all` task
   - Add informative echo statements

3. **arch.yml:**
   - Include internal taskfiles
   - Create `update-all` task
   - Add informative echo statements

**Files to modify:**

- `taskfiles/macos.yml`
- `taskfiles/wsl.yml`
- `taskfiles/arch.yml`

### Phase 5: Update Main Taskfile.yml

1. Add includes for internal taskfiles with `internal: true`
2. Remove `update` task
3. Remove `clean` task
4. Keep `install` and platform-specific install tasks

**Files to modify:**

- `Taskfile.yml`

### Phase 6: Update Documentation

1. **docs/reference/tasks.md:**
   - Remove references to generic `task update`
   - Add section for platform-specific update commands
   - Document `macos:update-all`, `wsl:update-all`, `arch:update-all`
   - Update philosophy section
   - Add examples of what each platform updates

**Files to modify:**

- `docs/reference/tasks.md`

### Phase 7: Create Changelog

1. Create `docs/changelog/2025-11-04-taskfile-modularity.md`
2. Update `docs/changelog.md` with summary

**Files to create/modify:**

- `docs/changelog/2025-11-04-taskfile-modularity.md`
- `docs/changelog.md`

---

## Testing Plan

1. **Syntax Check:**

   ```sh
   task --list           # Should parse without errors
   task --list-all       # Should show all tasks including internal
   ```

2. **Verify Internal Tasks Hidden:**

   ```sh
   task --list           # Should NOT show internal update tasks
   ```

3. **Test Platform Update-All (macOS):**

   ```sh
   task macos:update-all --dry    # Dry run to see what would execute
   # Then run for real and verify each component updates
   ```

4. **Verify Component Updates Work Individually:**

   ```sh
   # These should fail (internal tasks)
   task brew:update        # Should error or not be in list

   # Platform updates should work
   task macos:update-all   # Should succeed
   ```

5. **Check Documentation:**
   - Verify all links in tasks.md work
   - Verify examples are accurate
   - Test MkDocs build: `task docs:build`

---

## Expected Outcomes

### Before Refactor

- Generic `task update` only updates brew, npm, uv
- No way to update everything on a platform
- Component lists scattered across files
- Unclear what tasks are for users vs internal use

### After Refactor

- Clear platform-specific commands: `task macos:update-all`
- All updatable components included (brew, mas, npm, uv, cargo, shell, tmux)
- Single source of truth for component lists: `config/packages.yml`
- Clean separation of internal vs public tasks
- Easy to add new components (add to config, create internal task, include in platform update-all)
- Comprehensive documentation

---

## Risks and Mitigations

1. **Risk:** Breaking existing workflows
   - **Mitigation:** Document migration path, old commands will error clearly

2. **Risk:** cargo-update not available
   - **Mitigation:** Check for it, fallback to manual loop

3. **Risk:** TPM not installed
   - **Mitigation:** Check for TPM directory before trying to update

4. **Risk:** Platform detection fails
   - **Mitigation:** Keep existing platform detection logic, users can still call platform tasks directly

---

## Success Criteria

- [ ] All taskfiles parse correctly (`task --list` works)
- [ ] Internal tasks don't appear in `task --list`
- [ ] `task macos:update-all` updates all components
- [ ] `task wsl:update-all` updates all components
- [ ] `task arch:update-all` updates all components
- [ ] Documentation is comprehensive and accurate
- [ ] Changelog documents the change thoroughly
- [ ] Can add new component by: editing config/packages.yml, creating internal task, adding to update-all

---

## Notes

- This is a significant refactor but maintains backwards compatibility for install tasks
- Users will need to change from `task update` to `task macos:update-all` (or their platform)
- Much clearer what's being updated and platform-specific
- Sets foundation for easy expansion (new package managers, new tools)
