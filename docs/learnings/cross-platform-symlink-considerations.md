# Cross-Platform Symlink Considerations

**Date**: 2025-11-04
**Context**: Verified 132/132 symlinks working across common and macOS layers

## Critical Files That Must Work Everywhere

Git config files appear on all platforms and must NOT be excluded:

- `.gitconfig`, `.gitignore`, `.gitattributes` - Excluded `.git/` directory must not match these files

Shell configs have platform differences:

- macOS: `.profile` for login shells
- WSL: May use `.bash_profile` or `.bashrc`
- All: Platform-specific aliases and functions

## Common Exclusion Pattern Mistakes

**Don't use substring matching** for directory patterns:

```python
# WRONG: ".git" matches ".gitconfig"
if ".git" in path_str: return True

# CORRECT: Check complete path components
if "/.git/" in path_str or path_str.startswith(".git/"): return True
```

**Patterns to watch**:

- `.git/` vs `.gitconfig`, `.gitignore`, `.github/`
- `node_modules/` vs `node_modules.txt`
- `tmux/plugins/` vs `tmux/tmux.conf`

## Platform-Specific Files

**WSL binary names differ**:

- Ubuntu: `batcat`, `fdfind`
- macOS: `bat`, `fd`
Handle with symlinks in `~/.local/bin/`

**Case sensitivity**:

- Linux/WSL: Case-sensitive
- macOS: Case-insensitive (default)

## Testing Approach

Write tests for both what SHOULD and SHOULD NOT be excluded:

```python
# Directory should be excluded
assert should_exclude(Path(".git/config"))

# Similar files should NOT
assert not should_exclude(Path(".gitconfig"))
assert not should_exclude(Path(".gitignore"))
```

Test cross-platform in integration tests:

```python
for platform in ["macos", "wsl", "arch"]:
    # Verify .gitconfig, .gitignore, .gitattributes all symlink
```

## Key Learnings

- **Check complete path components** - not substrings
- **Test edge cases** - similar-named files that shouldn't match
- **Platform differences matter** - binary names, case sensitivity, line endings
- **Write regression tests** - prevent fixed bugs from returning

## Related

- [Directory Pattern Matching](directory-pattern-matching.md) - Pattern matching bug details
- [Relative Path Calculation](relative-path-calculation.md) - Symlink path calculation
