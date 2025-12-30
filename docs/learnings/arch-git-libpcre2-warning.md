# Arch Linux: Git libpcre2 Warning Spam

## Context

When running git commands on fresh Arch Linux installations, you may see this warning repeatedly:

```yaml
git: /usr/lib/libpcre2-8.so.0: no version information available (required by git)
```

## The Problem

- Warning appears on **every git command** (1300+ times in typical installation logs)
- Clutters logs and makes debugging harder
- Purely cosmetic - **git functions correctly**
- Caused by version symbol mismatch between git and libpcre2

## Root Cause

This is a known Arch Linux packaging issue where:

1. Git is compiled against libpcre2
2. The libpcre2 library doesn't export version symbols that git expects
3. Git prints warning but continues to work normally

## Impact

- **Functionality**: None - git works perfectly
- **User Experience**: Log spam, visual noise
- **Performance**: Negligible

## Solution

### Proper Fix: Reinstall pcre2 and Rebuild Library Cache

The proper solution is to ensure pcre2 is correctly installed and rebuild the library cache:

```bash
# Reinstall pcre2 to ensure version symbols
sudo pacman -S --noconfirm pcre2

# Rebuild library cache (standard Linux solution)
sudo ldconfig
```

This is implemented automatically in the Arch installation scripts under `management/arch/`.

### Why This Works

- `ldconfig` is the standard Linux utility for fixing library linking issues
- It updates the runtime linker bindings and caches
- Ensures git can find correct version information in libpcre2
- Not a hack - this is the proper system-level solution

### Already Fixed

If you're using the dotfiles installation process, this fix is automatically applied during package installation.

## Related Issues

- This does NOT cause the Neovim "local changes" warnings
- Git operations complete successfully despite the warning
- The warning appears in Docker containers and bare metal Arch installations

## Testing

Verify git works correctly despite warnings:

```bash
git --version          # Works
git status            # Works (with warning)
git log               # Works (with warning)
```

All commands function normally.

## Last Updated

2025-11-25
