# Directory Pattern Matching: Beware Substring Matches

**Date**: 2025-11-04
**Context**: `.git/` pattern excluded `.gitconfig`, breaking git configuration

## The Problem

Substring matching for directory patterns causes false positives:

```python
# BROKEN: ".git" substring matches ".gitconfig"
if pattern.endswith("/") and pattern.rstrip("/") in path_str:
    return True  # BUG!
```

Impact: `.gitconfig` was never symlinked to home directory.

## The Solution

Check for complete path components:

```python
if pattern.endswith("/"):
    dir_name = pattern.rstrip("/")
    if f"/{dir_name}/" in path_str or path_str.startswith(f"{dir_name}/"):
        return True
```

Results:
- `/.git/` matches `foo/.git/bar` ✓
- `.git/` matches `.git/config` ✓
- `.git` does NOT match `.gitconfig` ✓

## Key Learnings

- **Check complete path components** - substring matching is almost never correct for paths
- **Test similar filenames** - `.git/` vs `.gitconfig`, `node_modules/` vs `node_modules.txt`
- **Write regression tests** - prevent fixed bugs from returning

## Testing

Always test edge cases:

```python
# Directory should be excluded
assert should_exclude(Path(".git/config"))
assert should_exclude(Path("foo/.git/hooks"))

# Similar-named files should NOT be excluded
assert not should_exclude(Path(".gitconfig"))
assert not should_exclude(Path(".gitignore"))
assert not should_exclude(Path(".github/workflows/ci.yml"))
```
