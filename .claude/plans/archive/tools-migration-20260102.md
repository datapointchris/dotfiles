# Architectural Analysis: Tools and Dotfiles Boundaries

## The Core Problem

Dotfiles has evolved into a monorepo containing three fundamentally different things:

1. **Configuration management** (what dotfiles should be)
2. **Standalone applications** (sess, toolbox, refcheck, theme, font)
3. **Installation infrastructure** (symlinks manager, install scripts)

**The key insight: dotfiles should describe your environment, not contain your tools.**

## The Three Categories

### Category 1: Environment Configuration (stays in dotfiles)

- Symlinks manager - core infrastructure for dotfiles itself
- Shell libraries (logging.sh, formatting.sh, error-handling.sh)
- Simple glue scripts (<100 lines, no dependencies): menu
- Install scripts that fetch external tools
- All configuration files (platforms/)

### Category 2: Personal CLI Tools (move to ~/tools/)

- `sess` - Go, session manager
- `toolbox` - Go, tool discovery CLI
- `refcheck` - Python, reference validator
- `theme` - Bash+Python, theme system
- `font` - Bash, font management
- `notes` - Bash, note management with zk

### Category 3: Services/Web Applications (~/code/)

- ichrisbirch, timeline - web applications
- Homelab services
- Learning projects, experiments

## Directory Structure

```text
~/dotfiles/              # Configuration and environment setup ONLY
├── platforms/           # Config files to symlink
├── management/
│   ├── symlinks/        # Core infrastructure (stays)
│   ├── taskfiles/
│   └── install/
│       ├── github-releases/    # External binaries (lazygit, etc.)
│       ├── language-managers/  # nvm, uv, etc.
│       └── personal-tools/     # Your tools (same patterns!)
└── apps/                # ONLY simple glue scripts
    └── common/
        └── menu         # 50 lines, just launches other tools

~/tools/                 # Personal CLI tools (standalone git repos)
├── sess/                # Go
├── toolbox/             # Go
├── refcheck/            # Python
├── theme/               # Bash (includes themes/, data/)
├── font/                # Bash (includes data/)
└── notes/               # Bash

~/code/                  # Services, webapps, experiments
├── ichrisbirch/
├── timeline/
└── learning/
```

## Installation Patterns by Language

### Go Tools (sess, toolbox)

**Install from GitHub (no local copy needed):**

```bash
go install github.com/youruser/sess@main
go install github.com/youruser/toolbox@main
```

**Dotfiles installer** (`management/install/personal-tools/sess.sh`):

```bash
#!/bin/bash
# Same idempotent pattern as other installers
if command -v sess &>/dev/null && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
    log_info "sess already installed"
    exit 0
fi

log_info "Installing sess..."
go install github.com/youruser/sess@main
log_success "sess installed"
```

**Upgrade:**

```bash
go install github.com/youruser/sess@main  # Same command, gets latest
```

**Development workflow:**

```bash
cd ~/tools/sess
# Edit code...
go run ./cmd/sess          # Test locally
go build -o ~/go/bin/sess  # Install local build (overwrites)
git push                   # Push = live for fresh installs
```

---

### Python Tools (refcheck)

**Install from GitHub (no local copy needed):**

```bash
uv tool install git+https://github.com/youruser/refcheck
```

**Dotfiles installer** (`management/install/personal-tools/refcheck.sh`):

```bash
#!/bin/bash
if command -v refcheck &>/dev/null && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
    log_info "refcheck already installed"
    exit 0
fi

log_info "Installing refcheck..."
uv tool install git+https://github.com/youruser/refcheck
log_success "refcheck installed"
```

**Upgrade:**

```bash
uv tool upgrade refcheck
# or force reinstall:
uv tool install --force git+https://github.com/youruser/refcheck
```

**Development workflow:**

```bash
cd ~/tools/refcheck
# Edit code...
uv run refcheck            # Test with project's venv
uv tool install --force .  # Install local version
git push                   # Push = live for fresh installs
```

---

### Bash Tools (theme, font, notes)

**Install pattern: git clone (like nvm, oh-my-zsh):**

```bash
git clone https://github.com/youruser/theme ~/.local/share/theme
ln -sf ~/.local/share/theme/bin/theme ~/.local/bin/theme
```

**Dotfiles installer** (`management/install/personal-tools/theme.sh`):

```bash
#!/bin/bash
INSTALL_DIR="$HOME/.local/share/theme"
REPO="https://github.com/youruser/theme"

if [[ -d "$INSTALL_DIR" ]] && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
    log_info "theme already installed"
    exit 0
fi

log_info "Installing theme..."
if [[ -d "$INSTALL_DIR/.git" ]]; then
    git -C "$INSTALL_DIR" pull
else
    git clone "$REPO" "$INSTALL_DIR"
fi
ln -sf "$INSTALL_DIR/bin/theme" "$HOME/.local/bin/theme"
log_success "theme installed"
```

**Upgrade (built into the tool):**

```bash
# In theme itself, add upgrade command:
theme upgrade
# Which does:
git -C "$(dirname "$(realpath "$0")")/.." pull
```

**Development workflow:**

```bash
cd ~/tools/theme
# Edit code...
./bin/theme preview       # Test local changes directly
git push                  # Push = live for upgrades
```

**Why git clone instead of tarball:**

- Every push is immediately installable (no release ceremony)
- Upgrade is just `git pull` (simple, fast, incremental)
- No version management overhead - main branch IS the release
- Same CI/CD feel as web deployments: push = live

---

## Tool Structure Template

Each tool in ~/tools/ should have:

```text
~/tools/theme/
├── bin/
│   └── theme            # Main entry point
├── lib/                 # Supporting code
│   ├── lib.sh
│   └── storage.sh
├── data/                # Tool-specific data (themes, configs)
├── install.sh           # For public: curl | bash installation
├── README.md
└── .git/
```

**install.sh (for public installation):**

```bash
#!/bin/bash
set -e
INSTALL_DIR="${THEME_DIR:-$HOME/.local/share/theme}"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo "Updating theme..."
    git -C "$INSTALL_DIR" pull
else
    echo "Installing theme..."
    git clone https://github.com/youruser/theme "$INSTALL_DIR"
fi

ln -sf "$INSTALL_DIR/bin/theme" "$HOME/.local/bin/theme"
echo "Done! Run 'theme' to get started."
```

**Public can install with:**

```bash
curl -fsSL https://raw.githubusercontent.com/youruser/theme/main/install.sh | bash
```

---

## Summary: Installation Commands

| Tool Type | Install | Upgrade | Dev Test |
|-----------|---------|---------|----------|
| **Go** | `go install github.com/user/tool@main` | Same command | `go run .` or `go build` |
| **Python** | `uv tool install git+https://...` | `uv tool upgrade tool` | `uv run tool` |
| **Bash** | `git clone` + symlink | `tool upgrade` (git pull) | `./bin/tool` |

All are GitHub-based. No local copy needed on remote machines. Package managers (go, uv) or git handle everything.

---

## Migration Plan

### Moving to ~/tools/ (multi-file projects, own repos)

| Tool | Language | From | Install Method |
|------|----------|------|----------------|
| `sess` | Go | `apps/common/sess/` | `go install github.com/user/sess@main` |
| `toolbox` | Go | `apps/common/toolbox/` | `go install github.com/user/toolbox@main` |
| `theme` | Bash | `apps/common/theme/` | `git clone` → `~/.local/share/theme` |
| `font` | Bash | `apps/common/font/` | `git clone` → `~/.local/share/font` |
| `refcheck` | Python | `apps/common/refcheck` | `uv tool install git+https://...` |

### Staying in dotfiles/apps/ (single scripts, symlinked)

| Tool | Reason |
|------|--------|
| `menu` | Single file, 50 lines |
| `patterns` | Single file |
| `notes` | Single file |
| `aws-profiles` | Single file, AWS config glue |
| `backup-dirs` | Single file, system glue |
| `backup-incremental` | Single file, system glue |

### Staying in dotfiles/management/

| Component | Reason |
|-----------|--------|
| `symlinks/` | Core dotfiles infrastructure |
| Shell libraries | Part of environment setup |
| Install scripts | Orchestration layer |

### Migration Order (Detailed Steps)

Each step is atomic and committable. Test after each step.

---

#### PHASE 1: Go Tools (sess)

**Step 1.1: Add sess to packages.yml**

- Add `github.com/user/sess@main` to `go_tools` section
- Test: `grep sess management/packages.yml`
- Commit: "feat(packages): add sess to go_tools"

**Step 1.2: Remove sess from install.sh**

- Remove `run_installer "$custom_apps/sess.sh"` line
- Test: `grep -r "sess.sh" install.sh` (should return nothing)
- Commit: "refactor(install): remove sess custom-app call"

**Step 1.3: Delete old sess installer**

- Delete `management/common/install/custom-apps/sess.sh`
- Test: `ls management/common/install/custom-apps/` (sess.sh gone)
- Commit: "chore: remove old sess installer script"

**Step 1.4: Delete sess app directory**

- Delete `apps/common/sess/` entirely
- Test: `task symlinks:link` still works, `ls apps/common/` (sess gone)
- Commit: "chore: remove sess from dotfiles apps"

---

#### PHASE 2: Go Tools (toolbox)

**Step 2.1: Add toolbox to packages.yml**

- Add `github.com/user/toolbox@main` to `go_tools` section
- Test: `grep toolbox management/packages.yml`
- Commit: "feat(packages): add toolbox to go_tools"

**Step 2.2: Remove toolbox from install.sh**

- Remove `run_installer "$custom_apps/toolbox.sh"` line
- Test: `grep -r "toolbox.sh" install.sh` (should return nothing)
- Commit: "refactor(install): remove toolbox custom-app call"

**Step 2.3: Delete old toolbox installer**

- Delete `management/common/install/custom-apps/toolbox.sh`
- Test: `ls management/common/install/custom-apps/` (toolbox.sh gone)
- Commit: "chore: remove old toolbox installer script"

**Step 2.4: Delete toolbox app directory**

- Delete `apps/common/toolbox/` entirely
- Test: `task symlinks:link` still works
- Commit: "chore: remove toolbox from dotfiles apps"

---

#### PHASE 3: Python Tool (refcheck)

**Step 3.1: Add refcheck to packages.yml**

- Add `git+https://github.com/user/refcheck` to `uv_tools` section
- Test: `grep refcheck management/packages.yml`
- Commit: "feat(packages): add refcheck to uv_tools"

**Step 3.2: Delete refcheck app file**

- Delete `apps/common/refcheck`
- Test: `task symlinks:link` still works
- Commit: "chore: remove refcheck from dotfiles apps"

**Step 3.3: Update refcheck tests**

- Update or remove `tests/apps/test-refcheck.sh`
- Update or remove `tests/apps/test-refcheck-resolve-path.py`
- Test: `task test` passes
- Commit: "test: update refcheck tests for new location"

---

#### PHASE 4: Bash Tool (theme) - Data Setup

**Step 4.1: Create theme data directory in dotfiles**

- Create `platforms/common/.config/theme/`
- Move existing history/rejected files there (per-machine naming)
- Test: `ls platforms/common/.config/theme/`
- Commit: "feat(theme): add config data directory for cross-machine sync"

**Step 4.2: Run symlinks to link theme data**

- Test: `task symlinks:link`, verify `~/.config/theme/` exists
- Commit: (no commit needed, just verification)

---

#### PHASE 5: Bash Tool (theme) - Installer

**Step 5.1: Create theme custom installer**

- Create `management/common/install/custom-installers/theme.sh`
- Pattern: git clone to ~/.local/share/theme, symlink to ~/.local/bin/theme
- Test: Read the script, verify logic
- Commit: "feat(install): add theme custom installer"

**Step 5.2: Add theme installer to install.sh**

- Add `run_installer "$custom_installers/theme.sh"`
- Test: `grep theme.sh install.sh`
- Commit: "feat(install): call theme installer in install.sh"

**Step 5.3: Delete theme app directory**

- Delete `apps/common/theme/` entirely
- Test: `task symlinks:link` still works
- Commit: "chore: remove theme from dotfiles apps"

---

#### PHASE 6: Bash Tool (font) - Data Setup

**Step 6.1: Create font data directory in dotfiles**

- Create `platforms/common/.config/font/`
- Move existing history/rejected/font-info files there (per-machine naming)
- Test: `ls platforms/common/.config/font/`
- Commit: "feat(font): add config data directory for cross-machine sync"

---

#### PHASE 7: Bash Tool (font) - Installer

**Step 7.1: Create font custom installer**

- Create `management/common/install/custom-installers/font.sh`
- Pattern: git clone to ~/.local/share/font, symlink to ~/.local/bin/font
- Test: Read the script, verify logic
- Commit: "feat(install): add font custom installer"

**Step 7.2: Add font installer to install.sh**

- Add `run_installer "$custom_installers/font.sh"`
- Test: `grep font.sh install.sh`
- Commit: "feat(install): call font installer in install.sh"

**Step 7.3: Delete font app directory**

- Delete `apps/common/font/` entirely
- Test: `task symlinks:link` still works
- Commit: "chore: remove font from dotfiles apps"

---

#### PHASE 8: Update Scripts

**Step 8.1: Add theme/font update to update.sh**

- Add git pull for ~/.local/share/theme and ~/.local/share/font
- Test: Read update.sh, verify logic
- Commit: "feat(update): add theme and font git pull updates"

---

#### PHASE 9: Verification

**Step 9.1: Update verify-installed-packages.sh**

- Add checks for sess, toolbox, theme, font, refcheck
- Test: Run verification script
- Commit: "test(verify): add checks for migrated tools"

**Step 9.2: Full verification**

- Run: `sess --version`, `toolbox --version`, `theme current`, `font current`, `refcheck --help`
- Run: `task symlinks:check`
- No commit (just verification)

---

#### PHASE 10: Documentation

**Step 10.1: Update app-installation-patterns.md**

- Update to reflect new architecture
- Test: Read the doc
- Commit: "docs: update app-installation-patterns for tool migration"

**Step 10.2: Update CLAUDE.md**

- Update "App Installation Patterns" section
- Test: Read the section
- Commit: "docs: update CLAUDE.md app installation patterns"

---

#### PHASE 11: Cleanup

**Step 11.1: Remove custom-apps directory if empty**

- If `management/common/install/custom-apps/` is empty, delete it
- Test: `ls management/common/install/`
- Commit: "chore: remove empty custom-apps directory"

---

## Dotfiles Integration Checklist

### Files to CREATE

**New custom installers (like nvm.sh):**

```text
management/common/install/custom-installers/theme.sh   # git clone → ~/.local/share/theme
management/common/install/custom-installers/font.sh    # git clone → ~/.local/share/font
```

**New data directories (for symlinks manager):**

```text
platforms/common/.config/theme/
├── history-macos.jsonl
└── rejected-themes-macos.json

platforms/common/.config/font/
├── history-macos.jsonl
├── rejected-fonts-macos.json
└── font-info.json
```

### Files to MODIFY

| File | Changes Needed |
|------|----------------|
| `install.sh` | Remove sess/toolbox custom-apps calls; add theme/font custom-installer calls |
| `update.sh` | Add update for theme/font (git pull) |
| `management/packages.yml` | Add sess, toolbox to `go_tools`; add refcheck to `uv_tools` |
| `tests/install/verification/verify-installed-packages.sh` | Add checks for sess, toolbox, theme, font, refcheck |
| `docs/learnings/app-installation-patterns.md` | Update to reflect new architecture |
| `CLAUDE.md` | Update "App Installation Patterns" section |

### Files to DELETE

**Old app directories:**

```text
apps/common/sess/           # entire directory
apps/common/toolbox/        # entire directory
apps/common/theme/          # entire directory
apps/common/font/           # entire directory
apps/common/refcheck        # single file
```

**Old installers:**

```text
management/common/install/custom-apps/sess.sh
management/common/install/custom-apps/toolbox.sh
```

**Tests to update/remove:**

```text
tests/apps/test-refcheck.sh              # will break - update or remove
tests/apps/test-refcheck-resolve-path.py # will break - update or remove
```

### packages.yml Changes

Add to existing sections:

```yaml
go_tools:
  - github.com/user/sess@main
  - github.com/user/toolbox@main

uv_tools:
  - git+https://github.com/user/refcheck
```

### install.sh Changes

Remove:

```bash
run_installer "$custom_apps/sess.sh"
run_installer "$custom_apps/toolbox.sh"
```

Add:

```bash
run_installer "$custom_installers/theme.sh"
run_installer "$custom_installers/font.sh"
```

(sess/toolbox now installed via go_tools, refcheck via uv_tools)

### update.sh Changes

Add to existing update flow:

```bash
# Bash tools (git pull)
git -C ~/.local/share/theme pull 2>/dev/null || true
git -C ~/.local/share/font pull 2>/dev/null || true
```

### Verification After Migration

```bash
task symlinks:link              # symlinks still work (apps removed gracefully)
task symlinks:check             # no broken symlinks
sess --version                  # Go tool works (installed via go install)
toolbox --version               # Go tool works
refcheck --help                 # Python tool works (installed via uv)
theme current                   # Bash tool works (installed via git clone)
font current                    # Bash tool works
```

---

## Data Storage (theme/font)

User data stays in dotfiles for cross-machine sync:

```text
~/dotfiles/platforms/common/.config/theme/
├── history-macos.jsonl
├── history-arch.jsonl
└── rejected-themes-macos.json    # Per-machine (FIX NEEDED)

~/dotfiles/platforms/common/.config/font/
├── history-macos.jsonl
├── history-arch.jsonl
└── rejected-fonts-macos.json     # Per-machine (FIX NEEDED)
```

Symlinks manager links these to `~/.config/theme/` and `~/.config/font/`.

**Code fix needed:** Change `rejected-fonts.json` and `rejected-themes.json` to per-machine files (`rejected-fonts-{platform}.json`). This avoids git merge conflicts when rejecting on different machines. The `platforms` field in each entry becomes unnecessary since the file itself is per-machine. Tool should union all rejection files on read.

---

## Key Principles

1. **Dotfiles describes environment, doesn't contain tools**
2. **Tools are installed from GitHub, like any external tool**
3. **Push = live** (no release ceremony for personal tools)
4. **One install pattern per language** (go install, uv tool install, git clone)
5. **Each tool has upgrade command** (graceful, never crashes)
6. **Development is explicit** (`./bin/tool`, `go run .`, `uv run tool`)
