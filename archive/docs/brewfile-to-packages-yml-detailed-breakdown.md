# Brewfile to packages.yml Migration - Detailed Breakdown

**Date:** 2025-11-27
**Current State:** parse-packages.py updated with `--taps` support

---

## Current Brewfile Inventory

### Total Count

- **66 brew formulae** (CLI packages)
- **9 casks** (GUI applications)
- **75 total packages**

---

## Status by Package

### ✅ Already in packages.yml (35 formulae)

These are already defined in packages.yml - **NO ACTION NEEDED for Brewfile migration:**

| Package | Location in packages.yml | Notes |
|---------|-------------------------|-------|
| **ripgrep** | system_packages | apt/pacman/brew |
| **git** | system_packages | apt/pacman/brew |
| **gh** | system_packages | apt/pacman/brew |
| **tmux** | system_packages | apt/pacman/brew |
| **jq** | system_packages | apt/pacman/brew |
| **tree** | system_packages | apt/pacman/brew |
| **htop** | system_packages | apt/pacman/brew |
| **curl** | system_packages | apt/pacman/brew |
| **wget** | system_packages | apt/pacman/brew |
| **lua** | system_packages | apt/pacman/brew |
| **luajit** | system_packages | apt/pacman/brew |
| **luarocks** | system_packages | apt/pacman/brew |
| **shellcheck** | system_packages | apt/pacman/brew |
| **shfmt** | system_packages | apt/pacman/brew |
| **gnupg** | system_packages | apt/pacman/brew |
| **ffmpeg** | system_packages | apt/pacman/brew |
| **imagemagick** | system_packages | apt/pacman/brew |
| **chafa** | system_packages | apt/pacman/brew |
| **sevenzip** | system_packages | apt/pacman/brew (as 7zip) |
| **docker** | system_packages | ✅ JUST ADDED - apt: docker-ce, pacman: docker, brew: docker |
| **docker-compose** | system_packages | ✅ JUST ADDED - docker-compose-plugin |
| **colima** | N/A | ⏸️ NEEDS macos_packages section |
| **gum** | go_tools | ✅ JUST ADDED |
| **lazydocker** | go_tools | ✅ JUST ADDED |
| **bat** | cargo_packages | (via binstall) |
| **eza** | cargo_packages | (via binstall) |
| **fd** | cargo_packages | (via binstall) |
| **zoxide** | cargo_packages | (via binstall) |
| **git-delta** | cargo_packages | (via binstall) |
| **tinty** | cargo_packages | (via binstall) |
| **neovim** | github_binaries | (GitHub releases) |
| **fzf** | github_binaries | (GitHub releases) |
| **lazygit** | github_binaries | (GitHub releases) |
| **yazi** | github_binaries | (GitHub releases) |
| **glow** | github_binaries | (GitHub releases) |
| **duf** | github_binaries | (GitHub releases) |

---

### 🔄 Move to packages.yml system_packages (18 formulae)

These need to be ADDED to packages.yml with apt/pacman/brew entries:

| Package | Brewfile | packages.yml Action | Cross-Platform? |
|---------|----------|-------------------|-----------------|
| **git-secrets** | Line 26 | Add to system_packages | brew only (macOS) |
| **ruby** | Line 46 | Add to system_packages | brew only (macOS note) |
| **sbcl** | Line 50 | Add to system_packages | apt/pacman/brew |
| **lua-language-server** | Line 56 | Add to system_packages | brew only currently |
| **taplo** | Line 66 | Add to system_packages | apt/pacman/brew |
| **actionlint** | Line 67 | Add to system_packages | apt/pacman/brew |
| **awscli** | Line 80 | Add to system_packages | apt/pacman/brew |
| **mkcert** | Line 85 | Add to system_packages | apt/pacman/brew |
| **gpg-tui** | Line 87 | Add to system_packages | apt/pacman/brew |
| **trivy** | Line 88 | Add to system_packages | apt/pacman/brew |
| **postgresql@16** | Line 93 | Add to system_packages | apt/pacman/brew |
| **go-task** | Line 98 | Add to system_packages | apt/pacman/brew |
| **supervisor** | Line 99 | Add to system_packages | apt/pacman/brew |
| **watch** | Line 106 | Add to system_packages | apt/pacman (Linux has it) |
| **nmap** | Line 116 | Add to system_packages | apt/pacman/brew |
| **mpv** | Line 129 | Add to system_packages | apt/pacman/brew |
| **yt-dlp** | Line 130 | Add to system_packages | apt/pacman/brew |
| **graphviz** | Line 134 | Add to system_packages | apt/pacman/brew |
| **gource** | Line 135 | Add to system_packages | apt/pacman/brew |
| **figlet** | Line 140 | Add to system_packages | apt/pacman/brew |
| **bash** | Line 152 | Add to system_packages | apt/pacman/brew |
| **tmuxinator** | Line 153 | Add to system_packages | apt/pacman/brew |
| **tmuxinator-completion** | Line 154 | Add to system_packages | brew only |

---

### 🍎 macOS-Specific - Create macos_packages section (11 formulae)

These need a NEW `macos_packages:` section in packages.yml:

| Package | Brewfile | Reason for macOS-only | Notes |
|---------|----------|----------------------|-------|
| **duti** | Line 32 | macOS file associations | No Linux equivalent |
| **grep** | Line 38 | GNU grep (macOS has BSD) | Linux has GNU grep by default |
| **gnu-sed** | Line 39 | GNU sed (macOS has BSD) | Linux has GNU sed by default |
| **gawk** | Line 40 | GNU awk (macOS has BSD) | Linux has gawk by default |
| **coreutils** | Line 119 | GNU coreutils (macOS has BSD) | Linux has these by default |
| **findutils** | Line 120 | GNU findutils (macOS has BSD) | Linux has these by default |
| **gnu-tar** | Line 111 | GNU tar (macOS has BSD) | Linux has GNU tar by default |
| **mas** | Line 123 | Mac App Store CLI | macOS only |
| **resvg** | Line 133 | SVG tool (for Yazi) | ⚠️ Check if needed - might work cross-platform |
| **coretemp** | Line 107 | macOS CPU temp | macOS-specific |
| **borders** | Line 145 | macOS window borders | macOS-specific |
| **sketchybar** | Line 146 | macOS menubar | macOS-specific |
| **terminal-notifier** | Line 147 | macOS notifications | macOS-specific |
| **colima** | Line 73 | Docker VM for macOS | macOS needs VM, Linux doesn't |

---

### 🖥️ GUI Apps - Create macos_casks section (9 casks)

These need a NEW `macos_casks:` section in packages.yml:

| Cask | Brewfile | Category |
|------|----------|----------|
| **aerospace** | Line 161 | Window Management |
| **alfred** | Line 164 | Productivity |
| **bettertouchtool** | Line 165 | Productivity |
| **dbeaver-community** | Line 168 | Development |
| **macs-fan-control** | Line 171 | Utilities |
| **michaelvillar-timer** | Line 172 | Utilities |
| **multipass** | Line 173 | Utilities |
| **discord** | Line 176 | Communication |
| **slack** | Line 177 | Communication |
| **zoom** | Line 178 | Communication |
| **obsidian** | Line 181 | Notes & Knowledge |

---

### ❌ Will Be Removed (from brew cleanup) (~70 packages)

**These are NOT in Brewfile** but will be removed via `brew bundle cleanup`:

#### Duplicates (already in packages.yml)

- bat, eza, fd, git-delta, zoxide, tinty (cargo)
- neovim, lazygit, yazi, fzf, glow, duf (github_binaries)
- terraform-docs (go_tools)
- codespell (uv_tools)
- zsh-syntax-highlighting (shell_plugins)
- terraform, terraform-ls, tflint, terraformer, terrascan (moved to packages.yml)

#### Unneeded packages

- cmatrix, sl, pipes-sh (fun tools)
- iterm2, qutebrowser (terminals/browsers)
- sbt, openjdk, geckodriver, tokei, tlrc (unused dev tools)
- pandoc, docutils (doc tools)
- pgloader (database migration)
- pipx, virtualenv, python-tk@3.12 (Python tools - using uv)
- sox, mad (media tools)
- yq, tree-sitter-cli, guile (misc)
- buku, nginx (user decisions)

#### Neovim dependencies (not needed - statically linked)

- libuv, lpeg, luv, tree-sitter, unibilium

#### Docker Desktop

- docker-desktop (cask) - replacing with Colima

**Total to remove:** ~70 packages + 3 casks

---

## ⚠️ Special Cases - Need Decisions/Research

### 1. **pre-commit**

- **Status:** Currently installed via Homebrew (found in brew cleanup list)
- **Current:** NOT in Brewfile, NOT in packages.yml
- **Action:** ✅ Add to packages.yml system_packages (apt/pacman/brew)
- **Used by:** .pre-commit-config.yaml exists in repo

### 2. **zk** (note-taking tool)

- **Status:** Currently installed via Homebrew (found in brew cleanup list)
- **Current:** NOT in Brewfile, NOT in packages.yml
- **Has config:** platforms/common/.config/zk/config.toml exists
- **Action:** ✅ Add to packages.yml system_packages (apt/pacman/brew)

### 3. **resvg** (SVG renderer)

- **Status:** In Brewfile (Line 133)
- **Purpose:** SVG rendering tool (for Yazi)
- **Question:** Is this cross-platform or macOS-only?
- **Note in packages.yml:** "resvg removed - now embedded in Yazi as a Rust crate"
- **Action:** ❓ **DECISION NEEDED** - Remove from Brewfile if embedded in Yazi?

---

## Migration Plan (Updated)

### Phase 1: Add Missing Packages to packages.yml

#### A. Add to system_packages (18 packages)

```yaml
system_packages:
  # ... existing packages ...

  # Git tools
  - name: git-secrets
    brew: git-secrets
    description: Prevent committing secrets

  # Pre-commit hooks
  - name: pre-commit
    apt: pre-commit
    pacman: pre-commit
    brew: pre-commit
    description: Git pre-commit hook framework

  # Note-taking
  - name: zk
    apt: zk
    pacman: zk
    brew: zk
    description: Plain text note-taking assistant

  # Languages
  - name: ruby
    brew: ruby
    description: Ruby programming language (macOS only in Brewfile)

  - name: sbcl
    apt: sbcl
    pacman: sbcl
    brew: sbcl
    description: Steel Bank Common Lisp

  # Language Servers
  - name: lua-language-server
    brew: lua-language-server
    description: Lua LSP (macOS only for now)

  # Linters & Formatters
  - name: taplo
    apt: taplo
    pacman: taplo
    brew: taplo
    description: TOML formatter & linter

  - name: actionlint
    apt: actionlint
    pacman: actionlint
    brew: actionlint
    description: GitHub Actions linter

  # Infrastructure
  - name: awscli
    apt: awscli
    pacman: aws-cli
    brew: awscli
    description: AWS command line interface

  # Security
  - name: mkcert
    apt: mkcert
    pacman: mkcert
    brew: mkcert
    description: Local SSL certificates

  - name: gpg-tui
    apt: gpg-tui
    pacman: gpg-tui
    brew: gpg-tui
    description: GPG terminal UI

  - name: trivy
    apt: trivy
    pacman: trivy
    brew: trivy
    description: Container vulnerability scanner

  # Database
  - name: postgresql@16
    brew: postgresql@16
    description: PostgreSQL database (version-specific for macOS)

  # Build & Task
  - name: go-task
    apt: go-task
    pacman: go-task
    brew: go-task
    description: Modern taskfile runner

  - name: supervisor
    apt: supervisor
    pacman: supervisor
    brew: supervisor
    description: Process control system

  # System Utilities
  - name: watch
    apt: procps
    pacman: procps-ng
    description: Execute program periodically (Linux has it)

  - name: nmap
    apt: nmap
    pacman: nmap
    brew: nmap
    description: Network scanner

  # Media
  - name: mpv
    apt: mpv
    pacman: mpv
    brew: mpv
    description: Media player

  - name: yt-dlp
    apt: yt-dlp
    pacman: yt-dlp
    brew: yt-dlp
    description: YouTube downloader

  - name: graphviz
    apt: graphviz
    pacman: graphviz
    brew: graphviz
    description: Graph visualization

  - name: gource
    apt: gource
    pacman: gource
    brew: gource
    description: Repository visualization

  # Fun
  - name: figlet
    apt: figlet
    pacman: figlet
    brew: figlet
    description: ASCII art text

  # Shell
  - name: bash
    apt: bash
    pacman: bash
    brew: bash
    description: Updated bash shell

  - name: tmuxinator
    apt: tmuxinator
    pacman: tmuxinator
    brew: tmuxinator
    description: Tmux session manager

  - name: tmuxinator-completion
    brew: tmuxinator-completion
    description: Tmux completion (macOS only)
```

#### B. Create macos_packages section (14 packages)

```yaml
# NEW SECTION
macos_packages:
  - name: colima
    brew: colima
    description: Container runtime (Docker daemon via Lima VM)

  - name: duti
    brew: duti
    description: macOS file association manager

  # GNU tools (macOS has BSD versions)
  - name: grep
    brew: grep
    description: GNU grep

  - name: gnu-sed
    brew: gnu-sed
    description: GNU sed

  - name: gawk
    brew: gawk
    description: GNU awk

  - name: coreutils
    brew: coreutils
    description: GNU core utilities

  - name: findutils
    brew: findutils
    description: GNU find utilities

  - name: gnu-tar
    brew: gnu-tar
    description: GNU tar

  # macOS-specific utilities
  - name: mas
    brew: mas
    description: Mac App Store CLI

  - name: coretemp
    brew: coretemp
    description: CPU temperature monitoring

  - name: borders
    brew: borders
    description: Window border highlights

  - name: sketchybar
    brew: sketchybar
    description: Custom menubar

  - name: terminal-notifier
    brew: terminal-notifier
    description: macOS notifications from terminal

  # Maybe cross-platform? Need to verify:
  - name: resvg
    brew: resvg
    description: SVG rendering tool (for Yazi)
```

#### C. Create macos_casks section (11 casks)

```yaml
# NEW SECTION
macos_casks:
  # Window Management
  - name: aerospace
    description: Tiling window manager

  # Productivity
  - name: alfred
    description: Launcher & productivity

  - name: bettertouchtool
    description: Input customization

  # Development
  - name: dbeaver-community
    description: Universal database GUI

  # Utilities
  - name: macs-fan-control
    description: Fan control

  - name: michaelvillar-timer
    description: Timer app

  - name: multipass
    description: Ubuntu VM manager

  # Communication
  - name: discord
    description: Chat

  - name: slack
    description: Team chat

  - name: zoom
    description: Video conferencing

  # Notes & Knowledge
  - name: obsidian
    description: Note taking
```

---

### Phase 2: Update parse-packages.py

#### ✅ DONE - Added support for

- `--taps` flag to extract macos_taps
- `get_macos_taps()` function

#### TODO - Add support for

- `--type=macos` to extract macos_packages
- `--type=casks` to extract macos_casks

---

### Phase 3: Execute Brew Cleanup

```bash
cd ~/dotfiles
brew bundle cleanup --force
```

**Will remove:** ~70 packages + 3 casks

---

### Phase 4: Delete Brewfile

After confirming packages.yml has everything:

```bash
rm ~/dotfiles/Brewfile
```

---

## Summary Statistics

### Current State

- **Brewfile:** 66 formulae + 9 casks = 75 packages
- **packages.yml:** ~40 packages already defined

### After Migration

- **Brewfile:** DELETED
- **packages.yml:**
  - system_packages: ~58 packages (35 existing + 23 new)
  - macos_packages: ~14 packages (NEW section)
  - macos_casks: ~11 packages (NEW section)
  - macos_taps: 1 tap (docker/docker)
  - Total in packages.yml: ~83 packages

### Removals

- ~70 packages + 3 casks via brew cleanup

### Net Change

- Brewfile: 75 → 0 (eliminated)
- packages.yml: ~40 → ~83 (consolidated single source of truth)

---

## Questions Requiring Decisions

1. **resvg** - Remove from Brewfile? (packages.yml says "now embedded in Yazi")
2. **watch** - Linux has it by default, macOS needs it via brew - include in system_packages or macos_packages?
3. **coretemp** - Verify macOS-only or cross-platform?

---

## Files to Update

1. ✅ **parse-packages.py** - Added `--taps` support
2. ⏸️ **parse-packages.py** - TODO: Add `--type=macos` and `--type=casks`
3. ⏸️ **packages.yml** - Add 23 system_packages, 14 macos_packages, 11 macos_casks
4. ⏸️ **Install scripts** - Update to use `brew tap` from packages.yml
5. ⏸️ **Brewfile** - DELETE after migration complete
