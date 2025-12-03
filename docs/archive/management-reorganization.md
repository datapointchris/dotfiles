# Management Directory Reorganization Plan

**Status**: Planning
**Created**: 2025-11-28
**Problem**: Three overlapping hierarchies (platform, tool, operation) creating chaos

---

## Current Chaos - Three Competing Hierarchies

### The Three Dimensions:

1. **Platform**: macos, wsl, arch, common
2. **Tool Type**: GitHub binaries, package managers, language managers, plugins
3. **Operation**: install, update, configure

**Current organization mixes all three randomly**:
- `install-go.sh` - Tool-centric
- `update-macos.sh` - Platform-centric
- `fonts/download.sh` - Operation-centric

**This is madness** - no consistent organizing principle!

---

## Analysis of Current Scripts

### By Platform Need:

**macOS-specific** (6 scripts):
- update-macos.sh
- (macos package installation is inline in macos.yml)

**WSL-specific** (3 scripts):
- update-wsl.sh
- setup-docker-official-repo-ubuntu.sh
- wsl-docker-images.sh

**Arch-specific** (1 script):
- update-arch.sh

**Cross-platform** (26 scripts):
- All install-*.sh scripts
- npm-install-globals.sh
- nvm-install-*.sh

### By Tool Type:

**GitHub Release Binaries** (15 scripts):
- install-go.sh
- install-fzf.sh
- install-neovim.sh
- install-lazygit.sh
- install-yazi.sh
- install-glow.sh
- install-duf.sh
- install-awscli.sh
- install-claude-code.sh
- install-tenv.sh
- install-terraform-ls.sh
- install-tflint.sh
- install-terraformer.sh
- install-terrascan.sh
- install-trivy.sh

**Language Package Managers** (3 scripts):
- install-rust.sh (cargo)
- install-uv.sh (Python)
- nvm-install-*.sh (Node)

**Cargo Tools** (2 scripts):
- install-cargo-binstall.sh
- install-cargo-tools.sh

**Plugin Managers** (3 scripts):
- install-tpm.sh
- install-tmux-plugins.sh
- install-nvim-plugins.sh

**Utilities** (3 scripts):
- install-program-helpers.sh
- brew-audit.sh
- fonts/ (2 scripts)

### By Operation:

**Install** (26 scripts)
**Update** (3 scripts)
**Setup** (1 script)
**Helpers** (6 scripts in root management/)

---

## Problem Statement

**We have scripts organized by:**
- ❌ Platform (update-macos.sh)
- ❌ Tool (install-go.sh)
- ❌ Operation (fonts/download.sh)
- ❌ No clear pattern

**Questions that are hard to answer**:
1. "Where do I find all macOS installation logic?" - Scattered across macos.yml, install.sh, and individual install scripts
2. "Where do I find all GitHub binary installers?" - Mixed in with everything else
3. "Where do I add a new tool?" - Unclear

---

## Proposed Solution: Platform-First Organization

**Primary hierarchy**: Platform (matches your platform/ directory for configs)
**Secondary hierarchy**: Operation (install, update, configure)
**Tool scripts**: Remain modular, called by operation scripts

### Rationale:

1. **Matches existing structure**: You already have `platforms/common/`, `platforms/macos/`, etc.
2. **Clear boundaries**: Platform-specific logic is isolated
3. **Shared code is obvious**: Common tools are in `common/`
4. **Easy to find things**: "I need macOS install logic" → `management/macos/install.sh`

---

## Proposed Directory Structure

```
management/
├── common/                              # Cross-platform operations
│   ├── install/
│   │   ├── github-releases/            # GitHub binary installers
│   │   │   ├── go.sh
│   │   │   ├── fzf.sh
│   │   │   ├── neovim.sh
│   │   │   ├── lazygit.sh
│   │   │   ├── yazi.sh
│   │   │   ├── glow.sh
│   │   │   ├── duf.sh
│   │   │   ├── awscli.sh
│   │   │   ├── claude-code.sh
│   │   │   ├── tenv.sh
│   │   │   ├── terraform-ls.sh
│   │   │   ├── tflint.sh
│   │   │   ├── terraformer.sh
│   │   │   ├── terrascan.sh
│   │   │   ├── trivy.sh
│   │   │   └── zk.sh
│   │   ├── language-managers/          # Language version managers
│   │   │   ├── rust.sh                 # Installs rustup
│   │   │   ├── nvm.sh                  # Installs nvm
│   │   │   └── uv.sh                   # Installs uv
│   │   ├── language-tools/             # Tools for specific languages
│   │   │   ├── cargo-binstall.sh
│   │   │   ├── cargo-tools.sh
│   │   │   ├── go-tools.sh             # New (from go-tools.yml)
│   │   │   ├── npm-global.sh           # Renamed from npm-install-globals.sh
│   │   │   ├── uv-tools.sh             # New (from uv-tools.yml)
│   │   │   └── node-lts.sh             # Renamed from nvm-install-lts.sh
│   │   ├── plugins/                    # Plugin managers
│   │   │   ├── tmux-tpm.sh
│   │   │   ├── tmux-plugins.sh
│   │   │   ├── nvim-plugins.sh
│   │   │   └── shell-plugins.sh        # New (from shell-plugins.yml)
│   │   ├── fonts/                      # Font management
│   │   │   ├── download.sh
│   │   │   └── install.sh
│   │   └── helpers.sh                  # Shared helper functions
│   └── lib/                            # Shared libraries (if needed)
│       └── github-releases.sh          # Common logic for GitHub releases
├── macos/
│   ├── install-packages.sh             # Homebrew package installation
│   ├── update.sh                       # brew update, cargo update, etc.
│   └── configure/                      # macOS-specific configuration
│       ├── finder.sh
│       ├── dock.sh
│       └── safari.sh
├── wsl/
│   ├── install-packages.sh             # apt package installation
│   ├── update.sh                       # apt update, cargo update, etc.
│   └── setup-docker.sh                 # Docker setup for WSL
├── arch/
│   ├── install-packages.sh             # pacman/yay package installation
│   └── update.sh                       # pacman update, cargo update, etc.
├── symlinks/                           # Symlink manager (Python app)
│   └── (unchanged)
├── testing/                            # Test scripts
│   └── (unchanged)
├── utils/                              # Utility scripts
│   ├── detect-alternate-installations.sh
│   ├── verify-installation.sh
│   ├── run-and-summarize.sh
│   ├── summarize-log.sh
│   └── wsl-docker-images.sh
├── parse-packages.py                   # Package definition parser
├── packages.yml                        # Package definitions
└── test-install.sh                     # Main test script
```

---

## Key Design Decisions

### 1. Platform-First Hierarchy

```
management/
├── common/      # Tools that work on all platforms
├── macos/       # macOS-specific operations
├── wsl/         # WSL-specific operations
└── arch/        # Arch-specific operations
```

**Benefits**:
- Clear separation of platform-specific vs cross-platform
- Easy to find platform logic
- Matches `platforms/` directory structure
- Easy to add new platforms

### 2. GitHub Releases Get Their Own Directory

**Rationale**: 15 scripts follow identical pattern
- Download from GitHub releases API
- Extract binary
- Install to specific location
- All could potentially share common logic

**Future opportunity**: Create `lib/github-releases.sh` with shared functions

### 3. Operation Scripts at Platform Level

```
macos/
├── install-packages.sh   # One script to install all Homebrew packages
└── update.sh             # One script to update everything (brew, cargo, npm, etc.)
```

**Not**:
```
macos/
├── install/
│   ├── brew.sh
│   ├── cargo.sh
│   └── npm.sh
└── update/
    ├── brew.sh
    ├── cargo.sh
    └── npm.sh
```

**Rationale**: You run `task install-macos` or `update-macos.sh` - you don't install/update individual package managers separately.

### 4. Tool Scripts Remain Modular

Individual tool installers stay as small, focused scripts:
- `common/install/github-releases/neovim.sh`
- `common/install/language-tools/cargo-tools.sh`

These are called by the main install.sh script, not run directly by users.

---

## Migration Plan

### Phase 1: Create New Structure (No Deletion)

Create new directories and move scripts (keep old ones temporarily):

```bash
# Create structure
mkdir -p management/common/install/{github-releases,language-managers,language-tools,plugins,fonts}
mkdir -p management/common/lib
mkdir -p management/{macos,wsl,arch}/configure
mkdir -p management/utils

# Move GitHub release scripts
mv management/scripts/install-go.sh management/common/install/github-releases/go.sh
mv management/scripts/install-fzf.sh management/common/install/github-releases/fzf.sh
# ... (repeat for all 15 GitHub release tools)

# Move language managers
mv management/scripts/install-rust.sh management/common/install/language-managers/rust.sh
mv management/scripts/install-uv.sh management/common/install/language-managers/uv.sh
# ... etc

# Move language tools
mv management/scripts/install-cargo-binstall.sh management/common/install/language-tools/cargo-binstall.sh
mv management/scripts/npm-install-globals.sh management/common/install/language-tools/npm-global.sh
# ... etc

# Move plugins
mv management/scripts/install-tpm.sh management/common/install/plugins/tmux-tpm.sh
# ... etc

# Move fonts
mv management/scripts/fonts/* management/common/install/fonts/

# Move platform updates
mv management/scripts/update-macos.sh management/macos/update.sh
mv management/scripts/update-wsl.sh management/wsl/update.sh
mv management/scripts/update-arch.sh management/arch/update.sh

# Move utilities
mv management/detect-alternate-installations.sh management/utils/
mv management/verify-installation.sh management/utils/
mv management/run-and-summarize.sh management/utils/
mv management/summarize-log.sh management/utils/
```

### Phase 2: Create New Scripts from Taskfile Logic

**Extract from macos.yml**:
```bash
# Create management/macos/install-packages.sh
# Contains inline bash from macos.yml install-packages task

# Create management/macos/configure/finder.sh
# Contains inline bash from macos.yml configure-finder task
```

**Create from taskfiles**:
```bash
# management/common/install/language-tools/go-tools.sh
# Logic from go-tools.yml

# management/common/install/language-tools/uv-tools.sh
# Logic from uv-tools.yml

# management/common/install/plugins/shell-plugins.sh
# Logic from shell-plugins.yml
```

### Phase 3: Update install.sh References

Update install.sh to use new paths:

```bash
# Before:
bash management/scripts/install-go.sh

# After:
bash management/common/install/github-releases/go.sh
```

Or create a helper:
```bash
# In install.sh
COMMON_INSTALL="$DOTFILES_DIR/management/common/install"
GITHUB_RELEASES="$COMMON_INSTALL/github-releases"
LANGUAGE_TOOLS="$COMMON_INSTALL/language-tools"
PLUGINS="$COMMON_INSTALL/plugins"

# Then use:
bash "$GITHUB_RELEASES/go.sh"
bash "$LANGUAGE_TOOLS/cargo-tools.sh"
```

### Phase 4: Update Taskfile.yml (Simplified)

```yaml
version: '3'

tasks:
  default:
    desc: Show available tasks
    cmds:
      - task --list

  install:
    desc: Install dotfiles (delegates to install.sh)
    cmds:
      - bash install.sh {{.CLI_ARGS}}

  # Symlink management
  symlinks:link:
    desc: Create symlinks for dotfiles
    dir: management/symlinks
    env:
      UV_PROJECT: "{{.TASKFILE_DIR}}/management/symlinks"
    cmds:
      - uv run symlinks link {{.CLI_ARGS}}

  symlinks:unlink:
    desc: Remove symlinks
    dir: management/symlinks
    env:
      UV_PROJECT: "{{.TASKFILE_DIR}}/management/symlinks"
    cmds:
      - uv run symlinks unlink {{.CLI_ARGS}}

  symlinks:check:
    desc: Check for broken symlinks
    dir: management/symlinks
    env:
      UV_PROJECT: "{{.TASKFILE_DIR}}/management/symlinks"
    cmds:
      - uv run symlinks check

  symlinks:show:
    desc: Show current symlinks
    dir: management/symlinks
    env:
      UV_PROJECT: "{{.TASKFILE_DIR}}/management/symlinks"
    cmds:
      - uv run symlinks show {{.CLI_ARGS}}

  symlinks:relink:
    desc: Refresh all symlinks
    dir: management/symlinks
    env:
      UV_PROJECT: "{{.TASKFILE_DIR}}/management/symlinks"
    cmds:
      - uv run symlinks relink {{.CLI_ARGS}}

  # Documentation
  docs:serve:
    desc: Serve documentation locally
    cmds:
      - uv run mkdocs serve --livereload

  docs:build:
    desc: Build documentation
    cmds:
      - uv run mkdocs build

  docs:deploy:
    desc: Deploy documentation to GitHub Pages
    cmds:
      - uv run mkdocs gh-deploy --force

  # Font installation
  fonts:download:
    desc: Download coding fonts from GitHub releases
    cmds:
      - bash management/common/install/fonts/download.sh {{.CLI_ARGS}}

  fonts:install:
    desc: Install downloaded fonts to system font directory
    cmds:
      - bash management/common/install/fonts/install.sh {{.CLI_ARGS}}
```

**That's it**. No includes, no abstraction layers. Just a simple task list for common operations.

### Phase 5: Delete Old Files

Once install.sh is updated and tested:

```bash
# Delete old scripts directory
rm -rf management/scripts/

# Delete all taskfiles except root
rm -rf management/taskfiles/

# Keep only:
# - Taskfile.yml (root)
# - apps/common/sess/Taskfile.yml
# - apps/common/toolbox/Taskfile.yml
```

---

## Comparison: Before vs After

### Before (Current Chaos)

```
management/
├── scripts/                    # Flat, 33 files
│   ├── install-*.sh           # 26 files, no organization
│   ├── update-*.sh            # 3 files
│   ├── npm-*.sh               # Special case?
│   ├── nvm-*.sh               # Another special case?
│   └── fonts/                 # Only organized thing
├── taskfiles/                  # 18 files, mostly useless
│   ├── apt.yml                # Pure wrapper
│   ├── macos.yml              # 227 lines of inline bash
│   └── ...
└── [6 helper scripts at root]
```

**Problems**:
- No clear organization principle
- Hard to find things
- Platform logic scattered
- Taskfiles add no value

### After (Platform-First)

```
management/
├── common/                     # Cross-platform tools
│   └── install/
│       ├── github-releases/   # 16 similar scripts
│       ├── language-managers/ # 3 scripts
│       ├── language-tools/    # 6 scripts
│       ├── plugins/           # 4 scripts
│       └── fonts/             # 2 scripts
├── macos/                      # macOS operations
│   ├── install-packages.sh
│   ├── update.sh
│   └── configure/             # Platform-specific configs
├── wsl/                        # WSL operations
│   ├── install-packages.sh
│   ├── update.sh
│   └── setup-docker.sh
├── arch/                       # Arch operations
│   ├── install-packages.sh
│   └── update.sh
├── symlinks/                   # Symlink manager
├── testing/                    # Test scripts
├── utils/                      # Helper utilities
├── parse-packages.py
└── packages.yml
```

**Benefits**:
- Clear platform separation
- Tool types organized
- Easy to find things
- No useless taskfiles
- Matches platforms/ structure

---

## Benefits of This Organization

### 1. Discoverability

**Question**: "Where's the macOS installation logic?"
**Answer**: `management/macos/install-packages.sh`

**Question**: "Where do GitHub binary installers live?"
**Answer**: `management/common/install/github-releases/`

**Question**: "How do I add a new tool?"
**Answer**:
1. Add to packages.yml
2. Create script in appropriate category
3. Call from install.sh

### 2. Clear Boundaries

- **Platform-specific**: `macos/`, `wsl/`, `arch/`
- **Cross-platform**: `common/`
- **Utilities**: `utils/`
- **Infrastructure**: `symlinks/`, `testing/`

### 3. Scalability

Adding new tool types is easy:
```
common/install/
├── github-releases/    # Existing
├── language-managers/  # Existing
├── homebrew-casks/     # NEW - macOS GUI apps
└── container-images/   # NEW - Docker images
```

### 4. Consistency

All platform scripts have same structure:
```
macos/
├── install-packages.sh
└── update.sh

wsl/
├── install-packages.sh
└── update.sh

arch/
├── install-packages.sh
└── update.sh
```

Predictable and consistent.

---

## Implementation Effort

**Phase 1**: Create structure, move files (2 hours)
- Mostly `mkdir` and `mv` commands
- No logic changes

**Phase 2**: Extract taskfile logic to scripts (3 hours)
- Create new scripts from macos.yml, wsl.yml, arch.yml
- Extract go-tools.yml, uv-tools.yml, shell-plugins.yml

**Phase 3**: Update install.sh (1 hour)
- Update all paths
- Test thoroughly

**Phase 4**: Update Taskfile.yml (30 min)
- Remove includes
- Move symlinks tasks inline
- Move docs tasks inline

**Phase 5**: Delete old files (15 min)
- Remove management/scripts/
- Remove management/taskfiles/
- Clean up

**Total**: ~7 hours

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Break install.sh | High | Test on all platforms before deleting old files |
| Miss script references | Medium | Grep for all script paths before deleting |
| Path issues | Medium | Use variables for common paths |
| User confusion | Low | Update documentation |

---

## Next Steps

1. **Review this plan** - Does the structure make sense?
2. **Agree on hierarchy** - Platform-first vs Tool-first?
3. **Start Phase 1** - Create structure, move files
4. **Test incrementally** - Don't delete old files until new structure works

---

## Open Questions

1. **Should update scripts call individual tools** or just run bulk commands?
   - Option A: `update-macos.sh` calls brew, cargo, npm separately
   - Option B: `update-macos.sh` has inline: `brew update && cargo install-update -a`
   - **Recommendation**: Option B - simpler

2. **Do we need lib/ for shared code?**
   - Most GitHub release installers follow same pattern
   - Could extract to `common/lib/github-releases.sh`
   - **Recommendation**: Add if we see duplication, not preemptively

3. **Should platform configure/ scripts be separate files?**
   - macOS has 3+ config scripts (Finder, Dock, Safari)
   - Could be one large `configure-macos.sh` or split
   - **Recommendation**: Keep split - easier to maintain

---

## Conclusion

**Current state**: Three competing hierarchies (platform, tool, operation) mixed chaotically

**Proposed state**: Platform-first hierarchy with tool-type subdirectories

**Benefits**:
- Clear organization
- Easy to find things
- Matches existing platforms/ structure
- No useless taskfiles
- Scalable

**Recommendation**: Proceed with platform-first organization
