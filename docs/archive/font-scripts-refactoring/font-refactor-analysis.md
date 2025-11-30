# Font App Refactor & Reorganization Analysis

**Status**: Phase 1 Complete ✅
**Created**: 2025-11-28
**Completed**: 2025-11-28
**Scope**: Font app split, Go conversion analysis, management/ reorganization

---

## Executive Summary

The `font` app has grown to **3,304 lines of bash** across multiple components, performing two distinct responsibilities:

1. **Font Installation** (~1,525 lines): One-time download/install operations that belong in platform setup
2. **Font Management** (~1,779 lines): Runtime operations for testing, tracking, and switching fonts

This analysis explores:
- Splitting installation concerns into `management/` alongside other setup scripts
- Converting the runtime management app to Go (like `sess` and `toolbox`)
- Reorganizing `management/` directory for better scalability
- WSL font installation considerations and limitations
- Implementation plan with incremental stages

**Key Recommendation**: Proceed with split (high value, low risk) but defer Go conversion (moderate value, high effort).

---

## Current State Analysis

### Font App Architecture (as of Nov 2025)

```
apps/common/font/                               Total: 3,304 LOC
├── bin/font                    628 LOC         CLI dispatcher & runtime commands
├── lib/
│   ├── lib.sh                  467 LOC         Font discovery & preview generation
│   └── storage.sh              430 LOC         JSONL history & analytics
├── commands/
│   ├── download                945 LOC         Font family downloads (23 families)
│   ├── install                 358 LOC         System font installation
│   ├── cleanup                 222 LOC         One-time migration (legacy)
│   └── hoard                   256 LOC         Massive collection management
├── data/
│   ├── font-info.json                          Font metadata (47 fonts)
│   ├── history-{platform}.jsonl                Usage tracking (per-platform)
│   └── rejected-fonts.json                     Rejection tracking
└── tests/test                  347 LOC         Test suite
```

### Responsibility Separation (Current)

#### Installation/Setup Concerns (~1,525 LOC)
- `commands/download` (945 LOC) - Download 23 font families from GitHub
- `commands/install` (358 LOC) - Copy fonts to system directories
- `commands/cleanup` (222 LOC) - Legacy migration tool

**Why these belong in `management/`:**
- Run once during initial setup or periodic updates
- Platform-specific (macOS, Linux, WSL have different install paths)
- Analogous to `install-neovim.sh`, `install-go.sh`, etc.
- No need for these to be available as runtime commands

#### Runtime Management Concerns (~1,779 LOC)
- `bin/font` (628 LOC) - Commands: change, apply, like, dislike, rank, log, current
- `lib/lib.sh` (467 LOC) - Font discovery, fc-list integration, preview generation
- `lib/storage.sh` (430 LOC) - History tracking, analytics, rejected fonts
- `commands/hoard` (256 LOC) - Interactive large collection management

**Why these stay as the `font` app:**
- Used daily/weekly in interactive workflows
- Cross-platform logic (works anywhere)
- Needs to be in PATH for convenience
- Similar to `sess` (session manager) and `toolbox` (tool discovery)

---

## Proposal 1: Split Installation Scripts to `management/`

### Goal
Move one-time font installation operations to `management/scripts/` to align with other setup scripts.

### Implementation

#### New Files in `management/scripts/`

1. **`install-fonts-download.sh`** (~945 LOC)
   - Rename from `commands/download`
   - Download 23 font families from GitHub releases
   - Platform-agnostic (downloads same fonts everywhere)
   - Phases: download → prune variants → standardize names
   - Output: `~/fonts/{family}/`

2. **`install-fonts-system.sh`** (~358 LOC)
   - Rename from `commands/install`
   - Platform-specific installation:
     - macOS: `~/Library/Fonts/`
     - Linux: `~/.local/share/fonts/`
     - WSL: `/mnt/c/Windows/Fonts/` (with manual fallback)
   - Includes exclusion list and dry-run mode

3. **`install-fonts.sh`** (NEW, ~50 LOC)
   - Master wrapper that calls download + system install
   - Integrates with main Taskfile.yml
   - Example usage:
     ```bash
     bash management/scripts/install-fonts.sh          # Full install
     bash management/scripts/install-fonts.sh --download-only
     bash management/scripts/install-fonts.sh --install-only
     ```

#### Integration with Taskfile.yml

Add to `install-common-phases` (around Phase 4-5, after shell plugins):

```yaml
- |
  echo ""
  print_header "Phase 5 - Download & Install Fonts" "cyan"
  bash management/scripts/install-fonts.sh
```

Or as optional task:

```yaml
tasks:
  fonts:install:
    desc: Download and install coding fonts
    cmds:
      - bash management/scripts/install-fonts.sh
```

#### Changes to Font App

Remove from `apps/common/font/`:
- `commands/download` → moved to `management/scripts/install-fonts-download.sh`
- `commands/install` → moved to `management/scripts/install-fonts-system.sh`
- `commands/cleanup` → archive (no longer needed, was legacy migration)

Keep in `apps/common/font/`:
- `bin/font` - Runtime CLI
- `lib/lib.sh` - Font discovery & previews
- `lib/storage.sh` - History tracking
- `commands/hoard` - Large collection management (interactive, not setup)
- `data/` - All data files
- `tests/test` - Test suite

**Updated font app size**: ~1,779 LOC (46% reduction)

### Benefits

1. **Clearer separation of concerns**: Setup vs runtime operations
2. **Discoverable**: Font installation appears in Task automation like other tools
3. **Consistent with existing patterns**: Matches `install-neovim.sh`, `install-go.sh`, etc.
4. **Simpler font app**: Focused on management, not installation
5. **Platform integration**: Can be called during initial setup or separately

### Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing workflows | Keep legacy commands as deprecation warnings pointing to new scripts |
| Users expect `font install` | Add help text: "Run `task fonts:install` instead" |
| WSL complexity | Document manual steps, provide clear error messages |

### Effort Estimate

- **Time**: 2-3 hours
- **Complexity**: Low (mostly file moves + small refactoring)
- **Testing**: Verify on macOS, test WSL manually
- **Rollback**: Simple (git revert)

---

## Proposal 2: Convert Font App to Go

### Comparison: Bash vs Go Implementation

| Aspect | Current (Bash) | Proposed (Go) |
|--------|----------------|---------------|
| **Lines of Code** | 1,779 LOC | Estimated ~1,500-2,000 LOC |
| **Structure** | bin/ + lib/ + commands/ | cmd/ + internal/font/ + internal/ui/ |
| **Dependencies** | fzf, jq, fc-list, ImageMagick, chafa/viu (5 tools) | Cobra, Bubbletea, yaml.v3 + ImageMagick (1 external tool) |
| **Data Format** | JSONL (append-only) | JSONL or SQLite |
| **Testing** | Bash test framework (~347 LOC) | Go testing stdlib (easier mocking) |
| **Build Process** | None (symlinked script) | `task install` → `~/go/bin/font` |
| **Error Handling** | set -euo pipefail + manual checks | Explicit error returns, type safety |
| **Cross-platform** | Platform detection via env vars | runtime.GOOS + build tags |
| **Interactive UI** | fzf + chafa/viu | Bubbletea (integrated TUI) |
| **Performance** | Fast (native bash + fzf) | Fast (compiled binary) |
| **Maintainability** | Moderate (bash can get complex) | Higher (types, interfaces, refactoring tools) |

### Go Implementation Design

#### Package Structure

```
apps/common/font/
├── cmd/font/
│   └── main.go                         # CLI entry point
├── internal/
│   ├── config/
│   │   └── loader.go                   # Load font-info.json
│   ├── font/
│   │   ├── types.go                    # Font, HistoryEntry, RejectedFont
│   │   ├── interfaces.go               # FontDiscovery, PreviewGenerator, Storage
│   │   ├── discovery.go                # fc-list integration
│   │   ├── preview.go                  # ImageMagick wrapper
│   │   └── storage.go                  # JSONL history & rejection tracking
│   ├── ui/
│   │   ├── list.go                     # Bubbletea font picker
│   │   ├── preview.go                  # Terminal image display
│   │   └── styles.go                   # Lipgloss styling
│   └── ghostty/
│       └── config.go                   # Read/write Ghostty config
├── data/
│   ├── font-info.json
│   ├── history-{platform}.jsonl
│   └── rejected-fonts.json
├── Taskfile.yml
├── go.mod
├── go.sum
└── README.md
```

#### Core Libraries

1. **Cobra** - CLI framework (commands: change, apply, like, rank, log, etc.)
2. **Bubbletea** - Terminal UI for interactive font picker
3. **Bubbles** - List component for font selection
4. **Lipgloss** - Styling for preview display
5. **yaml.v3 / encoding/json** - Data parsing

**External dependencies** (still needed):
- **fc-list** - Font discovery (no pure Go alternative)
- **ImageMagick** - Preview generation (could use Go imaging libraries but ImageMagick is more powerful)

#### Key Design Decisions

**1. JSONL vs SQLite for History**

| Aspect | JSONL (current) | SQLite |
|--------|-----------------|--------|
| Append-only | Yes (simple write) | Requires INSERT |
| Git-friendly | Yes (text format) | No (binary) |
| Query speed | Slow (O(n) scan) | Fast (indexed) |
| Cross-platform sync | Easy (just merge files) | Complex (schema migrations) |
| **Recommendation** | Keep JSONL (fits existing workflow) | Only if history grows >10K entries |

**2. Dependency Injection (like sess)**

```go
// Interfaces for testability
type FontDiscovery interface {
    ListFonts() ([]Font, error)
    GetFontPath(name string) (string, error)
}

type Storage interface {
    LogAction(action, font, message string) error
    GetHistory() ([]HistoryEntry, error)
    GetFontStats(font string) (FontStats, error)
}

// Manager orchestrates operations
type Manager struct {
    discovery    FontDiscovery
    storage      Storage
    preview      PreviewGenerator
    configPath   string
}
```

**3. Interactive UI with Bubbletea**

```go
// Model for font picker
type fontPickerModel struct {
    fonts       []Font
    list        list.Model         // Bubbles list component
    preview     image.Image        // Current preview
    quitting    bool
}

// Bubbletea lifecycle
func (m fontPickerModel) Init() tea.Cmd
func (m fontPickerModel) Update(msg tea.Msg) (tea.Model, tea.Cmd)
func (m fontPickerModel) View() string
```

**4. Platform Detection**

```go
func detectPlatform() string {
    if platform := os.Getenv("PLATFORM"); platform != "" {
        return platform
    }

    switch runtime.GOOS {
    case "darwin":
        return "macos"
    case "linux":
        if _, err := os.Stat("/proc/version"); err == nil {
            // Check for WSL
            data, _ := os.ReadFile("/proc/version")
            if strings.Contains(string(data), "Microsoft") {
                return "wsl"
            }
        }
        return "linux"
    default:
        return runtime.GOOS
    }
}
```

### Benefits of Go Conversion

1. **Type Safety**: Compile-time error checking vs runtime bash errors
2. **Better Testing**: Mock interfaces, table-driven tests, coverage reports
3. **Integrated TUI**: Bubbletea replaces fzf + chafa (fewer external deps)
4. **Consistency**: Matches pattern of sess and toolbox (similar UX)
5. **Refactoring**: Go tooling makes large refactors safer
6. **Performance**: Compiled binary (though bash + fzf is already fast)
7. **Cross-platform**: runtime.GOOS handles platform detection uniformly
8. **Maintainability**: Easier to onboard contributors familiar with Go

### Drawbacks of Go Conversion

1. **Build Step Required**: Can't just edit and run (need `task install`)
2. **Larger Binary**: ~5-10 MB compiled binary vs ~2 KB bash script
3. **Learning Curve**: Requires Go knowledge to modify (bash is more accessible)
4. **Still Needs External Tools**: fc-list and ImageMagick can't be eliminated
5. **Effort**: ~20-30 hours of development + testing vs 0 hours for bash
6. **Migration Risk**: Existing history/data must be compatible
7. **No Clear Performance Win**: Bash + fzf is already fast for this use case

### Effort Estimate

| Phase | Tasks | Time |
|-------|-------|------|
| **1. Core Structure** | Create packages, types, interfaces | 4-6 hours |
| **2. Font Discovery** | fc-list wrapper, font path resolution | 3-4 hours |
| **3. Storage Layer** | JSONL read/write, history queries, stats | 4-6 hours |
| **4. Preview System** | ImageMagick wrapper, terminal display | 3-4 hours |
| **5. CLI Commands** | Cobra setup, 10+ commands (apply, rank, log, etc.) | 6-8 hours |
| **6. Bubbletea UI** | Interactive font picker with preview | 4-6 hours |
| **7. Ghostty Integration** | Config read/write, font application | 2-3 hours |
| **8. Testing** | Unit tests, mocks, integration tests | 6-8 hours |
| **9. Migration** | Ensure existing data works, documentation | 3-4 hours |
| **Total** | | **35-49 hours** (~1-1.5 weeks) |

### Recommendation: Defer Go Conversion

**Reasoning**:
- Current bash implementation works well (3,304 LOC is large but organized)
- No performance bottlenecks (fzf + bash is fast)
- External dependencies (fc-list, ImageMagick) can't be eliminated in Go
- High effort (35-49 hours) for moderate benefits
- More urgent priorities: Split installation scripts first

**When to reconsider**:
- History grows to 10K+ entries (SQLite becomes valuable)
- Want to eliminate fzf dependency (Bubbletea is compelling)
- Planning to add complex features (Go's type safety helps)
- Team grows (Go's tooling aids collaboration)

---

## Proposal 3: Reorganize `management/` Directory

### Current Structure Issues

```
management/
├── scripts/                    # 33 install/update scripts (flat structure)
│   ├── install-*.sh           # 25 tool installation scripts
│   ├── npm-install-globals.sh
│   ├── nvm-install-*.sh
│   ├── update-*.sh            # 3 platform update scripts
│   └── setup-docker-*.sh
├── macos-setup-scripts/        # 4 macOS-specific scripts
├── testing/                    # 5 test scripts
├── taskfiles/                  # 18 task files (well-organized)
├── symlinks/                   # Python app (well-organized)
└── [various root-level scripts]
```

**Problems**:
1. `scripts/` is flat with 33 files (will grow to 35+ with font scripts)
2. Unclear organization: install vs update vs setup vs npm/nvm
3. `macos-setup-scripts/` duplicates macOS concerns (preferences, apps, security)
4. Root-level scripts (`test-install.sh`, `verify-installation.sh`) lack discoverability

### Proposed Reorganization

#### Option A: Category-Based Structure

```
management/
├── install/                    # All installation scripts
│   ├── tools/                  # Individual tool installers
│   │   ├── awscli.sh
│   │   ├── claude-code.sh
│   │   ├── fzf.sh
│   │   ├── go.sh
│   │   ├── lazygit.sh
│   │   ├── neovim.sh
│   │   ├── rust.sh
│   │   ├── tmux-plugins.sh
│   │   ├── uv.sh
│   │   ├── yazi.sh
│   │   └── zk.sh
│   ├── fonts/                  # Font installation (NEW)
│   │   ├── download.sh         # Download font families
│   │   ├── install.sh          # Install to system
│   │   └── install-fonts.sh    # Master wrapper
│   ├── language-managers/      # Version managers
│   │   ├── nvm-install-lts.sh
│   │   ├── nvm-install-node.sh
│   │   └── npm-install-globals.sh
│   ├── docker/                 # Docker-specific
│   │   └── setup-official-repo-ubuntu.sh
│   └── helpers/                # Helper installers
│       └── install-program-helpers.sh
├── update/                     # Platform update scripts
│   ├── macos.sh
│   ├── wsl.sh
│   └── arch.sh
├── macos/                      # macOS-specific setup (merge macos-setup-scripts/)
│   ├── setup.sh                # Main setup script
│   ├── apps.sh                 # App installation & configuration
│   ├── preferences.sh          # System preferences
│   └── security.sh             # Security hardening
├── testing/                    # Test scripts (unchanged)
│   ├── test-arch-install-docker.sh
│   ├── test-current-user.sh
│   ├── test-install-helpers.sh
│   ├── test-macos-install-user.sh
│   └── test-wsl-install-docker.sh
├── taskfiles/                  # Task automation (unchanged)
├── symlinks/                   # Symlinks manager (unchanged)
├── lib/                        # Shared library functions
├── utils/                      # Utility scripts (NEW)
│   ├── test-install.sh         # Move from root
│   ├── verify-installation.sh  # Move from root
│   ├── run-and-summarize.sh    # Move from root
│   ├── summarize-log.sh        # Move from root
│   └── detect-alternate-installations.sh
├── packages.yml                # Package definitions (root)
└── parse-packages.py           # Package parser (root)
```

**Benefits**:
- Clear categorization: install/, update/, testing/, utils/
- Font scripts naturally fit in `install/fonts/`
- Scales well (each category can grow independently)
- Easy to find scripts by purpose

**Drawbacks**:
- Requires updating all Task references to scripts
- Some scripts could fit in multiple categories

#### Option B: Minimal Reorganization (Recommended)

```
management/
├── scripts/
│   ├── fonts/                  # NEW: Font installation
│   │   ├── download.sh
│   │   ├── install.sh
│   │   └── install-fonts.sh
│   ├── install-*.sh            # Keep existing flat structure
│   ├── npm-*.sh
│   ├── nvm-*.sh
│   ├── update-*.sh
│   └── setup-*.sh
├── macos-setup-scripts/        # Unchanged
├── testing/                    # Unchanged
├── taskfiles/                  # Unchanged
├── symlinks/                   # Unchanged
└── [root-level scripts]        # Unchanged
```

**Benefits**:
- Minimal disruption (only add `scripts/fonts/` subdirectory)
- No updates needed to existing Task references
- Easy migration path (can refactor later)

**Drawbacks**:
- Doesn't solve the flat structure problem
- Will eventually hit scalability limits

### Recommendation: Option B (Minimal Reorganization)

**Reasoning**:
- Prioritize getting font scripts moved first (immediate value)
- Avoid disrupting 18 Taskfiles that reference existing scripts
- Can do full reorganization later as separate effort
- `scripts/fonts/` subdirectory is clear and discoverable

**Future work**:
- If `scripts/` grows beyond 50 files, revisit Option A
- Consider consolidating install-*.sh scripts into subdirectories

---

## WSL Font Installation Considerations

### Key Findings from Research

**WSL Font Installation Challenges**:

1. **Fonts must be installed on Windows, not WSL**
   - Windows Terminal renders fonts from Windows font directory
   - Installing fonts in WSL Linux (`~/.local/share/fonts/`) won't affect Windows Terminal
   - Target: `C:\Windows\Fonts` → WSL path: `/mnt/c/Windows/Fonts/`

2. **Permission Requirements**
   - Copying to `/mnt/c/Windows/Fonts/` requires administrator privileges
   - Work computers may restrict this (Group Policy, corporate security)
   - Registry entries needed for proper installation:
     ```bash
     reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" \
       /v "FontName (TrueType)" /t REG_SZ /d "fontfile.ttf" /f
     ```

3. **File Permission Setup** (required before copy)
   ```bash
   icacls.exe 'font.ttf' /grant 'ALL APPLICATION PACKAGES':RX
   icacls.exe 'font.ttf' /grant 'ALL RESTRICTED APP PACKAGES':RX
   icacls.exe 'font.ttf' /grant Users:RX
   mv 'font.ttf' /mnt/c/Windows/Fonts/
   ```

4. **Alternative: Manual Installation**
   - Download fonts to `/tmp/fonts-to-install/` in WSL
   - Print instructions for user to manually drag-drop to Windows Font Settings
   - More reliable on restricted work computers

### Proposed WSL Installation Strategy

#### Automated Path (Home/Personal Computers)

```bash
install_fonts_wsl() {
    local font_dir="/mnt/c/Windows/Fonts"
    local source_dir="$HOME/fonts"

    echo "Installing fonts to Windows..."

    # Check write permissions
    if ! touch "$font_dir/.test" 2>/dev/null; then
        echo "ERROR: No write access to C:\Windows\Fonts"
        echo "Falling back to manual installation..."
        manual_install_wsl
        return
    fi
    rm "$font_dir/.test"

    # Install fonts
    for font in "$source_dir"/**/*.{ttf,otf,ttc}; do
        if [ -f "$font" ]; then
            filename=$(basename "$font")

            # Set permissions
            icacls.exe "$font" /grant 'ALL APPLICATION PACKAGES':RX 2>/dev/null
            icacls.exe "$font" /grant Users:RX 2>/dev/null

            # Copy to Windows
            cp "$font" "$font_dir/" && echo "✓ Installed $filename"
        fi
    done

    echo "Font installation complete"
    echo "Restart Windows Terminal to see new fonts"
}
```

#### Manual Path (Work Computers)

```bash
manual_install_wsl() {
    local staging_dir="/tmp/fonts-to-install"
    local source_dir="$HOME/fonts"

    mkdir -p "$staging_dir"

    # Copy fonts to staging area
    cp -r "$source_dir"/**/*.{ttf,otf,ttc} "$staging_dir/" 2>/dev/null

    local windows_path=$(wslpath -w "$staging_dir")

    cat <<EOF

╔════════════════════════════════════════════════════════════╗
║  Manual Font Installation Required (WSL)                   ║
╟────────────────────────────────────────────────────────────╢
║  Fonts have been downloaded to:                            ║
║  $windows_path
║                                                             ║
║  To install:                                                ║
║  1. Open File Explorer and navigate to the path above      ║
║  2. Select all .ttf/.otf font files                        ║
║  3. Right-click → "Install" or "Install for all users"     ║
║  4. Restart Windows Terminal                               ║
║                                                             ║
║  Or: Open Windows Settings → Personalization → Fonts       ║
║       Drag and drop font files to install                  ║
╚════════════════════════════════════════════════════════════╝

EOF
}
```

### Recommendation for WSL Support

1. **Attempt automated installation** (check write permissions first)
2. **Fall back to manual instructions** if permissions denied
3. **Document WSL-specific steps** in README
4. **Skip registry entries** (not essential, font cache handles discovery)
5. **Provide clear error messages** with Windows paths (use `wslpath -w`)

**Testing priority**:
- ✅ Test on personal WSL (automated should work)
- ⚠️ Test on work WSL (expect manual fallback)
- Document both workflows in installation guide

---

## Implementation Plan

### Phase 1: Split Installation Scripts (Recommended First Step)

**Goal**: Move font download/install to `management/scripts/fonts/`

**Tasks**:
1. Create `management/scripts/fonts/` directory
2. Move `apps/common/font/commands/download` → `management/scripts/fonts/download.sh`
3. Move `apps/common/font/commands/install` → `management/scripts/fonts/install.sh`
4. Create `management/scripts/fonts/install-fonts.sh` wrapper
5. Add WSL manual fallback logic to `install.sh`
6. Update main `Taskfile.yml` to include font installation
7. Add deprecation warnings to old commands in `font` app
8. Update documentation (README, installation guides)
9. Test on macOS, Linux, WSL (manual fallback)

**Deliverables**:
- `management/scripts/fonts/` with 3 scripts
- Updated Taskfile.yml
- Deprecation warnings in `font` app
- Updated docs

**Success Criteria**:
- `task fonts:install` downloads and installs fonts
- WSL falls back to manual instructions gracefully
- Old `font download` shows deprecation warning
- Font app size reduced from 3,304 LOC → ~1,779 LOC

**Effort**: 2-3 hours
**Risk**: Low (mostly file moves)
**Value**: High (clearer separation, better discoverability)

### Phase 2: Reorganize management/ (Optional)

**Goal**: Create `management/scripts/fonts/` subdirectory (Option B)

**Tasks**:
1. Already done in Phase 1 (fonts/ subdirectory created)
2. Optional: Add README.md to `management/scripts/` explaining organization
3. Optional: Create index of install scripts by category

**Deliverables**:
- Clear documentation of `scripts/` organization
- Optional: Script index/catalog

**Effort**: 1 hour
**Risk**: None (documentation only)
**Value**: Medium (improved discoverability)

### Phase 3: Font App Improvements (Short-term)

**Goal**: Improve existing bash implementation (defer Go conversion)

**Potential Improvements**:
1. **Neovim Integration**: Update font in Neovim config alongside Ghostty
2. **Export History**: Add `font export` command to backup history as CSV/JSON
3. **Custom Preview Text**: Allow per-language preview snippets
4. **Font Size Tracking**: Log font size changes in history
5. **Batch Operations**: `font like-all <pattern>` or `font reject-all <pattern>`
6. **Hoard Improvements**: Better stats, interactive keep/archive workflow

**Deliverables**:
- 2-3 new commands or enhancements
- Updated test suite

**Effort**: 4-8 hours (depends on features chosen)
**Risk**: Low (incremental improvements)
**Value**: High (immediate usability improvements)

### Phase 4: Go Conversion (Long-term, Optional)

**Goal**: Rewrite font app in Go (if benefits outweigh effort)

**Prerequisites**:
- Phase 1 complete (installation scripts already separated)
- Identified compelling reason (performance, new features, team growth)
- 1-1.5 weeks available for focused development

**Tasks** (see "Effort Estimate" section above):
1. Core structure & types (4-6 hours)
2. Font discovery & preview (6-8 hours)
3. Storage layer (4-6 hours)
4. CLI commands (6-8 hours)
5. Bubbletea UI (4-6 hours)
6. Ghostty integration (2-3 hours)
7. Testing & migration (9-12 hours)

**Deliverables**:
- Go binary at `~/go/bin/font`
- Feature parity with bash version
- Test coverage >70%
- Migration guide for existing users

**Effort**: 35-49 hours
**Risk**: Medium (migration, data compatibility)
**Value**: Medium (maintainability, consistency)

**Recommendation**: Defer until compelling reason emerges

---

## Risk Analysis

### Phase 1 Risks (Split Installation Scripts)

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Users expect old `font download` command | Low | High | Add deprecation warning with new command |
| WSL permissions denied | Medium | Medium | Graceful fallback to manual instructions |
| Breaking existing workflows | Low | Low | Keep old commands working with warnings |
| Font data incompatibility | Low | Low | Installation scripts don't touch data files |

### Phase 4 Risks (Go Conversion)

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| History data corruption during migration | High | Low | Comprehensive backup + validation |
| Feature parity gaps | Medium | Medium | Thorough testing, feature checklist |
| User adoption resistance | Low | High | Gradual rollout, keep bash version available |
| Development time overrun | Medium | Medium | Incremental approach, MVP first |
| External tool integration breaks | Medium | Low | Extensive integration testing |

---

## Cost-Benefit Summary

### Phase 1: Split Installation Scripts

**Costs**:
- 2-3 hours development
- Minor documentation updates
- User communication (deprecation warnings)

**Benefits**:
- Clearer separation of concerns (setup vs runtime)
- Better integration with Task automation
- Reduced font app complexity (46% LOC reduction)
- Discoverable font installation alongside other tools
- Foundation for future improvements

**ROI**: ⭐⭐⭐⭐⭐ (High value, low effort)

### Phase 4: Go Conversion

**Costs**:
- 35-49 hours development (1-1.5 weeks)
- Learning curve for contributors
- Ongoing maintenance of build process
- Risk of migration issues

**Benefits**:
- Type safety and compile-time checks
- Better testing infrastructure
- Consistency with sess/toolbox
- Integrated TUI (eliminate fzf dependency)
- Easier refactoring

**ROI**: ⭐⭐⭐☆☆ (Moderate value, high effort)

---

## Recommendations

### Immediate Action (Next 1-2 Weeks)

1. ✅ **Proceed with Phase 1** (split installation scripts)
   - High value, low risk, foundational for other improvements
   - Aligns with existing dotfiles patterns
   - Improves discoverability and maintainability

2. ✅ **Improve WSL installation experience**
   - Add manual fallback with clear instructions
   - Test on work computer (expect permission issues)

3. ✅ **Document font workflow**
   - Update README with new installation process
   - Add examples of font management commands

### Medium-term (1-3 Months)

1. ⚠️ **Consider Phase 3** (bash improvements)
   - Add Neovim integration
   - Export/backup functionality
   - Enhanced hoard management
   - Only if font app sees heavy use

2. ⚠️ **Evaluate management/ reorganization**
   - If `scripts/` grows beyond 50 files
   - Consider full restructure (Option A)

### Long-term (6+ Months)

1. ⏸️ **Defer Phase 4** (Go conversion) unless:
   - History grows to 10K+ entries (performance matters)
   - Want to eliminate external dependencies (fzf → Bubbletea)
   - Team collaboration increases (Go tooling helps)
   - Planning major feature additions (type safety valuable)

2. ⏸️ **Monitor font app usage**
   - If used infrequently, keep bash version
   - If becomes critical tool, Go conversion justified

---

## Next Steps

If proceeding with Phase 1:

1. Create feature branch: `git checkout -b feature/split-font-installation`
2. Create `management/scripts/fonts/` directory
3. Move and adapt scripts (download, install, wrapper)
4. Update Taskfile.yml with font installation tasks
5. Add deprecation warnings to old commands
6. Test on macOS (automated)
7. Test on WSL (manual fallback)
8. Update documentation
9. Create PR with detailed migration notes

**Estimated completion**: 2-3 hours of focused work

---

## Sources & References

### WSL Font Installation Research
- [How to install Powerline fonts on WSL - Stack Overflow](https://stackoverflow.com/questions/63148517/how-to-install-powerline-fonts-on-wsl)
- [Installing a Font in WSL - GitHub Gist](https://gist.github.com/rajeshkumaravel/2795c341f4adf9daffb1791dd5bd3004)
- [How to setup fonts in Linux subsystem - Super User](https://superuser.com/questions/1505879/how-to-setup-fonts-in-linux-subsystem)
- [Sharing Windows fonts with WSL - X410.dev](https://x410.dev/cookbook/wsl/sharing-windows-fonts-with-wsl/)
- [Installing fonts whose files are stored in WSL - GitHub Discussion](https://github.com/microsoft/WSL/discussions/6553)

### Internal Documentation
- `docs/learnings/app-installation-patterns.md` - App installation patterns (Go vs shell apps)
- `apps/common/sess/` - Go app example (session manager)
- `apps/common/toolbox/` - Go app example (tool discovery)
- `management/scripts/README.md` - Installation scripts documentation

### Analyzed Files
- `apps/common/font/bin/font` (628 LOC)
- `apps/common/font/lib/lib.sh` (467 LOC)
- `apps/common/font/lib/storage.sh` (430 LOC)
- `apps/common/font/commands/download` (945 LOC)
- `apps/common/font/commands/install` (358 LOC)
- `management/symlinks/symlinks/manager.py` (link_apps function)

---

## Phase 1 Implementation Summary (COMPLETED ✅)

**Completed**: 2025-11-28
**Duration**: ~2 hours
**Branch**: main (direct commit)

### Changes Made

**1. Created `management/scripts/fonts/` directory**
- `download.sh` - Downloads 23 font families from GitHub (945 LOC)
- `install.sh` - Platform-specific font installation (358 LOC)
- `README.md` - Documentation for font installation scripts

**2. Updated `Taskfile.yml`**
Added font installation to automatic install flow:
- Phase 2: `install-fonts-phase` - Runs after platform packages, before GitHub tools
- Renumbered remaining phases (3-10) to maintain sequential order
- Environment variable: `SKIP_FONTS=1` to skip (clean interface)
- WSL pre-check: Warns about potential manual steps upfront
- Standalone tasks still available:
  - `task fonts:download` - Download coding fonts
  - `task fonts:install` - Install fonts to system

**3. Updated `apps/common/font/bin/font`**
- Added deprecation warnings for `download` and `install` commands
- Directs users to new Task commands
- Removed old command files from `apps/common/font/commands/`

**4. Reduced font app size**
- Before: 3,304 LOC
- After: ~2,001 LOC (39% reduction)
- Clearer focus on runtime management vs setup

### Testing

✅ Verified on macOS:
- `task fonts:download --help` works
- `task fonts:install --help` works
- `font download` shows deprecation warning
- `font list` and `font current` still work (management commands unaffected)

### Files Modified

- `Taskfile.yml` - Added Phase 2 (fonts), renumbered phases 3-10
- `install.sh` - Added Phase 2 (fonts) to install_common_phases(), SKIP_FONTS support, updated help text
- `README.md` - Updated Quick Start to show `./install.sh` and `SKIP_FONTS=1` usage
- `apps/common/font/bin/font` - Added deprecation handling
- `management/scripts/fonts/download.sh` - Moved from `apps/common/font/commands/download`
- `management/scripts/fonts/install.sh` - Moved from `apps/common/font/commands/install`
- `management/scripts/fonts/README.md` - New documentation

### Files Removed

- `apps/common/font/commands/download` - Moved to management/
- `apps/common/font/commands/install` - Moved to management/
- `apps/common/font/commands/cleanup` - Deleted (legacy migration tool, no longer needed)

### Outstanding Items

- [x] Remove `apps/common/font/commands/cleanup` - Done (deleted)
- [ ] Consider `apps/common/font/commands/hoard` - Decide whether to keep, remove, or move fonts elsewhere
- [ ] Update main dotfiles README if it references font installation
- [ ] Test WSL font installation (manual fallback workflow)

### Success Metrics

✅ Clear separation of concerns (setup vs runtime)
✅ Integration with Task automation
✅ Discoverable alongside other installation scripts
✅ Backward compatibility via deprecation warnings
✅ Font app complexity reduced by 39%

---

**End of Analysis**
**Phase 1**: ✅ Complete
**Next Steps**: Monitor usage for 1-3 months, then reassess Phase 3 (bash improvements) or Phase 4 (Go conversion)
