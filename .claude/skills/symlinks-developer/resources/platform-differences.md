# Platform Differences

## macOS vs Linux Symlinks

### Case Sensitivity

**macOS**: Case-insensitive by default (APFS)

- `.gitconfig` and `.Gitconfig` are the same file
- Test on case-sensitive APFS if possible

**Linux**: Case-sensitive (ext4)

- `.gitconfig` and `.Gitconfig` are different files
- More strict file system behavior

### Binary Names

**macOS Intel**:

- GNU tools prefixed: `gls`, `gsed`, `gtar`
- BSD tools default: `ls`, `sed`, `tar`

**Linux**:

- GNU tools default: `ls`, `sed`, `tar`

**WSL Ubuntu**:

- GNU tools like native Linux
- Windows filesystem interop considerations

### Path Separators

Both use `/` for paths, but WSL has special cases:

- `/mnt/c/` for Windows C: drive access
- Windows paths converted at boundary

## Testing Across Platforms

### Recommended Approach

1. **Primary Development**: macOS Intel
2. **CI Testing**: Ubuntu Linux via GitHub Actions
3. **Manual Testing**: WSL for Windows-specific edge cases

### Platform-Specific Test Skips

Use `@pytest.mark.skipif` for platform-specific tests:

```python
import sys
import pytest

@pytest.mark.skipif(sys.platform == "darwin", reason="Linux-only test")
def test_linux_specific():
    pass
```

## Common Cross-Platform Pitfalls

1. **Line Endings**: Git should normalize (`.gitattributes`)
2. **Executable Permissions**: May differ between platforms
3. **Symlink Behavior**: Windows requires admin or dev mode
4. **Hidden Files**: Both use `.` prefix convention
