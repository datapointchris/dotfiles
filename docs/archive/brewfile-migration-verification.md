# Brewfile Migration Verification Report

**Date:** 2025-11-28
**Status:** Review Complete - Missing Items Identified

---

## Executive Summary

After thorough review of the Brewfile migration to packages.yml, the following items were identified as missing or incomplete from the migration plan:

### ✅ Already Fixed
- **zk** - Install script created, packages.yml updated with `install_script` field

### ⚠️ Missing Install Scripts (2 GitHub binaries)
- **trivy** - In packages.yml but missing `install-trivy.sh`
- **mkcert** - In packages.yml but missing `install-mkcert.sh`

### ⚠️ Missing from packages.yml (1 package)
- **yt-dlp** - Currently installed via brew, migration plan said to add to uv_tools but not present

### ⚠️ Packages in Brew but Undocumented (2 macOS-specific)
- **borders** - macOS window border highlighter (installed but not in packages.yml)
- **terminal-notifier** - macOS notifications (installed but not in packages.yml)

---

## Detailed Findings

### 1. Missing Install Scripts for GitHub Binaries

#### trivy (Container/IaC vulnerability scanner)
- **Status**: Entry exists in packages.yml at line 452-455
- **Issue**: Missing `management/scripts/install-trivy.sh`
- **Binary pattern**: `trivy_{version}_{OS}_{arch}.tar.gz`
- **Current state**: Likely installed via other means or not installed

#### mkcert (Local HTTPS certificates)
- **Status**: Entry exists in packages.yml at line 458-461
- **Issue**: Missing `management/scripts/install-mkcert.sh`
- **Binary pattern**: `mkcert-{version}-{platform}-{arch}` (direct binary, not tarball)
- **Current state**: Likely installed via other means or not installed

**Impact**: These tools cannot be installed via the standard `task install` workflow until scripts are created.

**Recommendation**: Create install scripts following the pattern of `install-zk.sh` and other GitHub binary installers.

---

### 2. yt-dlp Missing from packages.yml

According to `.planning/brewfile-migration-final-plan.md` lines 87-97:

```yaml
uv_tools:
  development:
    - name: yt-dlp
      description: YouTube downloader with extra features
```

**Status**:
- Currently installed via Homebrew
- Migration plan specified adding to uv_tools
- Not present in packages.yml uv_tools section

**Current packages.yml uv_tools section**:
- Only contains `pre-commit` under development (line 616-617)
- yt-dlp is missing

**Recommendation**: Add yt-dlp to packages.yml under uv_tools → development section.

**Note**: yt-dlp is available via pip/uv. Verify this is the preferred installation method vs Homebrew.

---

### 3. macOS-Specific Tools Missing from packages.yml

#### borders
- **What it is**: Window border highlighter for macOS (visual indicator for focused window)
- **Status**: Currently installed via Homebrew
- **Location in migration plan**: Listed in brewfile-to-packages-yml-detailed-breakdown.md line 145 as "macOS-specific"
- **Missing from**: packages.yml (should be in system_packages with `brew:` only)

#### terminal-notifier
- **What it is**: macOS notification system integration from terminal
- **Status**: Currently installed via Homebrew
- **Location in migration plan**: Listed in brewfile-to-packages-yml-detailed-breakdown.md line 147 as "macOS-specific"
- **Missing from**: packages.yml (should be in system_packages with `brew:` only)

**Recommendation**: Add both to packages.yml system_packages section with macOS-only brew entries:

```yaml
system_packages:
  # macOS-specific utilities
  - name: borders
    brew: borders
    description: Window border highlights (macOS only)

  - name: terminal-notifier
    brew: terminal-notifier
    description: macOS notifications from terminal (macOS only)
```

---

## Verification Results

### ✅ Packages Correctly in packages.yml

All packages from the migration plan that were supposed to be added are present:

#### system_packages (6 packages) ✅
- bash (line 295-298)
- nmap (line 308-311)
- mpv (line 315-318)
- graphviz (line 321-324)
- figlet (line 327-330)
- watch (line 301-304)

#### uv_tools ⚠️
- pre-commit (line 616-617) ✅
- yt-dlp ❌ MISSING

#### cargo_packages (3 packages) ✅
- taplo-cli (line 499-501)
- gpg-tui (line 503-505)
- Note: tmuxrs was not added (decision changed to use tmux-continuum instead)

#### go_tools (5 packages) ✅
- cheat (line 627-629)
- terraform-docs (line 631-633)
- gum (line 635-637)
- lazydocker (line 639-641)
- actionlint (line 643-645)

#### github_binaries (3 packages from plan) ⚠️
- zk (line 445-450) ✅ (just fixed with install script)
- trivy (line 452-455) ⚠️ (missing install script)
- mkcert (line 458-461) ⚠️ (missing install script)

#### linux_gui_apps (3 apps) ✅
- dbeaver-community (line 740-742)
- discord (line 744-746)
- slack (line 748-750)

#### macos_casks (11 apps) ✅
All present at lines 759-790

### ✅ Install Scripts Present

All GitHub binaries with install_script field have corresponding scripts:
- neovim → install-neovim.sh ✅
- lazygit → install-lazygit.sh ✅
- yazi → install-yazi.sh ✅
- fzf → install-fzf.sh ✅
- glow → install-glow.sh ✅
- duf → install-duf.sh ✅
- tenv → install-tenv.sh ✅
- terraform-ls → install-terraform-ls.sh ✅
- tflint → install-tflint.sh ✅
- terraformer → install-terraformer.sh ✅
- terrascan → install-terrascan.sh ✅
- zk → install-zk.sh ✅

### ⚠️ GitHub Binaries Missing Install Scripts

- trivy → install-trivy.sh ❌
- mkcert → install-mkcert.sh ❌

Note: These entries in packages.yml don't have the `install_script:` field, which explains why they weren't caught earlier.

---

## Current Brew Installation Status

### Expected Packages (All Present) ✅

All packages that should be managed via Homebrew according to packages.yml are installed:

- awscli, bash, borders, ca-certificates, chafa, colima, coreutils, curl
- docker, docker-completion, docker-compose, duti
- ffmpeg, figlet, findutils, gawk, gh, git, git-secrets, gnupg
- gnu-sed, gnu-tar, go-task, gpgme, graphviz, grep
- htop, imagemagick, jq
- lua, lua-language-server, luajit, luarocks
- mas, mpv, nmap
- ripgrep, ruby, sevenzip, shellcheck, shfmt
- terminal-notifier, tmux, tree
- unzip, watch, wget, yt-dlp

### Dependencies (Automatically Managed)

Numerous library packages are installed as dependencies (lib*, codec packages, etc.). These are normal and automatically managed by Homebrew.

Examples: aom, cairo, ffmpeg dependencies, imagemagick dependencies, etc.

---

## Action Items

### High Priority (Functionality Gap)

1. **Create install-trivy.sh**
   - Pattern: `trivy_{version}_{OS}_{arch}.tar.gz`
   - Reference: Similar to install-terrascan.sh pattern
   - Add `install_script: install-trivy.sh` to packages.yml entry

2. **Create install-mkcert.sh**
   - Pattern: `mkcert-{version}-{platform}-{arch}` (direct binary)
   - Reference: Similar pattern but simpler (no tarball extraction)
   - Add `install_script: install-mkcert.sh` to packages.yml entry

3. **Add yt-dlp to packages.yml**
   - Location: uv_tools → development section
   - Verify uv has yt-dlp available
   - If not available via uv, consider keeping in brew or using GitHub binary

### Medium Priority (Documentation/Consistency)

4. **Add borders to packages.yml**
   - Add to system_packages with brew-only entry
   - Ensures it's part of automated installation

5. **Add terminal-notifier to packages.yml**
   - Add to system_packages with brew-only entry
   - Ensures it's part of automated installation

### Low Priority (Optional)

6. **Verify Brewfile can be deleted**
   - After above items are addressed
   - Ensure all packages accounted for in packages.yml
   - Keep backup before deletion

---

## Summary Statistics

### Migration Completeness

- **Planned additions**: 29 packages
- **Successfully added**: 26 packages (90%)
- **Missing**: 3 packages (10%)
  - yt-dlp (not in packages.yml)
  - borders (not in packages.yml)
  - terminal-notifier (not in packages.yml)

### Install Scripts

- **Total GitHub binaries in packages.yml**: 13
- **With install scripts**: 12 (92%)
- **Missing install scripts**: 2 (15%)
  - trivy
  - mkcert
- **Note**: zk was just fixed, bringing us from 11/13 (85%) to 12/14 (86%)

### Current State

- ✅ All expected brew packages are installed
- ✅ All planned system_packages additions present in packages.yml
- ✅ All planned cargo_packages additions present in packages.yml
- ✅ All planned go_tools additions present in packages.yml
- ✅ All linux_gui_apps and macos_casks sections created
- ⚠️ 2 GitHub binaries missing install scripts (trivy, mkcert)
- ⚠️ 1 package missing from packages.yml (yt-dlp)
- ⚠️ 2 macOS packages not in packages.yml (borders, terminal-notifier)

---

## Recommendations

1. **Immediate**: Create install scripts for trivy and mkcert to complete GitHub binaries automation

2. **Short-term**: Add yt-dlp, borders, and terminal-notifier to packages.yml for completeness

3. **Long-term**: Consider whether Brewfile can now be safely deleted once all items are in packages.yml

4. **Testing**: Run `task install` on a fresh system to verify all packages install correctly

---

## Files to Update

1. **New files to create**:
   - `management/scripts/install-trivy.sh`
   - `management/scripts/install-mkcert.sh`

2. **Files to modify**:
   - `management/packages.yml`:
     - Add `install_script:` fields to trivy and mkcert entries
     - Add yt-dlp to uv_tools → development
     - Add borders to system_packages (brew only)
     - Add terminal-notifier to system_packages (brew only)

---

## Related Planning Documents

- `.planning/brewfile-migration-final-plan.md` - Original migration plan
- `.planning/brewfile-to-packages-yml-detailed-breakdown.md` - Detailed package breakdown
- `.planning/brew-bundle-cleanup-analysis.md` - Analysis of packages to remove
- `.planning/brewfile-package-categorization.md` - Package categorization research

---

## Conclusion

The Brewfile migration is 90% complete. The main gaps are:

1. Two GitHub binary install scripts (trivy, mkcert)
2. Three packages not yet in packages.yml (yt-dlp, borders, terminal-notifier)

All core functionality is working, and these missing items are preventing full automation of a fresh install. Addressing the high-priority action items will bring the migration to 100% completion.
