# Documentation Reorganization Plan - November 2025

## Executive Summary

The documentation has grown organically and now suffers from:

- **Significant duplication** in getting-started/ (3 files with 70% overlap)
- **Disorganized reference/** directory (13 files, several are mashups or duplicates)
- **Completed Go migration docs** still in active development/ section (should be archived)
- **Scattered workflow information** across multiple reference files
- **Missing opportunities** for platform-tabbed content

**Goal**: Create a leaner, more navigable documentation structure that eliminates duplication and provides clear paths to information.

**Impact**: Reduce from 30+ active docs to ~25 well-organized docs, with clearer structure and less redundancy.

---

## Problems Identified

### 1. Getting Started Duplication (70% overlap)

**Current state**:
- `getting-started/quickstart.md` - 41 lines, quick commands per platform
- `getting-started/installation.md` - 188 lines, detailed installation with same commands
- `getting-started/first-config.md` - Post-install configuration

**Problem**: Quickstart is essentially a TL;DR of installation. Users see two files and don't know which to use.

**Solution**: Merge quickstart into installation.md with a "TL;DR" section at top, delete quickstart.md.

---

### 2. Reference Directory Chaos (13 files, 5 are redundant)

**Current state**:
```bash
reference/
├── menu-system.md (455 lines) - Comprehensive menu guide
├── tool-discovery.md (291 lines) - Comprehensive toolbox guide
├── tools.md (68 lines) - Stub that says "use toolbox show"
├── workflow-tools-cheatsheet.md (242 lines) - Quick ref for all tools
├── quick-reference.md - DUPLICATE of workflow-tools-cheatsheet
├── symlinks.md ✓ Good
├── tasks.md ✓ Good
├── platforms.md ✓ Good
├── skills.md ✓ Good
├── hooks.md ✓ Good
├── troubleshooting.md ✓ Good
├── corporate.md - Very niche
├── github-pages.md - About publishing THIS site (dev topic)
├── nerd-fonts.md - Installation guide (getting-started topic)
└── script-formatting-library.md - Developer reference (dev topic)
```

**Problems**:
1. **Duplication**: quick-reference.md and workflow-tools-cheatsheet.md are identical
2. **Stub file**: tools.md is 68 lines that just says "use toolbox"
3. **Topic confusion**: 3 files belong in other sections
4. **No grouping**: 4 workflow tool docs (menu, toolbox, theme-sync, session) aren't grouped

**Solution**: Create workflow-tools/ subdirectory, consolidate duplicates, move misplaced files.

---

### 3. Go Migration Docs Still Active (Should Be Archived)

**Current state** (all in development/):
- `go-migration-strategy.md` (1,143 lines)
- `go-migration-quick-start.md` (265 lines)
- `go-migration-checklist.md` (372 lines)
- `go-menu-migration-complete.md` (528 lines) - **COMPLETED Nov 6, 2025**
- `go-tui-comparison-summary.md`

**Problem**: Migration is complete. These are planning/tracking docs no longer needed for daily use.

**Solution**: Archive to `docs/archive/go-migration/`, keep only active development guides.

---

### 4. Workflows Directory Underutilized

**Current state**:
- `workflows/note-taking.md` (only file)

**Problem**: Workflow information for sessions, themes, git, toolbox scattered across reference files.

**Solution**: Extract workflow content from reference mashups into focused workflow guides.

---

### 5. Missing Platform Tabs

**Current state**:
- `getting-started/installation.md` has separate markdown sections per platform
- Users must scroll to find their platform

**Opportunity**: Use MkDocs tabbed content (already configured in mkdocs.yml).

**Example**:
```markdown
=== "macOS"
    ```bash
    git clone ... && bash management/macos-setup.sh
    ```

=== "WSL Ubuntu"
    ```bash
    git clone ... && bash management/wsl-setup.sh
    ```

=== "Arch Linux"
    ```bash
    git clone ... && bash management/arch-setup.sh
    ```
```

---

## Proposed Solution

### New Documentation Structure

```text
docs/
├── getting-started/
│   ├── installation.md ← MERGED (quickstart + installation with tabs)
│   ├── first-config.md ← KEEP
│   └── fonts.md ← MOVED from reference/nerd-fonts.md
│
├── architecture/
│   ├── index.md
│   ├── menu-system.md (technical architecture)
│   ├── package-management.md
│   ├── path-ordering-strategy.md
│   └── tool-composition.md
│
├── reference/
│   ├── workflow-tools/ ← NEW DIRECTORY
│   │   ├── menu.md (user guide for menu system)
│   │   ├── toolbox.md (consolidated: tool-discovery + tools.md)
│   │   ├── session.md (NEW: extracted from cheatsheet)
│   │   ├── theme-sync.md (NEW: extracted from cheatsheet)
│   │   └── notes.md (NEW: extracted from cheatsheet)
│   ├── platforms.md ← KEEP
│   ├── symlinks.md ← KEEP
│   ├── tasks.md ← KEEP
│   ├── skills.md ← KEEP
│   ├── hooks.md ← KEEP
│   └── troubleshooting.md ← KEEP (add platform tabs)
│
├── workflows/ ← EXPANDED
│   ├── note-taking.md ← EXISTS
│   ├── sessions.md ← NEW (using sess/session command)
│   ├── themes.md ← NEW (theme-sync workflows)
│   ├── git.md ← NEW (forgit workflows)
│   └── tool-discovery.md ← NEW (toolbox usage patterns)
│
├── development/
│   ├── go-apps/ ← NEW DIRECTORY
│   │   ├── overview.md ← NEW (Go apps overview)
│   │   ├── go-development.md ← MOVED (coding standards)
│   │   ├── go-quick-reference.md ← MOVED (Go reference)
│   │   └── bubbletea-quick-reference.md ← MOVED (TUI reference)
│   ├── testing.md
│   ├── notes-system-setup.md
│   ├── shell-formatting.md ← MOVED from reference/
│   └── publishing-docs.md ← MOVED from reference/github-pages.md
│
├── learnings/ ← NO CHANGES
│   └── [14 existing learning docs]
│
└── archive/
    ├── go-migration/ ← NEW
    │   ├── strategy.md
    │   ├── quick-start.md
    │   ├── checklist.md
    │   ├── complete.md
    │   └── tui-comparison.md
    └── [existing archive content]
```

---

## Detailed Changes

### Phase 1: Getting Started Consolidation

#### 1.1 Merge quickstart.md into installation.md

**File**: `docs/getting-started/installation.md`

**New structure**:
```markdown
# Installation

## TL;DR

Quick installation commands for each platform:

=== "macOS"
    ```bash
    git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
    cd ~/dotfiles
    bash management/macos-setup.sh
    ```

=== "WSL Ubuntu"
    ```bash
    git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
    cd ~/dotfiles
    bash management/wsl-setup.sh
    ```

=== "Arch Linux"
    ```bash
    git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
    cd ~/dotfiles
    bash management/arch-setup.sh
    ```

## Prerequisites

[Existing content...]

## Detailed Installation

### macOS
[Detailed macOS steps...]

### WSL Ubuntu
[Detailed WSL steps...]

### Arch Linux
[Detailed Arch steps...]

## Verification
[Existing verification steps...]
```

**Action**: DELETE `docs/getting-started/quickstart.md`

#### 1.2 Move nerd-fonts.md to getting-started

**From**: `docs/reference/nerd-fonts.md`
**To**: `docs/getting-started/fonts.md`

**Reason**: Font installation is part of getting started, not an ongoing reference topic.

---

### Phase 2: Reference Directory Restructure

#### 2.1 Create workflow-tools/ subdirectory

**Action**: Create `docs/reference/workflow-tools/`

#### 2.2 Move and rename menu-system.md

**From**: `docs/reference/menu-system.md`
**To**: `docs/reference/workflow-tools/menu.md`

**Note**: Keep architecture/menu-system.md (different purpose - architecture vs user guide)

**Update content**: Focus on USER workflows, not technical architecture. Cross-reference architecture doc.

#### 2.3 Consolidate toolbox documentation

**Merge**:
- `docs/reference/tool-discovery.md` (291 lines - comprehensive)
- `docs/reference/tools.md` (68 lines - stub)

**Into**: `docs/reference/workflow-tools/toolbox.md`

**Action**: DELETE `docs/reference/tools.md` after merge

#### 2.4 Extract theme-sync from cheatsheet

**Source**: `docs/reference/workflow-tools-cheatsheet.md` (theme-sync section)
**Create**: `docs/reference/workflow-tools/theme-sync.md`

**Content**:
- What theme-sync does
- Installation/setup
- Commands: apply, current, favorites, random
- Configuration (tinty integration)
- Troubleshooting

#### 2.5 Extract session from cheatsheet

**Source**: `docs/reference/workflow-tools-cheatsheet.md` (session section)
**Create**: `docs/reference/workflow-tools/session.md`

**Content**:
- What sess/session does
- Installation/setup
- Commands: start, attach, list, kill
- Session management patterns
- Integration with tmux

#### 2.6 Extract notes from cheatsheet

**Source**: `docs/reference/workflow-tools-cheatsheet.md` (notes section)
**Create**: `docs/reference/workflow-tools/notes.md`

**Content**:
- What notes system does
- Installation/setup
- Commands and usage patterns
- Integration with note-taking workflow

#### 2.7 Delete duplicates and cheatsheet

**Actions**:
- DELETE `docs/reference/quick-reference.md` (duplicate of cheatsheet)
- DELETE `docs/reference/workflow-tools-cheatsheet.md` (content extracted to specific tools)

#### 2.8 Move developer-focused files

**Move**:
- `docs/reference/script-formatting-library.md` → `docs/development/shell-formatting.md`
- `docs/reference/github-pages.md` → `docs/development/publishing-docs.md`

**Optional**: Archive or keep `docs/reference/corporate.md` (decide based on usage)

---

### Phase 3: Archive Go Migration Docs

#### 3.1 Create archive directory

**Action**: Create `docs/archive/go-migration/`

#### 3.2 Move completed migration docs

**Move from development/**:
- `go-migration-strategy.md` → `archive/go-migration/strategy.md`
- `go-migration-quick-start.md` → `archive/go-migration/quick-start.md`
- `go-migration-checklist.md` → `archive/go-migration/checklist.md`
- `go-menu-migration-complete.md` → `archive/go-migration/complete.md`
- `go-tui-comparison-summary.md` → `archive/go-migration/tui-comparison.md`

#### 3.3 Keep active development docs

**Keep in development/**:
- `go-development.md` (coding standards)
- `go-quick-reference.md` (if actively used)
- `bubbletea-quick-reference.md` (for future TUI development)

#### 3.4 Optional: Create go-apps.md

**File**: `docs/development/go-apps.md`

**Content**:
- Overview of Go applications (sess, toolbox)
- Building and testing
- Development workflow
- Adding new commands
- Reference to completed migration for historical context

---

### Phase 4: Expand Workflows Directory

#### 4.1 Create sessions workflow

**File**: `docs/workflows/sessions.md`

**Content** (extract from reference/session.md and workflow-tools-cheatsheet):
- Common session management patterns
- Starting project sessions
- Switching between sessions
- Detaching and reattaching
- Killing orphaned sessions
- Integration with tmux

#### 4.2 Create themes workflow

**File**: `docs/workflows/themes.md`

**Content** (extract from reference/theme-sync.md):
- Exploring available themes
- Applying themes
- Setting favorite themes
- Random theme selection
- Customizing theme preferences
- Troubleshooting theme sync issues

#### 4.3 Create git workflow

**File**: `docs/workflows/git.md`

**Content** (may need to create from scratch or extract from existing docs):
- Common git operations
- Using forgit for interactive git
- Commit workflows
- Branch management
- Stashing and unstashing
- Viewing git status and diffs

#### 4.4 Create toolbox workflow

**File**: `docs/workflows/tool-discovery.md`

**Content** (extract from reference/toolbox.md):
- Discovering new tools
- Finding tool examples
- Searching tool registry
- Getting random tool suggestions
- Integrating new tools
- Maintaining tool registry

---

### Phase 5: Add Platform Tabs

#### 5.1 Update installation.md with tabs

**File**: `docs/getting-started/installation.md`

**Changes**:
- Add TL;DR section with tabbed commands (shown above)
- Consider tabbing detailed installation steps
- Keep verification section unified (works on all platforms)

#### 5.2 Add tabs to troubleshooting

**File**: `docs/reference/troubleshooting.md`

**Changes**:
- Tab platform-specific troubleshooting sections
- Keep general troubleshooting unified

---

### Phase 6: Update mkdocs.yml Navigation

**Update nav structure in mkdocs.yml**:

```yaml
nav:
  - Home: index.md
  - Getting Started:
      - Installation: getting-started/installation.md  # MERGED
      - First Configuration: getting-started/first-config.md
      - Fonts: getting-started/fonts.md  # MOVED
  - Architecture:
      - Overview: architecture/index.md
      - Package Management: architecture/package-management.md
      - PATH Ordering Strategy: architecture/path-ordering-strategy.md
      - Menu System: architecture/menu-system.md
  - Reference:
      - Platform Differences: reference/platforms.md
      - Workflow Tools:  # NEW SECTION
          - Menu: reference/workflow-tools/menu.md
          - Toolbox: reference/workflow-tools/toolbox.md
          - Session Manager: reference/workflow-tools/session.md
          - Theme Sync: reference/workflow-tools/theme-sync.md
          - Notes: reference/workflow-tools/notes.md
      - Symlinks Manager: reference/symlinks.md
      - Task Reference: reference/tasks.md
      - Skills System: reference/skills.md
      - Claude Code Hooks: reference/hooks.md
      - Troubleshooting: reference/troubleshooting.md
      - Corporate Setup: reference/corporate.md  # OPTIONAL: archive
  - Workflows:  # EXPANDED
      - Note Taking: workflows/note-taking.md
      - Session Management: workflows/sessions.md  # NEW
      - Theme Switching: workflows/themes.md  # NEW
      - Git Operations: workflows/git.md  # NEW
      - Tool Discovery: workflows/tool-discovery.md  # NEW
  - Development:
      - VM Testing: development/testing.md
      - Notes System Setup: development/notes-system-setup.md
      - Go Development Standards: development/go-development.md
      - Go Quick Reference: development/go-quick-reference.md  # OPTIONAL
      - Bubbletea Quick Reference: development/bubbletea-quick-reference.md
      - Shell Formatting: development/shell-formatting.md  # MOVED
      - Publishing Docs: development/publishing-docs.md  # MOVED
      - Go Apps Overview: development/go-apps.md  # NEW (optional)
  - Learnings:
      - Overview: learnings/index.md
      [... existing learnings ...]
  - Changelog:
      - Summary: changelog.md
      [... existing changelogs ...]
```

---

## Implementation Plan

### Step 1: Backup and Preparation

1. Create git branch: `git checkout -b docs/reorganization-nov-2025`
2. Verify docs build: `mkdocs serve`
3. Note current structure for rollback if needed

### Step 2: Execute Changes (Phases 1-5)

**Order matters** - do in this sequence:

1. **Phase 1**: Getting Started (merge, move fonts)
2. **Phase 2**: Reference directory (create subdirectory, consolidate, move files)
3. **Phase 3**: Archive Go migration docs
4. **Phase 4**: Create new workflow files
5. **Phase 5**: Add platform tabs

### Step 3: Update Navigation

1. Edit `mkdocs.yml` with new structure
2. Test navigation locally: `mkdocs serve`
3. Verify all links work

### Step 4: Validation

1. Build docs: `mkdocs build`
2. Check for broken links
3. Verify all pages render correctly
4. Review navigation flow
5. Test search functionality

### Step 5: Commit and Deploy

1. Commit changes with descriptive message
2. Push to GitHub
3. Verify GitHub Pages deployment
4. Review live site

---

## File Inventory

### Files to DELETE (5)

1. `docs/getting-started/quickstart.md` - merged into installation.md
2. `docs/reference/tools.md` - merged into toolbox.md
3. `docs/reference/quick-reference.md` - duplicate
4. `docs/reference/workflow-tools-cheatsheet.md` - extracted to specific files

### Files to MOVE (12)

| From | To | Reason |
|------|-----|--------|
| `reference/nerd-fonts.md` | `getting-started/fonts.md` | Getting started topic |
| `reference/menu-system.md` | `reference/workflow-tools/menu.md` | Group workflow tools |
| `reference/tool-discovery.md` | `reference/workflow-tools/toolbox.md` | Group & consolidate |
| `reference/script-formatting-library.md` | `development/shell-formatting.md` | Developer topic |
| `reference/github-pages.md` | `development/publishing-docs.md` | Developer topic |
| `development/go-migration-strategy.md` | `archive/go-migration/strategy.md` | Completed project |
| `development/go-migration-quick-start.md` | `archive/go-migration/quick-start.md` | Completed project |
| `development/go-migration-checklist.md` | `archive/go-migration/checklist.md` | Completed project |
| `development/go-menu-migration-complete.md` | `archive/go-migration/complete.md` | Completed project |
| `development/go-tui-comparison-summary.md` | `archive/go-migration/tui-comparison.md` | Completed project |

### Files to CREATE (9)

1. `docs/reference/workflow-tools/session.md` - extract from cheatsheet
2. `docs/reference/workflow-tools/theme-sync.md` - extract from cheatsheet
3. `docs/reference/workflow-tools/notes.md` - extract from cheatsheet
4. `docs/workflows/sessions.md` - workflow guide
5. `docs/workflows/themes.md` - workflow guide
6. `docs/workflows/git.md` - workflow guide
7. `docs/workflows/tool-discovery.md` - workflow guide
8. `docs/development/go-apps.md` - optional overview
9. `docs/archive/go-migration/README.md` - migration archive index

### Files to UPDATE (3)

1. `docs/getting-started/installation.md` - merge quickstart, add tabs
2. `docs/reference/troubleshooting.md` - add platform tabs
3. `mkdocs.yml` - update navigation

### Directories to CREATE (2)

1. `docs/reference/workflow-tools/`
2. `docs/archive/go-migration/`

---

## Estimated Effort

| Phase | Task | Time |
|-------|------|------|
| 1 | Getting Started consolidation | 1 hour |
| 2 | Reference restructure | 3-4 hours |
| 3 | Archive Go migration | 30 min |
| 4 | Create workflow files | 2-3 hours |
| 5 | Add platform tabs | 1 hour |
| 6 | Update mkdocs.yml | 1 hour |
| - | Testing & validation | 1-2 hours |
| **Total** | | **9-12 hours** |

---

## Success Criteria

✅ Documentation builds without errors
✅ All navigation links work
✅ No duplicate content across files
✅ Reference directory has clear organization (6 core files + workflow-tools/)
✅ Getting Started is streamlined (2 files instead of 3)
✅ Workflow information is in dedicated workflow guides
✅ Completed project docs are archived
✅ Platform-specific content uses tabs where appropriate
✅ Search functionality works correctly
✅ GitHub Pages deploys successfully

---

## Rollback Plan

If issues arise during implementation:

1. **Local issues**: `git reset --hard origin/main`
2. **Deployed issues**: Revert commit and redeploy
3. **Partial completion**: Keep completed phases, pause remaining work

---

## Notes

- This is a **content reorganization**, not a content rewrite
- Focus on moving and consolidating existing content
- Update file paths in cross-references as needed
- Preserve all git history during moves
- Consider keeping workflow-tools-cheatsheet.md as a quick reference index page pointing to detailed docs

---

## Approved Changes

✅ Keep `reference/corporate.md` (still being worked on)
✅ Keep `development/go-quick-reference.md`
✅ Create `development/go-apps/` directory to organize all Go development docs:
  - `development/go-apps/overview.md` (or index.md)
  - `development/go-apps/go-development.md` (standards)
  - `development/go-apps/go-quick-reference.md`
  - `development/go-apps/bubbletea-quick-reference.md`
✅ Add workflow tools cheatsheet content to main `index.md` as quick reference
✅ Rewrite and consolidate docs as needed per CLAUDE.md documentation guidelines
