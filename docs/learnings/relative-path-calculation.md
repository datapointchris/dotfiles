# Relative Path Calculation: Use stdlib, Don't Reinvent

**Date**: 2025-11-04
**Context**: Symlinks Python rewrite

## The Problem

When rewriting the bash `symlinks.sh` to Python, I attempted to manually calculate relative paths for symlinks. The implementation used flawed logic to find common ancestors and count directory levels, resulting in 122 broken symlinks across the entire dotfiles setup.

**Broken code** (lines 51-71 in `utils.py`):

```python
# Attempted to find "common ancestor" by checking if parts existed in both paths
common = Path(*[p for p in target_parent.parts if p in source.parts])

# Failed to properly count levels and build ../ sequences
levels_up = len([p for p in target_parent.parts if p not in common.parts])
relative_path = Path("/".join([".."] * levels_up))
```

This created invalid paths like `dotfiles/common/init.lua` instead of `../../dotfiles/common/.config/nvim/init.lua`.

## The Solution

Python's standard library has `os.path.relpath()` which handles all edge cases correctly:

```python
def make_relative_symlink(source: Path, target: Path) -> Path:
    """Calculate relative path from target to source for symlink creation."""
    import os
    target_parent = target.parent
    relative_path = os.path.relpath(str(source), str(target_parent))
    return Path(relative_path)
```

Even better with pathlib (Python 3.12+):

```python
def make_relative_symlink(source: Path, target: Path) -> Path:
    """Calculate relative path from target to source for symlink creation."""
    return source.relative_to(target.parent)  # Raises ValueError if not relative
```

For paths that aren't naturally relative, use `os.path.relpath()` which works in all cases.

## Key Learnings

**Use stdlib when available**: Complex algorithms like relative path calculation have corner cases. The standard library has already solved these problems correctly.

**Test before deploying**: Should have run comprehensive integration tests that create actual symlinks and verify they work, not just unit tests of the algorithm.

**The old code worked for a reason**: The bash script used Python's `os.path.normpath()` and relied on system tools. There was wisdom in that approach.

**Trust but verify**: When rewriting working code, don't assume your clever implementation is correct without thorough testing.

## Example

Calculate relative path from target to source:

```python
# Source: /Users/chris/dotfiles/common/.config/nvim/init.lua
# Target: /Users/chris/.config/nvim/init.lua
# Target parent: /Users/chris/.config/nvim/

result = os.path.relpath(source, target.parent)
# Result: "../../dotfiles/common/.config/nvim/init.lua"

# From /Users/chris/.config/nvim/, go up 2 levels (../..)
# Then down to dotfiles/common/.config/nvim/init.lua
```

## Testing Strategy

Integration test that creates real symlinks:

```python
def test_symlink_actually_works(tmp_path):
    # Create source file
    source = tmp_path / "dotfiles/common/.config/nvim/init.lua"
    source.parent.mkdir(parents=True)
    source.write_text("-- test")

    # Create target
    target = tmp_path / "home/.config/nvim/init.lua"
    target.parent.mkdir(parents=True)

    # Calculate and create symlink
    relative = make_relative_symlink(source, target)
    target.symlink_to(relative)

    # Verify it works
    assert target.exists()
    assert target.read_text() == "-- test"
```

This test would have caught the bug immediately.

## Related

- Python docs: [`os.path.relpath()`](https://docs.python.org/3/library/os.path.html#os.path.relpath)
- Python 3.12+: [`Path.relative_to(walk_up=True)`](https://docs.python.org/3/library/pathlib.html#pathlib.Path.relative_to)
