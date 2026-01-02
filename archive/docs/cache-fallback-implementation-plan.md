# Cache Fallback Implementation Plan

> **STATUS: ✅ COMPLETE** (2024-12-30)
>
> All cache fallback implementations are done. User confirmed Go, nvm, and fonts are blocked on corporate network.
>
> **Archived to:** `.planning/archive/`

**Created**: 2025-12-08
**Completed**: 2024-12-30
**Status**: ✅ ALL COMPLETE
**Goal**: Add cache fallback support for installers blocked by corporate firewalls

## ✅ Implementation Summary

### Phase 1 (Completed 2025-12-08): cargo-binstall

**What was implemented**:

1. ✅ Created `cache-manager.sh` - shared cache lookup library
2. ✅ Refactored `github-release-installer.sh` to source `cache-manager.sh` and `version-helpers.sh`
3. ✅ Eliminated duplicate `get_latest_version()` function (now wrapper for `fetch_github_latest_version()`)
4. ✅ Added idempotency check to `cargo-tools.sh`:
   - Checks if binary already installed before running cargo-binstall
   - Prevents spurious errors on already-installed tools
   - Works offline/on blocked networks
   - Updated `parse_packages.py` to support `--format=name_command` for cargo packages
5. ✅ Comprehensive tests: 20 passing (github-release-installer.bats)

### Phase 2 (Completed 2024-12-30): Go, nvm, fonts

User confirmed all three are blocked on corporate network. Implemented cache fallback for all:

**Go installer** (`management/common/install/language-managers/go.sh`):

- Sources `cache-manager.sh`
- Checks `~/.cache/dotfiles/` for `go*{version}*{OS}-{ARCH}*.tar.gz`
- Uses cached file if found, otherwise downloads
- Clear manual instructions on failure with cache path

**nvm installer** (`management/common/install/language-managers/nvm.sh`):

- Downloads install script to cache first (`~/.cache/dotfiles/nvm-v0.40.0-install.sh`)
- Executes from cache (not piped from curl)
- Cached script persists for future installs
- Clear manual instructions on failure with cache path

**Font installer library** (`management/common/lib/font-installer.sh`):

- `download_nerd_font()` checks `~/.cache/dotfiles/{Package}.tar.xz` first
- Uses cached archive if found, otherwise downloads
- Clear manual instructions on failure with cache path
- Benefits ALL Nerd Font installers (Iosevka, JetBrains, etc.)

**User workflow example**:

```bash
# On corporate network - Go blocked
$ bash management/common/install/language-managers/go.sh
[ERROR] Download failed
# Manual steps shown with exact URL and cache path

# User downloads in browser, moves to cache
$ mv ~/Downloads/go1.23.4.darwin-arm64.tar.gz ~/.cache/dotfiles/

# Re-run installer
$ bash management/common/install/language-managers/go.sh
[INFO] Found cached file: ~/.cache/dotfiles/go1.23.4.darwin-arm64.tar.gz
[SUCCESS] go version go1.23.4 darwin/arm64 installed
```

**Decisions**:

- ❌ **cargo-binstall cache fallback removed** - unnecessary complexity
  - cargo-binstall already falls back to building from source (good enough)
  - Idempotency check solves the real problem (spurious errors)
- ✅ **GitHub releases cache** - kept (already implemented and working)
- ✅ **Go installer** - cache fallback added
- ✅ **nvm installer** - cache fallback added (script cached, not piped)
- ✅ **Font installers** - cache fallback added to library (all Nerd Fonts benefit)

---

## Problem Statement

Corporate networks block downloads from:

- GitHub releases (github.com/*/releases/download/) ✅ **SOLVED**
- cargo-binstall binaries (fetches from GitHub)
- Language runtime downloads (go.dev, raw.githubusercontent.com)
- Font downloads (various sources)

Users need a way to manually download files and have installers discover them.

## Architecture Decision: Minimal Abstraction

**Principle**: Don't over-engineer. Each installer type has different needs.

**Approach**:

1. Reuse existing `check_local_cache_for_version()` where applicable
2. Add minimal, focused helpers only when duplication appears 3+ times
3. Each installer implements its own fallback logic
4. No generic "download manager" abstraction

**Why**:

- Different download types: tarballs, scripts, binaries, fonts
- Different sources: GitHub, go.dev, npm, custom sites
- Different extraction: tar, unzip, direct copy, pipe to bash
- Premature abstraction = maintenance burden

## Cache Convention

**Location**: `~/.cache/dotfiles/` (flat, XDG-compliant)
**Naming**: Fuzzy match on `{tool}*{version}*.{ext}`
**User workflow**: Download → `mv ~/Downloads/* ~/.cache/dotfiles/` → re-run installer

## Priority 1: cargo-binstall (IMPLEMENT NOW)

### Challenge

`cargo binstall` does the downloading internally - we can't intercept it.

When blocked:

```bash
$ cargo binstall bat
Error: Failed to download from GitHub
```

We need to install manually from cached GitHub release tarballs.

### Solution Architecture

**Flow**:

1. Try `cargo binstall <package>` (fast path)
2. On failure:
   - Map package → GitHub repo (bat → sharkdp/bat)
   - Fetch latest version from GitHub API
   - Check cache using existing `check_local_cache_for_version()`
   - If found: Extract tarball, install binary to `~/.cargo/bin/`
   - If not found: Show cache instructions

**Key insight**: cargo-binstall downloads GitHub releases, same files we already cache!

### Implementation Details

**File**: `management/common/install/language-tools/cargo-tools.sh`

**New function**:

```bash
install_from_cache_fallback() {
  local package="$1"
  local github_repo="$2"  # e.g., "sharkdp/bat"

  # Get latest version
  local version=$(get_latest_version "$github_repo")

  # Check cache (reuse existing function)
  local cached=$(check_local_cache_for_version "$package" "$version" "tar.gz")

  if [[ -n "$cached" ]]; then
    log_info "Found cached release, installing manually..."
    # Extract and install to ~/.cargo/bin/
    tar -xzf "$cached" -C /tmp
    mv /tmp/*/$package ~/.cargo/bin/
    chmod +x ~/.cargo/bin/$package
    return 0
  fi

  return 1
}
```

**Package → Repo mapping**:

```bash
declare -A CARGO_GITHUB_REPOS=(
  ["bat"]="sharkdp/bat"
  ["fd-find"]="sharkdp/fd"
  ["eza"]="eza-community/eza"
  ["zoxide"]="ajeetdsouza/zoxide"
  ["git-delta"]="dandavison/delta"
  ["tinty"]="tinted-theming/tinty"
)
```

**Modified install loop**:

```bash
while read -r package; do
  if cargo binstall -y "$package"; then
    log_success "$package installed"
  elif install_from_cache_fallback "$package" "${CARGO_GITHUB_REPOS[$package]}"; then
    log_success "$package installed from cache"
  else
    # Existing failure handling + cache instructions
  fi
done
```

### Edge Cases

**Binary name ≠ package name**:

- `fd-find` installs binary named `fd`
- Solution: Add binary name mapping if needed

**Tarball structure variations**:

- Some: `bat-v0.24.0/bat` (nested)
- Some: `bat` (root)
- Solution: Try both patterns with glob

**Multiple binaries**:

- Example: yazi ships with yazi + ya
- Solution: Install main binary only (matches cargo binstall behavior)

### Testing

**Unit test**: `tests/libraries/cargo-cache-fallback.bats`

```bash
@test "install_from_cache_fallback finds and installs cached release"
@test "install_from_cache_fallback handles nested tarball structure"
@test "install_from_cache_fallback returns 1 when no cache found"
```

**Integration test**: Mock cargo binstall failure, verify cache fallback

### User Workflow

```bash
# Corporate network blocks cargo binstall
$ bash management/common/install/language-tools/cargo-tools.sh
[ERROR] cargo binstall bat failed
[INFO] Checking cache for fallback...
[ERROR] Not found in cache

To install manually:
  1. Download: https://github.com/sharkdp/bat/releases/download/v0.24.0/bat-v0.24.0-x86_64-unknown-linux-gnu.tar.gz
  2. Move to: ~/.cache/dotfiles/
  3. Re-run installer

# User downloads in browser
$ mv ~/Downloads/bat-v0.24.0-x86_64-unknown-linux-gnu.tar.gz ~/.cache/dotfiles/

# Re-run installer
$ bash management/common/install/language-tools/cargo-tools.sh
[INFO] cargo binstall bat failed, checking cache...
[INFO] Found cached release: ~/.cache/dotfiles/bat-v0.24.0-x86_64-unknown-linux-gnu.tar.gz
[INFO] Installing manually...
[SUCCESS] bat installed from cache
```

## Priority 2: Go Installer (LATER)

### Current Behavior

Downloads tarball from go.dev:

```bash
GO_VERSION=$(curl https://go.dev/VERSION?m=text)
curl -fsSL "https://go.dev/dl/${GO_VERSION}.${OS}-${ARCH}.tar.gz" -o /tmp/go.tar.gz
```

### Solution

**Flow**:

1. Fetch version from go.dev API
2. Check cache for `go*{version}*{OS}-{ARCH}*.tar.gz`
3. If found: use cached tarball
4. If not found: try download
5. Extract and install

**Implementation**: ~20 lines added to `go.sh`

**Reuse**: Can use same `check_local_cache_for_version()` pattern

### Edge Cases

**Arch naming**: go1.21.5.linux-amd64.tar.gz vs darwin-arm64
**Cache matching**: Must match OS and arch in pattern

## Priority 3: nvm Installer (LATER)

### Current Behavior

Pipes install script directly to bash:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
```

**Problem**: Can't cache something piped to bash

### Solution

**Flow**:

1. Download script to cache first (not pipe)
2. Execute from cache
3. Cache persists for future installs

**Implementation**:

```bash
# Check cache
CACHED_SCRIPT=$(check_cache_for_pattern "nvm*install.sh")

if [[ -z "$CACHED_SCRIPT" ]]; then
  # Download to cache
  curl -fsSL "$NVM_INSTALL_SCRIPT" -o "$HOME/.cache/dotfiles/nvm-v0.40.0-install.sh"
  CACHED_SCRIPT="$HOME/.cache/dotfiles/nvm-v0.40.0-install.sh"
fi

# Execute from cache
NVM_DIR="$NVM_DIR" bash "$CACHED_SCRIPT"
```

**Benefit**: Script stays cached, future installs don't download

### Edge Cases

**Execute permissions**: Ensure cached script is executable
**Version in filename**: Include version for multiple nvm versions

## Priority 4: Font Installers (OPTIONAL)

### Analysis

**Fonts**: 10+ different installers, multiple sources

**Sources**:

- GitHub releases: FiraCode, CommitMono, Iosevka, IntelOne, Victor
- raw.githubusercontent.com: FiraCodeiScript
- Custom sites: Comic Mono (dtinth.github.io)
- Nerd Fonts: Special case (many fonts)

### Recommendation

**Only cache the most important** (2-3 fonts):

1. **FiraCode** - Most used in dotfiles
2. **Nerd Fonts** - Most used, largest downloads
3. Skip: Specialty fonts (Victor, Comic Mono, SGr variants)

**Reason**: Font installation is less critical than dev tools

### Implementation

Similar to GitHub releases pattern, each font installer adds cache check.

**Effort**: ~10 lines per font × 2 fonts = 20 lines

## Common Helpers: Decision Tree

**Question**: Should we create shared helper functions?

**Answer**: Only if we see duplication in 3+ places

**Current status**:

- GitHub releases: Has library ✅
- cargo-binstall: Uses GitHub library ✅
- Go: Simple inline cache check (~10 lines)
- nvm: Different pattern (script vs tarball)

**Decision**: No shared helpers needed yet. Re-evaluate after implementing Go/nvm.

**If we do create helpers**, put in: `management/common/lib/cache-helpers.sh`

Functions:

```bash
check_cache_for_pattern <pattern>  # Generic find in cache
show_cache_instructions <tool> <url> <version>  # Consistent messaging
```

## Implementation Order

1. ✅ **GitHub releases** - DONE (github-release-installer.sh)
2. 🎯 **cargo-binstall** - DO NOW (highest priority, known blocked)
3. ⏸️  **Go installer** - LATER (wait for user confirmation it's blocked)
4. ⏸️  **nvm installer** - LATER (wait for user confirmation)
5. ⏸️  **Fonts** - MAYBE (nice-to-have)

## Testing Strategy

**Unit tests**: Cache lookup functions
**Integration tests**: End-to-end with cached files
**Manual tests**: Each installer with real cached downloads

**Don't test**: Every edge case, focus on happy path + cache hit/miss

## Success Metrics

1. Reduced install failures on corporate networks
2. Clear error messages with exact download instructions
3. Minimal code added (<100 lines total for all implementations)
4. No code duplication (reuse GitHub library)
5. All existing tests pass

## Code Complexity Budget

**Maximum new code**:

- cargo-binstall: ~50 lines (mapping + fallback function)
- Go installer: ~20 lines (cache check)
- nvm installer: ~15 lines (download to cache first)
- Font installers: ~10 lines each × 2 = 20 lines
- **Total**: ~105 lines

**If exceeding budget**: Re-evaluate, consider shared helpers

## Open Questions

1. **cargo-binstall arch detection**: How to match tarball arch to system arch?
   - Solution: Reuse `get_platform_arch()` from github-release-installer.sh

2. **Binary name mapping**: fd-find → fd, git-delta → delta
   - Solution: Add optional third parameter to mapping

3. **Error messages**: Should we output JSON for failure logging?
   - Solution: Yes, use existing `output_failure_data()` for consistency

4. **Cache cleanup**: Should we auto-clean old versions?
   - Solution: No, user responsibility. Cache is explicitly opt-in.

## Next Steps

1. Review this plan
2. Implement cargo-binstall cache fallback
3. Test on blocked network (WSL at work)
4. Decide on Go/nvm based on real-world blocking data
5. Archive plan when complete
