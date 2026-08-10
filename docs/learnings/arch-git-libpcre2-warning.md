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

### It resolves upstream, and the workaround below never fixed it

The warning is a version-symbol mismatch between the `git` binary and the
`libpcre2-8` it was linked against, so only a rebuild of one of them clears it —
which happens on its own the next time either package is rebuilt in the repos.

The Arch installer used to run `pacman -S pcre2` and `sudo ldconfig` after every
package install, both `2>/dev/null || true`, and neither could have worked.
Reinstalling gives back the identical package, and `ldconfig` rebuilds
`/etc/ld.so.cache`, which has nothing to say about symbol versions. They were
added while debugging this, the warning stopped for an unrelated reason, and the
commands stayed. They did not survive the conversion of the package installers to
providers.

Run them by hand if a machine is showing the warning today — they cost nothing
and rule out an actually-broken cache — but expect the pair below to be the fix.

### The commands, for a machine showing this now

The proper solution is to ensure pcre2 is correctly installed and rebuild the library cache:

```bash
# Reinstall pcre2 to ensure version symbols
sudo pacman -S --noconfirm pcre2

# Rebuild library cache (standard Linux solution)
sudo ldconfig
```

### What `ldconfig` does and does not do

- It updates the runtime linker bindings and rebuilds `/etc/ld.so.cache`
- That fixes a library the linker cannot *find*
- It does not change which version symbols a compiled binary asks for, which is
  what this warning is about

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

2026-08-09
