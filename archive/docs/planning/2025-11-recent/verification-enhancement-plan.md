# Verification and Detection Enhancement Plan

## Overview

Enhance verify-installation.sh and detect-alternate-installations.sh to cover all tools installed by install.sh, improve platform awareness, and add better user feedback.

## Implementation Order

### HIGH PRIORITY

#### HIGH-1: Add Language Managers to detect-alternate-installations.sh

**What:** Add checks for nvm, uv, rustup, node, npm
**Why:** These are critical foundation tools that often have multiple installation methods
**Expected locations:**

- nvm: $HOME/.config/nvm/nvm.sh
- uv: $HOME/.cargo/bin/uv (or via pip)
- rustup: $HOME/.cargo/bin/rustup
- node: Managed by nvm (in PATH)
- npm: Managed by nvm (in PATH)

**Files to modify:**

- management/detect-alternate-installations.sh (line ~375, after tinty check)

**Test:**

```bash
bash management/detect-alternate-installations.sh
# Should detect if these are installed via brew/system packages
```

#### HIGH-2: Add Custom Apps to detect-alternate-installations.sh

**What:** Add checks for sess, toolbox, menu, notes, theme-sync
**Why:** These are our custom tools that should only exist in our managed locations
**Expected locations:**

- sess: $HOME/go/bin/sess
- toolbox: $HOME/go/bin/toolbox
- menu: $HOME/.local/bin/menu
- notes: $HOME/.local/bin/notes
- theme-sync: $HOME/.local/bin/theme-sync

**Files to modify:**

- management/detect-alternate-installations.sh (line ~375, after language managers)

**Test:**

```bash
bash management/detect-alternate-installations.sh
# Should show these tools and their locations
```

#### HIGH-3: Add Main npm/uv Tools to detect-alternate-installations.sh

**What:** Add checks for most commonly used npm and uv tools
**npm:** typescript-language-server, eslint, prettier, bash-language-server
**uv:** ruff, mypy, basedpyright, codespell
**Expected locations:**

- npm: $HOME/.local/share/npm/bin/*
- uv: $HOME/.local/share/uv/bin/* (uv uses different paths per tool)

**Files to modify:**

- management/detect-alternate-installations.sh (line ~375, after custom apps)

**Test:**

```bash
bash management/detect-alternate-installations.sh
# Should detect if npm/uv tools installed via other methods
```

### MEDIUM PRIORITY

#### MED-4: Add duti, glow, duf to verify-installation.sh

**What:** Add verification for useful Homebrew tools
**Why:** These are installed via brew and should be verified
**Expected behavior:**

- duti: File association tool (macOS only)
- glow: Markdown renderer (universal)
- duf: Better df (universal)

**Files to modify:**

- management/verify-installation.sh (line ~143, after jq in System Utilities)

**Test:**

```bash
bash management/verify-installation.sh | grep -E "(duti|glow|duf)"
# Should show verification results
```

#### MED-5: Add Platform Awareness to verify-installation.sh

**What:** Add clear platform-specific sections in output
**Why:** Makes it clear which tools are platform-specific vs universal
**Changes:**

1. Add "Platform Configuration" section after platform detection
2. Add "(Universal)" or "(macOS)" labels to section headers
3. Add platform-specific section for macOS tools

**Files to modify:**

- management/verify-installation.sh (lines 99-390)

**Test:**

```bash
bash management/verify-installation.sh
# Should show clear platform sections in output
```

#### MED-6: Improve install-*.sh Scripts to Warn About Alternates

**What:** Update install scripts to detect and warn about existing installations at different locations
**Why:** Provides better feedback during installation
**Pattern:**

```bash
if [ ! -f "$TARGET_PATH" ]; then
  if command -v tool >/dev/null 2>&1; then
    print_warning "tool found at $(command -v tool), installing to $TARGET_PATH anyway"
  fi
  # ... install
fi
```

**Files to modify:**

- management/scripts/install-go.sh
- management/scripts/install-fzf.sh
- management/scripts/install-neovim.sh
- management/scripts/install-lazygit.sh
- management/scripts/install-yazi.sh
- management/scripts/install-awscli.sh

**Test:**

```bash
# Install a tool via brew first
brew install lazygit
# Then run install script
bash management/scripts/install-lazygit.sh
# Should warn about brew version
```

### LOW PRIORITY

#### LOW-7: Add All npm/uv Tools to detect-alternate-installations.sh

**What:** Add checks for remaining npm/uv tools
**npm remaining:** typescript, yaml-language-server, vscode-langservers-extracted, gh-actions-language-server, markdownlint-cli
**uv remaining:** sqlfluff, mdformat, djlint, keymap-drawer, nbpreview

**Files to modify:**

- management/detect-alternate-installations.sh (expand npm/uv section)

**Test:**

```bash
bash management/detect-alternate-installations.sh
# Should check all 9 npm + 10 uv tools
```

#### LOW-8: Add --force Flag to install.sh

**What:** Add --force flag to re-install everything even if already installed
**Why:** Useful for fixing corrupted installations or upgrading tools
**Implementation:**

1. Add argument parsing to install.sh
2. Pass FORCE_INSTALL env var to all install scripts
3. Update install-*.sh scripts to respect FORCE_INSTALL

**Files to modify:**

- install.sh (add argument parsing)
- All management/scripts/install-*.sh (check FORCE_INSTALL)

**Test:**

```bash
bash install.sh --force
# Should re-install everything
```

### FINAL: Comprehensive Testing

**Test 1 - Fresh Install:**

```bash
# On a fresh system or Docker container
bash install.sh
bash management/verify-installation.sh
bash management/detect-alternate-installations.sh
# Should show all installed, no alternates
```

**Test 2 - With Alternates:**

```bash
# Install some tools via brew
brew install lazygit yazi
# Run detection
bash management/detect-alternate-installations.sh
# Should detect brew versions
```

**Test 3 - Cleanup:**

```bash
bash management/detect-alternate-installations.sh --clean
bash management/verify-installation.sh
# Should pass all checks
```

## Success Criteria

- ✅ All tools installed by install.sh are verified in verify-installation.sh
- ✅ All important tools are checked for alternates in detect-alternate-installations.sh
- ✅ Platform-specific tools clearly labeled in verification output
- ✅ Install scripts provide helpful warnings about existing installations
- ✅ Scripts work identically across macOS, WSL, and Arch
- ✅ Documentation updated to reflect new capabilities
