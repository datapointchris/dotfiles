# GitHub Release Installer Library

## Overview

The GitHub Release Installer library provides focused helper functions for installing binary tools from GitHub releases. It eliminates code duplication across 16+ similar installer scripts while maintaining clarity and simplicity.

## Design Philosophy

The library follows the "medium abstraction" principle:

- **Focused helpers** - Only abstract truly repetitive patterns
- **Inline complexity** - Single-use operations stay inline in functions
- **Explicit configuration** - Each script contains its own configuration inline
- **No YAML complexity** - Avoid complex packages.yml parsing for variations
- **Straightforward** - Easy to trace and understand what's happening

## Architecture

### Library Chain

```text
installer-script.sh
  └─> error-handling.sh (set -euo pipefail, traps, cleanup)
       └─> logging.sh (status messages with [LEVEL] prefixes)
            └─> colors.sh
```

Each installer script sources `error-handling.sh`, which automatically provides:

- Error safety with `set -euo pipefail`
- Trap handlers for cleanup
- Structured logging (auto-detects terminal vs pipe)
- Consistent error messages with file:line references

### Library Functions

Located in `management/common/lib/github-release-installer.sh`:

#### 1. `get_platform_arch()`

Handles platform/architecture detection with customizable capitalization.

**Usage:**

```bash
PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")
```

**Why it exists:** Different GitHub projects use different naming conventions:

- `lazygit`: `Darwin_x86_64`
- `duf`: `darwin_x86_64` (lowercase)
- `zk`: `macos-x86_64` (different platform name)

#### 2. `get_latest_version()`

Fetches the latest release version from GitHub API.

**Usage:**

```bash
VERSION=$(get_latest_version "owner/repo")
# Returns: v1.2.3
```

**Why it exists:** Every installer needs to fetch versions, same pattern every time.

#### 3. `should_skip_install()`

Checks if installation should be skipped (already installed, unless FORCE_INSTALL=true).

**Usage:**

```bash
if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi
```

**Why it exists:** Idempotency check used by every installer.

#### 4. `install_from_tarball()`

Complete installation pattern for tar.gz archives.

**What it does:**

1. Downloads tarball to /tmp
2. Registers cleanup trap
3. Extracts archive
4. Moves binary to ~/.local/bin
5. Sets executable permissions
6. Verifies installation

**Usage:**

```bash
install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "path/in/tarball"
```

**Why it's one function:** Download, extract, install, verify are always done together. Splitting them into separate functions creates unnecessary indirection.

#### 5. `install_from_zip()`

Same as `install_from_tarball()` but for zip files.

**Usage:**

```bash
install_from_zip "$BINARY_NAME" "$DOWNLOAD_URL" "path/in/zip"
```

## Script Patterns

### Simple Tarball Installer

Most common pattern (11 out of 16 tools):

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

BINARY_NAME="lazygit"
REPO="jesseduffield/lazygit"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing LazyGit"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/lazygit_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "lazygit"

print_banner_success "LazyGit installation complete"
exit_success
```

**Lines:** ~40-50 (was 90-120)

### Custom Installer (Special Cases)

Some tools need custom handling:

- **yazi**: Installs multiple binaries (yazi + ya), adds plugins
- **tenv**: Installs 7 binaries (tenv + proxy binaries)
- **terraformer**: Downloads raw binary (no archive)
- **zk**: Complex platform detection (macos vs linux, different arch naming)

These scripts use library helpers where applicable but handle their unique requirements inline.

## Code Savings

### Converted Scripts (11 tools)

| Tool | Before | After | Savings |
|------|--------|-------|---------|
| lazygit | 95 | 50 | -45 |
| yazi | 119 | 104 | -15 |
| duf | 89 | 40 | -49 |
| glow | 89 | 41 | -48 |
| tenv | 98 | 73 | -25 |
| terraform-ls | 91 | 37 | -54 |
| terrascan | 91 | 37 | -54 |
| tflint | 91 | 37 | -54 |
| trivy | 94 | 37 | -57 |
| zk | 97 | 40 | -57 |
| terraformer | 85 | 51 | -34 |
| **Total** | **1,039** | **547** | **-492 (47%)** |

### Library

- **Size:** 181 lines
- **Functions:** 5
- **Previous iteration:** 401 lines, 16 functions (over-abstracted)

### Grand Total

- **Before:** ~1,525 lines (estimated)
- **After:** 1,211 lines (181 library + 547 converted + 483 special cases)
- **Net savings:** 314 lines (20.6%)

## Special Case Scripts (Not Converted)

These 5 scripts have unique requirements that don't fit the standard pattern:

1. **awscli** - Uses official AWS installer, macOS via Homebrew
2. **claude-code** - Uses official installer, WSL skipped
3. **fzf** - Built from source with Go
4. **neovim** - AppImage extraction, multiple files
5. **terraform** - Wrapper around tenv, delegates installation

All still use error-handling.sh for structured logging consistency.

## Design Decisions

### Why Not More Abstraction?

**Rejected:** Complex packages.yml with all download patterns

```yaml
# TOO COMPLEX - requires YAML parser, hard to trace
github_binaries:
  - name: lazygit
    archive_format: tar.gz
    url_pattern: "{repo}/releases/download/{version}/lazygit_{version}_{platform}_{arch}.tar.gz"
    binary_pattern: "lazygit"
```

**Chosen:** Inline configuration in each script

```bash
# SIMPLE - easy to trace, self-contained
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/lazygit_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"
```

**Rationale:** URL patterns vary enough that YAML templates become complex. Inline keeps it explicit and traceable.

### Why Not Version Checking?

**Rejected:** Minimum version requirements, complex version comparison

**Chosen:** Always install latest from GitHub API

**Rationale:**

- Simpler code
- Latest is usually what you want
- Can pin specific version by editing script if needed
- Reduces maintenance burden

### Why Inline Download/Extract/Install?

**Rejected:** Separate `download_release()`, `extract_tarball()`, `install_binary()` functions

**Chosen:** Single `install_from_tarball()` function with inline operations

**Rationale:**

- These operations are ALWAYS done together
- Separate functions create unnecessary indirection
- Harder to trace: installer → install_from_tarball → download_release → download_with_retry
- Inline is more straightforward

## Integration with Error Handling

The library assumes `error-handling.sh` has been sourced by the calling script. This provides:

### Automatic Cleanup

```bash
# In install_from_tarball()
register_cleanup "rm -f '$temp_tarball' 2>/dev/null || true"
```

Cleanup happens automatically on exit (success or failure).

### Error Context

```bash
log_fatal "Failed to download from $download_url" "${BASH_SOURCE[0]}" "$LINENO"
```

Errors include file:line references for debugging.

### Structured Logging

Auto-detects terminal vs pipe:

**Terminal mode:**

```text
  ● Downloading lazygit...
  ✓ lazygit installed successfully
```

**Structured mode (pipe/log):**

```text
[INFO] Downloading lazygit...
[INFO] ✓ lazygit installed successfully
```

## Adding a New Tool

### Steps

1. Create new script in `management/common/install/github-releases/`
2. Use template pattern (see Simple Tarball Installer above)
3. Configure: BINARY_NAME, REPO, download URL pattern
4. Handle special cases inline if needed
5. Test on all platforms

### Time Required

- **Before library:** 30-60 minutes (80-120 lines of boilerplate)
- **After library:** 5-10 minutes (40-50 lines, mostly copy-paste)

**6x faster**

## Testing

Run individual installer:

```bash
bash management/common/install/github-releases/lazygit.sh
```

Force reinstall:

```bash
FORCE_INSTALL=true bash management/common/install/github-releases/lazygit.sh
```

Test structured logging:

```bash
# Visual mode (terminal)
bash management/common/install/github-releases/lazygit.sh

# Structured mode (pipe)
bash management/common/install/github-releases/lazygit.sh 2>&1 | cat
```

## Future Improvements

### Possible (Low Priority)

- Optional checksum verification (verify if present, but not required)
- Lightweight install log for audit trail (append-only)
- Helper for multi-binary installation pattern

### Not Recommended

- ❌ Complex packages.yml parsing - contradicts straightforward principle
- ❌ Automatic version checking/upgrades - adds complexity
- ❌ Rollback capability - idempotency is sufficient
- ❌ More abstraction layers - keep it simple

## Related Documentation

- [Error Handling](error-handling.md)
- [Shell Libraries](shell-libraries.md)
- Production-Grade Management Enhancements (planning doc)

## Files

**Library:**

- `management/common/lib/github-release-installer.sh` (181 lines)

**Converted Scripts:**

- `management/common/install/github-releases/lazygit.sh`
- `management/common/install/github-releases/yazi.sh`
- `management/common/install/github-releases/duf.sh`
- `management/common/install/github-releases/glow.sh`
- `management/common/install/github-releases/fzf.sh` (converted from build-from-source)
- `management/common/install/github-releases/neovim.sh` (extracts directory + symlinks binary)
- `management/common/install/github-releases/terrascan.sh`
- `management/common/install/github-releases/tflint.sh`
- `management/common/install/github-releases/trivy.sh`
- `management/common/install/github-releases/zk.sh`
- `management/common/install/github-releases/terraformer.sh`

**Moved to Custom Installers:**

- `management/common/install/custom-installers/awscli.sh` - Uses AWS custom installer
- `management/common/install/custom-installers/claude-code.sh` - Uses official installer script
- `management/common/install/custom-installers/terraform-ls.sh` - Uses releases.hashicorp.com (not GitHub)

**Moved to Language Managers:**

- `management/common/install/language-managers/tenv.sh` - Merged with terraform.sh to match nvm/uv pattern
