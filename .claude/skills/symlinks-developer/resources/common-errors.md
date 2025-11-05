# Common Symlinks Errors

## 1. Pattern Matching Bug - .gitconfig Excluded

**Problem**: Directory pattern `.git/` incorrectly excluded `.gitconfig` file.

**Cause**: Substring matching instead of complete path component checking.

**Fix**: Check for `/.git/` or starts with `.git/`, not just `.git` substring.

See: `docs/learnings/directory-pattern-matching.md`

## 2. Relative Path Calculation

**Problem**: Manual path calculation broke 122 symlinks.

**Cause**: Flawed "common ancestor" logic.

**Fix**: Use Python stdlib `Path.relative_to(walk_up=True)` (Python 3.12+).

See: `docs/learnings/relative-path-calculation.md`

## 3. Cross-Platform Files

**Problem**: Some files needed on all platforms weren't symlinked.

**Cause**: Exclusion patterns not considering cross-platform usage.

**Fix**: Test edge cases - `.gitconfig`, `.gitignore`, `.gitattributes` should NEVER be excluded.

See: `docs/learnings/cross-platform-symlink-considerations.md`
