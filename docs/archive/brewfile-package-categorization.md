# Brewfile Package Categorization - Complete Analysis

**Date:** 2025-11-27
**Status:** Research Complete - Awaiting User Decisions

---

## Quick Summary of User Decisions

✅ **Confirmed Removals:**
- resvg (embedded in Yazi)
- coretemp (not needed by Macs Fan Control - it's just a CLI temp monitor)
- sketchybar (not using)
- postgresql@16 (not needed)

✅ **Confirmed Additions:**
- watch → system_packages (used in `watchports` alias)

✅ **Already in packages.yml (4 packages):**
- git-secrets (line 267)
- ruby (line 169)
- lua-language-server (line 174)
- go-task (line 232)

---

## Package Analysis - The Remaining 18 Packages

### Category 1: System Packages (Simple - All Platforms) ✓

**Recommendation:** Add to system_packages - available in all package managers

| Package | apt | pacman | brew | Notes |
|---------|-----|--------|------|-------|
| **bash** | ✓ | ✓ | ✓ | Shell (macOS bash is outdated, need newer) |
| **nmap** | ✓ | ✓ | ✓ | Network scanner |
| **mpv** | ✓ | ✓ | ✓ | Media player |
| **graphviz** | ✓ | ✓ | ✓ | Graph visualization |
| **figlet** | ✓ | ✓ | ✓ | ASCII art text |

**Action:** Add 5 packages to system_packages section

---

### Category 2: Language-Specific Package Managers (Recommended 2025)

#### 2A. uv_tools (Python tools) ✓

**Recommendation:** Install via `uv tool install`

| Package | Why uv? | Source |
|---------|---------|--------|
| **pre-commit** | [Recommended in 2025](https://adamj.eu/tech/2025/05/07/pre-commit-install-uv/) - `uv tool install pre-commit` | Official uv docs |
| **yt-dlp** | [Available on PyPI](https://pypi.org/project/yt-dlp/) - `uv tool install "yt-dlp[default]"` | Official yt-dlp docs |
| **supervisor** | [Python process manager](https://supervisord.org/installing.html) - `uv tool install supervisor` | But might not be needed? |

**Action:** Add 2-3 packages to uv_tools section (if keeping supervisor)

**Question for user:** Do you actually use supervisor for process management?

#### 2B. cargo_packages (Rust tools) ✓

**Recommendation:** Install via `cargo install`

| Package | Why cargo? | Source |
|---------|------------|--------|
| **taplo** | [Official method](https://taplo.tamasfe.dev/cli/installation/binary.html) - `cargo install taplo-cli` | TOML formatter |
| **gpg-tui** | [Official method](https://github.com/orhun/gpg-tui) - `cargo install gpg-tui` | GPG key manager TUI |

**Action:** Add 2 packages to cargo_packages section

#### 2C. go_tools (Go tools) ✓

**Recommendation:** Install via `go install`

| Package | Why go? | Source |
|---------|---------|--------|
| **actionlint** | [Official method](https://github.com/rhysd/actionlint/blob/main/docs/install.md) - `go install github.com/rhysd/actionlint/cmd/actionlint@latest` | GitHub Actions linter |

**Action:** Add 1 package to go_tools section

---

### Category 3: System Packages with Special Handling

#### 3A. System packages with apt repo setup required

**Recommendation:** Add to system_packages (apt requires repo setup script)

| Package | apt (needs setup) | pacman | brew | Notes |
|---------|-------------------|--------|------|-------|
| **trivy** | [Official apt repo](https://trivy.dev/docs/latest/getting-started/installation/) | ✗ | ✓ | Container scanner |
| **awscli** | ✓ (unofficial) | ✗ | ✓ | AWS CLI - [official recommends installer](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |

**Notes:**
- **trivy**: Has official apt repository (similar to Docker setup script pattern)
- **awscli**: AWS recommends their installer, but system packages work fine

**Action:** Add 2 packages to system_packages, create apt setup script for trivy if needed

#### 3B. System packages available via brew/pacman, GitHub binary for apt

**Recommendation:** Add to system_packages OR github_binaries

| Package | brew | pacman | apt | GitHub Binaries | Recommendation |
|---------|------|--------|-----|-----------------|----------------|
| **zk** | [✓](https://formulae.brew.sh/formula/zk) | ✓ | ✗ | [✓](https://github.com/zk-org/zk) | **system_packages** (use GitHub for apt) |
| **mkcert** | [✓](https://formulae.brew.sh/formula/mkcert) | ✓ | ✗ | [✓](https://github.com/FiloSottile/mkcert) | **system_packages** (use GitHub for apt) |

**Action:** Add 2 packages to system_packages, note apt uses GitHub binaries

---

### Category 4: Ruby Ecosystem

**Recommendation:** Install via Ruby gems (tmuxinator is a Ruby tool)

| Package | Install Method | Notes |
|---------|----------------|-------|
| **tmuxinator** | `gem install tmuxinator` | [RubyGems preferred over brew](https://github.com/tmuxinator/tmuxinator) |
| **tmuxinator-completion** | Comes with tmuxinator | Completion script bundled |

**Action:** Document in packages.yml notes that tmuxinator uses `gem install`

**Alternative:** Could add to system_packages (brew has tmuxinator formula), but RubyGems is more universal

---

### Category 5: Questions for User

#### 5A. Likely Not Needed - Confirm Removal

| Package | Description | Usage Stats | Question |
|---------|-------------|-------------|----------|
| **sbcl** | Steel Bank Common Lisp | Low | Do you use Common Lisp development? |
| **gource** | Git visualization tool | [5,808 installs/year](https://formulae.brew.sh/formula/gource) (low) | Do you use this for visualizing git repos? |
| **supervisor** | Python process manager | Medium | Do you use this for managing background processes? |

**Recommendation:** Remove unless actively used

---

## GUI Applications Review

### Current macOS Casks with Linux Equivalents

From your Brewfile casks list, these need Linux versions:

| macOS Cask | Linux Equivalent | Install Method | Platforms |
|------------|------------------|----------------|-----------|
| **dbeaver-community** | dbeaver-ce | snap/flatpak/pacman | Arch (NOT WSL) |
| **discord** | discord | snap/flatpak/pacman | All (NOT WSL) |
| **slack** | slack | snap/flatpak/pacman | All (NOT WSL) |

**Notes:**
- Slack is in both MAS apps (id: 803453959) and Brewfile casks - keep cask version
- WSL: Don't install GUI apps (run in Windows)
- Linux: Use native package manager (pacman) or flatpak

### MAS Apps Review - Linux Equivalents

From your MAS apps, here are potential Linux equivalents:

| MAS App | Linux Alternative | Notes |
|---------|-------------------|-------|
| Microsoft Excel/Word/PowerPoint | LibreOffice | Office suite |
| Microsoft Remote Desktop | Remmina / xfreerdp | RDP client |
| Todoist | todoist (snap/flatpak) | Task management |
| NiBoard | Xournal++ | Whiteboard/sketching |
| Pixelstyle Photo Editor | GIMP / Krita | Photo editing |

**Most are macOS-specific utilities** (Color Picker, Dato, Forecast Bar, IPEVO Annotator, KnowledgeBase Builder) - no Linux equivalents needed.

---

## Final Categorization Summary

### Add to packages.yml:

**system_packages (9 new):**
- bash, nmap, mpv, graphviz, figlet (simple, all platforms)
- watch (used in aliases)
- zk, mkcert (use GitHub binaries for apt)
- trivy, awscli (may need apt repo setup)

**uv_tools (2-3 new):**
- pre-commit, yt-dlp
- supervisor (if keeping)

**cargo_packages (2 new):**
- taplo, gpg-tui

**go_tools (1 new):**
- actionlint

**Ruby ecosystem (document in notes):**
- tmuxinator (via `gem install tmuxinator`)

**Linux GUI apps (new section? or just document):**
- dbeaver-community (Arch only)
- discord (all platforms except WSL)

---

## Questions for User Before Proceeding

1. **sbcl** (Steel Bank Common Lisp) - Remove? Do you use Common Lisp?
2. **gource** (git visualization) - Remove? Do you use this?
3. **supervisor** (process manager) - Remove? Do you use this?
4. **tmuxinator** - Add to system_packages or document as `gem install`?
5. **Linux GUI apps** - Should we create a linux_gui_apps section in packages.yml, or just document separately?
6. **snap/flatpak** - Do you want to use system package managers (pacman) or universal (flatpak)?

---

## Sources

- [pre-commit with uv](https://adamj.eu/tech/2025/05/07/pre-commit-install-uv/)
- [zk installation](https://zk-org.github.io/zk/)
- [taplo binary releases](https://taplo.tamasfe.dev/cli/installation/binary.html)
- [actionlint installation](https://github.com/rhysd/actionlint/blob/main/docs/install.md)
- [AWS CLI installation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [mkcert GitHub](https://github.com/FiloSottile/mkcert)
- [gpg-tui GitHub](https://github.com/orhun/gpg-tui)
- [trivy installation](https://trivy.dev/docs/latest/getting-started/installation/)
- [supervisor installation](https://supervisord.org/installing.html)
- [yt-dlp installation](https://github.com/yt-dlp/yt-dlp/wiki/Installation)
- [tmuxinator GitHub](https://github.com/tmuxinator/tmuxinator)
