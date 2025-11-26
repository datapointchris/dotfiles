# Neovim AI Assistants

**Purpose**: Clean, focused AI assistance in Neovim using existing paid services

## Philosophy

Use separate tools for separate purposes instead of trying to integrate everything into Neovim. Keep Neovim configuration simple and maintainable while leveraging powerful AI tools where they work best.

## The Setup

### codecompanion.nvim - Chat with Copilot

Quick questions, code explanations, and learning - without forced code changes.

**Provider**: GitHub Copilot (included with existing subscription)

**Keybindings**:

- `<leader>ca` - Chat: Ask question (normal/visual mode)
- `<leader>cc` - Chat: Toggle chat window (right side, 40% width)
- `<leader>cq` - Chat: Quick actions (prompt picker)

**Why**: Fast, simple chat interface for quick questions that won't pollute Claude Code context. Copilot is great for explanations and small code examples without the complexity of full context management.

**Configuration**: `platforms/common/.config/nvim/lua/plugins/codecompanion.lua`

### sidekick.nvim - Next Edit Suggestions (NES)

Copilot multi-line completions for better code suggestions than basic inline completions.

**Provider**: GitHub Copilot

**Keybindings**:

- `<Tab>` - Accept/jump to next edit suggestion
- `<leader>ne` - Toggle NES on/off

**Why**: Smart multi-line code completions from Copilot provide context-aware suggestions across multiple cursor positions.

**Configuration**: `platforms/common/.config/nvim/lua/plugins/sidekick.lua`

**Note**: The CLI feature is disabled - use tmux/floaterminal for terminal access instead.

## What Was Removed

### claudecode.nvim

Removed due to direct file changes without proper diffs, slow typing lag, and buggy integration.

**Replaced with**: Tmux/floaterminal workflows for Claude Code CLI

### codecompanion.nvim with Claude

Removed due to Max plan OAuth tokens being blocked by Anthropic for non-Claude-Code usage.

**Replaced with**: codecompanion.nvim with Copilot

## Terminal Workflows for Claude Code

For large refactors and focused Claude work, use terminal access instead of Neovim integration.

### Neovim Floaterminal

- Keybinding: `<leader>tt`
- Opens: Floating terminal window (80% width/height)
- Use for: Quick terminal access in Neovim

### Tmux Claude Popup

- Keybinding: `Ctrl-g` (in tmux)
- Opens: Popup window (90% width/height) running `claude`
- Use for: Large refactors, multi-file changes, focused Claude work

Both options provide seamless pane navigation with vim-tmux-navigator keybindings.

## The Complete Workflow

### For quick questions/explanations

Press `<leader>ca` or `<leader>cc` in Neovim, ask Copilot your question, get answer in chat window without forced code changes. Easy to copy examples.

### For code completions

Start typing code, see multi-line NES suggestions appear as ghost text, press `<Tab>` to accept.

### For large/focused work

Press `Ctrl-g` in tmux or `<leader>tt` in Neovim, use Claude Code CLI for multi-file refactors with proper context management.

## Why This Approach Works

### Separation of Concerns

- **Copilot**: Quick questions and code completions
- **Claude Code**: Large refactors and complex changes
- **Neovim**: Fast editing without complex integrations

### No Integration Complexity

Each tool works in its optimal environment without trying to force everything into Neovim. This reduces bugs, improves performance, and keeps configuration maintainable.

### Existing Subscriptions

Uses services you're already paying for (GitHub Copilot, Claude) without additional costs or complex OAuth setups.

### Fast and Reliable

No typing lag, no buggy file changes, no OAuth token issues. Each tool does what it does best.

## Files

- `platforms/common/.config/nvim/lua/plugins/codecompanion.lua` - Copilot chat configuration
- `platforms/common/.config/nvim/lua/plugins/sidekick.lua` - NES configuration
- `platforms/common/.config/nvim/lua/core/keymaps.lua` - AI assistant keybindings
- `platforms/common/.config/nvim/lua/core/options.lua` - Neovim options
- `platforms/common/.config/nvim/lua/plugins/lualine.lua` - Status line integration

## Testing

Restart Neovim: `:qa` then `nvim`

Test chat: Press `<leader>ca` → Ask "What does this code do?" in any buffer

Test NES: Start typing code, watch for ghost text suggestions

Test terminal: Press `<leader>tt` → Terminal should open

## Related

- [Menu](../apps/menu.md) - Menu system for tool discovery
- [Claude Code Hooks](../reference/hooks.md) - Claude Code integration
