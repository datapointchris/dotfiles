# Changelog

This file contains high-level summaries of changes to the dotfiles repository. For detailed information about each change, see the corresponding file in `docs/changelog/`.

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
