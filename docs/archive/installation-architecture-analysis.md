# Installation Architecture Analysis & Duplication Report

**Status**: Analysis Complete
**Created**: 2025-11-28
**Issue**: Significant duplication between install.sh and Taskfile.yml install tasks

---

## Executive Summary

The dotfiles repository has **two parallel installation systems** with ~80% duplication:

1. **install.sh** (366 lines) - Newer, more complete, better UX
2. **Taskfile.yml install tasks** (244 lines) - Older, incomplete, missing 10 tools

According to install.sh's header comments, it was intended to **replace** the Taskfile install tasks, but this migration was never completed. The old platform setup scripts were removed, but the Taskfile install tasks remained and diverged.

**Current State**: Users are confused about which method to use, and maintaining both is a maintenance burden.

---

## The Duplication Problem

### What's Duplicated (100% overlap)

Both implement:
- Platform detection logic
- 10 installation phases with identical structure
- Same phase headers and descriptions
- Calls to the same scripts in `management/scripts/`

**Phases with 100% duplication**:
- Phase 2: Coding Fonts
- Phase 4: Rust/Cargo Tools
- Phase 5: Language Package Managers
- Phase 6: Shell Configuration
- Phase 7: Custom Go Applications
- Phase 9: Theme System
- Phase 10: Plugin Installation

### What's Diverged (incomplete sync)

**Phase 3: GitHub Release Tools**
- install.sh: 15 tools ✅
- Taskfile.yml: 5 tools ❌ (missing 10 tools)

**Missing from Taskfile.yml Phase 3**:
1. install-glow.sh
2. install-duf.sh
3. install-awscli.sh
4. install-claude-code.sh
5. task go-tools:install
6. task tenv:install
7. install-terraform-ls.sh
8. install-tflint.sh
9. install-terraformer.sh
10. install-terrascan.sh

**Phase 8: Symlinking**
- install.sh: `task symlinks:relink` (idempotent, safer)
- Taskfile.yml: `task symlinks:link` (may skip existing)

**Post-Install Configuration**
- install.sh: Configures ZSHDOTDIR, changes shell to zsh (WSL/Arch)
- Taskfile.yml: Missing post-install configuration entirely

**Feature Differences**:
- install.sh: Has `--force` flag for reinstalling
- Taskfile.yml: No force install support
- install.sh: Built-in `--help` with examples
- Taskfile.yml: Only `task --list`

---

## Architecture Overview

### Call Graph

```
User Entry Points:
  ./install.sh              ← RECOMMENDED (complete)
  task install              ← OUTDATED (incomplete)

install.sh flow:
  └─> detect_platform()
  └─> install_task()        [Bootstraps Task if needed]
  └─> install_{macos|wsl|arch}()
      ├─> Phase 1: task {platform}:install-packages
      ├─> Phase 2: fonts/download.sh + fonts/install.sh
      ├─> Phase 3: 15× install-*.sh + 2× task commands
      ├─> Phase 4-10: [same as Taskfile]
      └─> configure_shell()  [WSL/Arch only]

Taskfile.yml flow:
  task install
  └─> task install-{macos|wsl|arch}
      ├─> Phase 1: task {platform}:install-packages
      ├─> task install-fonts-phase
      └─> task install-common-phases
          ├─> Phase 3: ONLY 5 tools ❌
          ├─> Phase 4-10: [same as install.sh]
          └─> No post-install config ❌
```

### Shared Components (No Duplication)

Both systems call the **same** underlying scripts and tasks:

**Individual Install Scripts** (26 scripts in `management/scripts/`):
- install-go.sh, install-fzf.sh, install-neovim.sh, etc.
- Font installation: fonts/download.sh, fonts/install.sh

**Modular Taskfiles** (18 taskfiles in `management/taskfiles/`):
- Platform tasks: macos.yml, wsl.yml, arch.yml
- Package managers: brew.yml, apt.yml, pacman.yml, yay.yml, mas.yml
- Language tools: go-tools.yml, nvm.yml, npm-global.yml, uv-tools.yml
- Utilities: shell-plugins.yml, symlinks.yml, docs.yml

**Python Apps**:
- management/symlinks/ - Symlink manager

This is good - the actual installation logic is NOT duplicated, only the orchestration is duplicated.

---

## Historical Context

### Git History

**Commit de3c72f** (Nov 25, 2025):
> "Remove old platform-specific setup scripts that have been replaced by the unified installation system"

Deleted:
- management/macos-setup.sh
- management/wsl-setup.sh
- management/arch-setup.sh

Replaced by: "Task-based installation workflows"

**But install.sh header says**:
```bash
# Unified installation script that replaces:
# - Taskfile.yml install tasks        ← THIS WAS NEVER DONE
# - management/wsl-setup.sh            ← This was done
# - management/macos-setup.sh          ← This was done
# - management/arch-setup.sh           ← This was done
```

**Conflicting intent**: The commit message says replaced by "Task-based workflows", but install.sh says it replaces the Task workflows.

### Evolution Timeline

1. **Phase 1**: Platform-specific bash scripts (macos-setup.sh, wsl-setup.sh, arch-setup.sh)
2. **Phase 2**: Taskfile.yml install tasks created to unify installation
3. **Phase 3**: install.sh created as "unified installation script"
4. **Phase 4**: Old platform bash scripts removed (commit de3c72f)
5. **Phase 5** (incomplete): Taskfile install tasks should have been removed but weren't

**Result**: Two parallel installation systems

---

## Comparison Table

| Feature | install.sh | Taskfile.yml | Winner |
|---------|-----------|--------------|--------|
| **Completeness** | 15 tools in Phase 3 | 5 tools in Phase 3 | install.sh |
| **Post-install config** | Yes (ZSHDOTDIR, shell) | No | install.sh |
| **Force reinstall** | `--force` flag | None | install.sh |
| **Help documentation** | `--help` with examples | `task --list` | install.sh |
| **Error handling** | `set -euo pipefail`, die() | Basic | install.sh |
| **Path handling** | Absolute paths | Relative paths | install.sh |
| **Last updated** | commit a25a3b9 (recent) | commit 9f982ff (older) | install.sh |
| **Bootstrapping** | Installs Task if missing | Requires Task | install.sh |
| **Easy to call** | `./install.sh` | `task install` | Tie |
| **Maintenance burden** | Single file | Modular taskfiles | Tie |

**Score: install.sh wins 7/10 categories**

---

## Recommendations

### Option 1: Use install.sh as Primary (RECOMMENDED)

**Remove duplication by eliminating Taskfile install tasks**

**Rationale**:
- install.sh is more complete (15 vs 5 tools in Phase 3)
- install.sh is more maintained (updated more recently)
- install.sh provides better UX (help, error handling, bootstrapping)
- Matches stated intent in install.sh header
- Single source of truth reduces maintenance burden

**Actions**:

1. **Remove from Taskfile.yml** (lines 63-165):
   ```yaml
   # DELETE these tasks:
   - task: install (auto-detect)
   - task: install-macos
   - task: install-wsl
   - task: install-arch
   - task: install-common-phases
   - task: install-fonts-phase
   ```

2. **Keep modular taskfiles** (they're used by install.sh):
   - management/taskfiles/*.yml
   - All individual tasks (go-tools:install, nvm:install, etc.)

3. **Update README.md**:
   ```markdown
   # Before
   ./install.sh    # Automatically detects your platform
   Already have Homebrew and Task installed? Just run `task install`.

   # After
   ./install.sh    # Automatically detects your platform
   ```

4. **Optional: Add convenience wrapper**:
   ```yaml
   # Minimal wrapper for users who prefer Task
   tasks:
     install:
       desc: Install dotfiles (delegates to install.sh)
       cmds:
         - bash install.sh {{.CLI_ARGS}}
   ```

**Benefits**:
- ✅ Eliminates 80% duplication
- ✅ Single source of truth for installation
- ✅ Easier to maintain
- ✅ Clearer for users (one way to install)
- ✅ Still uses Task for modular components

**Drawbacks**:
- Users who memorized `task install` need to learn `./install.sh`
- Commit message de3c72f implied Task was the future (but install.sh is better)

---

### Option 2: Keep Both, Synchronize Them

**Maintain both systems in perfect sync**

**Rationale**:
- Some users prefer Task over bash
- Task provides better composition features
- Already have extensive taskfile infrastructure

**Actions**:

1. **Update Taskfile.yml to match install.sh**:
   - Add 10 missing tools to Phase 3
   - Change Phase 8 to use `symlinks:relink`
   - Add post-install configuration tasks
   - Add FORCE_INSTALL variable support
   - Update documentation

2. **Establish sync policy**:
   - Document that both MUST be kept identical
   - Add pre-commit hook to verify consistency
   - Create integration test comparing both methods
   - When updating one, update the other

**Benefits**:
- ✅ Flexibility (bash or Task)
- ✅ Leverages Task's features

**Drawbacks**:
- ❌ High maintenance burden
- ❌ Easy to diverge again (already happened once)
- ❌ Duplication remains
- ❌ Two sources of truth

---

### Option 3: Use Taskfile as Primary, Remove install.sh

**Commit to Task as the installation framework**

**Rationale**:
- Task provides better automation features
- Already have 18 modular taskfiles
- Can use Task's dependency management
- More modern approach

**Actions**:

1. **Update Taskfile.yml**:
   - Add 10 missing Phase 3 tools
   - Fix Phase 8 symlinks
   - Add post-install configuration
   - Add force install support
   - Improve help text

2. **Remove install.sh**

3. **Update README and docs**

4. **Handle bootstrapping**:
   - Create minimal bootstrap.sh that installs Task
   - Or document manual Task installation

**Benefits**:
- ✅ Leverages Task ecosystem
- ✅ Better task composition
- ✅ Status/preconditions features

**Drawbacks**:
- ❌ Chicken-egg: Task may not be available initially
- ❌ install.sh already handles Task bootstrapping
- ❌ Goes against stated intent in install.sh header
- ❌ Taskfile syntax more complex than bash for sequential operations

---

## My Recommendation: Option 1

**Use install.sh as primary, remove Taskfile install tasks**

### Why Option 1?

1. **install.sh is objectively better**:
   - More complete (15 vs 5 tools)
   - More recent (updated more recently)
   - Better UX (help, error handling, bootstrapping)
   - Handles Task installation (solves chicken-egg)

2. **Matches stated intent**:
   - install.sh header says it "replaces Taskfile.yml install tasks"
   - Just need to finish what was started

3. **Single source of truth**:
   - Easier to maintain
   - Can't diverge if there's only one
   - Clear for users

4. **Still uses Task**:
   - install.sh delegates to taskfiles extensively
   - Best of both worlds: bash orchestration + Task modules

5. **Minimal disruption**:
   - README already recommends `./install.sh`
   - Only removing unused code from Taskfile.yml
   - Modular taskfiles remain (they're valuable)

### Implementation Plan

**Phase A: Remove Duplication (30 min)**

1. Delete install tasks from Taskfile.yml:
   - Lines 63-165 (install, install-macos, install-wsl, install-arch, install-common-phases, install-fonts-phase)

2. Update README.md:
   - Remove "Just run `task install`" line
   - Keep `./install.sh` as the single recommended method

3. Optional: Add minimal wrapper:
   ```yaml
   tasks:
     install:
       desc: Install dotfiles (wrapper for install.sh)
       cmds:
         - bash install.sh {{.CLI_ARGS}}
   ```

**Phase B: Reorganize management/ (2-3 hours, optional)**

If you want to tackle the broader management/ organization:

1. **Create management/scripts/ subdirectories**:
   ```
   management/scripts/
   ├── install/          # Installation scripts
   │   ├── tools/       # Individual tool installers (install-*.sh)
   │   └── fonts/       # Font installation
   ├── update/          # Update scripts (update-*.sh)
   ├── helpers/         # Helper scripts (install-program-helpers.sh, etc.)
   └── testing/         # Already exists
   ```

2. **Move scripts to subdirectories**:
   - install-*.sh → install/tools/
   - fonts/ → install/fonts/
   - update-*.sh → update/

3. **Update references in install.sh and Taskfile.yml**

**Phase C: Document the Architecture (1 hour)**

Add to docs/architecture/:
- installation-workflow.md
- management-directory-guide.md
- taskfile-organization.md

---

## Conclusion

You have a well-designed modular system (the taskfiles and install scripts), but the top-level orchestration is duplicated between install.sh and Taskfile.yml.

**The fix is simple**: Complete the original migration plan by removing the Taskfile install tasks. Keep install.sh as the primary entry point, and keep the valuable modular taskfiles that both systems use.

This gives you:
- ✅ Single source of truth (install.sh)
- ✅ Modular components (taskfiles)
- ✅ No duplication
- ✅ Easy to maintain
- ✅ Clear for users

**Next step**: Review this analysis and decide if you want to proceed with Option 1.
