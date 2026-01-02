# Smart Installer Updates - Implementation Plan

**Date**: 2025-12-07
**Goal**: Make installers check versions and only install when updates are available
**Scope**: 4 custom installers + 11 GitHub release installers + language managers + Go apps

---

## Current State Analysis

### Installer Categories

1. **GitHub Release Installers** (11 tools)
   - neovim, lazygit, yazi, glow, duf, fzf, tflint, terraformer, terrascan, trivy, zk
   - Pattern: Fetch latest from GitHub API → Download → Install
   - Version source: GitHub API `/releases/latest`

2. **Custom Installers - Git-Based** (1 tool)
   - bats
   - Pattern: Clone specific tag → Run install.sh
   - Version source: GitHub API `/releases/latest` or `/tags`

3. **Custom Installers - Script-Based** (3 tools)
   - awscli, claude-code, terraform-ls
   - Pattern: Download/run external installer script
   - Version source: Varies by tool

4. **Language Managers** (4 tools)
   - go, rust, nvm, uv
   - Pattern: Download toolchain → Install
   - Version source: Official websites/APIs

5. **Custom Go Apps** (2 tools)
   - sess, toolbox
   - Pattern: Build from local source
   - Version source: Git commit hash of dotfiles

---

## Design Decisions

### Decision 1: How to Trigger Version Checking?

**Option A: Make FORCE_INSTALL smarter**

```bash
# FORCE_INSTALL=true means "check version and install if update available"
# Without FORCE_INSTALL means "skip if already installed" (current behavior)
FORCE_INSTALL=true bash installer.sh
```

**Option B: Add --update flag**

```bash
bash installer.sh --update  # Check version, install if needed
bash installer.sh           # Normal install (skip if exists)
```

**Decision: Option A** - FORCE_INSTALL becomes "force version check"

- Simpler: no new flags to add
- Already supported by all installers
- Semantic: "force install" = "install even if present" = "check and update"

---

### Decision 2: Version Comparison Strategy

**Semantic Version Comparison:**

```bash
version_compare() {
  local current="$1"
  local latest="$2"

  # Normalize versions (remove 'v' prefix)
  current="${current#v}"
  latest="${latest#v}"

  # Use sort -V for semantic version comparison
  if [[ "$current" == "$latest" ]]; then
    return 0  # Same version
  elif [[ $(printf '%s\n' "$current" "$latest" | sort -V | head -n1) == "$current" ]]; then
    return 1  # Current is older (update available)
  else
    return 2  # Current is newer (shouldn't happen)
  fi
}
```

**Usage:**

```bash
if version_compare "$CURRENT_VERSION" "$LATEST_VERSION"; then
  log_success "Already at latest version: $LATEST_VERSION"
  exit 0
fi

log_info "Update available: $CURRENT_VERSION → $LATEST_VERSION"
# Proceed with installation
```

---

### Decision 3: Error Handling for Version Checks

**Principle: Fail safe - install if version check fails**

```bash
# Fetch latest version
LATEST_VERSION=$(curl -fsSL "$API_URL" | grep '"tag_name"' | sed 's/.*"v\?\([^"]*\)".*/\1/' 2>/dev/null)

if [[ -z "$LATEST_VERSION" ]]; then
  log_warning "Could not fetch latest version from GitHub API"

  if [[ "${FORCE_INSTALL:-false}" == "true" ]]; then
    log_info "FORCE_INSTALL=true, proceeding with installation anyway"
    # Continue with install
  else
    # Existing behavior: fail with manual steps
    output_failure_data "..."
    exit 1
  fi
fi

# Check current version
if command -v tool >/dev/null 2>&1; then
  CURRENT_VERSION=$(tool --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)

  if [[ -n "$CURRENT_VERSION" ]] && [[ -n "$LATEST_VERSION" ]]; then
    if version_compare "$CURRENT_VERSION" "$LATEST_VERSION"; then
      log_success "Already at latest version: $LATEST_VERSION"
      exit 0
    fi

    log_info "Update available: $CURRENT_VERSION → $LATEST_VERSION"
  fi
fi

# If we get here, proceed with installation
```

---

## Implementation Plan by Installer Type

### Type 1: GitHub Release Installers (11 tools)

**Pattern:** All follow similar structure using GitHub API

**Files to modify:**

- `management/common/install/github-releases/neovim.sh`
- `management/common/install/github-releases/lazygit.sh`
- `management/common/install/github-releases/yazi.sh`
- `management/common/install/github-releases/glow.sh`
- `management/common/install/github-releases/duf.sh`
- `management/common/install/github-releases/fzf.sh`
- `management/common/install/github-releases/tflint.sh`
- `management/common/install/github-releases/terraformer.sh`
- `management/common/install/github-releases/terrascan.sh`
- `management/common/install/github-releases/trivy.sh`
- `management/common/install/github-releases/zk.sh`

**Current flow:**

```bash
# Skip if installed (unless FORCE_INSTALL)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v tool; then
  exit 0
fi

# Fetch latest version
LATEST_VERSION=$(curl GitHub API)

# Download and install
curl download → extract → install
```

**New flow:**

```bash
# Always fetch latest version (needed for version comparison)
LATEST_VERSION=$(curl GitHub API)
if [[ -z "$LATEST_VERSION" ]]; then
  # API failed - handle gracefully
fi

# Check current version
if command -v tool >/dev/null 2>&1; then
  CURRENT_VERSION=$(tool --version | parse)

  # Version comparison
  if [[ -n "$CURRENT_VERSION" ]] && version_compare "$CURRENT_VERSION" "$LATEST_VERSION"; then
    log_success "Already at latest version: $LATEST_VERSION"
    exit 0
  fi

  if [[ -n "$CURRENT_VERSION" ]]; then
    log_info "Update available: $CURRENT_VERSION → $LATEST_VERSION"
  fi
fi

# Proceed with download and install
```

**Changes needed:**

1. Move version fetching to top (before idempotency check)
2. Add version comparison logic
3. Add version_compare helper function (could be in a library)
4. Update each tool's version parsing (each has different --version format)

**Tool-specific version commands:**

```bash
neovim:    nvim --version | head -1 | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+'
lazygit:   lazygit --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
yazi:      yazi --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
fzf:       fzf --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
glow:      glow --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
duf:       duf --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
tflint:    tflint --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
terraformer: terraformer version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
terrascan: terrascan version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
trivy:     trivy --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
zk:        zk --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
```

---

### Type 2: Custom Installer - BATS (Git-Based)

**File:** `management/common/install/custom-installers/bats.sh`

**Current flow:**

```bash
# Skip if installed at target location
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v bats; then
  if [[ "$CURRENT_PATH" == "$INSTALL_PREFIX/bin/bats" ]]; then
    exit 0
  fi
fi

# Clone with tag
git clone --branch "$BATS_VERSION" ...
./install.sh
```

**New flow:**

```bash
# Fetch latest tag from GitHub
LATEST_VERSION=$(curl -fsSL "https://api.github.com/repos/bats-core/bats-core/releases/latest" | grep '"tag_name"' | sed 's/.*"\(v[^"]*\)".*/\1/')

# Check current version
if command -v bats >/dev/null 2>&1; then
  CURRENT_VERSION=$(bats --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
  CURRENT_VERSION="v$CURRENT_VERSION"  # Add v prefix to match tag

  if version_compare "$CURRENT_VERSION" "$LATEST_VERSION"; then
    log_success "Already at latest version: $LATEST_VERSION"
    exit 0
  fi

  log_info "Update available: $CURRENT_VERSION → $LATEST_VERSION"
fi

# Update BATS_VERSION to latest
BATS_VERSION="$LATEST_VERSION"

# Clone and install
git clone --branch "$BATS_VERSION" ...
```

**Changes needed:**

1. Fetch latest tag from GitHub API
2. Compare with current version
3. Use fetched version instead of hardcoded default

---

### Type 3: Custom Installer - AWS CLI

**File:** `management/common/install/custom-installers/awscli.sh`

**Current behavior:** Need to check what this installer does

**Investigation needed:**

1. How is awscli currently installed?
2. Does it have a native updater?
3. What's the version check command?
4. Where to get latest version?

**Possible approaches:**

- If installed via pip: `pip install --upgrade awscli`
- If installed via script: Re-run installer script with version check
- Version: `aws --version`
- Latest: Check PyPI API or GitHub releases

---

### Type 4: Custom Installer - Claude Code

**File:** `management/common/install/custom-installers/claude-code.sh`

**Current flow:**

```bash
# Uses official installer
curl -fsSL https://claude.ai/install.sh | bash
```

**Challenge:** External installer script - we don't control it

**Options:**

1. Check version before/after running installer
2. Let the official installer handle updates (it might be smart already)
3. Version: `claude --version`
4. Latest: Unknown - might need to check their release page

**Recommendation:** Check current version, run installer, check new version, report if updated

```bash
# Check current version
CURRENT_VERSION=$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")

# Run installer
curl -fsSL https://claude.ai/install.sh | bash

# Check new version
NEW_VERSION=$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")

if [[ -n "$CURRENT_VERSION" ]] && [[ "$CURRENT_VERSION" == "$NEW_VERSION" ]]; then
  log_success "Already at current version: $CURRENT_VERSION"
elif [[ -n "$CURRENT_VERSION" ]] && [[ -n "$NEW_VERSION" ]]; then
  log_success "Updated: $CURRENT_VERSION → $NEW_VERSION"
else
  log_success "Installed: $NEW_VERSION"
fi
```

---

### Type 5: Custom Installer - Terraform LS

**File:** `management/common/install/custom-installers/terraform-ls.sh`

**Pattern:** Likely GitHub releases (HashiCorp repo)

**Similar to Type 1** (GitHub Release Installers)

- Fetch from GitHub API
- Version compare
- Download and install if needed

---

### Type 6: Language Managers

**Files:**

- `management/common/install/language-managers/go.sh`
- `management/common/install/language-managers/rust.sh`
- `management/common/install/language-managers/nvm.sh`
- `management/common/install/language-managers/uv.sh`

**Go:**

- Current: Downloads from golang.org
- Version: `go version`
- Latest: Check golang.org/dl/ or GitHub
- Strategy: Similar to GitHub releases

**Rust:**

- Uses rustup (has built-in update: `rustup update`)
- Should we just call `rustup update` instead of re-running installer?

**NVM:**

- Git clone with tag
- Similar to BATS pattern

**UV:**

- External installer script
- Similar to Claude Code pattern

---

### Type 7: Custom Go Apps (sess, toolbox)

**Strategy:** Always rebuild (source is local)

**Enhancement:** Check if source changed since last build

```bash
# Get current git hash of app directory
CURRENT_HASH=$(git -C "$DOTFILES_DIR/apps/common/sess" rev-parse HEAD 2>/dev/null || echo "")

# Get hash from last build (stored in built binary or separate file?)
# This is complex - might not be worth it

# Alternative: Just always rebuild (they're fast)
cd "$DOTFILES_DIR/apps/common/sess" && task install
log_success "Rebuilt sess from latest source"
```

**Recommendation:** Keep simple - always rebuild

---

## Shared Helper Functions

Create a new library: `management/common/lib/version-helpers.sh`

```bash
#!/usr/bin/env bash

# Compare semantic versions
# Returns 0 if equal, 1 if current < latest, 2 if current > latest
version_compare() {
  local current="$1"
  local latest="$2"

  # Normalize (remove v prefix)
  current="${current#v}"
  latest="${latest#v}"

  if [[ "$current" == "$latest" ]]; then
    return 0
  fi

  # Sort and check which is first
  if [[ $(printf '%s\n' "$current" "$latest" | sort -V | head -n1) == "$current" ]]; then
    return 1  # current is older
  else
    return 2  # current is newer
  fi
}

# Fetch latest version from GitHub releases
fetch_github_latest_version() {
  local repo="$1"
  curl -fsSL "https://api.github.com/repos/${repo}/releases/latest" \
    2>/dev/null | grep '"tag_name":' | head -1 | sed -E 's/.*"([^"]+)".*/\1/'
}

# Parse version from command output
parse_version() {
  local output="$1"
  echo "$output" | grep -oE 'v?[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1
}
```

Source in installers:

```bash
source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
```

---

## Implementation Order

### Phase 1: Create Helper Library

1. Create `version-helpers.sh` with shared functions
2. Test version comparison with various inputs
3. Test GitHub API fetching

### Phase 2: Update GitHub Release Installers (Highest Impact)

1. Start with neovim (most critical)
2. Test thoroughly
3. Apply pattern to remaining 10 tools
4. Each tool needs custom version parsing

### Phase 3: Update Custom Installers

1. BATS (similar to GitHub releases)
2. Terraform LS (similar to GitHub releases)
3. AWS CLI (investigate current method)
4. Claude Code (wrapper around external installer)

### Phase 4: Update Language Managers

1. Go (similar to GitHub releases)
2. Rust (use rustup update)
3. NVM (similar to BATS)
4. UV (wrapper around external installer)

### Phase 5: Update update.sh

Once installers are smart, update.sh becomes:

```bash
print_section "Updating GitHub Release Tools" $section_color
if FORCE_INSTALL=true run_installer "$github_releases/neovim.sh" "neovim"; then
  log_success "Neovim check complete"
else
  log_warning "Neovim update failed"
fi
# ... repeat for each tool
```

---

## Testing Strategy

For each modified installer:

1. **Test: Already at latest version**

   ```bash
   FORCE_INSTALL=true bash installer.sh
   # Should output: "Already at latest version: X.X.X"
   ```

2. **Test: Update available**

   ```bash
   # Install old version first
   # Then run with FORCE_INSTALL=true
   # Should output: "Update available: X.X.X → Y.Y.Y"
   # Should proceed with installation
   ```

3. **Test: Not installed**

   ```bash
   FORCE_INSTALL=true bash installer.sh
   # Should install normally
   ```

4. **Test: GitHub API failure**

   ```bash
   # Simulate API failure (block network or use invalid repo)
   # Should handle gracefully
   ```

---

## Success Criteria

**For each installer:**

- ✅ Shows "Already at latest version" when current
- ✅ Shows "Update available: X → Y" when outdated
- ✅ Only downloads when update needed
- ✅ Handles API failures gracefully
- ✅ Works with FORCE_INSTALL=true in update.sh
- ✅ Maintains backward compatibility (normal install still works)

**For update.sh:**

- ✅ Clean if/else pattern for each tool
- ✅ Verbose output (shows all installer output)
- ✅ Proper success/failure logging
- ✅ Updates all tools that install.sh manages

---

## Next Steps

1. Review this plan - confirm approach
2. Create version-helpers.sh library
3. Start with neovim as proof of concept
4. Test thoroughly
5. Roll out to remaining installers
6. Update update.sh
