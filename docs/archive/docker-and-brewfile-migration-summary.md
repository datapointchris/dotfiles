# Docker Migration & Brewfile Elimination - Complete Summary

**Date:** 2025-11-27
**Status:** Planning Complete, Awaiting User Approval

---

## Overview

This document summarizes all planned changes for:
1. Migrating from Docker Desktop to Docker Official Repositories + Colima
2. Eliminating Brewfile in favor of packages.yml-only approach
3. Cleaning up ~70 duplicate/unused Homebrew packages

---

## ✅ Changes Already Made (No user approval needed)

### 1. packages.yml Updates

- ✅ Added `gum` to go_tools (used by menu/notes apps)
- ✅ Added `lazydocker` to go_tools (universal Docker TUI)
- ✅ Added `docker` and `docker-compose-plugin` for Linux (apt/pacman)
- ✅ Updated github_binaries section with platform-specific documentation

### 2. Brewfile Updates

- ✅ Added `colima`, `docker`, `docker-compose` to Brewfile (temporary)
- ✅ Removed `oxker` (using lazydocker instead)
- ✅ Added note that lazydocker is in packages.yml

### 3. Verification Scripts

- ✅ Updated verify-installation.sh to check:
  - Colima (macOS only)
  - Docker CLI (all platforms except WSL)
  - docker compose V2 (all platforms except WSL)
  - WSL detection (skips Docker checks on WSL)
  - gum and lazydocker at ~/go/bin/

### 4. Docker Official Repo Setup Scripts

- ✅ Created `setup-docker-official-repo-ubuntu.sh`
- ✅ Created `setup-docker-official-repo-macos.sh`

### 5. Brew Cleanup Analysis

- ✅ Updated with user decisions (buku, nginx, docker-desktop, gum)
- ✅ Updated Neovim dependencies analysis (can be removed)
- ✅ Final summary: ~70 packages + 3 casks to remove

---

## ⏸️ Changes Pending User Approval

### Phase 1: Execute Brew Cleanup (~70 packages to remove)

**Categories:**
1. **Unneeded packages** (31 items): cmatrix, sl, pipes-sh, iterm2, qutebrowser, sbt, openjdk, geckodriver, tokei, tlrc, pandoc, docutils, pgloader, pipx, virtualenv, python-tk@3.12, sox, yq, guile, buku, nginx, docker-desktop (cask)

2. **Duplicates** (28 items - already in packages.yml):
   - Cargo: bat, eza, fd, git-delta, zoxide, tinty
   - GitHub binaries: neovim, lazygit, yazi, fzf, glow, duf, terraform-ls, tflint, terraformer, terrascan
   - Go tools: terraform-docs
   - UV tools: codespell
   - Shell plugins: zsh-syntax-highlighting
   - Terraform: hashicorp/tap/terraform (using tenv)

3. **Neovim dependencies** (5 items - not needed):
   - libuv, lpeg, luv, tree-sitter, unibilium

**Command to execute:**
```bash
cd ~/dotfiles
brew bundle cleanup --force
```

**Expected removals:** ~70 packages + 3 casks

---

### Phase 2: Update packages.yml with Missing Packages

**Packages to add:**

#### Docker (Official Repos)
```yaml
system_packages:
  # Docker (via official repositories)
  - name: docker
    # Ubuntu: docker-ce (requires setup-docker-official-repo-ubuntu.sh first)
    # Arch: docker (official repos already up-to-date)
    # macOS: via Docker tap (requires setup-docker-official-repo-macos.sh first)
    apt: docker-ce
    pacman: docker
    brew: docker  # from docker/docker tap
    description: Docker Engine (official repositories)

  - name: docker-cli
    apt: docker-ce-cli
    description: Docker CLI (Ubuntu official repo)

  - name: containerd
    apt: containerd.io
    pacman: containerd
    description: Container runtime

  - name: docker-buildx-plugin
    apt: docker-buildx-plugin
    pacman: docker-buildx
    description: Docker Buildx plugin

  - name: docker-compose-plugin
    apt: docker-compose-plugin
    pacman: docker-compose
    brew: docker-compose  # from docker/docker tap
    description: Docker Compose V2 plugin
```

#### Other Missing Packages
```yaml
system_packages:
  - name: pre-commit
    apt: pre-commit
    pacman: pre-commit
    brew: pre-commit
    description: Git pre-commit hook framework

  - name: zk
    apt: zk  # if available, otherwise github_binaries
    pacman: zk
    brew: zk
    description: Plain text note-taking assistant
```

#### macOS-Specific (Brewfile → packages.yml)
```yaml
# New section for macOS-only packages
macos_packages:
  - name: colima
    brew: colima
    description: Container runtime (Docker daemon via Lima VM)

  # ... other macOS-specific tools
```

---

### Phase 3: Migrate Brewfile to packages.yml

**Current Brewfile contents to migrate:**

#### System Packages (move to packages.yml system_packages)

All brew formulae that are NOT macOS-specific:
- ripgrep, git, gh, tmux, jq, tree, htop
- git-secrets
- shellcheck, shfmt, taplo, actionlint
- lazydocker (already in go_tools), oxker (removed)
- awscli, mkcert, gnupg, gpg-tui, trivy
- postgresql@16, go-task, supervisor
- watch, coretemp, sevenzip, gnu-tar, curl, wget, nmap
- coreutils, findutils, mas
- ffmpeg, mpv, yt-dlp, imagemagick, chafa, resvg, graphviz, gource
- figlet, bash, tmuxinator, tmuxinator-completion

#### macOS-Specific Packages (move to new macos_packages section)

- duti, borders, sketchybar, terminal-notifier
- GNU tools: gnu-sed, gnu-tar, grep, coreutils, findutils

#### GUI Applications (move to new macos_casks section)
```yaml
macos_casks:
  - name: aerospace
  - name: alfred
  - name: bettertouchtool
  - name: dbeaver-community
  - name: macs-fan-control
  - name: michaelvillar-timer
  - name: multipass
  - name: discord
  - name: slack
  - name: zoom
  - name: obsidian
```

---

### Phase 4: Eliminate Brewfile

**After migration:**
1. Delete `Brewfile`
2. Update install scripts to read from packages.yml only
3. Update documentation

**New install workflow:**
```bash
# macOS
task macos:setup  # reads packages.yml for all packages + casks

# Ubuntu
task ubuntu:setup  # reads packages.yml

# Arch
task arch:setup  # reads packages.yml
```

---

## Docker Migration Workflow

### On macOS (Current System)

**Current state:**
- Docker Desktop installed (to be removed)
- docker CLI from Desktop
- docker compose from Desktop

**Migration steps:**

1. **Setup Docker official tap:**
   ```bash
   bash ~/dotfiles/management/scripts/setup-docker-official-repo-macos.sh
   ```

2. **Install Colima + Docker:**
   ```bash
   brew install colima docker docker-compose
   ```

3. **Configure docker-compose plugin:**
   ```bash
   mkdir -p ~/.docker
   cat > ~/.docker/config.json <<EOF
   {
     "cliPluginsExtraDirs": [
       "/usr/local/lib/docker/cli-plugins"
     ]
   }
   EOF
   ```

4. **Start Colima:**
   ```bash
   colima start
   ```

5. **Test:**
   ```bash
   docker ps
   docker compose version
   lazydocker
   ```

6. **Uninstall Docker Desktop:**
   ```bash
   brew uninstall --cask docker-desktop
   # Or manually via Applications folder
   ```

### On Ubuntu/Debian (Future)

**Setup steps:**

1. **Setup Docker official repository:**
   ```bash
   bash ~/dotfiles/management/scripts/setup-docker-official-repo-ubuntu.sh
   ```

2. **Install Docker:**
   ```bash
   sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   ```

3. **Add user to docker group:**
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```

4. **Enable Docker service:**
   ```bash
   sudo systemctl enable --now docker
   ```

5. **Test:**
   ```bash
   docker ps
   docker compose version
   lazydocker
   ```

### On Arch Linux (Future)

**Setup steps:**

1. **Install Docker (official Arch repos already up-to-date):**
   ```bash
   sudo pacman -S docker docker-compose docker-buildx
   ```

2. **Add user to docker group:**
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```

3. **Enable Docker service:**
   ```bash
   sudo systemctl enable --now docker
   ```

4. **Test:**
   ```bash
   docker ps
   docker compose version
   lazydocker
   ```

### On WSL (Work Laptop)

**No changes needed:**
- Uses Windows Docker Desktop (admin-managed)
- Docker CLI connects to Windows daemon
- Verification scripts skip Docker checks on WSL

---

## Files Modified (Summary)

### Created:

- `/Users/chris/dotfiles/management/scripts/setup-docker-official-repo-ubuntu.sh`
- `/Users/chris/dotfiles/management/scripts/setup-docker-official-repo-macos.sh`
- `/Users/chris/dotfiles/.planning/docker-and-brewfile-migration-summary.md` (this file)

### Modified:

- `/Users/chris/dotfiles/Brewfile` (added colima, docker, docker-compose; removed oxker)
- `/Users/chris/dotfiles/management/packages.yml` (added gum, lazydocker, docker, docker-compose-plugin)
- `/Users/chris/dotfiles/management/verify-installation.sh` (added Docker checks with WSL detection)
- `/Users/chris/dotfiles/.planning/brew-bundle-cleanup-analysis.md` (updated with user decisions)

### To be deleted (Phase 4):

- `/Users/chris/dotfiles/Brewfile`

---

## What Still Needs Decision

**None!** All user decisions have been made:
- ✅ docker-desktop → REMOVE (use Colima)
- ✅ buku → REMOVE
- ✅ nginx → REMOVE
- ✅ gum → KEEP (via packages.yml)
- ✅ Docker approach → Official repos everywhere

---

## Risks & Mitigation

### Risk 1: Docker migration breaks existing workflows

**Mitigation:** Test thoroughly before removing Docker Desktop
- Run `docker ps`, `docker-compose up` tests
- Verify lazydocker works
- Keep Docker Desktop installed until Colima is fully verified

### Risk 2: Brew cleanup removes needed package

**Mitigation:** Review cleanup list carefully before executing
- Analysis document has detailed reasoning for each package
- Can reinstall anything if needed
- No data loss (just package removal)

### Risk 3: Brewfile elimination breaks macOS setup

**Mitigation:** Migrate incrementally
- Keep Brewfile until packages.yml migration is complete
- Test install scripts at each step
- Can roll back by re-creating Brewfile from backup

---

## Approval Checklist

Before proceeding, user should review:

- [ ] Brew cleanup analysis (.planning/brew-bundle-cleanup-analysis.md)
- [ ] Packages to remove (~70 packages + 3 casks)
- [ ] Docker migration workflow (this document)
- [ ] Brewfile elimination plan (Phase 3-4)

Once approved, execute in order:
1. Phase 1: Brew cleanup
2. Phase 2: Update packages.yml
3. Phase 3: Migrate Brewfile
4. Phase 4: Eliminate Brewfile

---

## Questions?

- See `.planning/brew-bundle-cleanup-analysis.md` for detailed package analysis
- See packages.yml for current package configuration
- Docker official docs: https://docs.docker.com/engine/install/
