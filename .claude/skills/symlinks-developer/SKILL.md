---
description: "Managing dotfiles symlink system (project)"
tags: ["symlinks", "dotfiles", "cross-platform"]
---

# Symlinks Developer

Expertise in the dotfiles symlink management system.

## Core Principles

- Symlinks deploy configs from repo to $HOME
- Layer pattern: common base + platform overlay
- Exclusion patterns must check complete path components (not substrings)

## Common Patterns

### Running Symlinks

```bash
# After adding/removing files
symlinks relink macos
symlinks relink wsl
symlinks relink arch

# Check current symlinks
symlinks check macos
```

### Testing

```bash
cd tools/symlinks
pytest -v
pytest tests/test_utils.py  # Unit tests
pytest tests/test_integration.py  # Integration tests
```

## Critical Bugs to Avoid

See [Common Errors](resources/common-errors.md) for detailed examples:

1. **Substring matching** - `.git/` excluding `.gitconfig`
2. **Relative path calculation** - Use stdlib, not manual logic
3. **Platform differences** - Binary names, case sensitivity

## Resources

- [Common Errors](resources/common-errors.md) - Pattern matching bugs
- [Testing Guide](resources/testing-guide.md) - Pytest coverage
- [Platform Differences](resources/platform-differences.md) - macOS vs Linux

## Quick Reference

**Location**: `tools/symlinks/`

**Main file**: `symlinks/manager.py`

**Tests**: `tests/` directory (25 tests total)
