# Relative Path Calculation: Use stdlib, Don't Reinvent

**Date**: 2025-11-04
**Context**: Symlinks Python rewrite broke 122 symlinks with manual path calculation

## The Problem

Manual path calculation using flawed "common ancestor" logic broke all symlinks:

```python
# BROKEN: Attempted manual calculation
common = Path(*[p for p in target_parent.parts if p in source.parts])
levels_up = len([p for p in target_parent.parts if p not in common.parts])
```

Created invalid paths like `dotfiles/common/init.lua` instead of `../../dotfiles/common/.config/nvim/init.lua`.

## The Solution

Use Python stdlib - it handles all edge cases:

```python
def make_relative_symlink(source: Path, target: Path) -> Path:
    """Calculate relative path from target to source."""
    return source.relative_to(target.parent, walk_up=True)  # Python 3.12+
```

Or for older Python:

```python
import os
return Path(os.path.relpath(str(source), str(target.parent)))
```

## Key Learnings

- **Don't reinvent complex algorithms** - stdlib has solved these problems correctly
- **Test with real symlinks** - integration tests catch path bugs that unit tests miss
- **The old code worked for a reason** - don't assume your clever rewrite is better

## Testing

Always test symlinks actually work:

```python
def test_symlink_actually_works(tmp_path):
    source = tmp_path / "dotfiles/common/.config/nvim/init.lua"
    source.parent.mkdir(parents=True)
    source.write_text("-- test")

    target = tmp_path / "home/.config/nvim/init.lua"
    target.parent.mkdir(parents=True)

    relative = make_relative_symlink(source, target)
    target.symlink_to(relative)

    assert target.read_text() == "-- test"  # Symlink works!
```
