# Repository Restructure Plan - November 2025

## Objective

Reorganize the dotfiles repository to clearly separate:

1. **platforms/** - System configurations that get deployed
2. **apps/** - Personal CLI applications
3. **management/** - Repository management tools and scripts

## Goals

- Clear mental model: "What is this directory for?"
- Clean separation of concerns
- No confusion between dotfiles, apps, and repo tooling
- Taskfile only interfaces with management/
- Fix tools registry location (XDG compliance)
- Rename "tools" to "toolbox" (no namespace confusion)

## Current vs New Structure

### Current (Problematic)

```text
dotfiles/
├── common/           # Mix of configs and app source
├── macos/            # Platform configs
├── wsl/              # Platform configs
├── tools/            # Mix of repo tools (symlinks) and personal apps (sess)
├── config/           # Random packages.yml
├── install/          # Setup scripts
├── taskfiles/        # Task automation
└── docs/tools/registry.yml  # Wrong location!
```

### New (Clean)

```text
dotfiles/
├── platforms/        # System configurations
│   ├── common/
│   ├── macos/
│   └── wsl/
├── apps/             # Personal applications
│   ├── common/
│   ├── macos/
│   └── sess/
├── management/       # Repository tooling
│   ├── symlinks/
│   ├── taskfiles/
│   ├── packages.yml
│   └── *.sh (setup scripts)
└── docs/
```

## Pre-Migration Checklist

- [ ] Commit all current changes
- [ ] Create new branch: `git checkout -b repo-restructure`
- [ ] Verify symlinks manager works before migration
- [ ] Document current working state
- [ ] Back up any local-only files

## Migration Steps

### Phase 1: Create New Structure

```bash
# Create top-level directories
mkdir -p platforms apps management

# Create platform subdirectories
mkdir -p platforms/{common,macos,wsl}

# Create apps subdirectories
mkdir -p apps/{common,macos}

# Management will be populated by moving existing dirs
```

**Verification**: `ls -d */ | grep -E 'platforms|apps|management'`

---

### Phase 2: Move Platforms

**Action**: Move platform configurations

```bash
# Move common platform files
# Note: Using rsync to preserve structure, then verify before removing source
rsync -av common/ platforms/common/
# Verify, then: rm -rf common

# Move macos platform files
rsync -av macos/ platforms/macos/
# Verify, then: rm -rf macos

# Move wsl platform files
rsync -av wsl/ platforms/wsl/
# Verify, then: rm -rf wsl
```

**Critical**: Verify `.config/` structure is preserved:

```bash
ls platforms/common/.config/
# Should show: nvim, tmux, zsh, etc.
```

**Git**:

```bash
git add platforms/
git commit -m "refactor: move platform configs to platforms/ directory"
```

---

### Phase 3: Extract and Move Apps

**Action**: Separate apps from platform configs

```bash
# Apps currently in platforms/common/.local/bin/
cd platforms/common/.local/bin/

# Move to apps/common/
mv menu notes printcolors shelldocsparser tmux-colors-from-tinty ../../../../apps/common/

# Rename tools → toolbox
mv tools ../../../../apps/common/toolbox

# Handle theme-sync (check if it exists)
[ -f theme-sync ] && mv theme-sync ../../../../apps/common/

# Return to repo root
cd ../../../../
```

**Check for platform-specific apps**:

```bash
# Check if macos has any .local/bin/ apps
ls platforms/macos/.local/bin/ 2>/dev/null
# If exists, move to apps/macos/
```

**Move sess**:

```bash
# sess is currently in tools/sess/
# We'll move it after Phase 4
```

**Git**:

```bash
git add apps/
git add platforms/  # Changed files
git commit -m "refactor: extract apps from platforms to apps/ directory"
```

---

### Phase 4: Move Management Tools

**Action**: Consolidate repository management tools

```bash
# Move symlinks manager
mv tools/symlinks management/

# Move taskfiles
mv taskfiles management/

# Move install scripts directly to management/
mv install/macos-setup.sh management/
mv install/wsl-setup.sh management/
mv install/arch-setup.sh management/
rmdir install

# Move packages.yml from config/
mv config/packages.yml management/
rmdir config

# Move sess (last thing in tools/)
mv tools/sess apps/
rmdir tools
```

**Verification**:

```bash
ls management/
# Should show: symlinks/ taskfiles/ packages.yml macos-setup.sh wsl-setup.sh arch-setup.sh

ls apps/
# Should show: common/ macos/ sess/
```

**Git**:

```bash
git add management/ apps/
git rm -r tools/ install/ config/
git commit -m "refactor: consolidate repo tools in management/ directory"
```

---

### Phase 5: Rename tools → toolbox

**Action**: Rename the tool and update all references

```bash
# Already moved in Phase 3 as 'toolbox'
# Now update internal references

# Update the script itself
sed -i '' 's/DOTFILES_REGISTRY/TOOLBOX_REGISTRY/g' apps/common/toolbox

# Update registry path reference
sed -i '' 's|~/dotfiles/docs/tools/registry.yml|~/.config/toolbox/registry.yml|g' apps/common/toolbox

# Move registry to correct location in platforms
mkdir -p platforms/common/.config/toolbox
mv docs/tools/registry.yml platforms/common/.config/toolbox/
rmdir docs/tools
```

**Update documentation**:

```bash
# Update references in docs
grep -r "tools list" docs/ --files-with-matches | xargs sed -i '' 's/tools list/toolbox list/g'
grep -r "tools show" docs/ --files-with-matches | xargs sed -i '' 's/tools show/toolbox show/g'
# etc. (comprehensive grep/replace)
```

**Git**:

```bash
git add apps/common/toolbox platforms/common/.config/toolbox/
git rm docs/tools/registry.yml
git commit -m "refactor: rename tools to toolbox and move registry to XDG location"
```

---

### Phase 6: Update Symlinks Manager

**Action**: Update symlinks manager to handle new structure

**File**: `management/symlinks/symlinks/config.py`

Update paths to reflect new structure:

```python
# Line ~22
dotfiles_dir: Path = Field(
    default_factory=lambda: Path(os.environ.get("DOTFILES", Path.home() / "dotfiles")),
    description="Root directory of dotfiles repository",
)
```

No change needed here - dotfiles_dir is still the repo root.

**File**: `management/symlinks/symlinks/manager.py`

Add special handling for apps/ directory (add new method):

```python
def link_apps(self, platform: str) -> int:
    """Link apps from apps/{platform}/ to ~/.local/bin/

    Args:
        platform: Platform name (common, macos, wsl)

    Returns:
        Number of apps linked
    """
    apps_dir = self.dotfiles_dir / "apps" / platform
    if not apps_dir.exists():
        print(f"[yellow]No apps directory for {platform}[/]")
        return 0

    target_bin = self.target_dir / ".local" / "bin"
    target_bin.mkdir(parents=True, exist_ok=True)

    print(f"[blue]Linking {platform} apps to ~/.local/bin/...[/]")
    count = 0

    for app in apps_dir.iterdir():
        # Skip directories (like sess/ which needs building)
        if app.is_dir():
            continue

        if should_exclude(app):
            continue

        target = target_bin / app.name

        # Remove existing symlink or file
        if target.exists() or target.is_symlink():
            target.unlink()

        # Create relative symlink
        relative_source = make_relative_symlink(app, target)
        target.symlink_to(relative_source)
        print(f"  [green]✓[/] {app.name} → ~/.local/bin/{app.name}")
        count += 1

    return count
```

Update `create_symlinks` method to use new platform paths:

```python
def create_symlinks(self, platform: str) -> int:
    """Create symlinks for a platform.

    Args:
        platform: Platform name (common, macos, wsl, arch)

    Returns:
        Total number of symlinks created
    """
    # Link platform configs
    platform_dir = self.dotfiles_dir / "platforms" / platform
    if not platform_dir.exists():
        print(f"[red]✗[/] Platform directory does not exist: {platform}")
        return 0

    config_count = self._link_directory(platform_dir, platform)

    # Link apps
    app_count = self.link_apps(platform)

    return config_count + app_count

def _link_directory(self, source_dir: Path, layer: str) -> int:
    """Link files from source directory (old create_symlinks logic)"""
    # ... existing create_symlinks code renamed
```

**File**: `management/symlinks/symlinks/cli.py`

Update help text to reference new structure:

```python
# Update any path references from common/ to platforms/common/
```

**Test the changes**:

```bash
cd management/symlinks
uv run symlinks --help
uv run symlinks check common
```

**Git**:

```bash
git add management/symlinks/
git commit -m "refactor: update symlinks manager for new directory structure"
```

---

### Phase 7: Update Taskfiles

**Action**: Update all taskfile path references

**Main Taskfile.yml** (root):

```yaml
# Update includes to reference management/taskfiles/
includes:
  macos: ./management/taskfiles/macos.yml
  wsl: ./management/taskfiles/wsl.yml
  arch: ./management/taskfiles/arch.yml
  brew: ./management/taskfiles/brew.yml
  npm: ./management/taskfiles/npm.yml
  nvm: ./management/taskfiles/nvm.yml
  uv: ./management/taskfiles/uv.yml
  symlinks: ./management/taskfiles/symlinks.yml
  shell: ./management/taskfiles/shell.yml
  docs: ./management/taskfiles/docs.yml
```

**Update symlinks.yml**:

```yaml
# Change from tools/symlinks to management/symlinks
tasks:
  link:
    desc: "Link dotfiles for current platform"
    dir: management/symlinks
    cmds:
      - uv run symlinks link {{.PLATFORM}}

  # ... update all other tasks similarly
```

**Update npm.yml**:

```yaml
# Change packages.yml path from config/ to management/
tasks:
  install:
    cmds:
      - |
        PACKAGES=$(yq e '.npm_globals.language_servers[].name' management/packages.yml)
        # ... rest of logic
```

**Update all other taskfiles** that reference:

- `config/packages.yml` → `management/packages.yml`
- `tools/symlinks` → `management/symlinks`
- `common/` → `platforms/common/`

**Search for references**:

```bash
grep -r "config/packages.yml" management/taskfiles/
grep -r "tools/symlinks" management/taskfiles/
grep -r "\./common" management/taskfiles/
```

**Git**:

```bash
git add Taskfile.yml management/taskfiles/
git commit -m "refactor: update taskfile paths for new structure"
```

---

### Phase 8: Update Setup Scripts

**Action**: Update install scripts for new structure

**management/macos-setup.sh**:

```bash
# Update any references to:
# - common/ → platforms/common/
# - tools/symlinks → management/symlinks
# - taskfiles/ → management/taskfiles/

# Search for these patterns:
grep -n "common/" management/macos-setup.sh
grep -n "tools/" management/macos-setup.sh
```

Likely changes needed:

```bash
# Example updates (verify actual script content):
# OLD: cd common && ...
# NEW: cd platforms/common && ...

# OLD: ./tools/symlinks/...
# NEW: ./management/symlinks/...
```

**Repeat for**:

- `management/wsl-setup.sh`
- `management/arch-setup.sh`

**Git**:

```bash
git add management/*.sh
git commit -m "refactor: update setup scripts for new directory structure"
```

---

### Phase 9: Update Documentation

**Action**: Update all documentation for new structure

**Files to update**:

1. `README.md` - Update directory structure diagram
2. `CLAUDE.md` - Update project structure, paths, rules
3. `docs/architecture/index.md` - Update structure diagram
4. All other docs referencing old paths

**Search for references**:

```bash
# Find files referencing old structure
grep -r "common/.local/bin" docs/
grep -r "tools/symlinks" docs/
grep -r "config/packages.yml" docs/
grep -r "install/macos-setup" docs/
grep -r "^tools\s" docs/  # "tools" command references

# Update to:
# - apps/common/
# - management/symlinks/
# - management/packages.yml
# - management/macos-setup.sh
# - toolbox (command)
```

**Update documentation-audit plan**:

```bash
# Update .planning/documentation-audit-2025-11.md with new paths
# May need to adjust some tasks based on new structure
```

**Git** (multiple commits as you update sections):

```bash
git add README.md
git commit -m "docs: update README for new repository structure"

git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for new structure and toolbox rename"

git add docs/architecture/
git commit -m "docs: update architecture docs for new directory layout"

# ... more commits as you go through docs
```

---

### Phase 10: Update Apps for New Paths

**Action**: Update apps that reference repo structure

**apps/common/toolbox**:

```bash
# Already updated in Phase 5
# Verify registry path:
grep "REGISTRY" apps/common/toolbox
# Should show: REGISTRY="${XDG_CONFIG_HOME:-$HOME/.config}/toolbox/registry.yml"
```

**apps/common/menu**:

```bash
# Check if menu references any repo paths
grep "dotfiles" apps/common/menu
# Update any hardcoded paths to new structure
```

**Check other apps**:

```bash
for app in apps/common/*; do
  echo "=== $app ==="
  grep -n "dotfiles\|common/\|tools/" "$app" 2>/dev/null || echo "No references"
done
```

**Git**:

```bash
git add apps/
git commit -m "refactor: update app internal paths for new structure"
```

---

### Phase 11: Test Migration

**Action**: Verify everything still works

**Test symlinks manager**:

```bash
cd management/symlinks
uv run symlinks check common
uv run symlinks check macos  # or wsl
uv run symlinks show
```

**Test symlinks deployment** (in a safe way):

```bash
# Create a test directory
mkdir -p /tmp/dotfiles-test-home

# Test linking
cd management/symlinks
SYMLINKS_TARGET_DIR=/tmp/dotfiles-test-home uv run symlinks link common

# Verify structure
ls -la /tmp/dotfiles-test-home/.config/
ls -la /tmp/dotfiles-test-home/.local/bin/

# Clean up
rm -rf /tmp/dotfiles-test-home
```

**Test taskfiles**:

```bash
task --list-all
# Should work without errors

task symlinks:check
# Should show correct paths
```

**Test apps**:

```bash
# Verify toolbox works (after symlinking or direct run)
apps/common/toolbox list

# Check registry location
ls -la ~/.config/toolbox/registry.yml
# Should exist after platforms/common symlinked
```

**Test documentation build**:

```bash
task docs:serve
# Check http://localhost:8000
# Verify all links work
```

---

### Phase 12: Cleanup and Final Verification

**Action**: Remove old directories, clean up artifacts

**Verify old directories removed**:

```bash
# These should NOT exist:
ls common 2>&1 | grep "No such file"
ls macos 2>&1 | grep "No such file"
ls wsl 2>&1 | grep "No such file"
ls tools 2>&1 | grep "No such file"
ls install 2>&1 | grep "No such file"
ls config 2>&1 | grep "No such file"

# These SHOULD exist:
ls -d platforms apps management
```

**Verify new structure**:

```bash
tree -L 2 -d platforms apps management
```

**Check git status**:

```bash
git status
# Should show clean working directory or only expected changes
```

**Final commit**:

```bash
git add -A
git commit -m "refactor: complete repository restructure

- platforms/ for system configs
- apps/ for personal applications
- management/ for repo tooling
- Renamed tools → toolbox
- Moved registry to XDG location
- Updated all references and documentation"
```

---

### Phase 13: Deploy and Verify on Actual System

**Action**: Test on your actual system

**Backup current state**:

```bash
# Backup current symlinks
ls -la ~/.config > /tmp/config-before.txt
ls -la ~/.local/bin > /tmp/bin-before.txt
```

**Deploy from new structure**:

```bash
task symlinks:link
```

**Verify**:

```bash
# Check configs symlinked correctly
ls -la ~/.config/nvim
ls -la ~/.config/tmux
ls -la ~/.config/toolbox

# Check apps symlinked correctly
ls -la ~/.local/bin/menu
ls -la ~/.local/bin/toolbox
ls -la ~/.local/bin/notes

# Test apps work
toolbox list
menu help
theme-sync current
```

**Test workflow**:

```bash
# Try your normal workflow
# - Open tmux
# - Use menu
# - Check toolbox
# - Edit a config file
# - Run tasks
```

---

## Rollback Plan

If anything breaks:

```bash
# Return to previous commit
git log --oneline -10  # Find commit before restructure
git checkout <commit-hash>

# Or if on branch:
git checkout main  # Return to stable branch
```

## Success Criteria

- [ ] All three top-level directories exist: platforms/, apps/, management/
- [ ] Platform configs properly nested: platforms/{common,macos,wsl}/
- [ ] Apps separated by platform: apps/{common,macos}/
- [ ] sess/ in apps/
- [ ] Management tools consolidated: management/{symlinks/,taskfiles/,*.sh,packages.yml}
- [ ] tools renamed to toolbox
- [ ] Registry at platforms/common/.config/toolbox/registry.yml
- [ ] Symlinks manager handles apps/ → ~/.local/bin/
- [ ] All taskfiles reference management/ paths
- [ ] All documentation updated
- [ ] Symlinks deploy successfully
- [ ] Apps work from ~/.local/bin/
- [ ] Task commands work
- [ ] Documentation builds

## Post-Migration Tasks

1. Update GitHub README with new structure
2. Create a migration guide for anyone who forked
3. Update any external references to repo structure
4. Consider updating .gitignore if needed
5. Run full test suite if you have one

## Timeline Estimate

- Phase 1-4: 30 minutes (directory moves)
- Phase 5: 15 minutes (rename tools → toolbox)
- Phase 6: 45 minutes (update symlinks manager)
- Phase 7: 30 minutes (update taskfiles)
- Phase 8: 15 minutes (update setup scripts)
- Phase 9: 1-2 hours (update documentation)
- Phase 10: 15 minutes (update app paths)
- Phase 11-13: 30 minutes (testing and deployment)

**Total: 4-5 hours** (can be done in multiple sessions)

## Notes

- Take breaks between phases
- Commit after each phase for safety
- Test thoroughly before deploying to actual system
- Keep old branch around for a week before deleting
- Update this plan if you discover new issues
