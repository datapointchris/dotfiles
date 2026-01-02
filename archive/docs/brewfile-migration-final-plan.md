# Brewfile Migration - Final Plan

**Date:** 2025-11-27
**Status:** All Decisions Made - Ready for Execution

---

## Executive Summary

Migrating from dual package management (Brewfile + packages.yml) to **single source of truth** (packages.yml only). This includes:

- Removing ~70 duplicate/unneeded packages
- Adding 14 packages to packages.yml
- Switching from tmuxinator to tmux-continuum
- Setting up Flatpak for Linux GUI apps
- Eliminating Brewfile entirely

---

## ✅ ALL USER DECISIONS FINALIZED

### Removals (12 items)

**From Brewfile:**

- ❌ resvg (embedded in Yazi)
- ❌ coretemp (CLI temp monitor, not needed by Macs Fan Control)
- ❌ sketchybar (not using)
- ❌ postgresql@16 (not needed)
- ❌ sbcl (not using Common Lisp)
- ❌ gource (not using git visualization)
- ❌ supervisor (switched to containers)
- ❌ tmuxinator (switching to tmux-continuum)
- ❌ tmuxinator-completion (goes with tmuxinator)

**From MAS Apps:**

- ❌ KnowledgeBase Builder (not using)
- ❌ Slack (keeping cask version for automation)

### Already in packages.yml (4 items - no action needed)

- ✅ git-secrets (line 267)
- ✅ ruby (line 169)
- ✅ lua-language-server (line 174)
- ✅ go-task (line 232)

### Add to packages.yml

#### system_packages (6 new)

```yaml
- name: bash
  apt: bash
  pacman: bash
  brew: bash
  description: Bash shell (macOS default is outdated)

- name: nmap
  apt: nmap
  pacman: nmap
  brew: nmap
  description: Network scanner

- name: mpv
  apt: mpv
  pacman: mpv
  brew: mpv
  description: Media player

- name: graphviz
  apt: graphviz
  pacman: graphviz
  brew: graphviz
  description: Graph visualization

- name: figlet
  apt: figlet
  pacman: figlet
  brew: figlet
  description: ASCII art text

- name: watch
  apt: procps
  pacman: procps-ng
  brew: watch
  description: Execute program periodically (used in watchports alias)
```

#### uv_tools (2 new)

```yaml
uv_tools:
  development:
    - name: pre-commit
      description: Git pre-commit hook framework

    - name: yt-dlp
      description: YouTube downloader with extra features
```

#### cargo_packages (3 new)

```yaml
cargo_packages:
  - name: taplo
    description: TOML formatter and toolkit

  - name: gpg-tui
    description: Terminal UI for managing GPG keys

  - name: tmuxrs
    description: Rust-based tmux session manager (tmuxinator replacement)
```

#### go_tools (1 new)

```yaml
go_tools:
  - name: actionlint
    package: github.com/rhysd/actionlint/cmd/actionlint
    description: GitHub Actions workflow linter
```

#### github_binaries (3 new)

```yaml
github_binaries:
  - name: zk
    repo: zk-org/zk
    binary_pattern: "zk_{version}_{platform}_{arch}.tar.gz"
    description: Plain text note-taking assistant

  - name: trivy
    repo: aquasecurity/trivy
    binary_pattern: "trivy_{version}_{OS}_{arch}.tar.gz"
    description: Container/IaC vulnerability scanner

  - name: mkcert
    repo: FiloSottile/mkcert
    binary_pattern: "mkcert-{version}-{platform}-{arch}"
    description: Local HTTPS certificates for development
```

#### NEW SECTION: linux_gui_apps (Flatpak)

```yaml
# ================================================================
# LINUX GUI APPLICATIONS
# ================================================================
# Installed via Flatpak (universal across all Linux distributions)
# Platform: Linux only (NOT WSL - GUI runs in Windows)
# Install: flatpak install flathub <app-id>

linux_gui_apps:
  - name: dbeaver-community
    flatpak_id: com.dbeaver.DBeaverCommunity
    description: Universal database GUI

  - name: discord
    flatpak_id: com.discordapp.Discord
    description: Chat platform

  - name: slack
    flatpak_id: com.slack.Slack
    description: Team communication
```

#### macOS Casks (keep all 11)

```yaml
# ================================================================
# MACOS CASKS
# ================================================================
# GUI applications for macOS
# Installed via: brew install --cask <name>

macos_casks:
  - name: aerospace
    description: Tiling window manager

  - name: alfred
    description: Launcher & productivity

  - name: bettertouchtool
    description: Input customization

  - name: dbeaver-community
    description: Universal database GUI

  - name: macs-fan-control
    description: Fan control utility

  - name: michaelvillar-timer
    description: Timer app

  - name: multipass
    description: Ubuntu VM manager

  - name: discord
    description: Chat platform

  - name: slack
    description: Team communication (using cask for automation, removed from MAS)

  - name: zoom
    description: Video conferencing

  - name: obsidian
    description: Note taking
```

### AWS CLI

**Already have install script:** `management/scripts/install-awscli.sh`

**Action:** Document in packages.yml notes section:

```yaml
# AWS CLI Installation:
#   macOS: Official installer (not brew - see management/scripts/install-awscli.sh)
#   Linux: Official installer (script downloads from AWS)
#   Not in system_packages - AWS recommends official installer only
```

### tmux Session Management

**Changed from tmuxinator to tmux-continuum:**

**Files modified:**

- ✅ `platforms/common/.config/tmux/tmux.conf` - Added tmux-continuum plugin
- ✅ `management/packages.yml` - Updated tmux_plugins documentation

**tmux.conf changes (lines 319-322):**

```tmux
# Automatic restore and continuous saving of tmux sessions
set -g @plugin 'tmux-plugins/tmux-continuum'
set -g @continuum-restore 'on'       # auto-restore sessions on tmux start
set -g @continuum-save-interval '15' # auto-save every 15 minutes
```

**Tmuxinator configs to delete:**

- `platforms/macos/.config/tmuxinator/ichrisbirch-development.yml`
- `platforms/macos/.config/tmuxinator/ichrisbirch-dev-monitoring.yml`
- `platforms/macos/.config/tmuxinator/ichrisbirch-prod-monitoring.yml`

---

## Summary of Package Counts

### Removals from Brewfile

| Category | Count | Packages |
|----------|-------|----------|
| **Unneeded** | 9 | resvg, coretemp, sketchybar, postgresql@16, sbcl, gource, supervisor, tmuxinator, tmuxinator-completion |
| **Duplicates** | ~60 | Already in packages.yml via cargo, go_tools, github_binaries, etc. |
| **Total to remove** | ~70 | Via `brew bundle cleanup --force` |

### Additions to packages.yml

| Category | Count | Packages |
|----------|-------|----------|
| **system_packages** | 6 | bash, nmap, mpv, graphviz, figlet, watch |
| **uv_tools** | 2 | pre-commit, yt-dlp |
| **cargo_packages** | 3 | taplo, gpg-tui, tmuxrs |
| **go_tools** | 1 | actionlint |
| **github_binaries** | 3 | zk, trivy, mkcert |
| **linux_gui_apps** | 3 | dbeaver-community, discord, slack |
| **macos_casks** | 11 | aerospace, alfred, bettertouchtool, dbeaver-community, macs-fan-control, michaelvillar-timer, multipass, discord, slack, zoom, obsidian |
| **Total additions** | 29 | New packages + documentation |

### MAS Apps Changes

- ❌ Remove KnowledgeBase Builder
- ❌ Remove Slack (using cask instead)
- ✅ Keep remaining 13 MAS apps

---

## File Changes Required

### Files to Modify

1. **management/packages.yml**
   - Add 6 system_packages
   - Add 2 uv_tools
   - Add 3 cargo_packages
   - Add 1 go_tools
   - Add 3 github_binaries
   - Create new `linux_gui_apps:` section with 3 apps
   - Create new `macos_casks:` section with 11 apps
   - Add AWS CLI note to comments
   - Remove Slack from mas_apps
   - Remove KnowledgeBase Builder from mas_apps

2. **management/parse-packages.py**
   - Add `--type=linux-gui` support
   - Add `--type=macos-casks` support
   - Add `get_linux_gui_apps()` function
   - Add `get_macos_casks()` function

3. **Brewfile**
   - DELETE (after migration complete)

### Files to Delete

1. **Brewfile** (after all packages migrated)
2. **platforms/macos/.config/tmuxinator/*.yml** (3 files - outdated configs)

### Files Already Modified ✅

1. **platforms/common/.config/tmux/tmux.conf** - Added tmux-continuum
2. **management/packages.yml** - Updated tmux_plugins documentation

---

## Execution Order

### Phase 1: Update packages.yml ⏳

1. Add 6 system_packages
2. Add 2 uv_tools
3. Add 3 cargo_packages
4. Add 1 go_tools
5. Add 3 github_binaries
6. Create linux_gui_apps section (3 apps)
7. Create macos_casks section (11 apps)
8. Remove Slack from mas_apps
9. Remove KnowledgeBase Builder from mas_apps
10. Add AWS CLI documentation note

### Phase 2: Update parse-packages.py ⏳

1. Add `--type=linux-gui` support
2. Add `--type=macos-casks` support

### Phase 3: Execute Brew Cleanup ⏳

```bash
cd ~/dotfiles
brew bundle cleanup --force
```

**Expected removals:** ~70 packages

### Phase 4: Delete Old Files ⏳

```bash
# Delete Brewfile
rm ~/dotfiles/Brewfile

# Delete tmuxinator configs
rm ~/dotfiles/platforms/macos/.config/tmuxinator/*.yml
```

### Phase 5: Install tmux-continuum ⏳

```bash
# In tmux, press:
prefix + I  # (capital I) - installs new plugins
```

### Phase 6: Test Everything ⏳

```bash
# Verify installations
task verify

# Test parse-packages.py
python management/parse-packages.py --type=linux-gui
python management/parse-packages.py --type=macos-casks
```

---

## Risks & Mitigation

### Risk 1: Brew cleanup removes needed package

**Mitigation:**

- All decisions documented and reviewed
- Can reinstall anything if needed
- No data loss (just package removal)

### Risk 2: Parse-packages.py breaks existing scripts

**Mitigation:**

- Only adding new functionality (--type=linux-gui, --type=macos-casks)
- Existing functionality unchanged
- Test before committing

### Risk 3: Missing a package during migration

**Mitigation:**

- Comprehensive categorization document created
- All 75 Brewfile packages accounted for
- Can reference Brewfile before deletion

---

## Post-Migration Workflow

### macOS

```bash
# Install system packages
task macos:install-system

# Install casks
for cask in $(python management/parse-packages.py --type=macos-casks); do
  brew install --cask "$cask"
done

# Install other packages (cargo, npm, uv, go, github binaries)
task install
```

### Linux (Arch/Ubuntu)

```bash
# Install system packages
task arch:install-system  # or ubuntu:install-system

# Install GUI apps (Flatpak)
for app in $(python management/parse-packages.py --type=linux-gui); do
  flatpak install -y flathub "$app"
done

# Install other packages
task install
```

---

## Questions Answered

### ✅ Why remove tmuxinator?

- Config files are outdated (reference supervisor, which you switched away from)
- Cryptic layout strings (e.g., `69b9,230x60,0,0{111x60,0,0[111x23...`)
- tmux-resurrect + continuum provide automatic session persistence without config files
- tmuxrs available if you need project templates later

### ✅ Why Flatpak for Linux GUI apps?

- Universal across all Linux distributions
- Default in many distros (Linux Mint, Zorin)
- Better update management than AppImage
- Not Ubuntu-specific like Snap
- Verified software on Flathub

### ✅ Why keep Slack as cask instead of MAS?

- Automation/scripting consistency (matches other casks)
- `brew uninstall --zap` removes all metadata
- No need for manual App Store interactions
- Fits dotfiles automation philosophy

### ✅ Why GitHub binaries for zk/trivy/mkcert?

- System packages lag behind or don't exist (apt doesn't have zk/mkcert)
- Official recommendation for trivy
- Consistent install method across platforms
- Always get latest versions

### ✅ Why keep AWS CLI install script?

- AWS officially recommends their installer (not system packages)
- System packages are unofficial and lag behind
- Install script already working and tested
- Installs to `~/.local/` (no sudo needed)

---

## Files Reference

**Planning documents:**

- `.planning/docker-and-brewfile-migration-summary.md` (original plan)
- `.planning/brew-bundle-cleanup-analysis.md` (package analysis)
- `.planning/brewfile-to-packages-yml-detailed-breakdown.md` (migration breakdown)
- `.planning/brewfile-package-categorization.md` (research & categorization)
- `.planning/brewfile-migration-final-plan.md` (this file - final decisions)

**Implementation files:**

- `management/packages.yml` (single source of truth)
- `management/parse-packages.py` (package extraction)
- `management/scripts/install-awscli.sh` (AWS CLI installer)
- `platforms/common/.config/tmux/tmux.conf` (tmux config with continuum)

**To be deleted:**

- `Brewfile`
- `platforms/macos/.config/tmuxinator/*.yml` (3 files)

---

## Ready for Execution

All decisions made. All packages categorized. Ready to execute migration.

**Estimated time:** 30-60 minutes (mostly brew cleanup and package downloads)

**Rollback plan:** Keep Brewfile backup until everything verified working
