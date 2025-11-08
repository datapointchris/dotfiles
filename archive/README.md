# Archive Directory

This directory contains archived code and tools that have been replaced or deprecated.

## Archived Items

### menu-go-v1 (Archived 2025-11-07)

**Why archived:** Replaced with simple `dotfiles` launcher script.

**What it was:**

- Complex Go-based menu system with Bubbletea TUI
- menu-go-new: Go CLI backend
- menu-new: Bash wrapper with fzf
- menu: Original Bubbletea TUI binary (17MB)

**Why it was too complex:**

- Three different implementations trying to solve same problem
- Heavy maintenance burden (Go TUI + CLI + Bash wrapper)
- Added cognitive overhead instead of reducing it
- Menu itself became something to remember/forget

**What replaced it:**

- Simple `dotfiles` launcher (gum-based, <100 lines)
- Direct tool usage (session, tools, theme-sync)
- Composition with fzf when exploring (tools list | fzf)
- Documentation in MkDocs for reference

**If you need to reference:**

- Code is in git history: `git log archive/menu-go-v1-archived-2025-11-07/`
- Planning docs in `planning/universal-menu-redesign/`
- Final working version before archival in git tag `menu-go-v1-final`

---

## Philosophy

When archiving tools, document:

1. What it was
2. Why it was archived
3. What replaced it
4. How to reference if needed

Remember: Archiving isn't failure - it's learning what doesn't work and simplifying.
