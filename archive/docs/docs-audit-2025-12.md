# Documentation Audit Report - December 2025

Comprehensive audit of `docs/` directory against actual project state.

## Executive Summary

The documentation has significant gaps and outdated references from recent refactoring:

- **Major issue**: `management/taskfiles/` directory no longer exists, but 50+ references remain
- **Major issue**: Theme system completely rewritten (tinty/theme-sync → unified `theme` CLI), but 52 docs still reference old system
- **Missing app docs**: theme, printcolors, shelldocsparser, workflows (4 undocumented apps)
- **Missing research**: Hyprland guide exists but not in navigation
- **Broken links**: apps/index.md references non-existent ghostty-theme.md
- **Test file debris**: 3 test files at docs root that should be deleted
- **Hook docs mismatch**: docs/reference/tools/hooks.md describes hooks that have been moved/renamed

---

## 1. FILES TO DELETE

### 1.1 Test File Debris at docs Root

These appear to be leftover test files that should be removed:

```text
docs/final-hook-test.md
docs/hook-final-test.md
docs/agent-id-test.md
```

---

## 2. MISSING DOCUMENTATION

### 2.1 Missing App Documentation

Apps exist in `apps/common/` but have no docs:

| App | Location | Priority | Notes |
|-----|----------|----------|-------|
| **theme** | `apps/common/theme/` | HIGH | Major tool, replaces tinty/theme-sync. Has internal CLAUDE.md |
| **printcolors** | `apps/common/printcolors` | LOW | Simple utility |
| **shelldocsparser** | `apps/common/shelldocsparser` | LOW | Parser utility |
| **workflows** | `apps/common/workflows` | MEDIUM | Workflow automation |

**Action**: Create `docs/apps/theme.md` (HIGH PRIORITY) - this is a major app with complex functionality.

### 2.2 Missing Research in Navigation

File exists but NOT in mkdocs.yml nav:

```text
docs/research/hyprland/understanding-hyprland.md
```

**Action**: Add to research section in mkdocs.yml.

### 2.3 Incomplete apps/index.md

The apps index page is missing several apps that have documentation:

**Listed in nav but missing from index grid cards:**

- patterns
- refcheck
- backup-incremental

**References non-existent file:**

- `ghostty-theme.md` - this file doesn't exist!

---

## 3. OUTDATED DOCUMENTATION

### 3.1 management/taskfiles/ References (CRITICAL)

The `management/taskfiles/` directory **no longer exists**. All tasks are now in root `Taskfile.yml`.

**Files with references (non-archive):**

| File | Impact |
|------|--------|
| `docs/index.md:175` | Structure diagram shows `taskfiles/` |
| `docs/architecture/index.md:29` | Structure diagram shows `taskfiles/` |
| `docs/architecture/package-management.md` (multiple) | References taskfiles organization |
| `docs/reference/tools/tasks.md:247-269` | Entire section about "Modular Taskfile Organization" is obsolete |
| `docs/reference/tools/skills.md:47` | File trigger references `taskfiles/*.yml` |
| `docs/development/go-apps/overview.md:126` | References updating `taskfiles/install.yml` |
| `docs/development/go-apps/go-development.md:621` | Shows `taskfiles/go.yml` example |
| `docs/learnings/testing-bootstrap-dependencies.md` | References `management/taskfiles/` |
| `docs/learnings/idempotent-installation-patterns.md` | References `management/taskfiles/` |
| `docs/learnings/wsl-ubuntu-package-versions.md` | References taskfiles |
| `docs/learnings/arch-git-libpcre2-warning.md` | References `management/taskfiles/arch.yml` |
| `docs/learnings/task-shell-printf-compatibility.md` | References `management/taskfiles/wsl.yml` |

**Action**: Update all references. The root `Taskfile.yml` is now flat/simple.

### 3.2 tinty/theme-sync References (CRITICAL)

The old theme system (tinty, theme-sync) has been completely replaced by the unified `theme` CLI.

**52 files still reference tinty or theme-sync** (run `grep -r "tinty\|theme-sync" docs/`).

**Non-archive files needing updates:**

| File | Notes |
|------|-------|
| `docs/changelog.md` | OK - historical record |
| `docs/research/development-environments.md` | May need update |
| `docs/reference/tools/symlinks.md` | Check if tinty mention is current |
| `docs/learnings/package-version-analysis.md` | Check if current |
| `docs/learnings/go-tui-ecosystem-research.md` | Check if current |
| `docs/architecture/path-ordering-strategy.md` | Check if current |

**The `docs/archive/` files are OK** - they're historical records.

### 3.3 Hooks Documentation Mismatch

`docs/reference/tools/hooks.md` describes hooks that are in the **wrong location** or **don't exist**:

**Hooks referenced as project-specific but actually in ~/.claude/hooks/:**

- `markdown_formatter.py` - exists in ~/.claude/hooks/, not .claude/hooks/
- `notification-desktop` - exists in ~/.claude/hooks/, not .claude/hooks/
- `pre-compact-save-state` - exists in ~/.claude/hooks/, not .claude/hooks/
- `session-start` - exists in ~/.claude/hooks/, not .claude/hooks/

**Hooks referenced that don't exist anywhere:**

- `check-bash-error-safety` - NOT FOUND
- `user-prompt-submit-skill-activation` - NOT FOUND

**Hook name mismatch:**

- Doc says `stop-commit-reminder` but actual file is `stop-dotfiles-changelog-reminder`

**Actual project hooks (.claude/hooks/):**

```text
check-feature-docs
stop-build-check
stop-dotfiles-changelog-reminder
```

**Action**: Rewrite hooks.md to accurately reflect the two-tier system.

---

## 4. STRUCTURAL ISSUES

### 4.1 apps/index.md Grid Cards Incomplete

Current grid cards only show:

- Development Tools: Notes, Session Manager
- Utilities: Menu, Toolbox, Backup Dirs
- Platform-Specific: Font, Ghostty Theme (broken link!)

**Missing from grids:**

- patterns (has doc)
- refcheck (has doc)
- backup-incremental (has doc)
- theme (needs doc created first)

### 4.2 research/index.md Missing Hyprland

The research index only lists:

- AI Research
- Development Environments

But `docs/research/hyprland/understanding-hyprland.md` exists and isn't linked.

---

## 5. ACCURACY ISSUES

### 5.1 Structure Diagrams Outdated

Multiple docs show this outdated structure:

```text
management/
├── symlinks/        # Correct
├── taskfiles/       # WRONG - doesn't exist
├── *.sh             # Correct
└── packages.yml     # Correct
```

**Correct structure:**

```text
management/
├── symlinks/           # Python symlinks manager
├── orchestration/      # Platform orchestration
├── common/             # Common installers and lib
├── macos/              # macOS-specific
├── wsl/                # WSL-specific
├── arch/               # Arch-specific
├── packages.yml        # Package definitions
└── *.sh                # Root-level scripts
```

Files to update:

- `docs/index.md:155-179`
- `docs/architecture/index.md:9-33`

### 5.2 Font Doc Says "macOS only"

`docs/apps/index.md:45-46` says Font is "Font management for macOS" but the font tool now has multi-platform support (recent commit: `feat(font): add multi-platform font apply support`).

---

## 6. PRIORITY ACTION LIST

### HIGH Priority (Breaking/Critical)

1. **Delete test files** at docs root
2. **Fix ghostty-theme.md broken link** in apps/index.md (remove or create)
3. **Create docs/apps/theme.md** - major undocumented app
4. **Update reference/tools/tasks.md** - taskfiles section completely obsolete
5. **Fix reference/tools/hooks.md** - hooks described don't match reality

### MEDIUM Priority (Outdated)

6. **Update structure diagrams** in index.md and architecture/index.md
7. **Update apps/index.md** - add missing apps to grid cards, fix "macOS only" for font
8. **Add Hyprland to research nav** in mkdocs.yml
9. **Review tinty/theme-sync references** in non-archive docs
10. **Update learnings referencing taskfiles/**

### LOW Priority (Nice to have)

11. **Create docs for minor apps**: printcolors, shelldocsparser, workflows
12. **Audit archive/** for any outdated references that got moved there

---

## 7. FILES TO MODIFY

| File | Changes Needed |
|------|----------------|
| `mkdocs.yml` | Add Hyprland research to nav |
| `docs/apps/index.md` | Fix broken link, add missing apps, fix "macOS only" |
| `docs/apps/theme.md` | CREATE - new file |
| `docs/index.md` | Update structure diagram |
| `docs/architecture/index.md` | Update structure diagram |
| `docs/reference/tools/tasks.md` | Remove/update taskfiles section |
| `docs/reference/tools/hooks.md` | Rewrite to match actual hook locations |
| `docs/reference/tools/skills.md` | Update taskfiles reference |
| `docs/development/go-apps/overview.md` | Update taskfiles reference |
| `docs/development/go-apps/go-development.md` | Update taskfiles reference |
| `docs/learnings/*.md` (6+ files) | Update taskfiles references |
| `docs/architecture/package-management.md` | Update taskfiles references |
| `docs/research/index.md` | Add Hyprland link |

---

## 8. VERIFICATION COMMANDS

After updates, verify with:

```bash
# Check for remaining taskfiles references (should only be in archive/)
grep -r "management/taskfiles" docs/ --include="*.md" | grep -v archive/

# Check for remaining tinty references (should only be in archive/)
grep -r "tinty\|theme-sync" docs/ --include="*.md" | grep -v archive/ | grep -v changelog

# Check for broken internal links
cd docs && mkdocs build 2>&1 | grep -i "warning\|error"

# Verify all nav files exist
# (mkdocs will warn about missing files)
```
