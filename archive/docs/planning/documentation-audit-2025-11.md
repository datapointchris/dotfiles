# Documentation Audit and Update Plan - November 2025

**Status**: Updated after repository restructure completion (November 2025)

## Executive Summary

Comprehensive audit of all documentation in `docs/` (excluding archive) to ensure accuracy with current repository state. Major updates needed:

1. **Repository Restructure** (COMPLETED): Update all docs from old structure (common/, tools/, taskfiles/) to new structure (platforms/, apps/, management/)
2. **Notes System Migration** (COMPLETED): Update from nb/Obsidian to zk CLI
3. **Tool Renames**: Update tools → toolbox references
4. **Session Manager**: Update sesh → sess references
5. **Architecture Simplification**: Simplify overly complex docs to match current simple implementations

**Recent Changes Since Plan Created**:

- Repository restructured to platforms/, apps/, management/ (November 2025)
- notes CLI updated to use zk backend (November 2025)
- zk documentation created at docs/development/notes-system-setup.md (November 2025)
- Tool registry moved to XDG location: platforms/common/.config/toolbox/registry.yml

## Current State Analysis

### Repository Structure (Current - Post November 2025 Restructure)

```text
dotfiles/
├── platforms/           # System configurations (deployed to $HOME)
│   ├── common/          # Shared configs (all platforms)
│   │   ├── .config/     # XDG configs (nvim, tmux, zsh, git, etc.)
│   │   └── .local/      # XDG user files
│   ├── macos/           # macOS-specific overrides
│   ├── wsl/             # WSL Ubuntu overrides
│   └── arch/            # Arch Linux overrides
├── apps/                # Personal CLI applications (source)
│   ├── common/          # Cross-platform tools (menu, notes, toolbox, theme-sync, etc.)
│   ├── macos/           # macOS-specific tools (ghostty-theme, aws-profiles)
│   └── sess/            # Session manager (Go app)
├── management/          # Repository management tools
│   ├── symlinks/        # Symlinks manager (Python)
│   ├── taskfiles/       # Task automation modules
│   ├── packages.yml     # Package definitions
│   └── *.sh             # Platform setup scripts
├── docs/                # MkDocs documentation
└── .claude/             # Skills and hooks
```

### Key Changes Not Reflected in Docs

1. **Repository Structure**: Complete restructure to platforms/, apps/, management/ (November 2025)
2. **Notes System**: Removed obsidian and nb, now using zk CLI as backend (COMPLETED)
3. **Notes CLI**: Updated to use zk instead of Obsidian (COMPLETED)
4. **Session Manager**: Using sess (not sesh) - custom Go tool
5. **Menu System**: Significantly simplified from complex architecture
6. **Tool Registry**: Now at platforms/common/.config/toolbox/registry.yml (XDG compliant)
7. **Tools Command**: Renamed to "toolbox" to avoid namespace confusion

### Documentation Files (Non-Archive)

Total files to audit: 48 markdown files across:

- architecture/ (4 files)
- changelog/ (5 files)
- development/ (9 files)
- getting-started/ (3 files)
- learnings/ (12 files)
- reference/ (12 files)
- workflows/ (1 file)
- root level (2 files)

## Issues Identified by Category

### Critical (Completely Incorrect)

1. **workflows/note-taking.md** - Entirely about nb (565 lines), needs complete rewrite for zk
2. **architecture/sesh-architecture-diagram.md** - Documents old "sesh" tool, we use "sess"
3. **All architecture docs** - Show old structure (common/, tools/, etc.) instead of new (platforms/, apps/, management/)

### High Priority (Structural Errors)

4. **architecture/index.md** - Shows old directory structure, needs update for platforms/apps/management
5. **architecture/menu-system.md** - Overly complex for current simple bash implementation
6. **reference/menu-system.md** - May reference removed nb/obsidian integration
7. **mkdocs.yml:159** - Points to "development/testing.md" - verify link works
8. **README.md** - Shows old structure, needs update for new layout

### Medium Priority (Potential Outdated References)

9. **reference/quick-reference.md** - Likely references nb/obsidian, old paths
10. **reference/workflow-tools-cheatsheet.md** - Likely references nb/obsidian, old paths
11. **architecture/tool-composition.md** - May show nb/obsidian in diagrams, old structure
12. **platforms/common/.config/toolbox/registry.yml** - May list nb/obsidian (was docs/tools/registry.yml)

### Low Priority (Minor Updates Needed)

12. Various getting-started guides may reference old workflows
13. Development docs may have outdated build/test instructions
14. Reference platform docs may need verification

## Detailed Audit Plan

### Phase 1: Critical Fixes (Complete Rewrites)

#### Task 1.1: Rewrite Note-Taking Documentation

**File**: `docs/workflows/note-taking.md`

**Current State**: 565 lines entirely about nb
**Required Action**: Complete rewrite for zk CLI

**Subtasks**:

- Document current zk setup and configuration (already exists at docs/development/notes-system-setup.md)
- Explain zk notebook structure ($HOME/notes/)
- Document basic zk workflows (new, list, edit, search)
- Document notes CLI wrapper (already updated to use zk)
- Add examples and best practices
- Keep under 200 lines (follow learnings format - concise)
- Reference existing notes-system-setup.md for detailed setup

**Dependencies**: None
**Estimated Effort**: 1 hour (notes CLI already done)

#### Task 1.2: Fix/Remove sesh Architecture Diagram

**File**: `docs/architecture/sesh-architecture-diagram.md`

**Current State**: Documents old "sesh" tool architecture
**Required Action**: Decide if sess needs architecture doc or remove

**Subtasks**:

- Check if sess is simple enough to not need architecture doc
- If complex: Create new sess-architecture.md based on apps/sess/ code
- If simple: Remove file and update mkdocs.yml navigation
- Update any references to this doc in other files

**Dependencies**: None
**Estimated Effort**: 30 mins analysis, 1 hour if rewrite needed

#### Task 1.3: Update All Architecture Docs for New Structure

**Files**: `docs/architecture/*.md`, `README.md`

**Current State**: Show old structure (common/, tools/, taskfiles/, install/, config/)
**Required Action**: Update to new structure (platforms/, apps/, management/)

**Subtasks**:

- Update architecture/index.md directory structure diagram
- Update all path references: common/ → platforms/common/
- Update all path references: tools/symlinks → management/symlinks/
- Update all path references: taskfiles/ → management/taskfiles/
- Update all path references: tools/sess → apps/sess/
- Update all path references: common/.local/bin/*→ apps/common/*
- Update tool registry path: docs/tools/registry.yml → platforms/common/.config/toolbox/registry.yml
- Update README.md structure diagram
- Update any other architecture docs with old paths

**Dependencies**: None
**Estimated Effort**: 1-2 hours

### Phase 2: High Priority Structural Fixes

#### Task 2.1: Update Menu System Reference Docs

**File**: `docs/reference/menu-system.md`

**Current State**: May reference old workflows and paths
**Required Action**: Update for current implementation and new structure

**Subtasks**:

- Remove nb/obsidian references
- Update session manager references (sess not sesh)
- Update paths: apps/common/menu instead of common/.local/bin/menu
- Verify all commands and examples work
- Update knowledge registry section if changed
- Cross-check with actual menu script behavior

**Dependencies**: Task 1.3 (architecture paths updated)
**Estimated Effort**: 30-45 mins

#### Task 2.2: Simplify Menu System Architecture

**File**: `docs/architecture/menu-system.md`

**Current State**: ~150 lines of complex architecture docs
**Required Action**: Simplify to match current bash implementation

**Subtasks**:

- Read current `apps/common/menu` implementation
- Assess if architecture doc is even needed for simple bash script
- If keeping: Drastically simplify - remove complex diagrams
- Focus on: what it does, how to use it, available commands
- Remove references to nb/obsidian integration
- Update tool integrations list to current state (zk, sess, toolbox, theme-sync)
- Update all path references to new structure
- Consider splitting into architecture vs reference

**Dependencies**: Task 1.3 (structure updated)
**Estimated Effort**: 1 hour

#### Task 2.4: Verify Development Testing Link

**File**: mkdocs.yml navigation, `docs/development/testing.md`

**Current State**: mkdocs.yml:159 points to development/testing.md
**Required Action**: Verify file exists and link works

**Subtasks**:

- Check if file exists at correct path
- If missing: find correct file or remove from navigation
- If exists: verify content is accurate and up-to-date
- Update mkdocs.yml if path changed

**Dependencies**: None
**Estimated Effort**: 10 mins

### Phase 3: Medium Priority Reference Updates

#### Task 3.1: Update Quick Reference

**File**: `docs/reference/quick-reference.md`

**Current State**: Likely references nb/obsidian
**Required Action**: Update all workflow tool references

**Subtasks**:

- Replace nb references with zk
- Remove obsidian references
- Update session manager to sess (not sesh)
- Verify all command examples work
- Check keyboard shortcuts are current
- Update tool compositions

**Dependencies**: Tasks 1.1, 2.3
**Estimated Effort**: 20-30 mins

#### Task 3.2: Update Workflow Tools Cheatsheet

**File**: `docs/reference/workflow-tools-cheatsheet.md`

**Current State**: Likely references nb/obsidian
**Required Action**: Update for current toolset

**Subtasks**:

- Replace nb with zk examples
- Remove obsidian entries
- Add zk common commands
- Update sess examples
- Verify theme-sync examples
- Check tools discovery examples

**Dependencies**: Task 1.1
**Estimated Effort**: 20-30 mins

#### Task 3.3: Update Tool Composition Architecture

**File**: `docs/architecture/tool-composition.md`

**Current State**: May show nb/obsidian in diagrams
**Required Action**: Update tool integration diagrams

**Subtasks**:

- Read file and identify all tool references
- Update diagrams to show zk (not nb/obsidian)
- Update sess (not sesh)
- Verify all workflow compositions are current
- Update examples to match current tools

**Dependencies**: Tasks 1.1, 2.2
**Estimated Effort**: 30-45 mins

#### Task 3.4: Update Toolbox Registry

**File**: `platforms/common/.config/toolbox/registry.yml`

**Current State**: May list nb/obsidian (was previously at docs/tools/registry.yml)
**Required Action**: Update tool entries for current toolset

**Subtasks**:

- Remove nb entry if present
- Remove obsidian entry if present
- Add/update zk entry with correct metadata
- Update sess entry (verify not sesh)
- Verify all other tools are current
- Check examples and documentation links
- Update any docs referencing old path (docs/tools/registry.yml)

**Dependencies**: Task 1.1, 1.3
**Estimated Effort**: 20-30 mins

### Phase 4: Comprehensive File-by-File Review

#### Task 4.1: Architecture Files

**Files**:

- `docs/architecture/index.md` (covered in 2.1)
- `docs/architecture/menu-system.md` (covered in 2.2)
- `docs/architecture/sesh-architecture-diagram.md` (covered in 1.2)
- `docs/architecture/tool-composition.md` (covered in 3.3)

**Status**: All covered in earlier phases

#### Task 4.2: Getting Started Files

**Files**:

- `docs/getting-started/quickstart.md`
- `docs/getting-started/installation.md`
- `docs/getting-started/first-config.md`

**Required Actions**:

- Verify installation instructions are current
- Check package lists match current requirements
- Update workflow tool setup (zk not nb)
- Verify symlink setup instructions
- Check platform-specific instructions

**Dependencies**: Tasks 1.1, 2.1
**Estimated Effort**: 45 mins total

#### Task 4.3: Reference Files

**Files** (12 total, some already covered):

- `docs/reference/platforms.md` - Verify package names
- `docs/reference/menu-system.md` (covered in 2.3)
- `docs/reference/tools.md` - Update tool listings
- `docs/reference/tool-discovery.md` - Verify examples
- `docs/reference/tasks.md` - Check task commands
- `docs/reference/symlinks.md` - Verify examples
- `docs/reference/skills.md` - Check Claude Code skills
- `docs/reference/hooks.md` - Verify hook configs
- `docs/reference/troubleshooting.md` - Update solutions
- `docs/reference/corporate.md` - Verify setup steps
- `docs/reference/github-pages.md` - Check build process
- `docs/reference/quick-reference.md` (covered in 3.1)
- `docs/reference/workflow-tools-cheatsheet.md` (covered in 3.2)

**Required Actions**: Review each for accuracy, update outdated references

**Dependencies**: Earlier phases
**Estimated Effort**: 2-3 hours total

#### Task 4.4: Development Files

**Files** (9 total):

- `docs/development/testing.md` (covered in 2.4)
- `docs/development/go-migration-strategy.md`
- `docs/development/go-migration-quick-start.md`
- `docs/development/go-migration-checklist.md`
- `docs/development/go-tui-comparison-summary.md`
- `docs/development/bubbletea-quick-reference.md`
- `docs/development/go-development.md`
- `docs/development/go-quick-reference.md`
- `docs/development/go-menu-migration-complete.md`

**Required Actions**:

- Verify Go development docs reflect current state
- Check if Go migration is complete (seems so)
- Update build/test instructions
- Verify examples compile and run

**Dependencies**: None
**Estimated Effort**: 1-2 hours

#### Task 4.5: Learnings Files

**Files** (12 total):

- All learnings files (bash testing, git, symlinks, Go, etc.)

**Required Actions**:

- Quick verification each learning is still relevant
- Check examples still work
- Update any tool references (nb→zk, etc.)
- Ensure links to other docs are valid

**Dependencies**: Earlier phases
**Estimated Effort**: 1 hour

#### Task 4.6: Changelog Files

**Files** (5 files):

- `docs/changelog.md`
- `docs/changelog/2025-11-05.md`
- `docs/changelog/2025-11-04.md`
- `docs/changelog/2025-11-04-taskfile-modularity.md`
- `docs/changelog/2025-11-04-taskfile-simplification.md`
- `docs/changelog/2025-11-02.md`

**Required Actions**:

- Light review - changelogs are historical
- Verify links to other docs work
- Check if outdated references need clarification notes

**Dependencies**: None
**Estimated Effort**: 20 mins

#### Task 4.7: Root Level Files

**Files**:

- `docs/index.md`
- `docs/README.md`
- `docs/publishing.md`

**Required Actions**:

- Update main landing page for accuracy
- Verify README is current
- Check publishing process still works

**Dependencies**: All earlier phases
**Estimated Effort**: 30 mins

### Phase 5: Cross-Cutting Verification

#### Task 5.1: Link Validation

**Action**: Verify all internal documentation links work

**Subtasks**:

- Check all `[text](../path)` links resolve
- Verify mkdocs.yml navigation entries exist
- Test relative links between docs
- Fix broken links or update paths

**Dependencies**: All file updates complete
**Estimated Effort**: 30-45 mins

#### Task 5.2: Code Example Verification

**Action**: Test code examples actually work

**Subtasks**:

- Run bash command examples
- Test zk commands work
- Verify sess commands execute
- Check theme-sync examples
- Test symlink commands

**Dependencies**: All file updates complete
**Estimated Effort**: 45 mins - 1 hour

#### Task 5.3: Screenshot/Diagram Updates

**Action**: Update any outdated diagrams or screenshots

**Subtasks**:

- Identify diagrams showing old tools
- Update Mermaid diagrams if used
- Regenerate screenshots if needed
- Update architecture diagrams

**Dependencies**: All file updates complete
**Estimated Effort**: 1-2 hours (if diagrams need updates)

#### Task 5.4: MkDocs Navigation Audit

**Action**: Ensure mkdocs.yml navigation matches files

**Subtasks**:

- Check every nav entry has corresponding file
- Verify no orphaned files missing from nav
- Update navigation structure if needed
- Test local docs site builds cleanly

**Dependencies**: All file updates complete
**Estimated Effort**: 20 mins

## Execution Strategy

### Principles

1. **One section at a time** - Complete each task fully before moving on
2. **Commit after each task** - Clear progress tracking
3. **Fix ALL pre-commit errors** - No skipping checks
4. **Test examples** - Don't document commands that don't work
5. **Ask when uncertain** - But only after analyzing codebase

### Order of Execution

1. Phase 1 (Critical) - Foundation for other updates
2. Phase 2 (High Priority) - Structural fixes
3. Phase 3 (Medium Priority) - Reference updates
4. Phase 4 (File-by-file) - Systematic review
5. Phase 5 (Verification) - Quality assurance

### Commit Strategy

Each task gets its own commit:

- `docs: rewrite note-taking guide for zk CLI`
- `docs: fix architecture diagram directory paths`
- `docs: simplify menu system architecture`
- `docs: update reference docs for current toolset`
- etc.

### Pre-commit Checks

All commits must pass:

- markdownlint (fix MD040 manually, --fix won't handle it)
- yamllint
- shellcheck (if relevant)
- prettier

## Success Criteria

- [ ] All docs accurately reflect current repository structure
- [ ] No references to removed tools (nb, obsidian, sesh)
- [ ] All code examples tested and working
- [ ] All internal links validated
- [ ] MkDocs site builds without errors
- [ ] All pre-commit checks passing
- [ ] Each phase committed separately

## Estimated Total Time

**Original Estimate**: 14-17 hours
**Adjusted After Restructure**: 12-15 hours (notes CLI already done, zk docs exist)

- Phase 1: 2-3 hours (reduced - notes CLI done, zk setup doc exists)
- Phase 2: 2-3 hours
- Phase 3: 2 hours
- Phase 4: 4-5 hours (many files need path updates for new structure)
- Phase 5: 2-3 hours

**Breakdown by Change Type**:

- Repository structure path updates: 6-8 hours (most files affected)
- Tool updates (zk, sess, toolbox): 3-4 hours
- Architecture simplification: 2-3 hours
- Verification and testing: 1-2 hours

Spread across multiple sessions to maintain quality and attention to detail.

## Notes

- Some docs may be candidates for archive if no longer relevant
- Consider creating new learnings from this audit process
- Update CLAUDE.md if documentation philosophy changes discovered
- May discover additional issues during execution - update plan accordingly
