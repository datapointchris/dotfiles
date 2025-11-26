# Neovim AI Assistants

Clean, focused AI assistance using existing paid services. Separate tools for separate purposes - keep Neovim simple while leveraging AI where it works best.

## Tools

| Tool | Provider | Purpose | Keybindings |
|------|----------|---------|-------------|
| **codecompanion.nvim** | GitHub Copilot | Chat, questions, explanations | `<leader>ca` (ask), `<leader>cc` (toggle), `<leader>cq` (quick actions) |
| **sidekick.nvim** | GitHub Copilot | Multi-line code completions (NES) | `<Tab>` (accept), `<leader>ne` (toggle) |
| **Claude Code** | Claude (via terminal) | Large refactors, multi-file changes | `Ctrl-g` (tmux popup), `<leader>tt` (floaterminal) |

## Workflow

**Quick questions:** `<leader>ca` → Ask Copilot → Get answer in chat window

**Code completions:** Type code → See NES ghost text → `<Tab>` to accept

**Large refactors:** `Ctrl-g` (tmux) or `<leader>tt` (neovim) → Claude Code CLI

## Why This Works

Each tool operates in its optimal environment - no integration complexity, no typing lag, uses existing subscriptions (GitHub Copilot, Claude). Copilot for quick tasks, Claude Code for focused work, Neovim stays fast and simple.

## Configuration

- `platforms/common/.config/nvim/lua/plugins/codecompanion.lua` - Copilot chat
- `platforms/common/.config/nvim/lua/plugins/sidekick.lua` - NES completions
- `platforms/common/.config/nvim/lua/core/keymaps.lua` - AI keybindings
