# Learnings

Quick-reference lessons learned from dotfiles development. Each learning captures a specific bug, gotcha, or best practice worth remembering.

## Available Learnings

### [Relative Path Calculation](relative-path-calculation.md)

Python stdlib path resolution vs manual calculation.

**Key lesson**: Use `Path.relative_to(walk_up=True)` instead of manual path calculation to avoid breaking symlinks.

### [Directory Pattern Matching](directory-pattern-matching.md)

Glob pattern matching for directories and the significance of trailing slashes.

**Key lesson**: Check for `/.git/` or starts with `.git/`, not substring match, to avoid excluding `.gitconfig`.

### [Cross-Platform Symlinks](cross-platform-symlink-considerations.md)

Windows vs Unix symlink behavior differences.

**Key lesson**: Test cross-platform edge cases - `.gitconfig`, `.gitignore`, `.gitattributes` should never be excluded.

### [Documentation Consolidation](documentation-consolidation-principles.md)

Principles for maintaining focused, clear documentation from CLAUDE.md refactor.

**Key lesson**: Focus on what's needed, remove verbose explanations and outdated content, consolidate related sections, reference other docs instead of duplicating.

## Format

Learnings follow a concise format (30-50 lines):

1. **Problem**: What went wrong
2. **Solution**: How to do it correctly
3. **Key Learnings**: Bullet points of actionable wisdom
4. **Testing**: Brief example (optional)
5. **Related**: Links to other learnings

## Adding Learnings

Create new learning in `docs/learnings/` when you discover something worth remembering.

Target 30-50 lines total - if longer, it belongs in main documentation not learnings.
