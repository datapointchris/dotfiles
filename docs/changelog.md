# Changelog

This file contains high-level summaries of changes to the dotfiles repository. For detailed information about each change, see the corresponding file in `docs/changelog/`.

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
