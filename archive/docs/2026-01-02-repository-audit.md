# Dotfiles Repository Audit - January 2026

Post-app-migration comprehensive review of repository alignment with stated philosophy.

## Executive Summary

The repository is **well-organized overall** with a clear philosophy and good separation of concerns. However, there are several documentation inaccuracies that create confusion, particularly around the app installation patterns and the now-removed taskfiles directory.

**Severity Breakdown**:

- **Critical**: 0 issues
- **High**: 2 issues (misleading structure diagrams, outdated CLAUDE.md references)
- **Medium**: 4 issues
- **Low**: 3 issues

## Philosophy Alignment Assessment

### Core Philosophy (from README)

| Principle | Assessment | Notes |
|-----------|------------|-------|
| Fail Fast and Loud | ✅ Aligned | Installation scripts follow this pattern |
| Explicit Over Hidden | ✅ Aligned | Platform detection is upfront |
| Straightforward and Simple | ✅ Aligned | Three install scripts, one per platform |
| Linear and Predictable | ✅ Aligned | Clear installation phases |
| Universal Tools | ✅ Aligned | Install scripts are platform-agnostic |

### Package Management Philosophy

| Principle | Assessment | Notes |
|-----------|------------|-------|
| System packages for system tools | ✅ Aligned | apt/brew/pacman for core utilities |
| Language managers for dev tools | ✅ Aligned | uv (Python), nvm (Node), cargo |
| GitHub releases for latest versions | ✅ Aligned | neovim, lazygit, yazi, fzf |

### Tool Composition Philosophy

| Principle | Assessment | Notes |
|-----------|------------|-------|
| Small, focused tools | ✅ Aligned | sess, toolbox, theme, notes are separate |
| Unix philosophy | ✅ Aligned | Tools output parseable data |
| Shell-level composition | ✅ Aligned | fzf/gum integration at shell level |

## Issues Found

### HIGH Priority

#### 1. Structure Diagrams Show Non-Existent Apps Directories

**Files affected**:

- `README.md:42-43`
- `docs/index.md:165-170`
- `docs/architecture/index.md:20-25`
- `CLAUDE.md:186-189`

**Problem**: Documentation shows this structure:

```text
apps/
├── common/
│   ├── sess/        # WRONG - doesn't exist
│   ├── toolbox/     # WRONG - doesn't exist
│   ├── theme/       # WRONG - doesn't exist
│   ├── menu         # Correct - exists
│   └── notes        # Correct - exists
```

**Reality**: `apps/common/` only contains shell scripts:

```text
apps/common/
├── aws-profiles
├── backup-dirs
├── backup-incremental
├── menu
├── notes
├── patterns
├── printcolors
├── shelldocsparser
└── workflows
```

The Go apps (`sess`, `toolbox`) are installed from GitHub via `go install`. The bash tools (`theme`, `font`) are cloned from GitHub to `~/.local/share/`.

**Impact**: Confuses readers about where tools live and how to modify them.

**Fix**: Update all structure diagrams to:

```text
apps/                # Personal CLI applications (shell scripts)
│   ├── common/      # Cross-platform: menu, notes, backup-dirs, patterns
│   ├── macos/       # macOS-specific tools
│   └── arch/        # Arch-specific tools
```

Add separate section explaining external tools:

```text
External tools (installed from GitHub):
- sess, toolbox: go install github.com/datapointchris/...
- theme, font: cloned to ~/.local/share/
```

#### 2. CLAUDE.md References Deleted taskfiles/ Directory

**File**: `CLAUDE.md:186,262`

**Problem**: CLAUDE.md references `management/taskfiles/` which no longer exists:

```markdown
- `taskfiles/` - Modular Task automation
...
- Modular Taskfile system in `management/taskfiles/` directory
```

**Impact**: AI assistants and contributors get incorrect guidance.

**Fix**: Update CLAUDE.md to reflect the simplified Taskfile.yml structure.

### MEDIUM Priority

#### 3. docs/architecture/tool-composition.md References Wrong Locations

**Problem**: States "Bash/Shell scripts are in `~/.local/bin/` (symlinked from `apps/common/` and `apps/{platform}/)":

```markdown
**Go binaries** are in `~/go/bin/` (built and installed via Task)
```

Actually installed via `go install`, not Task.

**Fix**: Update to reflect accurate installation methods.

#### 4. Changelog Has Obsolete taskfiles References

**File**: `docs/changelog.md`

Multiple references to taskfiles that no longer exist (lines 129-156, 328-329). While historical, this could confuse readers.

**Fix**: Consider adding a note that taskfiles were consolidated into root Taskfile.yml on a specific date.

#### 5. docs/index.md Task Commands Don't Exist

**Problem**: Line 119-120:

```bash
task install             # Auto-detect platform and install
task update              # Update all packages
```

These tasks don't exist in the current Taskfile.yml.

**Fix**: Remove these lines or update to reflect actual tasks.

#### 6. README Shows taskfiles/ in Structure

**File**: `README.md:46`

Same issue as CLAUDE.md - shows `taskfiles/` directory that doesn't exist.

**Fix**: Remove the taskfiles line from the structure diagram.

### LOW Priority

#### 7. Large Archive Directory Growing

**Path**: `archive/`

The archive directory contains 99+ files (historical docs, old Go app code). While untracked by git according to status, it adds complexity.

**Observation**: The archive serves as historical reference but isn't needed for daily work.

**Recommendation**: Consider moving to a separate branch or repository if it continues growing.

#### 8. .claude/sessions/ Has 170+ Session Files

**Path**: `.claude/sessions/`

Accumulating session JSON files. Not a repository issue per se, but worth periodic cleanup.

#### 9. platforms/windows/ Exists But Unused

**Path**: `platforms/windows/`

Contains only a directory stub. Not causing issues but clutters structure.

**Recommendation**: Remove or document its intended purpose.

## What's Working Well

### Excellent Documentation Structure

- `docs/learnings/` captures extracted wisdom effectively
- `docs/architecture/` explains the "why" well
- MkDocs navigation is well-organized
- App-specific documentation is accurate

### Clean Separation of Concerns

- `platforms/` for configs
- `apps/` for shell scripts
- `management/` for installation/orchestration
- Clear common vs platform-specific split

### Accurate Core Documentation

- `docs/learnings/app-installation-patterns.md` is accurate and helpful
- `docs/architecture/package-management.md` is thorough
- `docs/architecture/tool-composition.md` explains philosophy well
- `docs/reference/tools/tasks.md` accurately reflects current Taskfile.yml

### Strong packages.yml Implementation

- Single source of truth working as intended
- Good categorization (system, cargo, npm, uv, go)
- Clear comments explaining decisions

## Recommended Actions

### Quick Wins (< 30 minutes)

1. Update structure diagrams in README.md, docs/index.md, CLAUDE.md
2. Remove `task install` and `task update` references from docs/index.md
3. Remove taskfiles/ reference from CLAUDE.md

### Medium Effort (1-2 hours)

1. Update docs/architecture/tool-composition.md for accuracy
2. Add consolidation note to docs/changelog.md
3. Review and update docs/architecture/index.md

### Housekeeping (Optional)

1. Remove platforms/windows/ if not planned
2. Periodic .claude/sessions/ cleanup

## Fixes Applied

All HIGH and MEDIUM priority issues have been fixed:

### Fixed Files

1. **README.md** - Updated structure diagram, added external tools note
2. **docs/index.md** - Updated structure diagram, fixed task commands, added external tools note
3. **docs/architecture/index.md** - Updated structure diagram, added external tools note
4. **CLAUDE.md** - Removed taskfiles reference, fixed apps directory description
5. **docs/architecture/tool-composition.md** - Fixed Go installation method, corrected tool examples
6. **docs/changelog.md** - Added 2025-12 consolidation note explaining taskfiles removal

## Verification Checklist

After fixes, verify:

- [x] All structure diagrams match reality
- [x] No references to `management/taskfiles/` in active docs
- [x] `task --list` matches documented tasks
- [x] CLAUDE.md accurately reflects app installation patterns
- [ ] No broken internal links in docs (not checked)

## Summary

The repository's **philosophy is sound and well-implemented**. The issues found are documentation lag from recent refactoring (app migration, taskfiles consolidation). The actual code and installation system work correctly - it's the docs that need updating to match.

Priority should be updating the high-visibility files (README.md, CLAUDE.md, docs/index.md) since these are the entry points for understanding the repository.
