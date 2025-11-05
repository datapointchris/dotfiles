# Changelog

This file contains high-level summaries of changes to the dotfiles repository. For detailed information about each change, see the corresponding file in `docs/changelog/`.

---

## 2025-11-04 {#2025-11-04}

### Bootstrap Script Cleanup

Removed duplicate package installation from WSL and Arch bootstrap scripts. Bootstrap scripts now follow the macOS pattern: install only what's needed to run Task, then delegate everything to taskfiles.

**Key Changes:**

- `wsl-setup.sh` - Removed duplicate apt package installation (git, curl, wget, build-essential, etc.)
- `arch-setup.sh` - Removed duplicate pacman package installation (git, curl, wget, base-devel, etc.)
- Deleted obsolete `lsp-corporate.sh` - no longer needed since migrating from Mason to native LSP
- Updated documentation to reflect bootstrap script changes

**Philosophy:**
Bootstrap scripts install the minimum prerequisites to run Task. All package installation and configuration is handled by taskfiles for consistency and maintainability.

**Files Changed:**

- Modified: `install/wsl-setup.sh`, `install/arch-setup.sh`
- Deleted: `install/lsp-corporate.sh`
- Modified: `docs/getting-started/installation.md`, `docs/getting-started/quickstart.md`

See [detailed changelog](changelog/2025-11-04.md#bootstrap-cleanup) for full details.

### Claude Code Hooks Implementation

Implemented comprehensive hooks system combining Claude Code hooks (AI workflow automation) and Git hooks (pre-commit framework) to maintain code quality and documentation standards.

**Claude Code Hooks (Phase 1):**

- `session-start` - Auto-loads git status, recent commits, directory structure on session start
- `stop-build-check` - Runs pytest when tools/symlinks modified
- `stop-commit-reminder` - Reminds about commits needing changelog

**Git Automation (Phase 2):**

- `check-feature-docs` - Enforces documentation updates with code changes (blocks feat/fix commits without docs)
- `check-changelog` - Blocks commits after 3 pending changelog entries
- `post-commit-log` - Tracks significant commits to `.claude/.pending-changelog`
- Conventional commits enforcement via pre-commit framework

**Documentation:**

- Comprehensive `docs/reference/hooks.md` with examples and workflows
- Troubleshooting guide and philosophy section
- Complete implementation plan for future phases (Skills & Advanced Automation)

**Philosophy:**
Atomic commits with synchronized documentation. Feature commits include usage docs, changelog commits document the development journey separately.

See [detailed changelog](changelog/2025-11-04.md#hooks-implementation) for full details.

### Shell & Configuration Improvements

**Shell Functions:**

- Added `commithelp()` function to suggest commit types based on staged files
- Enhanced `lscommits` with detailed commit type descriptions
- Migrated environment functions (development/testing/production) to simple aliases
- Added `risky` alias for `claude --dangerously-skip-permissions`

**Configuration:**

- Disabled blink-cmp autocomplete for markdown and text filetypes (Neovim)
- Integrated tinty Base16 theme management for tmux
- Disabled GNU coreutils PATH addition (macOS) - kept as g-prefixed commands
- Added nvm initialization to profile
- Added dotfiles/scripts/utils to PATH

**Documentation:**

- Refactored learnings documentation with conciseness guidelines (30-50 lines max)
- Condensed relative-path-calculation learning from 101 to 58 lines

See [detailed changelog](changelog/2025-11-04.md#shell-config-improvements) for full details.

---

## 2025-11-05 {#2025-11-05}

### Major Dotfiles Simplification

Comprehensive refactoring to reduce complexity and eliminate unnecessary abstraction. Removed ~2,750 lines of code and documentation while maintaining all functionality.

**Key Changes:**

- Deleted themes.yml taskfile (305 lines) - complete duplication of theme-sync script
- Simplified nvm.yml (48% reduction), npm.yml (44% reduction), uv.yml (48% reduction)
- Converted simple shell functions to aliases
- **Rewrote ALL documentation files** - removed marketing language, hand-holding, and fluff (68% reduction)
- Fixed critical error in platforms.md about ZSHDOTDIR configuration
- Updated mkdocs.yml navigation to match reality (removed all dead file references)
- Archived planning documents
- **Fixed tools command availability** - moved from macos/ to common/ so WSL and Arch get it too
- **Fixed critical symlinks.sh bug** - broken link detection failed on macOS due to BSD vs GNU realpath differences

**Philosophy Change:**
Task handles coordination, tools handle commands. No wrapper tasks for simple one-liners. Documentation written in direct, technical tone for Chris, not general audience.

**Files Changed:**

- Deleted: `taskfiles/themes.yml`, `scripts/utils/tools`
- Modified: `Taskfile.yml`, `taskfiles/nvm.yml`, `taskfiles/npm.yml`, `taskfiles/uv.yml`
- Modified: `macos/.shell/macos-functions.sh`, `macos/.shell/macos-aliases.sh`
- Modified: All active documentation files (13 files rewritten)
- Modified: `mkdocs.yml` (updated navigation)
- Moved: `macos/.local/bin/tools` → `common/.local/bin/tools`
- Moved: 4 planning docs to `docs/archive/planning/`

See [detailed changelog](changelog/2025-11-05.md) for complete analysis, error documentation, and lessons learned.

---

## 2025-11-04 {#2025-11-04}

### Phase 6 Complete - Cross-Platform Expansion & VM Testing

Implemented comprehensive cross-platform testing and installation framework for dotfiles across macOS, Ubuntu (WSL), and Arch Linux. Created VM-based automated testing environment with bootstrap scripts and extensive documentation for rapid iteration and confident deployments.

**Key Changes:**

- Created platform-specific installation tasks (install-macos, install-wsl, install-arch)
- Added auto-detection install task that detects platform and runs appropriate installation
- Created 3 bootstrap scripts for automated testing (macos-setup.sh, wsl-setup.sh, arch-setup.sh)
- Comprehensive VM testing framework documentation (multipass, UTM/QEMU)
- Detailed platform differences reference (package names, quirks, troubleshooting)
- Integrated themes system across all platforms

**Architecture Decision:**

Chose VM-based testing framework over manual testing. multipass for Ubuntu (fast, lightweight), UTM/QEMU for Arch (accurate environment), and fresh user accounts for macOS (VMs too complex). Bootstrap scripts handle prerequisites, Taskfile handles complex logic.

**Files Changed:**

- Created: `scripts/install/macos-setup.sh` (90 lines)
- Created: `scripts/install/wsl-setup.sh` (120 lines)
- Created: `scripts/install/arch-setup.sh` (105 lines)
- Created: `docs/vm_testing_guide.md` (400+ lines)
- Created: `docs/platform_differences.md` (450+ lines)
- Modified: `Taskfile.yml` (added install tasks, themes include)

See [detailed changelog](changelog/2025-11-04.md#phase-6-cross-platform) for full implementation details, testing strategies, and platform-specific quirks.

---

### Phase 5 Complete - Tool Discovery System

Implemented command-line tool discovery system with `tools` command to help learn about and remember the 31 installed tools. Focuses on discovery over tracking, keeping configs clean while providing helpful tool information.

**Key Changes:**

- Created tools command (350 lines) with 8 subcommands
- Installed yq for YAML processing (added to Brewfile)
- Leveraged existing Phase 2 registry (31 tools, 15 categories)
- Commands: list, show, search, categories, count, random, installed, help
- Color-coded output for better UX
- Zero shell config changes (clean, maintainable)

**Philosophy:**

Chose "discovery over tracking" - no usage statistics, no function wrappers, no shell pollution. Simple system that helps you remember what tools you have and when to use them, without complexity that clutters configs.

**Files Changed:**

- Created: `macos/.local/bin/tools`
- Modified: `Brewfile` (added yq)
- Modified: `CLAUDE.md`

See [detailed changelog](changelog/2025-11-04.md#phase-5-tool-discovery) for implementation details and design decisions.

---

### Phase 4 Complete - Base16 Theme Synchronization

Implemented cross-application theme synchronization using tinty (Rust-based Base16 theme manager). The system works in parallel with existing ghostty-theme script, allowing independent management of Ghostty themes while synchronizing tmux, bat, fzf, and shell colors.

**Key Changes:**

- Installed and configured tinty with 12 Base16 favorite themes
- Created theme-sync command (285 lines) for theme management
- Created taskfiles/themes.yml (274 lines) with 30+ theme tasks
- Modified tmux.conf to source Base16 themes dynamically
- Backed up original custom tmux colors to themes/backup/
- Integrated with bat, fzf, and shell (LS_COLORS) via tinted-shell

**Architecture Decision:**

Chose parallel systems approach - ghostty-theme handles Ghostty's 600+ themes with live preview, while theme-sync manages Base16 themes across other applications. This provides flexibility without forcing everything into Base16 constraints.

**Files Changed:**

- Created: `~/.config/tinty/config.toml`
- Created: `themes/backup/tmux-original-colors.conf`
- Created: `taskfiles/themes.yml`
- Created: `macos/.local/bin/theme-sync`
- Modified: `common/.config/tmux/tmux.conf`
- Modified: `CLAUDE.md`

See [detailed changelog](changelog/2025-11-04.md#phase-4-theme-sync) for full implementation details, testing results, and integration points.

---

## 2025-11-02 {#2025-11-02}

### Migrated Neovim Completion from nvim-cmp to blink.cmp

Replaced nvim-cmp with blink.cmp for faster, more modern completion functionality. blink.cmp offers 0.5-4ms response times compared to nvim-cmp's 60ms debounce, resulting in much snappier completions.

**Key Changes:**

- Migrated all completion sources: LSP, Copilot, path, snippets, buffer, and lazydev
- Copilot integration required special blink-cmp-copilot adapter
- Updated LSP configuration to use blink.cmp capabilities
- Replicated all custom keymaps (Tab, Ctrl+n/p, Ctrl+j/k, etc.)
- Backed up old nvim-cmp configuration to nvim-cmp.lua.bak

**Files Changed:**

- Created: `common/.config/nvim/lua/plugins/blink-cmp.lua`
- Modified: `common/.config/nvim/lua/lsp/init.lua`
- Modified: `common/.config/nvim/lua/plugins/copilot.lua`
- Backed up: `common/.config/nvim/lua/plugins/nvim-cmp.lua.bak`

See [detailed changelog](changelog/2025-11-02.md#blink-cmp-migration) for troubleshooting steps and learnings.

### Enhanced Notification System with Fidget and Noice

Improved the notification system to make error messages more visible and searchable while keeping LSP progress notifications unobtrusive.

**Key Changes:**

- Configured Fidget for LSP progress (small, bottom-right corner, rounded borders)
- Configured Noice for error/warning messages with extended visibility (10s for errors, 7s for warnings)
- Added Telescope integration for searching through all messages
- Added custom keymaps: `<leader>fmm` (search messages), `<leader>fmh` (message history)

**Files Changed:**

- Modified: `common/.config/nvim/lua/plugins/fidget.lua`
- Modified: `common/.config/nvim/lua/plugins/noice.lua`

See [detailed changelog](changelog/2025-11-02.md#notification-system) for configuration details.

---
